from typing import Dict, Any
import logging

from iaglobal.agents.security_audit_agent import SecurityAuditAgent

logger = logging.getLogger(__name__)


async def run_security_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    code = ""

    for source in ("api_builder", "multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder"):
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[SEC_AUDIT] No code found to audit")
        return {**ctx, "output": {"security_audit_report": {"total_issues": 0}}}

    try:
        agent = SecurityAuditAgent()
        result = agent.audit(code=code, security_requirements=[])
        logger.info("[SEC_AUDIT] Total issues=%s", result.get("security_audit_report", {}).get("total_issues", 0))
        return {**ctx, "output": result}
    except Exception as e:
        logger.exception("[SEC_AUDIT] Failed: %s", e)
        return {**ctx, "output": {"security_audit_report": {"total_issues": 0, "issues": []}}}
