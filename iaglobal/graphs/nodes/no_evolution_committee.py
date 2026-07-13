# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_evolution_committee.py

"""
Evolution committee — avalia resultados de evolução e aprova/rejeita.
Usa EvolutionCommittee do metacognition. Integra com Obsidian/Memory.
"""

import time
import logging
from typing import Dict, Any

from iaglobal.evolution.metacognition.evolution_committee import EvolutionCommittee
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

logger = logging.getLogger(__name__)


async def run_evolution_committee(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    result = await EvolutionCommittee.evaluate(ctx)

    # Persistir para Obsidian (vault)
    try:
        subconscious = SubconsciousAPI()
        task_snippet = str(ctx.get("input", {}).get("task", ""))[:80]
        await subconscious.escrever_curto_prazo(
            f"evolution_committee_{int(time.time())}",
            f"Decisão: {result.get('status')}\n"
            f"Aprovados: {result.get('approved_count')}/{result.get('total')}\n"
            f"Task: {task_snippet}",
            tags=["#evolucao", "#comite", f"#status-{result.get('status')}"],
        )
    except Exception as e:
        logger.debug("Erro ao escrever no Obsidian: %s", e)

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
        },
    }
