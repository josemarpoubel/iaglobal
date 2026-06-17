"""Evolution Homocysteine Pool — Pool de skills candidatas aguardando validação."""
from typing import Dict, Any
import logging

from iaglobal.evolution.metabolism.homocysteine_pool import homocysteine_pool

logger = logging.getLogger(__name__)


async def run_evolution_homocysteine(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Mostra estatísticas do pool
    all_candidates = homocysteine_pool.candidates
    pending = homocysteine_pool.get_pending()
    production_ready = homocysteine_pool.get_ready_for_methylation()

    stats = {
        "total_candidates": len(all_candidates),
        "pending_review": len(pending),
        "ready_for_methylation": len(production_ready),
    }

    logger.info("[EVOLUTION_HOMOCYSTEINE] Pool: %d total, %d pendentes, %d prontos para metilação",
                stats["total_candidates"], stats["pending_review"], stats["ready_for_methylation"])

    # Retorna lista de candidatos para inspeção
    candidates_info = [c.to_dict() for c in all_candidates[:10]]

    return {
        **ctx,
        "output": f"Pool: {stats['total_candidates']} candidatas, {stats['ready_for_methylation']} prontas",
        "evolution_homocysteine": {
            "stats": stats,
            "candidates": candidates_info,
        },
    }