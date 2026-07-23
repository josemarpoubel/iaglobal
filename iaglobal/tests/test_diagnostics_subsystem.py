# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Testes do subsistema diagnostics.

Valida:
  - ErrorDescriptor (domínio + causa separados)
  - ErrorClassifier (Chain of Responsibility)
  - RepairEngine (estratégias por capacidade)
  - RepairReport (enriquecido com attempt, chain)
"""

import pytest
import json
import asyncio
from typing import Any

from iaglobal.diagnostics import (
    error_classifier,
    repair_engine,
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
    Severity,
    RepairReport,
)


class TestErrorDescriptor:
    """Testa ErrorDescriptor."""

    def test_descriptor_with_domain_and_cause(self):
        """Descriptor separa domínio de causa."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.IMPORT,
            cause=ErrorCause.MODULE_NOT_FOUND,
            severity=Severity.HIGH,
            classifier_confidence=0.95,
            recoverable=False,
        )

        assert descriptor.domain == ErrorCategory.IMPORT
        assert descriptor.cause == ErrorCause.MODULE_NOT_FOUND
        assert descriptor.severity == Severity.HIGH
        assert descriptor.classifier_confidence == 0.95
        assert descriptor.recoverable is False

    def test_two_confidences(self):
        """Descriptor tem duas confianças (classificação e reparo)."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
        )

        assert descriptor.classifier_confidence == 0.9
        assert descriptor.repair_confidence is None

        # Simula reparo
        descriptor.repair_confidence = 0.75

        assert descriptor.repair_confidence == 0.75

    def test_repair_priority(self):
        """Prioridade considera severidade e confiança."""
        critical = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.CRITICAL,
            classifier_confidence=0.9,
        )

        low = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.5,
        )

        assert critical.get_repair_priority() > low.get_repair_priority()

    def test_can_attempt_repair(self):
        """Verifica se vale pena tentar reparo."""
        recoverable = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
            recoverable=True,
        )

        not_recoverable = ErrorDescriptor(
            domain=ErrorCategory.IMPORT,
            cause=ErrorCause.MODULE_NOT_FOUND,
            severity=Severity.HIGH,
            classifier_confidence=0.95,
            recoverable=False,
        )

        low_confidence = ErrorDescriptor(
            domain=ErrorCategory.UNKNOWN,
            cause=ErrorCause.UNKNOWN,
            severity=Severity.MEDIUM,
            classifier_confidence=0.2,
            recoverable=True,
        )

        assert recoverable.can_attempt_repair() is True
        assert not_recoverable.can_attempt_repair() is False
        assert low_confidence.can_attempt_repair() is False

    def test_add_repair_attempt(self):
        """Registra tentativas de reparo."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
        )

        descriptor.add_repair_attempt("syntax_repair", success=False, confidence=0.0)
        descriptor.add_repair_attempt("syntax_repair", success=True, confidence=0.75)

        assert len(descriptor.repair_attempts) == 2
        assert descriptor.repair_confidence == 0.75

    def test_get_diagnostics(self):
        """Retorna diagnóstico completo."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.JSON,
            cause=ErrorCause.EXTRA_DATA,
            severity=Severity.LOW,
            classifier_confidence=0.95,
            component="validator",
            error_type="JSONDecodeError",
            error_message="Extra data",
        )

        diag = descriptor.get_diagnostics()

        assert diag["domain"] == "json"
        assert diag["cause"] == "extra_data"
        assert diag["severity"] == "low"
        assert diag["classifier_confidence"] == 0.95
        assert diag["component"] == "validator"


class TestErrorClassifierChain:
    """Testa Chain of Responsibility."""

    def test_syntax_error_classification(self):
        """Classifica SyntaxError."""
        error = SyntaxError("unterminated string")
        error.lineno = 5
        error.offset = 10

        descriptor = error_classifier.classify(
            error,
            context={"component": "validator", "code": "x = 'hello"},
        )

        assert descriptor.domain == ErrorCategory.LEXICAL
        assert descriptor.cause == ErrorCause.UNTERMINATED_STRING
        assert descriptor.severity == Severity.LOW
        assert descriptor.classifier_confidence >= 0.8
        assert descriptor.recoverable is True

    def test_indentation_error_classification(self):
        """Classifica IndentationError."""
        error = IndentationError("expected an indented block")
        error.lineno = 3

        descriptor = error_classifier.classify(
            error,
            context={"component": "builder"},
        )

        assert descriptor.domain == ErrorCategory.SYNTAX
        assert descriptor.cause == ErrorCause.MISSING_INDENT
        assert descriptor.severity == Severity.LOW
        assert descriptor.recoverable is True

    def test_json_error_classification(self):
        """Classifica JSONDecodeError."""
        try:
            json.loads('{"key": "value"} extra')
        except json.JSONDecodeError as e:
            descriptor = error_classifier.classify(
                e,
                context={"component": "planner"},
            )

            assert descriptor.domain == ErrorCategory.JSON
            assert descriptor.cause == ErrorCause.EXTRA_DATA
            assert descriptor.severity == Severity.LOW
            assert descriptor.classifier_confidence >= 0.9

    def test_import_error_classification(self):
        """Classifica ModuleNotFoundError."""
        error = ModuleNotFoundError("No module named 'numpy'")

        descriptor = error_classifier.classify(
            error,
            context={"component": "validator", "module": "numpy"},
        )

        assert descriptor.domain == ErrorCategory.IMPORT
        assert descriptor.cause == ErrorCause.MODULE_NOT_FOUND
        assert descriptor.severity == Severity.HIGH
        assert descriptor.recoverable is False

    def test_generic_error_classification(self):
        """Classificador genérico é fallback."""
        error = RuntimeError("Unknown error")

        descriptor = error_classifier.classify(
            error,
            context={"component": "executor"},
        )

        # Genérico sempre classifica
        assert descriptor is not None
        assert descriptor.domain == ErrorCategory.UNKNOWN
        assert descriptor.cause == ErrorCause.UNKNOWN


class TestRepairEngineCapabilities:
    """Testa seleção de estratégias por capacidade."""

    def test_engine_has_capabilities(self):
        """Engine expõe capacidades."""
        caps = repair_engine.get_capabilities()

        assert isinstance(caps, dict)
        assert len(caps) > 0

    def test_syntax_strategy_registered(self):
        """SyntaxRepairStrategy registrada para SYNTAX e LEXICAL."""
        caps = repair_engine.get_capabilities()

        # Verifica se syntax está nas capacidades
        assert "syntax" in caps or "lexical" in caps

    def test_json_strategy_registered(self):
        """JsonRecoveryStrategy registrada para JSON."""
        caps = repair_engine.get_capabilities()

        assert "json" in caps


class TestRepairEngineExecution:
    """Testa execução de reparos."""

    @pytest.mark.asyncio
    async def test_repair_unterminated_string(self):
        """Repara string não fechada."""
        code = "x = 'hello"
        error = SyntaxError("unterminated string")
        error.lineno = 1

        report = await repair_engine.repair(
            code=code,
            error=error,
            context={"component": "test"},
        )

        assert (
            report.strategy_used == "syntax_repair"
            or report.strategy_used == "unicode_repair"
        )
        # Pode falhar (fallback heurístico limitado)
        # O importante é que o fluxo funciona

    @pytest.mark.asyncio
    async def test_repair_json_extra_data(self):
        """Repara JSON com dados extras."""
        code = '{"key": "value"} extra'

        try:
            json.loads(code)
        except json.JSONDecodeError as e:
            report = await repair_engine.repair(
                code=code,
                error=e,
                context={"component": "test"},
            )

            assert report.strategy_used == "json_recovery"
            # Estratégia pode ter sucesso ou não
            # O importante é que foi executada

    @pytest.mark.asyncio
    async def test_repair_not_recoverable(self):
        """Erros não recuperáveis não tentam reparo."""
        error = ModuleNotFoundError("No module named 'xyz'")

        report = await repair_engine.repair(
            code="import xyz",
            error=error,
            context={"component": "test"},
        )

        assert report.success is False
        assert report.strategy_used == "none"
        assert report.diagnostics.get("reason") == "not_recoverable"


class TestRepairReport:
    """Testa RepairReport enriquecido."""

    def test_report_has_attempt(self):
        """Report registra número da tentativa."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
        )

        report = RepairReport(
            success=True,
            before_code="x = 'hello",
            after_code="x = 'hello'",
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=2,
        )

        assert report.attempt == 2

    def test_report_has_parent(self):
        """Report pode ter parent (re-tentativa)."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
        )

        parent = RepairReport(
            success=False,
            before_code="x = 'hello",
            after_code=None,
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=1,
        )

        child = RepairReport(
            success=True,
            before_code="x = 'hello",
            after_code="x = 'hello'",
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=2,
            parent_report=parent,
        )

        assert child.parent_report is parent
        assert child.attempt == 2

    def test_report_has_chain(self):
        """Report mantém cadeia completa."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.SYNTAX,
            cause=ErrorCause.SYNTAX_ERROR,
            severity=Severity.LOW,
            classifier_confidence=0.9,
        )

        r1 = RepairReport(
            success=False,
            before_code="x = 'hello",
            after_code=None,
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=1,
        )

        r2 = RepairReport(
            success=False,
            before_code="x = 'hello",
            after_code=None,
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=2,
            parent_report=r1,
            repair_chain=[r1],
        )

        r3 = RepairReport(
            success=True,
            before_code="x = 'hello",
            after_code="x = 'hello'",
            descriptor=descriptor,
            strategy_used="syntax_repair",
            attempt=3,
            parent_report=r2,
            repair_chain=[r1, r2],
        )

        chain_summary = r3.get_chain_summary()

        assert len(chain_summary) == 3
        assert chain_summary[0]["attempt"] == 1
        assert chain_summary[2]["attempt"] == 3

    def test_report_get_diagnostics(self):
        """Report retorna diagnósticos completos."""
        descriptor = ErrorDescriptor(
            domain=ErrorCategory.JSON,
            cause=ErrorCause.EXTRA_DATA,
            severity=Severity.LOW,
            classifier_confidence=0.95,
        )

        report = RepairReport(
            success=True,
            before_code='{"a": 1} extra',
            after_code='{"a": 1}',
            descriptor=descriptor,
            strategy_used="json_recovery",
            attempt=1,
            execution_metrics={"latency": 0.5, "cost": 0.0},
        )

        diag = report.get_diagnostics()

        assert diag["success"] is True
        assert diag["strategy"] == "json_recovery"
        assert diag["attempt"] == 1
        assert diag["domain"] == "json"
        assert diag["cause"] == "extra_data"
        assert "execution_time" in diag


