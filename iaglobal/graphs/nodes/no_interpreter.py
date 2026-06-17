import logging
from typing import Dict, Any
from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)

async def run_interpreter(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing interpreter handler")
    agent = EnhancementAgent()
    task = ctx.get("task", "")
    intake = ctx.get("intake", {})
    result = agent.enhance(task=task, intake=intake)
    ctx["interpreter"] = result
    return ctx
