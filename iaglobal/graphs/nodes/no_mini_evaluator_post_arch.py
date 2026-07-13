# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_mini_evaluator_post_arch.py
"""
Mini Evaluator — Gate de metacognição leve após architect.
Interrompe a pipeline se a arquitetura não atender aos requisitos mínimos.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_mini_evaluator_post_arch(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avalia rapidamente se o output da arquitetura atende aos requisitos mínimos.
    Retorna score e decisão: continue, regress, abort.
    """
    start_time = time.time()

    memory = ctx.get("memory", {})
    arch_output = memory.get("architect", {}).get("output", "")

    score = 100
    decision = "continue"

    if not arch_output or len(arch_output) < 50:
        score = 30
        decision = "regress"

    logger.info(
        "[MINI_EVALUATOR_POST_ARCH] Arquitetura: score=%d, decision=%s", score, decision
    )

    latency_ms = (time.time() - start_time) * 1000.0

    return {
        "output": f"Mini-evaluation (arch): score={score}, decision={decision}",
        "score": score,
        "decision": decision,
        "execution_metrics": {
            "model": "mini_evaluator_post_arch",
            "success": True,
            "latency": latency_ms,
            "cost": 0.0,
        },
    }
