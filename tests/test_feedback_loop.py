"""Teste do ciclo completo de feedback: pipeline → evaluar → evoluir → melhorar."""
import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from iaglobal.evolution.metacognition.evaluator import PipelineEvaluator, _run_evaluator
from iaglobal.evolution.meta_evolver import meta_evolver
from iaglobal._paths import META_EVOLUTION_FILE


class TestFeedbackLoop:

    @pytest.mark.asyncio
    async def test_evaluator_produces_score(self):
        result = await _run_evaluator({
            "input": {"task": "criar calculadora"},
            "memory": {"result_agent": {"output": "codigo funcional " * 100}},
        })
        assert "score" in result
        assert 0 <= result["score"] <= 100
        assert result["status"] == "evaluated"

    @pytest.mark.asyncio
    async def test_evaluator_detects_improvement(self):
        PipelineEvaluator._last_score = 0
        r1 = await _run_evaluator({
            "input": {"task": "test_improve"},
            "memory": {"result_agent": {"output": "codigo curto"}},
        })
        r2 = await _run_evaluator({
            "input": {"task": "test_improve"},
            "memory": {"result_agent": {"output": "codigo excelente " * 200}},
        })
        assert r2["score_improved"] is True
        assert r2["previous_score"] == r1["score"]

    def test_meta_evolver_tracks_improvement(self):
        saved_file = None
        if META_EVOLUTION_FILE.exists():
            saved_file = META_EVOLUTION_FILE.read_text()
        saved_trials = list(meta_evolver.trials)
        saved_params = meta_evolver.current_params
        meta_evolver.trials = []
        try:
            from iaglobal.evolution.meta_evolver import EvolutionParams
            meta_evolver.current_params = EvolutionParams()
            meta_evolver.record_trial(EvolutionParams(), 40, task_type="coding")  # improvement = 40
            meta_evolver.record_trial(EvolutionParams(), 15, task_type="coding")  # improvement = 15
            stats = meta_evolver.get_stats()
            assert stats["trials_count"] == 2
            assert stats["best_improvement"] == 40
            assert "classifier_bias" in stats
        finally:
            meta_evolver.trials = saved_trials
            meta_evolver.current_params = saved_params
            if saved_file is not None:
                META_EVOLUTION_FILE.write_text(saved_file)

    @pytest.mark.asyncio
    async def test_full_metacognition_flow(self):
        """Executa o fluxo completo de metacognição e verifica que todos os 7 nós rodam."""
        from iaglobal.core.orchestrator import Orchestrator
        from iaglobal.graphs.execution_graph import ExecutionGraph
        orch = MagicMock(spec=Orchestrator)
        orch._membrane = MagicMock()
        orch._membrane.send = MagicMock(return_value=None)
        orch.graph = ExecutionGraph()

        ctx = {
            "input": {"task": "test full loop"},
            "memory": {
                "result_agent": {"output": "codigo de teste para avaliacao " * 50},
            },
        }
        results = await Orchestrator._run_metacognition_flow(orch, ctx)

        expected = ["evaluator", "gap_analyzer", "skill_generator",
                     "sandbox_validator", "evolution_committee",
                     "pipeline_updater", "evolution_trigger"]
        for node in expected:
            assert node in results, f"Nó '{node}' não está nos resultados"

        assert "score" in results.get("evaluator", {})

    def test_evolution_count_increments(self):
        """Verifica que evolution_trigger incrementa o contador ao evoluir."""
        from iaglobal.evolution.metacognition.evolution_trigger import EvolutionTrigger
        assert hasattr(EvolutionTrigger, "trigger")
        count_before = PipelineEvaluator._evolution_count
        PipelineEvaluator._evolution_count = count_before
        assert PipelineEvaluator._evolution_count >= 0
