import logging
import time
from typing import Any, Dict

from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.cognition.outcome_tracker import outcome_tracker, ExecutionOutcome
from iaglobal.cognition.reputation_engine import reputation_engine
from iaglobal.evolution.same_engine import same_pool, same_inhibitor, COST_CREATE_SKILL, RECHARGE_RATE

logger = logging.getLogger(__name__)


class EvolutionTrigger:
    """Dispara evolução genética baseada nos resultados da metacognição.
    Verifica budget SAMe antes de evoluir — previne explosão de mutações inúteis."""

    @classmethod
    async def trigger(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        evaluator_output = memory.get("evaluator", {}).get("output", {})
        score = evaluator_output.get("score", 0) if isinstance(evaluator_output, dict) else 0
        task = str(ctx.get("input", {}).get("task", ""))

        triggered = False
        reason = ""
        same_used = 0

        if score < 40:
            triggered = True
            reason = f"Score baixo ({score}) — necessário evoluir agentes"
        elif score < 70:
            triggered = True
            reason = f"Score médio ({score}) — evolução preventiva"

        same_used = 0
        if triggered:
            if not same_inhibitor.can_mutate("evolution_trigger", COST_CREATE_SKILL, critical=True):
                triggered = False
                reason = f"SAMe insuficiente — evolução bloqueada (saldo: {same_pool.balance('evolution_trigger')})"
            else:
                same_pool.spend("evolution_trigger", COST_CREATE_SKILL)
                same_used = COST_CREATE_SKILL
                try:
                    graph = ctx.get("graph")
                    if graph is None:
                        from iaglobal.graphs.builder import build_pipeline_from_nodes
                        graph = build_pipeline_from_nodes()
                    engine = EvolutionEngine(graph=graph)
                    await engine.set_task_async(task)
                    await engine.evolve()
                    logger.info("[EVO-TRIGGER] Ciclo evolutivo disparado: %s (SAMe restante: %d)",
                               reason, same_pool.balance("evolution_trigger"))
                    from iaglobal.evolution.metacognition.evaluator import PipelineEvaluator
                    PipelineEvaluator._evolution_count += 1
                    from iaglobal.evolution.meta_evolver import meta_evolver, EvolutionParams
                    before = score or 0.0
                    after = PipelineEvaluator._last_score or before
                    meta_evolver.record_trial(
                        params=EvolutionParams(),
                        improvement=after - before,
                        task_type=task or "general",
                    )
                    cls._record_outcome(ctx, score, True, reason)
                except Exception as e:
                    logger.warning("[EVO-TRIGGER] Falha no ciclo evolutivo: %s", e)
                    cls._record_outcome(ctx, score, False, str(e))
                    triggered = False
                    reason = f"Falha na evolução: {e}"

        if score >= 70:
            same_pool.recharge("evolution_trigger")
            logger.info("[EVO-TRIGGER] SAMe recarregado (+%d) para evolution_trigger", RECHARGE_RATE)

        return {
            "evolution_triggered": triggered,
            "reason": reason,
            "score": score,
            "same_balance": same_pool.balance("evolution_trigger"),
            "same_used": same_used,
            "status": "triggered" if triggered else "skipped",
        }

    @classmethod
    def _record_outcome(cls, ctx: dict, score: int, success: bool, reason: str):
        try:
            outcome_tracker.record(ExecutionOutcome(
                provider="metacognition",
                model="evolution_trigger",
                fingerprint=str(ctx.get("execution_id", ctx.get("input", {}).get("task", "unknown"))),
                latency_ms=0,
                token_cost=0,
                success_score=score / 100.0 if success else 0,
                retries=0,
                timestamp=time.time(),
            ))
            reputation_engine.invalidate_cache()
        except Exception as e:
            logger.debug("[EVO-TRIGGER] Falha ao registrar outcome: %s", e)


async def _run_evolution_trigger(ctx: dict) -> dict:
    return await EvolutionTrigger.trigger(ctx)
