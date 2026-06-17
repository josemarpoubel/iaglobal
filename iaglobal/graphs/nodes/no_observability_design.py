import logging
from typing import Dict, Any
from iaglobal.agents.performance_design_agent import PerformanceDesignAgent

logger = logging.getLogger(__name__)

async def run_observability_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing observability_design handler")
    agent = PerformanceDesignAgent()
    design_context = ctx.get("design_context", ctx)
    result = agent.analyze(design_context=design_context)
    ctx["observability_design"] = result
    return ctx
