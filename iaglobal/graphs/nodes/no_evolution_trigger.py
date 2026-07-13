# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_evolution_trigger.py

"""
Evolution Trigger Node — Decide se as métricas justificam disparar uma autoevolução.
Usa o metacognition EvolutionTrigger (não o legado EvolutionTriggerAgent).
"""

import time
import logging
from typing import Dict, Any

from iaglobal.evolution.metacognition.evolution_trigger import EvolutionTrigger

logger = logging.getLogger(__name__)


def _extract_metrics(memory: Dict[str, Any]) -> Dict[str, Any]:
    raw_metrics = (
        memory.get("metrics", {}) if isinstance(memory.get("metrics", {}), dict) else {}
    )
    raw_output = (
        raw_metrics.get("output", {})
        if isinstance(raw_metrics.get("output", {}), dict)
        else {}
    )

    evaluator_out = memory.get("evaluator", {}).get("output", {})
    if not isinstance(evaluator_out, dict):
        evaluator_out = {}
    evaluator_score = (
        evaluator_out.get("score", 0) if isinstance(evaluator_out, dict) else 0
    )

    scores = [float(evaluator_score)] if evaluator_score else []
    for node_result in memory.values():
        if not isinstance(node_result, dict):
            continue
        output = node_result.get("output")
        if isinstance(output, dict):
            for key in ("score", "avg_score", "validation_score", "quality_score"):
                value = output.get(key)
                if isinstance(value, (int, float)):
                    scores.append(float(value))
                    break

    avg_score = sum(scores) / len(scores) if scores else 0.0
    evolution_count = evaluator_out.get("evolution_count", 0)
    if not evolution_count and isinstance(raw_output, dict):
        evolution_count = raw_output.get("generations", 0)

    return {
        "avg_score": avg_score,
        "scores": scores,
        "generations": evolution_count,
    }


async def run_evolution_trigger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avalia a necessidade de mutação do pipeline de forma assíncrona e não-bloqueante.
    Mapeia a decisão, latência e custo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "evolution_trigger_agent_llm"

    memory = ctx.get("memory", {})

    logger.info(
        "[EVOLUTION_TRIGGER] Analisando telemetria acumulada para tomada de decisão evolutiva..."
    )

    try:
        # Usa o metacognition EvolutionTrigger (substitui o legado EvolutionTriggerAgent)
        evolution_trigger_ctx = dict(ctx)
        evolution_trigger_ctx["memory"] = memory
        evolution_trigger_ctx["metrics"] = _extract_metrics(memory)
        result = await EvolutionTrigger.trigger(evolution_trigger_ctx)

        should_evolve = result.get("evolution_triggered", False)
        reason = result.get("reason", "unknown")
        evolution_result = result.get("evolution", {})
        score = result.get("score", 0)

        if should_evolve:
            logger.info(
                "[EVOLUTION_TRIGGER] Ciclo evolutivo disparado: score=%s | motivo=%s",
                score,
                reason,
            )
        else:
            logger.info(
                "[EVOLUTION_TRIGGER] Evolução não disparada: score=%s | motivo=%s",
                score,
                reason,
            )

        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "output": result,
            "evolution_trigger": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.002),
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[EVOLUTION_TRIGGER] Falha crítica no pipeline do Evolution Trigger Node: %s",
            e,
        )

        return {
            "output": {
                "should_evolve": False,
                "reason": f"Trigger agent failure: {str(e)}",
            },
            "evolution_trigger": {"should_evolve": False, "reason": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
