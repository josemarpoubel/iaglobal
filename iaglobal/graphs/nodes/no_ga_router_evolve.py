# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_ga_router_evolve.py
"""
no_ga_router_evolve — Nó que executa evolução dos pesos IVM via algoritmo genético.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.evolution.ga_router_optimizer import GARouterOptimizer

logger = logging.getLogger(__name__)


async def run_ga_router_evolve(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa evolução dos pesos IVM.

    Args:
        context: {"generations": int, "population": int}

    Returns:
        {"best_weights": dict, "generations_run": int}
    """
    generations = context.get("generations", 10)

    optimizer = GARouterOptimizer()
    best_weights = optimizer.run_evolution(generations=generations)

    logger.info(f"[GA-EVOLVE] New IVM weights evolved: {best_weights}")

    return {
        "best_weights": best_weights,
        "generations_run": generations,
        "execution_metrics": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ga_evolution": True,
        },
    }
