# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
PythonNormalizer — Pipeline de normalização sintática para código Python.

Pipeline:
  LLM Output
      ↓
  Extract Code (remove markdown, texto externo)
      ↓
  Sanitize (limpeza básica)
      ↓
  ruff format (padronização determinística)
      ↓
  ruff check --fix (correções automáticas)
      ↓
  ast.parse (validação sintática)
      ↓
  NormalizeResult

Uso:
    normalizer = PythonNormalizer()
    result = normalizer.normalize(code)

    if result.syntax_valid:
        return result.fixed  # código normalizado
    else:
        # enviar para RepairEngine
"""

from __future__ import annotations

import ast
import re
import subprocess
import tempfile
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("iaglobal")


# =============================================================================
# Exceções específicas de normalização
# =============================================================================


class NormalizationError(Exception):
    """Erro base para falhas de normalização."""

    pass


class FormatterUnavailableError(NormalizationError):
    """Raised quando formatter (ruff) não está disponível."""

    pass


class InvalidPythonError(NormalizationError):
    """Raised quando código Python é sintaticamente inválido."""

    def __init__(self, message: str, code: str, line: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.line = line


class ASTValidationError(NormalizationError):
    """Raised quando validação AST falha."""

    pass


class SanitizationError(NormalizationError):
    """Raised quando sanitização falha."""

    pass


@dataclass
class NormalizeResult:
    """Resultado enriquecido da normalização com métricas e observabilidade."""

    original: str
    sanitized: str
    formatted: str
    fixed: str
    syntax_valid: bool
    syntax_error: Optional[str] = None
    ruff_format_errors: list = None
    ruff_check_errors: list = None

    # Métricas de transformação
    format_changed: bool = False
    fix_changed: bool = False

    # Performance
    duration_ms: float = 0.0

    # Observabilidade
    warnings: list = None

    def __post_init__(self):
        if self.ruff_format_errors is None:
            object.__setattr__(self, "ruff_format_errors", [])
        if self.ruff_check_errors is None:
            object.__setattr__(self, "ruff_check_errors", [])
        if self.warnings is None:
            object.__setattr__(self, "warnings", [])

    @property
    def changed(self) -> bool:
        """Retorna True se alguma transformação foi aplicada."""
        return self.format_changed or self.fix_changed

    @property
    def transformation_summary(self) -> dict:
        """Retorna resumo das transformações aplicadas."""
        return {
            "format_changed": self.format_changed,
            "fix_changed": self.fix_changed,
            "syntax_valid": self.syntax_valid,
            "duration_ms": self.duration_ms,
            "warnings_count": len(self.warnings),
        }


class PythonNormalizer:
    """
    Contrato explícito para normalização de código Python gerado por LLM.

    Pipeline determinístico que garante qualidade de código antes de validação,
    pontuação ou persistência.

    Pipeline:
        1. Extract & Sanitize - Remove markdown e texto externo
        2. Ruff Format - Padronização determinística de formatação
        3. Ruff Check --fix - Correções automáticas de estilo e imports
        4. AST Parse - Validação sintática final

    Contrato de uso:
        normalizer = PythonNormalizer()
        result = normalizer.normalize(code)

        if result.syntax_valid:
            # Código está pronto para validação, pontuação ou persistência
            normalized_code = result.fixed
        else:
            # Enviar para RepairEngine ou LLM retry
            pass
    """

    def __init__(self, ruff_path: Optional[str] = None):
        """
        Inicializa o normalizador com pipeline completo.

        Args:
            ruff_path: Caminho para o executável do ruff. Se None, usa 'ruff' do PATH.
        """
        self.ruff_cmd = ruff_path or "ruff"
        self._ruff_available = self._verify_ruff_available()

    def _verify_ruff_available(self) -> bool:
        """Verifica se ruff está disponível. Retorna True se disponível."""
        try:
            subprocess.run(
                [self.ruff_cmd, "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(
                f"Ruff não encontrado ({self.ruff_cmd}). "
                "Pipeline de normalização continuará sem formatação automática. "
                "Instale com: pip install ruff"
            )
            return False

    def normalize(self, code: str) -> NormalizeResult:
        """
        Executa o pipeline completo de normalização conforme contrato.

        Este é o método principal do contrato PythonNormalizer.

        Args:
            code: Código original gerado por LLM (pode conter markdown, texto, etc.)

        Returns:
            NormalizeResult: Resultado enriquecido com todas as etapas e status

        Garante que:
        - Todo código passa por extração e sanitização
        - Formatação é padronizada com ruff format
        - Correções automáticas são aplicadas com ruff check --fix
        - Validação sintática é realizada com ast.parse
        """
        start_time = time.time()
        warnings = []

        # =====================================================================
        # ETAPA 1: EXTRAÇÃO E SANITIZAÇÃO (Contrato: código puro)
        # =====================================================================
        sanitized = self._extract_and_sanitize(code)

        # =====================================================================
        # ETAPA 2: RUFF FORMAT — pula se ruff não estiver disponível
        # =====================================================================
        if self._ruff_available:
            formatted, format_errors = self._ruff_format(sanitized)
            format_changed = formatted != sanitized
        else:
            formatted, format_errors = sanitized, []
            format_changed = False

        # =====================================================================
        # ETAPA 3: RUFF CHECK --FIX — pula se ruff não estiver disponível
        # =====================================================================
        if self._ruff_available:
            fixed, check_errors = self._ruff_check(formatted)
            fix_changed = fixed != formatted
        else:
            fixed, check_errors = formatted, []
            fix_changed = False

        # =====================================================================
        # ETAPA 4: VALIDAÇÃO AST (Contrato: código sintaticamente válido)
        # =====================================================================
        syntax_valid, syntax_error = self._ast_validate(fixed)

        duration_ms = (time.time() - start_time) * 1000

        # Coleta warnings
        if format_errors:
            warnings.extend(format_errors)
        if check_errors:
            warnings.extend(check_errors)

        return NormalizeResult(
            original=code,
            sanitized=sanitized,
            formatted=formatted,
            fixed=fixed,
            syntax_valid=syntax_valid,
            syntax_error=syntax_error,
            ruff_format_errors=format_errors or [],
            ruff_check_errors=check_errors or [],
            format_changed=format_changed,
            fix_changed=fix_changed,
            duration_ms=duration_ms,
            warnings=warnings or [],
        )

    def _extract_and_sanitize(self, code: str) -> str:
        """
        Extrai código de blocos markdown e remove texto externo.

        Remove:
        - Blocos ```python ... ```
        - Texto antes/depois do código
        - Comentários de LLM ("Aqui está seu código:", etc.)
        """
        text = code.strip()

        # Padrão 1: Extrair de blocos markdown ```python
        markdown_pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(markdown_pattern, text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Se múltiplos blocos, junta todos
            text = "\n\n".join(m.strip() for m in matches)

        # Padrão 2: Remover texto comum de LLM antes do código
        llm_prefixes = [
            r"^(?:here|aqui)\s+(?:is|está)\s+(?:your|o)\s+(?:code|código)[:.]?\s*",
            r"^(?:sure|claro)[,\.]?\s*(?:here|aqui)\s+(?:is|está)?\s*",
            r"^(?:certainly|com certeza)[,\.]?\s*",
            r"^(?:of course|é claro)[,\.]?\s*",
            r"^(?:yes|sim)[,\.]?\s*",
        ]

        for prefix_pattern in llm_prefixes:
            text = re.sub(prefix_pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

        # Padrão 3: Remover texto após o código (assinaturas, explicações)
        llm_suffixes = [
            r"\n\s*(?:hope|espero)\s+(?:this|isto)\s+(?:helps|ajuda)[:.]?\s*$",
            r"\n\s*(?:let me|deixe-me)\s+(?:know|saber)\s+(?:if|se)\s*",
            r"\n\s*(?:feel|sinta-se)\s+(?:free|livre)\s+to\s+",
        ]

        for suffix_pattern in llm_suffixes:
            text = re.sub(suffix_pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

        # Limpeza final: remove linhas vazias extras
        lines = text.split("\n")
        lines = [line for line in lines if line.strip() or lines.index(line) == 0]

        return "\n".join(lines).strip()

    def _ruff_format(self, code: str) -> tuple[str, list]:
        """
        Executa ruff format no código.

        Args:
            code: Código sanitizado

        Returns:
            Tuple (código formatado, lista de erros)
        """
        errors = []

        try:
            # Cria arquivo temporário
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Executa ruff format
                result = subprocess.run(
                    [self.ruff_cmd, "format", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Lê código formatado
                with open(temp_path, "r", encoding="utf-8") as f:
                    formatted_code = f.read()

                # Captura erros do stderr
                if result.stderr:
                    errors = result.stderr.strip().split("\n")

                return formatted_code, errors

            finally:
                # Limpa arquivo temporário
                Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            logger.warning("Ruff format timeout")
            errors.append("Timeout ao formatar código")
            return code, errors
        except Exception as e:
            logger.warning(f"Ruff format falhou: {e}")
            errors.append(str(e))
            return code, errors

    def _ruff_check(self, code: str) -> tuple[str, list]:
        """
        Executa ruff check --fix no código.

        Args:
            code: Código formatado

        Returns:
            Tuple (código com correções, lista de erros/warnings)
        """
        errors = []

        try:
            # Cria arquivo temporário
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Executa ruff check --fix
                result = subprocess.run(
                    [self.ruff_cmd, "check", "--fix", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Lê código corrigido
                with open(temp_path, "r", encoding="utf-8") as f:
                    fixed_code = f.read()

                # Captura output (imports removidos, etc.)
                if result.stdout:
                    errors.extend(result.stdout.strip().split("\n"))

                # Warnings do stderr
                if result.stderr:
                    errors.extend(result.stderr.strip().split("\n"))

                return fixed_code, errors

            finally:
                # Limpa arquivo temporário
                Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            logger.warning("Ruff check timeout")
            errors.append("Timeout ao verificar código")
            return code, errors
        except Exception as e:
            logger.warning(f"Ruff check falhou: {e}")
            errors.append(str(e))
            return code, errors

    def _ast_validate(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Valida sintaxe do código com ast.parse().

        Args:
            code: Código normalizado

        Returns:
            Tuple (valid, error_message)
        """
        # Código vazio ou apenas whitespace não é válido
        if not code or not code.strip():
            return False, "Código vazio ou nulo"

        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"SyntaxError: {e.msg} at line {e.lineno}, col {e.offset}"
            logger.debug(f"AST validation failed: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.debug(f"AST validation failed: {error_msg}")
            return False, error_msg


# =============================================================================
# CONTRATO EXPLÍCITO: Ponto único de normalização
# =============================================================================

__all__ = ["PythonNormalizer", "NormalizeResult", "normalize_before_repair"]


def normalize_before_repair(
    code: str, error: Optional[str] = None
) -> tuple[str, bool, NormalizeResult]:
    """
    Função utilitária para normalização antes de RepairEngine ou validação.

    Contrato: Todo código gerado por LLM deve passar por normalização antes
    de qualquer processamento adicional.

    Args:
        code: Código original a ser normalizado
        error: Mensagem de erro opcional (para logging)

    Returns:
        Tuple: (código_normalizado, syntax_valid, NormalizeResult)

    Uso:
        # No RepairEngine
        normalized_code, syntax_valid, result = normalize_before_repair(code, str(error))
        if syntax_valid:
            return normalized_code  # pronto para reparo estrutural

        # Na validação
        normalized_code, syntax_valid, result = normalize_before_repair(code)
        if syntax_valid:
            return normalized_code  # pronto para validação AST
    """
    try:
        normalizer = PythonNormalizer()
        result = normalizer.normalize(code)

        if result.syntax_valid:
            logger.info(
                f"Normalização bem-sucedida: {len(result.warnings)} warnings, "
                f"{result.duration_ms:.2f}ms"
            )
            return result.fixed, True, result
        else:
            logger.warning(f"Código inválido após normalização: {result.syntax_error}")
            return result.fixed, False, result

    except Exception as e:
        logger.warning(f"Normalização falhou: {e}")
        error_result = NormalizeResult(
            original=code,
            sanitized=code,
            formatted=code,
            fixed=code,
            syntax_valid=False,
            syntax_error=str(e),
            warnings=[f"Normalização falhou: {e}"],
        )
        return code, False, error_result
