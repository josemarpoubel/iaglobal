"""Pipeline updater — gera mudancas sugeridas para o pipeline com base em evolução."""
from typing import Dict, Any
import logging

from iaglobal.agents.evolution_agent import PipelineUpdaterAgent

logger = logging.getLogger(__name__)


async def run_pipeline_updater(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    update_context = {
        "evolution_result": memory.get("evolution_committee", {}),
    }
    agent = PipelineUpdaterAgent()
    changes = agent.update(update_context)
    logger.info("[PIPELINE_UPDATER] %d mudancas sugeridas", len(changes))
    return {**ctx, "output": changes, "pipeline_updates": changes}
