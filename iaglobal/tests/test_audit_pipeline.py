import json
import time
import pytest
from unittest.mock import MagicMock, patch

from iaglobal.events import (
    DecisionEvent, DecisionLock, resolve_locked_model,
    store, dispatcher, EventType, PipelineStep,
)
from iaglobal.events.replay import DecisionReplaySystem
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.memory.db_manager import db

EXEC_ID = "test-audit-integration"


def setup_module():
    store.start()
    db.delete_execution_events(EXEC_ID)


def teardown_module():
    db.delete_execution_events(EXEC_ID)


# =====================================================================
# 1. DecisionEvent — criação e serialização
# =====================================================================

class TestDecisionEvent:
    def test_criar_evento_minimo(self):
        e = DecisionEvent(step="test_step", execution_id="e1")
        assert e.step == "test_step"
        assert e.execution_id == "e1"
        d = e.to_dict()
        assert d["step"] == "test_step"

    def test_criar_evento_completo(self):
        e = DecisionEvent(
            step="model_selection", execution_id="e1",
            selected="ollama/qwen2.5:0.5b",
            reason="highest_expected_reward",
            scores_snapshot={"ollama/a": 0.8, "gemini/b": 0.7},
            exploration=False,
            latency_ms=10,
            metadata={"source": "bandit_v2"},
        )
        d = e.to_dict()
        assert d["selected"] == "ollama/qwen2.5:0.5b"
        assert d["exploration"] is False
        assert d["scores_snapshot"]["ollama/a"] == 0.8

    def test_round_trip(self):
        original = DecisionEvent(step="lock", execution_id="e1", status="immutable", selected="m1")
        restored = DecisionEvent.from_dict(original.to_dict())
        assert restored.step == original.step
        assert restored.status == original.status
        assert restored.selected == original.selected


# =====================================================================
# 2. DecisionLock — imutabilidade e integração
# =====================================================================

class TestDecisionLock:
    def test_lock_frozen(self):
        lock = DecisionLock(execution_id="e1", selected_model="m1", strategy="fast", score=0.8)
        with pytest.raises(Exception):
            lock.selected_model = "m2"

    def test_lock_para_dict(self):
        lock = DecisionLock("e1", "m1", "fast", 0.8, {"m1": 0.8, "m2": 0.6})
        d = lock.to_dict()
        assert d["selected_model"] == "m1"
        assert d["scores_snapshot"]["m2"] == 0.6

    def test_resolve_locked_model(self):
        lock = DecisionLock("e1", "ollama/x", "fast", 0.8)
        ctx = {"input": {"metadata": {"decision_lock": lock.to_dict()}}}
        assert resolve_locked_model(ctx, "fallback") == "ollama/x"

    def test_resolve_fallback(self):
        assert resolve_locked_model({"input": {"metadata": {}}}, "fallback") == "fallback"
        ctx = {"input": {"metadata": {"model": "ollama/y"}}}
        assert resolve_locked_model(ctx, "fallback") == "ollama/y"


# =====================================================================
# 3. DecisionEventStore — persistência e consulta
# =====================================================================

class TestDecisionEventStore:
    def test_persistir_evento(self):
        from iaglobal.models.event_bus import bus
        de = DecisionEvent(step="memory_lookup", execution_id=EXEC_ID, result="HIT")
        bus.publish(EventType.PIPELINE_STAGE, {
            "decision_event": de.to_dict(), "step": "memory_lookup",
        }, source="test")
        time.sleep(0.05)
        rows = store.query(execution_id=EXEC_ID, step="memory_lookup")
        assert len(rows) >= 1

    def test_persistir_multiplos(self):
        from iaglobal.models.event_bus import bus
        steps = ["candidate_selection", "model_selection", "lock"]
        for s in steps:
            de = DecisionEvent(step=s, execution_id=EXEC_ID, selected="m1" if s != "candidate_selection" else None)
            bus.publish(EventType.PIPELINE_STAGE, {
                "decision_event": de.to_dict(), "step": s,
            }, source="test")
        time.sleep(0.05)
        assert store.count(execution_id=EXEC_ID) >= 4

    def test_consultar_por_step(self):
        locks = store.query(step="lock")
        assert len(locks) >= 1
        assert locks[0]["step"] == "lock"

    def test_consultar_por_execution(self):
        rows = store.replay(EXEC_ID)
        assert len(rows) >= 1
        for r in rows:
            assert r["_parsed"] is not None

    def test_contar(self):
        total = store.count()
        assert total >= 4
        step_count = store.count(step="lock")
        assert step_count >= 1

    def test_stats(self):
        stats = store.stats()
        assert stats["inserted"] >= 4
        assert stats["failed"] == 0


# =====================================================================
# 4. DecisionEventDispatcher — roteamento
# =====================================================================

class TestDecisionEventDispatcher:
    def setup_method(self):
        self.captured = []
        dispatcher.start()

    def test_registrar_handler(self):
        def handler(data):
            self.captured.append(data.get("step"))
        dispatcher.on("lock", handler)
        assert dispatcher.handler_count("lock") >= 1
        dispatcher.off("lock", handler)

    def test_rotear_evento(self):
        from iaglobal.models.event_bus import bus
        received = []
        dispatcher.on("lock", lambda d: received.append(d.get("selected")))
        de = DecisionEvent(step="lock", execution_id="d1", selected="ollama/z")
        bus.publish(EventType.PIPELINE_STAGE, {
            "decision_event": de.to_dict(), "step": "lock",
        }, source="test")
        time.sleep(0.05)
        assert len(received) >= 1
        assert received[-1] == "ollama/z"

    def test_nao_rotear_outro_step(self):
        from iaglobal.models.event_bus import bus
        received = []
        dispatcher.on("execution_metrics", lambda d: received.append(True))
        de = DecisionEvent(step="memory_store", execution_id="d1")
        bus.publish(EventType.PIPELINE_STAGE, {
            "decision_event": de.to_dict(), "step": "memory_store",
        }, source="test")
        time.sleep(0.05)
        assert len(received) == 0


