# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
ErrorDescriptor — Objeto rico de diagnóstico.

Separa:
  - domain: Domínio do erro (JSON, IMPORT, SYNTAX, etc.)
  - cause: Causa específica (MODULE_NOT_FOUND, EXTRA_DATA, etc.)
  - severity: CRITICAL, HIGH, MEDIUM, LOW
  - classifier_confidence: Confiança da classificação
  - repair_confidence: Confiança do reparo (preenchida pós-reparo)

Uso:
  descriptor = ErrorDescriptor(
      domain=ErrorCategory.IMPORT,
      cause=ErrorCause.MODULE_NOT_FOUND,
      severity=Severity.HIGH,
      classifier_confidence=0.95,
      recoverable=False,
  )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum, auto


class ErrorCategory(str, Enum):
    """Domínios de erro."""

    SYNTAX = "syntax"  # Erros de sintaxe Python
    LEXICAL = "lexical"  # Caracteres inválidos, strings
    JSON = "json"  # Erros de parsing JSON
    IMPORT = "import"  # Erros de importação
    RUNTIME = "runtime"  # Erros de execução
    NETWORK = "network"  # Timeouts, conexão
    VALIDATION = "validation"  # Erros de validação
    UNKNOWN = "unknown"  # Não classificado


class ErrorCause(str, Enum):
    """Causas específicas de erro."""

    # SYNTAX / LEXICAL
    SYNTAX_ERROR = "syntax_error"
    UNTERMINATED_STRING = "unterminated_string"
    MISSING_INDENT = "missing_indent"
    INVALID_CHARACTER = "invalid_character"
    INVALID_DECIMAL = "invalid_decimal"
    EXPECTING_INDENT = "expecting_indent"

    # JSON
    JSON_PARSE_ERROR = "json_parse_error"
    EXTRA_DATA = "extra_data"
    EXPECTING_VALUE = "expecting_value"
    INVALID_ESCAPE = "invalid_escape"
    MISSING_COMMA = "missing_comma"

    # IMPORT
    IMPORT_ERROR = "import_error"
    MODULE_NOT_FOUND = "module_not_found"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    CIRCULAR_IMPORT = "circular_import"
    RELATIVE_IMPORT = "relative_import"

    # RUNTIME
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    TYPE_ERROR = "type_error"
    ATTRIBUTE_ERROR = "attribute_error"
    KEY_ERROR = "key_error"

    # NETWORK
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    DNS_ERROR = "dns_error"

    # VALIDATION
    SCHEMA_MISMATCH = "schema_mismatch"
    MISSING_FIELD = "missing_field"
    INVALID_FORMAT = "invalid_format"

    # UNKNOWN
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Níveis de severidade."""

    CRITICAL = "critical"  # Bloqueante, sistema comprometido
    HIGH = "high"  # Funcionalidade principal afetada
    MEDIUM = "medium"  # Funcionalidade secundária
    LOW = "low"  # Incômodo, workaround possível

    def priority_score(self) -> float:
        """Retorna score numérico para ordenação (0.0-1.0)."""
        scores = {
            Severity.CRITICAL: 1.0,
            Severity.HIGH: 0.75,
            Severity.MEDIUM: 0.5,
            Severity.LOW: 0.25,
        }
        return scores.get(self, 0.5)


@dataclass
class ErrorDescriptor:
    """
    Objeto rico de diagnóstico de erro.

    Separa domínio (onde ocorreu) de causa (por que ocorreu).
    Mantém duas confianças: classificação e reparo.

    Atributos:
        domain: Domínio do erro (ErrorCategory)
        cause: Causa específica (ErrorCause)
        severity: Severidade (Severity)
        classifier_confidence: Confiança da classificação (0.0-1.0)
        repair_confidence: Confiança do reparo (0.0-1.0, pós-reparo)
        recoverable: Se erro pode ser recuperado
        component: Componente onde ocorreu
        error_type: Nome da exceção
        error_message: Mensagem do erro
        error_line: Linha do erro (se disponível)
        error_column: Coluna do erro (se disponível)
        traceback: Stack trace (se disponível)
        metadata: Dados extras do contexto
        context: Contexto adicional
        repair_attempts: Lista de tentativas de reparo
        parent_report: Report anterior (se re-tentativa)
    """

    # Identificação principal
    domain: ErrorCategory
    cause: ErrorCause
    severity: Severity

    # Confianças (separadas)
    classifier_confidence: float = 0.5
    repair_confidence: Optional[float] = None

    # Recuperabilidade
    recoverable: bool = True

    # Detalhes do erro
    component: str = "unknown"
    error_type: str = ""
    error_message: str = ""
    error_line: Optional[int] = None
    error_column: Optional[int] = None
    traceback: Optional[str] = None

    # Contexto e metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    # Histórico de reparos
    repair_attempts: List[Dict[str, Any]] = field(default_factory=list)
    parent_report: Optional[Any] = None  # Forward reference

    def can_attempt_repair(self) -> bool:
        """Verifica se vale a pena tentar reparo."""
        return self.recoverable and self.classifier_confidence > 0.3

    def get_repair_priority(self) -> float:
        """
        Calcula prioridade de reparo (0.0-1.0).

        Considera:
          - Severidade (peso 0.6)
          - Confiança da classificação (peso 0.4)
        """
        severity_weight = 0.6
        confidence_weight = 0.4

        priority = (
            self.severity.priority_score() * severity_weight
            + self.classifier_confidence * confidence_weight
        )

        return min(1.0, max(0.0, priority))

    def get_diagnostics(self) -> Dict[str, Any]:
        """Retorna diagnóstico completo para logging/telemetria."""
        return {
            "domain": self.domain.value,
            "cause": self.cause.value,
            "severity": self.severity.value,
            "classifier_confidence": self.classifier_confidence,
            "repair_confidence": self.repair_confidence,
            "recoverable": self.recoverable,
            "component": self.component,
            "error_type": self.error_type,
            "error_message": self.error_message[:200] if self.error_message else "",
            "error_line": self.error_line,
            "error_column": self.error_column,
            "repair_attempts": len(self.repair_attempts),
        }

    def add_repair_attempt(self, strategy_name: str, success: bool, confidence: float):
        """Registra tentativa de reparo."""
        self.repair_attempts.append(
            {
                "strategy": strategy_name,
                "success": success,
                "confidence": confidence,
            }
        )

        # Atualiza confiança de reparo se sucesso
        if success:
            self.repair_confidence = confidence

    def is_critical(self) -> bool:
        """Verifica se erro é crítico."""
        return self.severity == Severity.CRITICAL

    def is_high_confidence(self) -> bool:
        """Verifica se classificação é de alta confiança."""
        return self.classifier_confidence >= 0.85

    def __str__(self) -> str:
        return (
            f"ErrorDescriptor({self.domain.value}/{self.cause.value}, "
            f"severity={self.severity.value}, "
            f"confidence={self.classifier_confidence:.2f}, "
            f"recoverable={self.recoverable})"
        )

    def __repr__(self) -> str:
        return self.__str__()
