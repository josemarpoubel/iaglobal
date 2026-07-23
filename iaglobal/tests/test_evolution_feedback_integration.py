# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Integration test: SemaphoreTracker → ExecutionReport → Hook → Bandit weight change.

Proves the full adaptive loop end-to-end:
  fake pipeline execution
    → SemaphoreTracker records contention
    → ExecutionReport.finish() embeds timeline
    → EvolutionFeedbackHook.apply() penalizes slow providers
    → Bandit weights reflect the penalty
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from iaglobal.observability.semaphore_tracker import get_semaphore_tracker
from iaglobal.observability.execution_report import init_execution_report
from iaglobal.observability.execution_events import emit, NODE_STARTED, NODE_FINISHED
from iaglobal.evolution.evolution_feedback_hook import (
    EvolutionFeedbackHook,
    EvolutionSignal,
)


class TestEvolutionFeedbackIntegration:
    def test_full_loop_weight_change(self):
        """
        Simula uma execução inteira:
        1. SemaphoreTracker recebe timeout_rate alto
        2. ExecutionReport gera relatório com timeline
        3. Hook lê semaphore_health e penaliza Bandit
        """
        # ── 1. Setup: limpa estado global do semaphore tracker ──
        st = get_semaphore_tracker()
        st._models.clear()

        # ── 2. Simula contenção no semáforo ──
        st.record_acquire_start(
            "ollama/qwen2.5:0.5b", "critic", execution_id="integ-test-1"
        )
        st.record_timeout(
            "ollama/qwen2.5:0.5b", "critic", 1200.0, execution_id="integ-test-1"
        )

        st.record_acquire_start(
            "ollama/qwen2.5:0.5b", "critic", execution_id="integ-test-1"
        )
        st.record_timeout(
            "ollama/qwen2.5:0.5b", "critic", 1050.0, execution_id="integ-test-1"
        )

        st.record_acquire_start(
            "groq/llama-3.1-8b", "critic", execution_id="integ-test-1"
        )
        st.record_acquired(
            "groq/llama-3.1-8b", "critic", 5.0, execution_id="integ-test-1"
        )
        st.record_released("groq/llama-3.1-8b", "critic", execution_id="integ-test-1")

        # ── 3. ExecutionReport coleta eventos de nó ──
        er = init_execution_report("integ-test-1")
        emit(NODE_STARTED, "integ-test-1", "planner")
        emit(NODE_FINISHED, "integ-test-1", "planner", success=True, latency=0.3)
        emit(NODE_STARTED, "integ-test-1", "critic")
        emit(NODE_FINISHED, "integ-test-1", "critic", success=True, latency=1.2)

        finished = er.finish()

        # Verifica que o relatório tem timeline + mermaid
        assert "timeline_text" in finished
        assert "mermaid_dag" in finished
        assert "ollama/qwen" in finished["timeline_text"]
        assert "groq/llama" in finished["timeline_text"]

        # ── 4. Hook lê semaphore_health e ajusta Bandit ──
        class MockBandit:
            def __init__(self):
                self.weights = {
                    "ollama/qwen2.5:0.5b": 1.0,
                    "groq/llama-3.1-8b": 1.0,
                }

        bandit = MockBandit()
        hook = EvolutionFeedbackHook(
            persist_path=Path("/tmp/test_bandit_feedback.jsonl")
        )

        health = st.health_report()
        assert "ollama/qwen2.5:0.5b" in health
        assert health["ollama/qwen2.5:0.5b"]["timeouts"] == 2
        assert health["ollama/qwen2.5:0.5b"]["timeout_rate"] == 1.0

        signal = EvolutionSignal(
            provider="ollama",
            model="ollama/qwen2.5:0.5b",
            semaphore_health=health,
        )
        asyncio.run(hook.apply(bandit, signal, execution_id="integ-test-1"))

        # ollama deve ser penalizado
        assert bandit.weights["ollama/qwen2.5:0.5b"] < 1.0, (
            f"Esperava penalidade, mas weight={bandit.weights['ollama/qwen2.5:0.5b']}"
        )
        # groq deve permanecer
        assert bandit.weights["groq/llama-3.1-8b"] == 1.0

        # ── 5. Verifica persistência ──
        assert len(hook.feedback_history) == 1
        entry = hook.feedback_history[0]
        assert entry["model"] == "ollama/qwen2.5:0.5b"
        assert entry["execution_id"] == "integ-test-1"
        assert entry["penalty"] < 0
        assert any("timeout_rate" in r for r in entry["reasons"])

        # ── 6. Hook carrega histórico do disco ──
        hook2 = EvolutionFeedbackHook(
            persist_path=Path("/tmp/test_bandit_feedback.jsonl")
        )
        assert len(hook2.feedback_history) == 1
        assert hook2.feedback_history[0]["model"] == "ollama/qwen2.5:0.5b"

        # ── 7. Verifica que o report JSON é válido ──
        assert json.dumps(finished)  # serializável

        # Cleanup
        Path("/tmp/test_bandit_feedback.jsonl").unlink(missing_ok=True)

    def test_no_contention_no_penalty(self):
        """Sem contenção, o hook não altera pesos."""
        st = get_semaphore_tracker()
        st._models.clear()

        st.record_acquire_start("groq/llama", "critic", execution_id="integ-test-2")
        st.record_acquired("groq/llama", "critic", 3.0, execution_id="integ-test-2")
        st.record_released("groq/llama", "critic", execution_id="integ-test-2")

        class MockBandit:
            def __init__(self):
                self.weights = {"groq/llama": 2.0}

        bandit = MockBandit()
        hook = EvolutionFeedbackHook(persist_path=Path("/tmp/test_bandit_noop.jsonl"))

        signal_noop = EvolutionSignal(
            provider="groq",
            model="groq/llama",
            semaphore_health=st.health_report(),
        )
        asyncio.run(hook.apply(bandit, signal_noop, execution_id="integ-test-2"))

        assert bandit.weights["groq/llama"] == 2.0  # unchanged
        assert len(hook.feedback_history) == 0  # no adjustments persisted

        # Cleanup
        Path("/tmp/test_bandit_noop.jsonl").unlink(missing_ok=True)

    def test_timeline_in_execution_report_contains_semaphore_data(self):
        """timeline_text dentro do ExecutionReport inclui Semaphore Health."""
        st = get_semaphore_tracker()
        st._models.clear()

        st.record_acquire_start("ollama/glm4", "judge", execution_id="integ-test-3")
        st.record_gate_rejected("ollama/glm4", "judge", execution_id="integ-test-3")

        er = init_execution_report("integ-test-3")
        emit(NODE_STARTED, "integ-test-3", "judge")
        emit(NODE_FINISHED, "integ-test-3", "judge", success=True, latency=0.1)

        report = er.finish()

        assert "Semaphore Health" in report.get("timeline_text", "")
        assert "ollama/glm4" in report.get("timeline_text", "")

    def test_apply_is_async(self):
        """Contrato: EvolutionFeedbackHook.apply() é async function."""
        import inspect

        assert inspect.iscoroutinefunction(EvolutionFeedbackHook.apply)
