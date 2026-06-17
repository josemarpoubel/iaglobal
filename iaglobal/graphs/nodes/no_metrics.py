import logging
from typing import Dict, Any
from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent

logger = logging.getLogger(__name__)

async def run_metrics(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing metrics handler")
    agent = PerformanceAuditAgent()
    code = ctx.get("coder", {}).get("output", "")
    result = agent.audit(code=code, performance_requirements=[])
    ctx["metrics"] = result
    return ctx
