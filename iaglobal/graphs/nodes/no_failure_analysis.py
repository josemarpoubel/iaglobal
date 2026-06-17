from typing import Dict, Any
import logging

from iaglobal.agents.failure_analysis_agent import FailureAnalysisAgent

logger = logging.getLogger(__name__)


async def run_failure_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    debugger_data = memory.get("debugger") or {}
    error_log = (
        (memory.get("code_executor") or {}).get("error", "")
        or (debugger_data.get("debug_result") or {}).get("error", "")
    )

    try:
        system_data = FailureAnalysisAgent.collect_system_data()
        report = FailureAnalysisAgent.generate_report(system_data)
        logger.info("[FAILURE_ANALYSIS] Dados coletados: %d erros, %d chamadas de provedores",
                     system_data.get("errors", {}).get("total", 0),
                     system_data.get("metrics", {}).get("total_calls", 0))

        result = {"error_type": "none", "findings": [], "suggestion_count": 0}
        if error_log:
            result = FailureAnalysisAgent.analyze(error_log=error_log, prompt=task_str)
            logger.info("[FAILURE_ANALYSIS] Error type=%s suggestions=%d",
                         result.get("error_type"), result.get("suggestion_count", 0))

        paths = FailureAnalysisAgent.persist_report(system_data, report)
        if "report_path" in paths:
            result["report_path"] = paths["report_path"]
            result["data_path"] = paths["data_path"]

        return {
            **ctx,
            "output": result,
            "failure_analysis": result,
            "system_errors": system_data.get("errors", {}),
            "provider_metrics": system_data.get("metrics", {}),
            "failure_report": report,
        }
    except Exception as e:
        logger.exception("[FAILURE_ANALYSIS] Failed: %s", e)
        return {**ctx, "output": {"error_type": "unknown", "findings": [], "suggestion_count": 0}}
