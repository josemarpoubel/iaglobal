import logging
from typing import Dict, Any
from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)

async def run_security(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing security handler")
    agent = SecurityAuditAgent()
    code = ctx.get("coder", {}).get("output", "")
    result = agent.audit(code=code, security_requirements=[])
    ctx["security"] = result
    return ctx
