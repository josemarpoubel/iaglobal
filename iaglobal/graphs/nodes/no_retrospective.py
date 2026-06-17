import logging
from typing import Dict, Any
from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)

async def run_retrospective(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing retrospective handler")
    agent = ReflexionAgent()
    code = ctx.get("coder", {}).get("output", "")
    task = ctx.get("task", "")
    result = await agent.analisar_resultado(code, {}, task)
    ctx["retrospective"] = {"analysis": result}
    return ctx
