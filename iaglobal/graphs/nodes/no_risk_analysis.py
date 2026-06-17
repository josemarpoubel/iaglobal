import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

async def run_risk_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("Executing risk_analysis handler")
    agent = PlannerAgent()
    task = ctx.get("task", "")
    result = await agent.criar_plano_execucao(task)
    ctx["risk_analysis"] = result
    return ctx
