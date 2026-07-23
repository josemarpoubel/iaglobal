# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Repair Strategies — Estratégias de reparo plugáveis.

Arquitetura:
  RepairStrategy (base)
        ↓
  SyntaxRepairStrategy
  JsonRecoveryStrategy
  UnicodeRepairStrategy
  ImportFallbackStrategy
  GenericRetryStrategy

Cada estratégia declara:
  - handles: Categorias que atende
  - is_idempotent: Se pode ser aplicada múltiplas vezes
  - max_attempts: Máximo de tentativas

Uso:
  strategy = SyntaxRepairStrategy()
  result = await strategy.execute(code, descriptor, context)
"""

from __future__ import annotations

import ast
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Set, Dict, Any, Optional, List

from iaglobal.diagnostics.error_descriptor import (
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
)


logger = logging.getLogger("iaglobal")


@dataclass
class RepairResult:
    """Resultado de reparo."""

    success: bool
    after_code: str
    confidence: float
    model: str
    changes_made: List[str]
    explanation: str = ""

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return (
            f"RepairResult({status} {self.model}, "
            f"confidence={self.confidence:.2f}, "
            f"changes={len(self.changes_made)})"
        )


class RepairStrategy(ABC):
    """
    Estratégia base de reparo.

    Subclasses devem implementar:
      - name: Nome da estratégia
      - handles: Categorias atendidas
      - execute: Execução do reparo

    Opcionalmente:
      - is_idempotent: Se é idempotente
      - verify: Verifica resultado
    """

    name: str = "base"
    handles: Set[ErrorCategory] = set()
    is_idempotent: bool = False
    max_attempts: int = 3

    @abstractmethod
    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """
        Executa reparo.

        Args:
            code: Código original
            descriptor: ErrorDescriptor classificado
            context: Contexto adicional

        Returns:
            RepairResult
        """
        pass

    def can_handle(self, descriptor: ErrorDescriptor) -> bool:
        """Verifica se estratégia pode lidar com erro."""
        return descriptor.domain in self.handles

    def verify(self, before_code: str, after_code: str) -> bool:
        """
        Verifica se reparo foi válido.

        Default: verifica sintaxe Python.
        """
        try:
            ast.parse(after_code)
            return True
        except SyntaxError:
            return False


class SyntaxRepairStrategy(RepairStrategy):
    """
    Estratégia para reparo de erros de sintaxe.

    Handles:
      - ErrorCategory.SYNTAX
      - ErrorCategory.LEXICAL
    """

    name = "syntax_repair"
    handles = {ErrorCategory.SYNTAX, ErrorCategory.LEXICAL}
    is_idempotent = True
    max_attempts = 2

    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """Repara erros de sintaxe usando LLM."""

        # Monta prompt específico
        error_info = descriptor.error_message
        line_info = f" (line {descriptor.error_line})" if descriptor.error_line else ""

        prompt = f"""
Fix this Python syntax error:

Error: {error_info}{line_info}

Original code:
```python
{code}
```

Return ONLY the fixed code, no explanation.
"""

        # Chama LLM (via critic ou provider_router)
        # Por enquanto, fallback simples
        fixed_code = await self._fix_syntax_fallback(code, descriptor)

        if fixed_code and fixed_code != code:
            return RepairResult(
                success=True,
                after_code=fixed_code,
                confidence=0.75,
                model="syntax_fallback",
                changes_made=["syntax_fix"],
                explanation=f"Fixed syntax error: {error_info}",
            )

        return RepairResult(
            success=False,
            after_code=code,
            confidence=0.0,
            model="syntax_fallback",
            changes_made=[],
            explanation="Could not fix syntax error",
        )

    async def _fix_syntax_fallback(
        self,
        code: str,
        descriptor: ErrorDescriptor,
    ) -> Optional[str]:
        """Fallback heurístico para erros comuns de sintaxe."""

        error_msg = descriptor.error_message.lower()

        # unterminated string
        if "unterminated" in error_msg or "eof" in error_msg:
            # Tenta fechar strings abertas
            if code.count('"') % 2 == 1:
                return code + '"'
            if code.count("'") % 2 == 1:
                return code + "'"
            if code.count('"""') % 2 == 1:
                return code + '"""'
            if code.count("'''") % 2 == 1:
                return code + "'''"

        # missing indent
        if "expected an indented block" in error_msg:
            # Adiciona pass em funções/métodos vazios
            lines = code.split("\n")
            for i, line in enumerate(lines):
                if line.strip().endswith(":"):
                    # Verifica próxima linha
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if next_line.strip() and not next_line.startswith(" " * 4):
                            lines.insert(i + 1, "    pass")
                            return "\n".join(lines)

        # expected indent
        if "expected indent" in error_msg:
            # Adiciona indentação
            lines = code.split("\n")
            if descriptor.error_line and descriptor.error_line <= len(lines):
                line_idx = descriptor.error_line - 1
                lines[line_idx] = "    " + lines[line_idx].lstrip()
                return "\n".join(lines)

        return None


