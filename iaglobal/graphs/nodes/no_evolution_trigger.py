"""Evolution trigger — decide se o pipeline deve evoluir."""
from typing import Dict, Any
import logging

from iaglobal.agents.evolution_agent import EvolutionTriggerAgent

logger = logging.getLogger(__name__)


async def run_evolution_trigger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    trigger_context = {
        "metrics": memory.get("metrics", {}),
    }
    agent = EvolutionTriggerAgent()
    result = agent.should_evolve(trigger_context)
    logger.info("[EVOLUTION_TRIGGER] should_evolve=%s reason=%s",
                result["should_evolve"], result["reason"])
    return {**ctx, "output": result, "evolution_trigger": result}
