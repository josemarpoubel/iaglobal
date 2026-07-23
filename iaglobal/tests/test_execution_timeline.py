# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Tests for execution timeline, colored Mermaid DAG, and Obsidian export.
"""

from __future__ import annotations

from iaglobal.observability.execution_timeline import (
    build_execution_timeline,
    export_to_obsidian,
    NODE_COLORS,
)
from iaglobal.observability.semaphore_tracker import (
    SemaphoreTracker,
    get_semaphore_tracker,
)


class TestSemaphoreTracker:
    def test_empty_tracker(self):
        t = SemaphoreTracker()
        h = t.health_report()
        assert h == {}

    def test_acquire_release_cycle(self):
        t = SemaphoreTracker()
        t.record_acquire_start("groq/llama", "critic")
        t.record_acquired("groq/llama", "critic", 15.2)
        t.record_released("groq/llama", "critic")

        mm = t.get_metrics("groq/llama")
        assert mm.acquires == 1
        assert mm.releases == 1
        assert mm.timeouts == 0
        assert mm.avg_wait_ms == 15.2
        assert mm.leak_ratio == 0.0

    def test_timeout_tracking(self):
        t = SemaphoreTracker()
        t.record_acquire_start("ollama/qwen", "coder")
        t.record_timeout("ollama/qwen", "coder", 1000.0)

        mm = t.get_metrics("ollama/qwen")
        assert mm.timeouts == 1
        assert mm.timeout_rate == 1.0

    def test_gate_rejection(self):
        t = SemaphoreTracker()
        t.record_acquire_start("ollama/glm4", "judge")
        t.record_gate_rejected("ollama/glm4", "judge")

        mm = t.get_metrics("ollama/glm4")
        assert mm.gate_rejections == 1

    def test_starvation(self):
        t = SemaphoreTracker()
        t.record_starvation("debugger", ["ollama/a", "ollama/b"], 3)
        h = t.health_report()
        assert "ollama/a" in h
        assert "ollama/b" in h

    def test_singleton(self):
        t1 = get_semaphore_tracker()
        t2 = get_semaphore_tracker()
        assert t1 is t2

    def test_health_report_format(self):
        t = SemaphoreTracker()
        t.record_acquire_start("groq/llama", "critic")
        t.record_acquired("groq/llama", "critic", 10.0)
        t.record_released("groq/llama", "critic")
        t.record_timeout("ollama/qwen", "coder", 2000.0)

        h = t.health_report()
        assert "groq/llama" in h
        assert "ollama/qwen" in h
        entry = h["groq/llama"]
        assert "acquires" in entry
        assert "releases" in entry
        assert "timeouts" in entry
        assert "avg_wait_ms" in entry
        assert "leak_ratio" in entry
        assert "timeout_rate" in entry


class TestExecutionTimeline:
    def test_empty_timeline(self):
        result = build_execution_timeline()
        assert "timeline_text" in result
        assert "mermaid_dag" in result
        assert "consolidated_metrics" in result
        assert result["consolidated_metrics"]["success"] == 0

    def test_timeline_from_execution_report(self):
        execution_report = {
            "nodes": [
                {
                    "node": "coder",
                    "status": "success",
                    "latency_ms": 1500.0,
                    "start_time": "2026-07-21T10:00:00",
                    "end_time": "2026-07-21T10:00:01",
                    "provider": "ollama",
                    "model": "qwen2.5",
                },
                {
                    "node": "planner",
                    "status": "success",
                    "latency_ms": 500.0,
                    "start_time": "2026-07-21T10:00:00",
                    "end_time": "2026-07-21T10:00:00",
                    "provider": "ollama",
                    "model": "qwen2.5",
                },
            ]
        }
        result = build_execution_timeline(
            execution_report=execution_report,
            total_nodes=2,
            pipeline_duration_ms=2000.0,
        )
        assert result["consolidated_metrics"]["success"] == 2
        assert "coder" in result["timeline_text"]
        assert "planner" in result["timeline_text"]

    def test_mermaid_contains_executed_nodes(self):
        execution_report = {
            "nodes": [
                {
                    "node": "coder",
                    "status": "success",
                    "latency_ms": 100.0,
                    "start_time": "2026-07-21T10:00:00",
                    "end_time": "2026-07-21T10:00:00",
                }
            ]
        }
        result = build_execution_timeline(execution_report=execution_report)
        dag = result["mermaid_dag"]
        assert "coder" in dag
        assert "success" in dag
        assert "flowchart TD" in dag

    def test_mermaid_color_classes(self):
        result = build_execution_timeline()
        dag = result["mermaid_dag"]
        assert "classDef success" in dag
        assert "classDef failed" in dag
        assert "classDef skipped" in dag
        assert "classDef aborted" in dag
        assert "classDef timeout" in dag
        assert "classDef pending" in dag

    def test_skip_reasons_in_timeline(self):
        execution_report = {
            "nodes": [
                {
                    "node": "coder",
                    "status": "success",
                    "latency_ms": 100.0,
                    "start_time": "2026-07-21T10:00:00",
                    "end_time": "2026-07-21T10:00:00",
                }
            ]
        }
        skip_reasons = {
            "dep_node": "dependency_not_met",
            "abort_node": "aborted_by_sanity_barrier",
        }
        result = build_execution_timeline(
            execution_report=execution_report,
            skip_reasons=skip_reasons,
        )
        timeline = result["timeline_text"]
        assert "Dependência pendente" in timeline or "dependency_not_met" in timeline

    def test_semaphore_health_in_timeline(self):
        semaphore_health = {
            "groq/llama": {
                "acquires": 1,
                "releases": 1,
                "timeouts": 0,
                "gate_rejections": 0,
                "avg_wait_ms": 12.5,
                "max_wait_ms": 12.5,
                "timeout_rate": 0.0,
                "leak_ratio": 0.0,
            }
        }
        result = build_execution_timeline(semaphore_health=semaphore_health)
        timeline = result["timeline_text"]
        assert "Semaphore Health" in timeline
        assert "groq/llama" in timeline
        assert "12.5ms" in timeline

    def test_consolidated_metrics_format(self):
        semaphore_health = {
            "ollama/qwen": {
                "acquires": 5,
                "releases": 5,
                "timeouts": 1,
                "gate_rejections": 2,
                "avg_wait_ms": 200.0,
                "max_wait_ms": 500.0,
                "timeout_rate": 0.1667,
                "leak_ratio": 0.0,
            }
        }
        result = build_execution_timeline(semaphore_health=semaphore_health)
        cm = result["consolidated_metrics"]
        assert "semaphore_health" in cm
        assert cm["semaphore_health"]["ollama/qwen"]["timeouts"] == 1

    def test_export_to_obsidian(self, tmp_path):
        from iaglobal.observability.execution_timeline import build_execution_timeline

        result = build_execution_timeline()
        paths = export_to_obsidian(result, "test-exec-1", vault_path=tmp_path)
        assert "timeline" in paths
        assert "mermaid" in paths
        assert "metrics" in paths
        assert paths["timeline"].exists()
        assert paths["mermaid"].exists()
        assert paths["metrics"].exists()
        assert paths["timeline"].suffix == ".md"
        assert paths["mermaid"].suffix == ".mmd"
        assert paths["metrics"].suffix == ".json"

    def test_node_colors_defined(self):
        assert "success" in NODE_COLORS
        assert "failed" in NODE_COLORS
        assert "aborted" in NODE_COLORS
        assert "timeout" in NODE_COLORS
        assert "dependency_not_met" in NODE_COLORS
