import logging
from typing import Dict, Any
from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)

async def run_gap_analyzer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing gap_analyzer handler")
    agent = ReflexionAgent()
    code = ctx.get("coder", {}).get("output", "")
    task = ctx.get("task", "")
    result = await agent.analisar_resultado(code, {}, task)
    ctx["gap_analyzer"] = {"analysis": result}
    return ctx
