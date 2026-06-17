import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

async def run_technology_selection(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("Executing technology_selection handler")
    agent = PlannerAgent()
    task = ctx.get("task", "")
    result = await agent.criar_plano_execucao(task)
    ctx["technology_selection"] = result
    return ctx
