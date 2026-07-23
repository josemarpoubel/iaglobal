import ast
import re

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, List, Optional, Dict, Any

from .ast_security import validate_ast_security_str
from .syntax import validar_sintaxe
from iaglobal.utils.logger import logger
from iaglobal.security.ast_gateway import ASTGateway
from iaglobal.diagnostics.python_normalizer import (
    PythonNormalizer,
    normalize_before_repair,
)

_ast_gateway = ASTGateway()


class Decision(Enum):
    COMMIT = "commit"
    RETRY = "retry"
    ROLLBACK = "rollback"


@dataclass
class ValidationResult:
    valid: bool
    code: Optional[str]
    errors: List[str]
    decision: Decision = Decision.COMMIT
    score: float = 1.0
    issues: List[str] = field(default_factory=list)


class FeedbackEngine:
    """
    ÚNICO ponto de verdade para validação de código e decisão de merge.

    Pipeline determinístico conforme contrato PythonNormalizer:
      1. Extract & Sanitize (remoção de markdown e texto externo)
      2. Ruff Format (padronização determinística)
      3. Ruff Check --fix (correções automáticas)
      4. AST Parse (validação sintática)
      5. AST Security Validation
      6. Decisão: commit / retry / rollback
      7. Patch safe apply (merge incremental com rollback em falha)

    Contrato: Todo código gerado por LLM deve passar por normalização
    antes de validação, pontuação ou persistência.
    """

    def __init__(self, snapshotter=None):
        self._snapshotter = snapshotter

    @staticmethod
    def _is_python_code(code: str) -> bool:
        """Detecta se o código é Python baseado em padrões sintáticos."""
        if not code or len(code.strip()) < 10:
            return False
        # Se começa com <!DOCTYPE, <html, ou tag HTML, não é Python
        first_lines = code.strip().split("\n")[:3]
        first_stripped = "\n".join(first_lines).strip()
        if re.match(
            r"^\s*<(!DOCTYPE|html|head|body|div|script|style)",
            first_stripped,
            re.IGNORECASE,
        ):
            return False
        # Se começa com # === comentário de seção === (markdown-style, não Python)
        if re.match(r"^# === .+ ===$", first_lines[0].strip()):
            return False
        # Padrões fortes de Python
        python_indicators = [
            r"\bdef\s+\w+\s*\(",
            r"\bclass\s+\w+",
            r"\bimport\s+\w+",
            r"\bfrom\s+\w+\s+import",
            r"\bif\s+__name__\s*==\s*[\"']__main__[\"']",
            r"\basync\s+def",
            r"\bawait\s+",
            r"\byield\s+",
            r"\braise\s+\w+",
            r"\bwith\s+\w+",
            r"print\s*\(",
        ]
        for pattern in python_indicators:
            if re.search(pattern, code):
                return True
        return False

    def validate(
        self, code: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Valida código usando pipeline de normalização conforme contrato.

        Pipeline determinístico:
        1. Normalização completa (PythonNormalizer)
        2. Validação AST
        3. Validação de segurança AST
        4. Decisão de commit/retry/rollback

        Args:
            code: Código a ser validado
            context: Contexto opcional para decisão

        Returns:
            ValidationResult com decisão e código validado
        """
        errors = []
        issues = []

        # Se não for Python, pula validação AST e retorna aprovado
        if not self._is_python_code(code):
            logger.info(
                "[FEEDBACK] Código não-Python detectado — pulando validação AST"
            )
            return ValidationResult(
                valid=True,
                code=code,
                errors=[],
                decision=Decision.COMMIT,
                score=1.0,
                issues=["Validação AST pulada (código não-Python)"],
            )

        try:
            # =================================================================
            # ETAPA 1: NORMALIZAÇÃO CONFORME CONTRATO PYTHONNORMALIZER
            # =================================================================
            normalized_code, syntax_valid, norm_result = normalize_before_repair(code)

            if not syntax_valid:
                logger.warning(
                    f"[FEEDBACK] Código inválido após normalização: {norm_result.syntax_error}"
                )
                return ValidationResult(
                    valid=False,
                    code=None,
                    errors=[f"Normalização falhou: {norm_result.syntax_error}"],
                    decision=Decision.RETRY,
                    score=0.0,
                    issues=["código_inválido_após_normalização"],
                )

            # Usa código normalizado para validação
            code = normalized_code

            # =================================================================
            # ETAPA 2: VALIDAÇÃO AST
            # =================================================================
            validar_sintaxe(code)
            result = _ast_gateway.parse(code)
            if not result.valid:
                return ValidationResult(
                    valid=False,
                    code=None,
                    errors=result.errors,
                    decision=Decision.RETRY,
                    score=0.0,
                )

            # =================================================================
            # ETAPA 3: VALIDAÇÃO DE SEGURANÇA AST
            # =================================================================
            safe, violations = validate_ast_security_str(code)
            if not safe:
                raise ValueError(f"Security violations: {violations}")

            logger.info(
                "[FEEDBACK] Código aprovado: normalização + sintaxe + AST security OK"
            )
            return ValidationResult(
                valid=True,
                code=code,
                errors=[],
                decision=Decision.COMMIT,
                score=1.0,
            )

        except SyntaxError as e:
            errors.append(f"SyntaxError: {e}")
            issues.append("erro de sintaxe — retry recomendado")
        except ValueError as e:
            errors.append(f"SecurityViolation: {e}")
            issues.append("violação de segurança — rollback")
        except Exception as e:
            errors.append(str(e))
            issues.append("erro inesperado")

        decision = self._decide(errors, context)
        logger.warning(
            f"[FEEDBACK] Validação falhou: {errors} → decisão: {decision.value}"
        )

        return ValidationResult(
            valid=False,
            code=None,
            errors=errors,
            decision=decision,
            score=0.0,
            issues=issues,
        )

    def validate_mcp_call(self, tool_schema: dict, arguments: dict) -> bool:
        """Valida argumentos de chamada MCP contra schema da tool."""
        params = tool_schema.get("parameters", {})
        if not params:
            return True

        for key, spec in params.items():
            if "type" in spec:
                val = arguments.get(key)
                expected = spec["type"]
                if expected == "string" and not isinstance(val, (str, type(None))):
                    logger.warning(
                        "[MCP-SCHEMA] %s esperava string, recebeu %s",
                        key,
                        type(val).__name__,
                    )
                    return False
                elif (
                    expected == "integer"
                    and val is not None
                    and not isinstance(val, int)
                ):
                    logger.warning(
                        "[MCP-SCHEMA] %s esperava integer, recebeu %s",
                        key,
                        type(val).__name__,
                    )
                    return False
                elif (
                    expected == "boolean"
                    and val is not None
                    and not isinstance(val, bool)
                ):
                    logger.warning(
                        "[MCP-SCHEMA] %s esperava boolean, recebeu %s",
                        key,
                        type(val).__name__,
                    )
                    return False
        return True

    def _decide(self, errors: List[str], context: Optional[Dict] = None) -> Decision:
        """Decide próximo passo baseado no tipo de erro e contexto."""
        error_text = " ".join(errors).lower()

        if "security" in error_text or "forbidden" in error_text:
            return Decision.ROLLBACK

        retry_count = (context or {}).get("retry_count", 0)
        if retry_count >= 2:
            return Decision.ROLLBACK

        if "syntax" in error_text or "invalid" in error_text:
            return Decision.RETRY

        return Decision.RETRY

    def apply_patch(
        self, original_code: str, patch: str
    ) -> Tuple[bool, str, List[str]]:
        """Aplica patch incremental de forma segura.

        Estratégia: substituição simples por enquanto (patch é o código completo
        gerado pelo LLM). Em versões futuras, suportará diff real.

        Returns:
            (sucesso, código_final, erros)
        """
        errors = []

        result = self.validate(patch)
        if not result.valid:
            return False, original_code, result.errors

        logger.info("[FEEDBACK] Patch aplicado com sucesso (merge seguro)")
        return True, result.code or original_code, []

    def validate_and_apply(
        self, original_code: str, patch: str, context: Optional[Dict] = None
    ) -> ValidationResult:
        """Valida e aplica patch com rollback automático em falha.

        Fluxo completo do temp.md:
          LLM gera PATCH → ValidationEngine (AST + syntax) →
          Se válido → SafeMerge → persist event → schedule snapshot →
          Se inválido → decide retry or rollback
        """
        if context is None:
            context = {}

        result = self.validate(patch, context)
        if result.valid:
            success, merged, apply_errors = self.apply_patch(original_code, patch)
            if success:
                result.code = merged
                return result
            result.valid = False
            result.errors = apply_errors
            result.decision = self._decide(apply_errors, context)

        # Rollback automático se decisão for ROLLBACK
        if result.decision == Decision.ROLLBACK and self._snapshotter:
            snap_id = self._snapshotter.get_latest_snapshot_id()
            if snap_id:
                logger.info(f"[FEEDBACK] Rollback acionado para snapshot {snap_id}")
                result.code = None  # caller deve carregar o snapshot

        return result


# Alias para compatibilidade
ValidationEngine = FeedbackEngine
