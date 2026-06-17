import logging
from typing import Dict, Any
from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)

async def run_domain_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing domain_analysis handler")
    agent = EnhancementAgent()
    task = ctx.get("task", "")
    intake = ctx.get("intake", {})
    result = agent.enhance(task=task, intake=intake)
    ctx["domain_analysis"] = result
    return ctx
