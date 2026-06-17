import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

async def run_business_rules(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("Executing business_rules handler")
    agent = PlannerAgent()
    task = ctx.get("task", "")
    result = await agent.criar_plano_execucao(task)
    ctx["business_rules"] = result
    return ctx
