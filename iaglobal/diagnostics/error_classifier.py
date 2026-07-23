# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Error Classifier — Chain of Responsibility para classificação de erros.

Arquitetura:
  Exception
      ↓
  SyntaxClassifier → JsonClassifier → ImportClassifier → GenericClassifier
      ↓
  ErrorDescriptor(domain, cause, severity, confidence)

Cada classificador:
  - Verifica se pode classificar (can_classify)
  - Se sim: retorna ErrorDescriptor
  - Se não: passa para próximo na cadeia
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from iaglobal.diagnostics.error_descriptor import (
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
    Severity,
)


class BaseErrorClassifier:
    """
    Classificador base para Chain of Responsibility.

    Uso:
      classifier = SyntaxClassifier()
      classifier.set_next(JsonClassifier())

      descriptor = classifier.classify(error, context)
    """

    def __init__(self):
        self._next: Optional[BaseErrorClassifier] = None

    def set_next(self, classifier: "BaseErrorClassifier") -> "BaseErrorClassifier":
        """Define próximo classificador na cadeia."""
        self._next = classifier
        return classifier  # Retorna para permitir chaining

    def classify(
        self, error: Any, context: Dict[str, Any]
    ) -> Optional[ErrorDescriptor]:
        """
        Tenta classificar erro.

        Se não conseguir, passa para próximo na cadeia.
        """
        if self.can_classify(error, context):
            return self._classify(error, context)

        # Passa para próximo
        if self._next:
            return self._next.classify(error, context)

        # Fim da cadeia
        return None

    def can_classify(self, error: Any, context: Dict[str, Any]) -> bool:
        """Verifica se este classificador pode lidar com o erro."""
        raise NotImplementedError

    def _classify(self, error: Any, context: Dict[str, Any]) -> ErrorDescriptor:
        """Efetua classificação (chamado apenas se can_classify=True)."""
        raise NotImplementedError


class SyntaxErrorClassifier(BaseErrorClassifier):
    """Classifica erros de sintaxe Python."""

    def can_classify(self, error: Any, context: Dict[str, Any]) -> bool:
        return isinstance(error, (SyntaxError, IndentationError))

    def _classify(self, error: Any, context: Dict[str, Any]) -> ErrorDescriptor:
        error_msg = str(error).lower()

        # Determina causa específica
        if "unterminated" in error_msg or "eof" in error_msg:
            cause = ErrorCause.UNTERMINATED_STRING
            domain = ErrorCategory.LEXICAL
            severity = Severity.LOW
            confidence = 0.9
        elif "expected an indented block" in error_msg:
            cause = ErrorCause.MISSING_INDENT
            domain = ErrorCategory.SYNTAX
            severity = Severity.LOW
            confidence = 0.95
        elif "invalid character" in error_msg:
            cause = ErrorCause.INVALID_CHARACTER
            domain = ErrorCategory.LEXICAL
            severity = Severity.LOW
            confidence = 0.85
        elif "invalid decimal" in error_msg:
            cause = ErrorCause.INVALID_DECIMAL
            domain = ErrorCategory.LEXICAL
            severity = Severity.MEDIUM
            confidence = 0.7
        else:
            cause = ErrorCause.SYNTAX_ERROR
            domain = ErrorCategory.SYNTAX
            severity = Severity.MEDIUM
            confidence = 0.6

        return ErrorDescriptor(
            domain=domain,
            cause=cause,
            severity=severity,
            classifier_confidence=confidence,
            component=context.get("component", "unknown"),
            error_type=type(error).__name__,
            error_message=str(error),
            error_line=getattr(error, "lineno", None),
            error_column=getattr(error, "offset", None),
            metadata={"code": context.get("code", "")},
        )


class JsonErrorClassifier(BaseErrorClassifier):
    """Classifica erros de JSON."""

    def can_classify(self, error: Any, context: Dict[str, Any]) -> bool:
        import json

        return isinstance(error, json.JSONDecodeError)

    def _classify(self, error: Any, context: Dict[str, Any]) -> ErrorDescriptor:
        error_msg = str(error).lower()

        # Causa específica
        if "extra data" in error_msg:
            cause = ErrorCause.EXTRA_DATA
            domain = ErrorCategory.JSON
            severity = Severity.LOW
            confidence = 0.95
        elif "expecting" in error_msg:
            cause = ErrorCause.EXPECTING_VALUE
            domain = ErrorCategory.JSON
            severity = Severity.MEDIUM
            confidence = 0.8
        elif "invalid escape" in error_msg:
            cause = ErrorCause.INVALID_ESCAPE
            domain = ErrorCategory.JSON
            severity = Severity.MEDIUM
            confidence = 0.85
        else:
            cause = ErrorCause.JSON_PARSE_ERROR
            domain = ErrorCategory.JSON
            severity = Severity.MEDIUM
            confidence = 0.7

        return ErrorDescriptor(
            domain=domain,
            cause=cause,
            severity=severity,
            classifier_confidence=confidence,
            component=context.get("component", "unknown"),
            error_type=type(error).__name__,
            error_message=str(error),
            error_line=getattr(error, "lineno", None),
            error_column=getattr(error, "colno", None),
            metadata={"json_text": context.get("json_text", "")},
        )


