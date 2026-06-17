from typing import Dict, Any
import logging

from iaglobal.agents.performance_design_agent import PerformanceDesignAgent

logger = logging.getLogger(__name__)


async def run_performance_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))

    design_context = {
        "architecture": memory.get("architect", {}).get("output", {}),
        "requirements": memory.get("requirements", {}).get("output", {}),
        "system_design": memory.get("system_design", {}).get("output"),
        "api_design": memory.get("api_design", {}).get("output"),
        "database_design": memory.get("database_design", {}).get("output"),
        "dependency_analysis": memory.get("dependency", {}).get("output"),
    }

    try:
        agent = PerformanceDesignAgent()
        result = agent.analyze(design_context=design_context, knowledge_context="", error_context="")
        logger.info("[PERF_DESIGN] Score=%s", result.get("score", "N/A"))
        return {**ctx, "output": result}
    except Exception as e:
        logger.exception("[PERF_DESIGN] Failed: %s", e)
        return {**ctx, "output": {"performance_design_report": {}, "score": 0}}
