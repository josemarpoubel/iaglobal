import logging
from typing import Dict, Any
from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)

async def run_compliance_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing compliance_audit handler")
    agent = SecurityAuditAgent()
    code = ctx.get("coder", {}).get("output", "")
    result = agent.audit(code=code, security_requirements=[])
    ctx["compliance_audit"] = result
    return ctx
