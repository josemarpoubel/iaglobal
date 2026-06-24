# iaglobal/graphs/nodes/no_evolution_committee.py

"""
Evolution committee — avalia resultados de evolução e aprova/rejeita.
Usa EvolutionCommittee do metacognition.
"""
import time
import logging
from typing import Dict, Any

from iaglobal.evolution.metacognition.evolution_committee import EvolutionCommittee

logger = logging.getLogger(__name__)


async def run_evolution_committee(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    result = await EvolutionCommittee.evaluate(ctx)
    status = result.get("status", "rejected")
    score = result.get("approved_count", 0) / max(result.get("total", 1), 1)
    logger.info("[EVOLUTION_COMMITTEE] Status: %s (%.0f%%)", status, score * 100)
    latency_ms = (time.time() - start_time) * 1000.0
    return {
        "output": result,
        "evolution_committee": result,
        "execution_metrics": {
            "model": "evolution_committee",
            "success": "status" in result,
            "latency": latency_ms,
            "cost": ctx.get("estimated_cost", 0.01),
        }
    }

