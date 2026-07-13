# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_pipeline_updater.py

"""
Pipeline updater — gera mudanças sugeridas para o pipeline com base em evolução.
Usa PipelineUpdater do metacognition.
"""

import time
import logging
from typing import Dict, Any

from iaglobal.evolution.metacognition.pipeline_updater import PipelineUpdater

logger = logging.getLogger(__name__)


async def run_pipeline_updater(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    result = await PipelineUpdater.update(ctx)
    updates = result.get("updates", [])
    logger.info("[PIPELINE_UPDATER] %d mudanças sugeridas", len(updates))
    latency_ms = (time.time() - start_time) * 1000.0
    return {
        "output": updates,
        "pipeline_updates": updates,
        "execution_metrics": {
            "model": "pipeline_updater",
            "success": True,
            "latency": latency_ms,
            "cost": ctx.get("estimated_cost", 0.005),
        },
    }
