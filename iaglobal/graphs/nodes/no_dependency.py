"""Dependency handler — verifica dependencias do projeto."""
from typing import Dict, Any
import logging

from iaglobal.agents.dependency_agent import verify_dependencies

logger = logging.getLogger(__name__)


async def run_dependency(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))
    context = memory.get("coder", {}).get("output", "") or task

    result = verify_dependencies(context=context)
    missing = result.get("missing", [])

    logger.info("[DEPENDENCY] %d dependencias, %d ausentes",
                len(result.get("dependencies", [])), len(missing))

    return {
        **ctx,
        "output": result,
        "dependencies": result,
    }
