import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

async def run_deployment_plan(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("Executing deployment_plan handler")
    agent = PlannerAgent()
    task = ctx.get("task", "")
    result = await agent.criar_plano_execucao(task)
    ctx["deployment_plan"] = result
    return ctx
