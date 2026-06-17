"""Evolution committee — avalia resultados de evolução e aprova/rejeita."""
from typing import Dict, Any
import logging

from iaglobal.agents.evolution_agent import EvolutionCommitteeAgent

logger = logging.getLogger(__name__)


async def run_evolution_committee(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    evolution_context = {
        "evolution_report": memory.get("skill_generator", {}),
        "metrics": memory.get("metrics", {}),
    }
    agent = EvolutionCommitteeAgent()
    result = agent.evaluate(evolution_context)
    logger.info("[EVOLUTION_COMMITTEE] Verdict: %s (score=%.1f)",
                result["committee_verdict"], result["score"])
    return {**ctx, "output": result, "evolution_committee": result}