class ImportErrorClassifier(BaseErrorClassifier):
    """Classifica erros de import."""

    def can_classify(self, error: Any, context: Dict[str, Any]) -> bool:
        return isinstance(error, (ImportError, ModuleNotFoundError))

    def _classify(self, error: Any, context: Dict[str, Any]) -> ErrorDescriptor:
        error_msg = str(error).lower()

        # Causa específica
        if "no module named" in error_msg:
            cause = ErrorCause.MODULE_NOT_FOUND
            domain = ErrorCategory.IMPORT
            severity = Severity.HIGH
            confidence = 0.95
            recoverable = False
        elif "cannot import" in error_msg:
            cause = ErrorCause.SYMBOL_NOT_FOUND
            domain = ErrorCategory.IMPORT
            severity = Severity.HIGH
            confidence = 0.9
            recoverable = False
        elif "circular import" in error_msg:
            cause = ErrorCause.CIRCULAR_IMPORT
            domain = ErrorCategory.IMPORT
            severity = Severity.CRITICAL
            confidence = 0.95
            recoverable = False
        elif "relative import" in error_msg:
            cause = ErrorCause.RELATIVE_IMPORT
            domain = ErrorCategory.IMPORT
            severity = Severity.HIGH
            confidence = 0.85
            recoverable = False
        else:
            cause = ErrorCause.IMPORT_ERROR
            domain = ErrorCategory.IMPORT
            severity = Severity.HIGH
            confidence = 0.8
            recoverable = False

        return ErrorDescriptor(
            domain=domain,
            cause=cause,
            severity=severity,
            classifier_confidence=confidence,
            recoverable=recoverable,
            component=context.get("component", "unknown"),
            error_type=type(error).__name__,
            error_message=str(error),
            metadata={"module": context.get("module", "")},
        )


class GenericErrorClassifier(BaseErrorClassifier):
    """Classificador genérico (sempre classifica como fallback)."""

    def can_classify(self, error: Any, context: Dict[str, Any]) -> bool:
        return True  # Sempre pode classificar

    def _classify(self, error: Any, context: Dict[str, Any]) -> ErrorDescriptor:
        error_msg = str(error).lower()

        # Tenta inferir domínio
        if "timeout" in error_msg:
            domain = ErrorCategory.NETWORK
            cause = ErrorCause.TIMEOUT
            severity = Severity.MEDIUM
            confidence = 0.7
            recoverable = True
        elif "permission" in error_msg or "access" in error_msg:
            domain = ErrorCategory.RUNTIME
            cause = ErrorCause.PERMISSION_DENIED
            severity = Severity.HIGH
            confidence = 0.8
            recoverable = False
        elif "file" in error_msg or "not found" in error_msg:
            domain = ErrorCategory.RUNTIME
            cause = ErrorCause.FILE_NOT_FOUND
            severity = Severity.MEDIUM
            confidence = 0.6
            recoverable = True
        else:
            domain = ErrorCategory.UNKNOWN
            cause = ErrorCause.UNKNOWN
            severity = Severity.MEDIUM
            confidence = 0.5
            recoverable = False

        return ErrorDescriptor(
            domain=domain,
            cause=cause,
            severity=severity,
            classifier_confidence=confidence,
            recoverable=recoverable,
            component=context.get("component", "unknown"),
            error_type=type(error).__name__,
            error_message=str(error),
            metadata=context,
        )


class ErrorClassifierEngine:
    """
    Engine que constrói e gerencia cadeia de classificadores.

    Uso:
      engine = ErrorClassifierEngine()
      descriptor = engine.classify(error, context)
    """

    def __init__(self):
        self._chain: Optional[BaseErrorClassifier] = None
        self._build_chain()

    def _build_chain(self):
        """Constrói cadeia de classificadores."""
        # Ordem importa: específicos primeiro, genérico por último
        syntax = SyntaxErrorClassifier()
        json_cls = JsonErrorClassifier()
        import_cls = ImportErrorClassifier()
        generic = GenericErrorClassifier()

        # Constrói cadeia
        syntax.set_next(json_cls).set_next(import_cls).set_next(generic)

        self._chain = syntax

    def classify(
        self, error: Any, context: Optional[Dict[str, Any]] = None
    ) -> ErrorDescriptor:
        """
        Classifica erro usando cadeia de classificadores.

        Args:
            error: Exceção ou erro
            context: Contexto (component, code, etc.)

        Returns:
            ErrorDescriptor completo
        """
        context = context or {}

        if not self._chain:
            # Fallback de emergência
            return ErrorDescriptor(
                domain=ErrorCategory.UNKNOWN,
                cause=ErrorCause.UNKNOWN,
                severity=Severity.MEDIUM,
                classifier_confidence=0.0,
                recoverable=False,
                error_message=f"Classifier chain not initialized: {error}",
            )

        result = self._chain.classify(error, context)

        if result is None:
            # Should never happen (GenericErrorClassifier always matches)
            return ErrorDescriptor(
                domain=ErrorCategory.UNKNOWN,
                cause=ErrorCause.UNKNOWN,
                severity=Severity.MEDIUM,
                classifier_confidence=0.0,
                recoverable=False,
                error_message=f"Classification failed: {error}",
            )

        return result

    def add_classifier(self, classifier: BaseErrorClassifier, position: int = 0):
        """
        Adiciona classificador na cadeia.

        position=0: início (alta prioridade)
        position=-1: fim (baixa prioridade, antes do genérico)
        """
        if position == 0:
            classifier.set_next(self._chain)
            self._chain = classifier
        else:
            # Encontra penúltimo e adiciona antes do genérico
            current = self._chain
            while (
                current
                and current._next
                and not isinstance(current._next, GenericErrorClassifier)
            ):
                current = current._next

            if current:
                classifier.set_next(current._next)
                current._next = classifier


# Singleton global
error_classifier = ErrorClassifierEngine()
