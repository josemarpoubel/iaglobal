import logging
from typing import Dict, Any
from iaglobal.agents.security_design_agent import SecurityDesignAgent

logger = logging.getLogger(__name__)

async def run_threat_modeling(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing threat_modeling handler")
    agent = SecurityDesignAgent()
    design_context = ctx.get("design_context", ctx)
    result = agent.analyze(design_context=design_context)
    ctx["threat_modeling"] = result
    return ctx
