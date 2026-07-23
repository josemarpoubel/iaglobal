# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Tests for pipeline coverage report and ExecutionEventBus integration.
"""

from __future__ import annotations

from iaglobal.graphs.pipeline_coverage import build_coverage_report
from iaglobal.graphs.skip_reason import (
    DEPENDENCY_NOT_MET,
    ALREADY_EXECUTED,
    ABORTED_BY_SANITY,
    REASON_LABELS,
)
from iaglobal.observability.execution_events import (
    get_event_bus,
    emit,
    NODE_STARTED,
    NODE_FINISHED,
)
from iaglobal.observability.execution_report import (
    ExecutionReport,
    init_execution_report,
    get_execution_report,
)


class TestCoverageReport:
    def test_empty_report(self):
        """Coverage report com dados vazios deve ser válido."""
        report = build_coverage_report()
        assert report["summary"]["total_executed"] == 0
        assert report["summary"]["coverage_pct"] == 0.0
        assert "phases" in report
        assert "mermaid" in report

    def test_with_execution_report(self):
        """Coverage reflete nós do execution_report."""
        er = init_execution_report("test-coverage-1")
        try:
            for nid, status in [
                ("coder", "success"),
                ("tester", "failed"),
                ("planner", "success"),
            ]:
                emit(NODE_STARTED, "test-coverage-1", nid)
                emit(
                    NODE_FINISHED, "test-coverage-1", nid, success=(status == "success")
                )
            finished = er.finish()
            report = build_coverage_report(execution_report=finished)

            assert report["summary"]["total_executed"] == 3
            assert report["summary"]["coverage_pct"] > 0
            # Should have phase classification
            assert len(report["phases"]) > 0
        finally:
            # Clean up global state
            import iaglobal.observability.execution_report as _er

            _er._execution_report = None

    def test_with_skip_reasons(self):
        """Skip reasons são refletidos no relatório."""
        skip_reasons = {
            "node_a": DEPENDENCY_NOT_MET,
            "node_b": ALREADY_EXECUTED,
            "node_c": ABORTED_BY_SANITY,
        }
        report = build_coverage_report(skip_reasons=skip_reasons)

        assert report["summary"]["total_executed"] == 0
        assert len(report["skipped_nodes"]) == 3
        assert report["skip_breakdown_raw"][DEPENDENCY_NOT_MET] == 1
        assert report["skip_breakdown_raw"][ALREADY_EXECUTED] == 1
        assert report["skip_breakdown_raw"][ABORTED_BY_SANITY] == 1

    def test_skip_labels(self):
        """Skip reasons têm labels human-readable."""
        assert REASON_LABELS[DEPENDENCY_NOT_MET] == "Dependência pendente"
        assert REASON_LABELS[ALREADY_EXECUTED] == "Já executado (checkpoint)"
        assert REASON_LABELS[ABORTED_BY_SANITY] == "Abortado — Sanity Barrier"

    def test_mermaid_generated(self):
        """Relatório inclui diagrama Mermaid."""
        report = build_coverage_report()
        mermaid = report["mermaid"]
        assert "```mermaid" in mermaid
        assert "gantt" in mermaid
        assert "section" in mermaid

    def test_mermaid_with_executed(self):
        """Nós executados aparecem como 'done' no Mermaid."""
        er = init_execution_report("test-coverage-mermaid")
        try:
            emit(NODE_STARTED, "test-coverage-mermaid", "planner")
            emit(NODE_FINISHED, "test-coverage-mermaid", "planner", success=True)
            finished = er.finish()
            report = build_coverage_report(execution_report=finished)
            mermaid = report["mermaid"]
            assert "planner" in mermaid
            assert "done" in mermaid
        finally:
            import iaglobal.observability.execution_report as _er

            _er._execution_report = None


class TestExecutionEventBusWiring:
    def test_event_bus_singleton(self):
        """get_event_bus retorna o mesmo singleton."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_emit_node_started(self):
        """NODE_STARTED é recebido por subscribers."""
        bus = get_event_bus()
        received = []

        def _handler(event):
            received.append(event)

        bus.subscribe(NODE_STARTED, _handler)
        emit(NODE_STARTED, "exec-1", "coder", strategy="general")
        assert len(received) == 1
        assert received[0].event_type == NODE_STARTED
        assert received[0].execution_id == "exec-1"
        assert received[0].node_id == "coder"

    def test_emit_node_finished(self):
        """NODE_FINISHED carrega métricas de sucesso/latência."""
        bus = get_event_bus()
        received = []

        def _handler(event):
            received.append(event)

        bus.subscribe(NODE_FINISHED, _handler)
        emit(NODE_FINISHED, "exec-2", "tester", success=True, latency=1.5, error=None)
        assert len(received) == 1
        assert received[0].payload.get("success") is True
        assert received[0].payload.get("latency") == 1.5

    def test_execution_report_accumulates_events(self):
        """ExecutionReport acumula NodeRecords de eventos emitidos."""
        er = init_execution_report("exec-report-test")
        try:
            emit(NODE_STARTED, "exec-report-test", "node_a")
            emit(NODE_FINISHED, "exec-report-test", "node_a", success=True, latency=2.0)

            emit(NODE_STARTED, "exec-report-test", "node_b")
            emit(
                NODE_FINISHED, "exec-report-test", "node_b", success=False, error="fail"
            )

            finished = er.finish()
            assert finished["summary"]["total_nodes"] == 2
            assert finished["summary"]["executed"] == 2
            assert finished["summary"]["failures"] == 1

            # Check node records
            nodes_by_id = {n["node"]: n for n in finished["nodes"]}
            assert nodes_by_id["node_a"]["status"] == "success"
            assert nodes_by_id["node_b"]["status"] == "failed"
            assert nodes_by_id["node_b"]["exception"] == "fail"
        finally:
            import iaglobal.observability.execution_report as _er

            _er._execution_report = None
