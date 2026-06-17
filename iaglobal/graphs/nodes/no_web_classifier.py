import logging
from typing import Dict, Any
from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)

async def run_web_classifier(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing web_classifier handler")
    agent = EnhancementAgent()
    task = ctx.get("task", "")
    intake = ctx.get("intake", {})
    result = agent.enhance(task=task, intake=intake)
    ctx["web_classifier"] = result
    return ctx
