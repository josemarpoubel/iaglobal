import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

async def run_task_breakdown(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("Executing task_breakdown handler")
    agent = PlannerAgent()
    task = ctx.get("task", "")
    result = await agent.criar_plano_execucao(task)
    ctx["task_breakdown"] = result
    return ctx
