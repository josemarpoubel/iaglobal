from typing import Dict, Any
import logging

from iaglobal.agents.security_design_agent import SecurityDesignAgent

logger = logging.getLogger(__name__)


async def run_security_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    requirements = ctx.get("requirements") or {}
    architecture = ctx.get("architecture") or {}
    knowledge_context = str(ctx.get("knowledge_context", ""))
    error_context = str(ctx.get("error_context", ""))

    design_context = {
        "architecture": architecture,
        "requirements": requirements,
    }

    agent = SecurityDesignAgent()
    result = agent.analyze(
        design_context=design_context,
        knowledge_context=knowledge_context,
        error_context=error_context,
    )

    security_design_report = result.get("security_design_report", {})
    security_requirements = result.get("security_requirements", [])

    logger.info(
        "[SECURITY_DESIGN] Controles de seguranca: %d issues encontradas",
        security_design_report.get("total_issues", 0),
    )

    return {
        **ctx,
        "security_design": security_design_report,
        "output": security_design_report,
        "security_requirements": security_requirements,
    }
