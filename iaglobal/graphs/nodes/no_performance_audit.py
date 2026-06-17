from typing import Dict, Any
import logging

from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent

logger = logging.getLogger(__name__)


async def run_performance_audit(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        logger.warning("[PERF_AUDIT] No code found to audit")
        return {**ctx, "output": {"performance_audit_report": {"total_bottlenecks": 0}}}

    try:
        agent = PerformanceAuditAgent()
        result = agent.audit(code=code, performance_requirements=[])
        logger.info("[PERF_AUDIT] Score=%s", result.get("performance_audit_report", {}).get("risk_score", "N/A"))
        return {**ctx, "output": result}
    except Exception as e:
        logger.exception("[PERF_AUDIT] Failed: %s", e)
        return {**ctx, "output": {"performance_audit_report": {"total_bottlenecks": 0, "risk_score": 0}}}
