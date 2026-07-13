# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ReactPy Node - Geração de componentes UI reativos.
===================================================
Integra com o skill registry para produção de componentes ReactPy.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_reactpy(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa geração de componentes ReactPy.

    Args:
        ctx: Contexto com task e memory

    Returns:
        Output com código ReactPy gerado
    """
    start_time = time.time()
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    if not task:
        return {"output": "", "reactpy": {"error": "no task provided"}}

    # Lazy import para evitar dependência pesada
    try:
        from iaglobal.agents.coder_agent import CoderAgent

        agent = CoderAgent()

        # Contexto ReactPy
        reactpy_context = "reactpy component generation with dark theme"

        # Executa via coder_agent
        artifact = await agent.generate(task=task, contexto=reactpy_context)

        latency_ms = (time.time() - start_time) * 1000

        return {
            "output": artifact.code if hasattr(artifact, "code") else "",
            "reactpy": {
                "output": artifact.code if hasattr(artifact, "code") else "",
                "files": artifact.files if hasattr(artifact, "files") else {},
                "model": artifact.model_used
                if hasattr(artifact, "model_used")
                else "unknown",
            },
            "execution_metrics": {
                "model": "coder-reactpy",
                "success": bool(artifact.code),
                "latency": latency_ms,
                "cost": 0.0,
                "task_type": "reactpy_generation",
            },
        }
    except Exception as e:
        logger.exception("[REACTPY] Failed: %s", e)
        return {
            "output": "",
            "reactpy": {"error": str(e)},
            "execution_metrics": {
                "model": "fallback",
                "success": False,
                "latency": (time.time() - start_time) * 1000,
                "cost": 0.0,
                "task_type": "reactpy_generation",
            },
        }
