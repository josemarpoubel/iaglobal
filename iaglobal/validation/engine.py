import ast
import logging
import re
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, List, Optional, Dict, Any

from .ast_security import validate_ast_security_str
from .syntax import validar_sintaxe
from .normalization import normalizar_codigo
from iaglobal.utils.logger import logger


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

    Pipeline:
      1. Normalização (LLM cleanup)
      2. Syntax check (ast.parse)
      3. AST security validation
      4. Decisão: commit / retry / rollback
      5. Patch safe apply (merge incremental com rollback em falha)
    """

    def __init__(self, snapshotter=None):
        self._snapshotter = snapshotter

    @staticmethod
    def _is_python_code(code: str) -> bool:
        """Detecta se o código é Python baseado em padrões sintáticos."""
        if not code or len(code.strip()) < 10:
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

    def validate(self, code: str, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Valida código e retorna resultado com decisão."""
        import re
        errors = []
        issues = []

        # Se não for Python, pula validação AST e retorna aprovado
        if not self._is_python_code(code):
            logger.info("[FEEDBACK] Código não-Python detectado — pulando validação AST")
            return ValidationResult(
                valid=True, code=code, errors=[],
                decision=Decision.COMMIT, score=1.0,
                issues=["Validação AST pulada (código não-Python)"]
            )

        try:
            code = normalizar_codigo(code)
            if not code or len(code.strip()) < 5:
                return ValidationResult(
                    valid=False, code=None, errors=["Código vazio após normalização"],
                    decision=Decision.RETRY, score=0.0,
                )

            validar_sintaxe(code)
            tree = ast.parse(code)
            safe, violations = validate_ast_security_str(code)
            if not safe:
                raise ValueError(f"Security violations: {violations}")

            logger.info("[FEEDBACK] Código aprovado: sintaxe + AST security OK")
            return ValidationResult(
                valid=True, code=code, errors=[],
                decision=Decision.COMMIT, score=1.0,
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
        logger.warning(f"[FEEDBACK] Validação falhou: {errors} → decisão: {decision.value}")

        return ValidationResult(
            valid=False, code=None, errors=errors,
            decision=decision, score=0.0, issues=issues,
        )

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

    def apply_patch(self, original_code: str, patch: str) -> Tuple[bool, str, List[str]]:
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

    def validate_and_apply(self, original_code: str, patch: str,
                           context: Optional[Dict] = None) -> ValidationResult:
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