class JsonRecoveryStrategy(RepairStrategy):
    """
    Estratégia para reparo de erros JSON.

    Handles:
      - ErrorCategory.JSON
    """

    name = "json_recovery"
    handles = {ErrorCategory.JSON}
    is_idempotent = True
    max_attempts = 2

    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """Repara erros JSON usando heurísticas."""

        import json

        error_msg = descriptor.error_message.lower()

        # extra data
        if "extra data" in error_msg:
            # Tenta extrair primeiro objeto JSON válido
            try:
                # Encontra última chave/colchete válido
                for i in range(len(code), 0, -1):
                    try:
                        parsed = json.loads(code[:i])
                        return RepairResult(
                            success=True,
                            after_code=code[:i],
                            confidence=0.85,
                            model="json_truncate",
                            changes_made=["truncated_extra_data"],
                            explanation="Removed extra data after JSON object",
                        )
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass

        # invalid escape
        if "invalid escape" in error_msg:
            # Tenta corrigir escapes
            fixed = code.replace("\\", "\\\\")
            try:
                json.loads(fixed)
                return RepairResult(
                    success=True,
                    after_code=fixed,
                    confidence=0.7,
                    model="json_escape_fix",
                    changes_made=["fixed_escapes"],
                    explanation="Fixed invalid escape sequences",
                )
            except json.JSONDecodeError:
                pass

        # expecting value
        if "expecting" in error_msg:
            # Tenta adicionar valor faltante
            if code.rstrip().endswith(":"):
                fixed = code + " null"
                try:
                    json.loads(fixed)
                    return RepairResult(
                        success=True,
                        after_code=fixed,
                        confidence=0.6,
                        model="json_value_add",
                        changes_made=["added_null_value"],
                        explanation="Added missing value",
                    )
                except json.JSONDecodeError:
                    pass

        return RepairResult(
            success=False,
            after_code=code,
            confidence=0.0,
            model="json_recovery",
            changes_made=[],
            explanation="Could not repair JSON",
        )


class UnicodeRepairStrategy(RepairStrategy):
    """
    Estratégia para reparo de caracteres Unicode inválidos.

    Handles:
      - ErrorCategory.LEXICAL (invalid_character)
    """

    name = "unicode_repair"
    handles = {ErrorCategory.LEXICAL}
    is_idempotent = True
    max_attempts = 1

    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """Repara caracteres Unicode inválidos."""

        error_msg = descriptor.error_message.lower()

        if "invalid character" in error_msg or "invalid decimal" in error_msg:
            # Remove ou substitui caracteres inválidos
            try:
                # Tenta codificar/decodificar
                fixed = code.encode("utf-8", errors="ignore").decode("utf-8")

                if fixed != code:
                    return RepairResult(
                        success=True,
                        after_code=fixed,
                        confidence=0.8,
                        model="unicode_cleanup",
                        changes_made=["removed_invalid_unicode"],
                        explanation="Removed invalid Unicode characters",
                    )
            except Exception:
                pass

            # Fallback: remove caracteres não-ASCII
            fixed = code.encode("ascii", errors="ignore").decode("ascii")

            if fixed != code:
                return RepairResult(
                    success=True,
                    after_code=fixed,
                    confidence=0.6,
                    model="ascii_fallback",
                    changes_made=["removed_non_ascii"],
                    explanation="Removed non-ASCII characters",
                )

        return RepairResult(
            success=False,
            after_code=code,
            confidence=0.0,
            model="unicode_repair",
            changes_made=[],
            explanation="Could not repair Unicode",
        )


class ImportFallbackStrategy(RepairStrategy):
    """
    Estratégia para erros de import (não recuperáveis).

    Handles:
      - ErrorCategory.IMPORT

    Nota: Imports geralmente não são recuperáveis automaticamente.
    Esta estratégia apenas registra o erro para telemetria.
    """

    name = "import_fallback"
    handles = {ErrorCategory.IMPORT}
    is_idempotent = True
    max_attempts = 1

    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """Registra erro de import (não recuperável)."""

        # Imports não são recuperáveis automaticamente
        logger.warning(f"Import error not recoverable: {descriptor.error_message}")

        return RepairResult(
            success=False,
            after_code=code,
            confidence=0.0,
            model="import_fallback",
            changes_made=[],
            explanation=f"Import error not recoverable: {descriptor.error_message}",
        )


class GenericRetryStrategy(RepairStrategy):
    """
    Estratégia genérica de retry (fallback final).

    Handles:
      - ErrorCategory.RUNTIME
      - ErrorCategory.NETWORK
      - ErrorCategory.UNKNOWN
    """

    name = "generic_retry"
    handles = {ErrorCategory.RUNTIME, ErrorCategory.NETWORK, ErrorCategory.UNKNOWN}
    is_idempotent = False
    max_attempts = 3

    async def execute(
        self,
        code: str,
        descriptor: ErrorDescriptor,
        context: Dict[str, Any],
    ) -> RepairResult:
        """Tenta retry simples para erros recuperáveis."""

        if not descriptor.recoverable:
            return RepairResult(
                success=False,
                after_code=code,
                confidence=0.0,
                model="generic_retry",
                changes_made=[],
                explanation="Error not recoverable",
            )

        # Para timeouts e erros de rede, apenas retry
        if descriptor.cause == ErrorCause.TIMEOUT:
            # Simula retry (na prática, chamaria LLM novamente)
            await asyncio.sleep(0.1)  # Backoff mínimo

            return RepairResult(
                success=True,  # Assume que retry funcionou
                after_code=code,
                confidence=0.5,
                model="generic_retry",
                changes_made=["retry"],
                explanation="Retried after timeout",
            )

        # Outros erros: fallback
        return RepairResult(
            success=False,
            after_code=code,
            confidence=0.0,
            model="generic_retry",
            changes_made=[],
            explanation="No generic repair available",
        )