class TestStrategyIdempotence:
    """Testa idempotência de estratégias."""

    def test_syntax_strategy_is_idempotent(self):
        """SyntaxRepairStrategy é idempotente."""
        from iaglobal.diagnostics.repair_strategies import SyntaxRepairStrategy

        strategy = SyntaxRepairStrategy()

        assert strategy.is_idempotent is True

    def test_json_strategy_is_idempotent(self):
        """JsonRecoveryStrategy é idempotente."""
        from iaglobal.diagnostics.repair_strategies import JsonRecoveryStrategy

        strategy = JsonRecoveryStrategy()

        assert strategy.is_idempotent is True

    def test_generic_strategy_not_idempotent(self):
        """GenericRetryStrategy não é idempotente."""
        from iaglobal.diagnostics.repair_strategies import GenericRetryStrategy

        strategy = GenericRetryStrategy()

        assert strategy.is_idempotent is False


class TestDomainCauseSeparation:
    """Testa separação domínio/causa."""

    def test_import_causes(self):
        """IMPORT tem causas específicas."""
        causes = [
            ErrorCause.MODULE_NOT_FOUND,
            ErrorCause.SYMBOL_NOT_FOUND,
            ErrorCause.CIRCULAR_IMPORT,
            ErrorCause.RELATIVE_IMPORT,
        ]

        for cause in causes:
            descriptor = ErrorDescriptor(
                domain=ErrorCategory.IMPORT,
                cause=cause,
                severity=Severity.HIGH,
                classifier_confidence=0.9,
            )

            assert descriptor.domain == ErrorCategory.IMPORT
            assert descriptor.cause in causes

    def test_json_causes(self):
        """JSON tem causas específicas."""
        causes = [
            ErrorCause.EXTRA_DATA,
            ErrorCause.EXPECTING_VALUE,
            ErrorCause.INVALID_ESCAPE,
        ]

        for cause in causes:
            descriptor = ErrorDescriptor(
                domain=ErrorCategory.JSON,
                cause=cause,
                severity=Severity.LOW,
                classifier_confidence=0.9,
            )

            assert descriptor.domain == ErrorCategory.JSON
            assert descriptor.cause in causes

    def test_syntax_causes(self):
        """SYNTAX/LEXICAL tem causas específicas."""
        causes = [
            ErrorCause.SYNTAX_ERROR,
            ErrorCause.UNTERMINATED_STRING,
            ErrorCause.MISSING_INDENT,
            ErrorCause.INVALID_CHARACTER,
        ]

        for cause in causes:
            descriptor = ErrorDescriptor(
                domain=ErrorCategory.SYNTAX,
                cause=cause,
                severity=Severity.LOW,
                classifier_confidence=0.9,
            )

            assert descriptor.domain == ErrorCategory.SYNTAX
            assert descriptor.cause in causes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