# =====================================================================
# 5. DecisionReplaySystem — análise e replay
# =====================================================================

class TestDecisionReplaySystem:
    def setup_method(self):
        self.replay = DecisionReplaySystem()

    def test_summary(self):
        s = self.replay.summary(EXEC_ID)
        assert s is not None
        assert s["execution_id"] == EXEC_ID
        assert s["events"] >= 4

    def test_what_if(self):
        # Need a model_selection event with scores_snapshot
        from iaglobal.models.event_bus import bus
        de = DecisionEvent(
            step="model_selection", execution_id=EXEC_ID,
            selected="ollama/a",
            scores_snapshot={"ollama/a": 0.8, "gemini/b": 0.7},
            exploration=False,
        )
        bus.publish(EventType.PIPELINE_STAGE, {
            "decision_event": de.to_dict(), "step": "model_selection",
        }, source="test")
        de2 = DecisionEvent(
            step="execution_metrics", execution_id=EXEC_ID,
            reward_signal=0.9, latency_ms=100, metadata={"success": True},
        )
        bus.publish(EventType.PIPELINE_STAGE, {
            "decision_event": de2.to_dict(), "step": "execution_metrics",
        }, source="test")
        time.sleep(0.05)

        w = self.replay.what_if(EXEC_ID, "gemini/b")
        assert w is not None
        assert w["original_model"] == "ollama/a"
        assert w["alternative_model"] == "gemini/b"
        assert w["score_delta"] == -0.1
        assert w["would_be_better"] is False

    def test_train_bandit(self):
        credit = CreditAssignmentEngine()
        r = self.replay.train_bandit(EXEC_ID, credit, node="test_train")
        assert r["trained"] is True
        assert r["model"] is not None
        assert r["new_score"] > 0

    def test_nonexistent(self):
        assert self.replay.summary("nonexistent") is None
        w = self.replay.what_if("nonexistent", "m1")
        assert w is None

    def test_explain_fallback(self):
        result = self.replay.explain(EXEC_ID)
        assert result is not None
        assert "analysis" in result
        assert result["summary"] is not None


# =====================================================================
# 6. PipelineStep — constantes
# =====================================================================

class TestPipelineConstants:
    def test_pipeline_step_values(self):
        assert PipelineStep.TASK_NORMALIZATION == "task_normalization"
        assert PipelineStep.MEMORY_LOOKUP == "memory_lookup"
        assert PipelineStep.CANDIDATE_SELECTION == "candidate_selection"
        assert PipelineStep.MODEL_SELECTION == "model_selection"
        assert PipelineStep.LOCK == "lock"
        assert PipelineStep.EXECUTION_METRICS == "execution_metrics"
        assert PipelineStep.MEMORY_STORE == "memory_store"
        assert PipelineStep.EVOLUTION_CHECK == "evolution_check"
        assert len(PipelineStep.ALL) == 8

    def test_event_type_pipeline_stage(self):
        assert EventType.PIPELINE_STAGE == "pipeline.stage.completed"


# =====================================================================
# 7. CreditAssignmentEngine — bandit básico
# =====================================================================

class TestCreditEngine:
    def test_score_inicial(self):
        credit = CreditAssignmentEngine()
        assert credit.score("n1", "m1", "s1") == 0.5

    def test_record_success(self):
        credit = CreditAssignmentEngine()
        credit.record(ExecutionEvent(node="n1", success=True, latency=1.0, model="m1", strategy="s1"))
        assert credit.score("n1", "m1", "s1") == 1.0

    def test_record_mixed(self):
        credit = CreditAssignmentEngine()
        credit.record(ExecutionEvent(node="n2", success=True, latency=1.0, model="m2", strategy="s2"))
        credit.record(ExecutionEvent(node="n2", success=False, latency=2.0, model="m2", strategy="s2"))
        assert credit.score("n2", "m2", "s2") == 0.5


# =====================================================================
# 8. CLI Renderers — saída formatada
# =====================================================================

class TestCLIRenderers:
    def test_history_renderer(self):
        from iaglobal.cli.output import HistoryRenderer, ReplayRenderer
        from io import StringIO
        import sys

        buf = StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            HistoryRenderer.render_execution([], "empty-id")
            HistoryRenderer.render_stats({"total": 0, "by_step": {}})
            ReplayRenderer.render_summary({
                "execution_id": "test", "events": 3, "model": "m1",
                "cache": "MISS", "task_type": "coding",
                "ambiguity": 0.5, "small_model": True, "reward_signal": 0.9,
                "latency_ms": 100, "exploration": False, "evolution_triggered": False,
            })
            ReplayRenderer.render_explain({"execution_id": "test", "analysis": "test analysis"})
        finally:
            sys.stdout = old
        output = buf.getvalue()
        assert "empty-id" in output
        assert "test analysis" in output


# Run with: python -m pytest iaglobal/tests/test_audit_pipeline.py -v
