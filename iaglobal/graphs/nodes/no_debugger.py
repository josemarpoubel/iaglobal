from typing import Dict, Any
import logging

from iaglobal.agents.debugger_agent import DebuggerAgent, DebugResult
from iaglobal.models.task import Task

logger = logging.getLogger(__name__)


async def run_debugger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    for source in ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder"):
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
        logger.warning("[DEBUGGER] No code found to debug")
        return {**ctx, "output": "", "debug_result": None}

    task = Task(objective=task_str, context={"code": code})

    try:
        agent = DebuggerAgent()
        result: DebugResult = await agent.run(task)
        logger.info("[DEBUGGER] success=%s attempts=%d elapsed=%.2fs", result.success, result.attempts, result.execution_time)
        return {
            **ctx,
            "output": result.code,
            "debug_result": {
                "success": result.success,
                "code": result.code,
                "error": result.error,
                "attempts": result.attempts,
                "execution_time": result.execution_time,
            },
        }
    except Exception as e:
        logger.exception("[DEBUGGER] Failed: %s", e)
        return {**ctx, "output": code, "debug_result": {"success": False, "error": str(e)}}
