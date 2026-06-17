"""Evolution Methylation Cycle — Valida e promove skills candidatas a production."""
from typing import Dict, Any
import logging

from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
from iaglobal.evolution.metabolism.homocysteine_pool import homocysteine_pool, CandidateSkill

logger = logging.getLogger(__name__)
_methylation = MethylationCycle()


async def run_evolution_methylation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Obtém skills candidatas do pool
    candidates = homocysteine_pool.get_candidates_for_methylation()

    if not candidates:
        logger.info("[EVOLUTION_METHYLATION] Nenhuma skill candidata para avaliar")
        return {**ctx, "output": "Nenhuma skill candidata", "evolution_methylation": {"promoted": 0}}

    promoted = 0
    for candidate in candidates:
        if _methylation.run(candidate):
            promoted += 1

    logger.info("[EVOLUTION_METHYLATION] %d skills promovidas a production", promoted)

    return {
        **ctx,
        "output": f"{promoted} skills promovidas a production",
        "evolution_methylation": {
            "total_candidates": len(candidates),
            "promoted": promoted,
        },
    }