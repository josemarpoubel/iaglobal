# iaglobal/graphs/nodes/no_mini_evaluator_post_build.py
"""
Mini Evaluator — Gate de metacognição leve após construcao.
Interrompe a pipeline se o código gerado não atender aos requisitos.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_mini_evaluator_post_build(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avalia rapidamente se o output do code_executor atende aos requisitos.
    Verifica se código HTML tem @media queries para tasks responsivas.
    Retorna score e decisão: continue, regress, abort.
    """
    start_time = time.time()
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", "")).lower()
    
    score = 100
    decision = "continue"
    
    # Check if this is a responsive/web task
    if any(kw in task for kw in ["pagina", "site", "landing", "email", "newsletter", "dark", "escuro", "responsive", "mobile"]):
        # Check frontend_builder output for media queries
        fb_output = memory.get("frontend_builder", {}).get("output", "")
        if fb_output and "@media" not in fb_output:
            score = 40
            decision = "regress"
            logger.info("[MINI_EVALUATOR_POST_BUILD] Frontend sem @media: score=%d, decision=%s", score, decision)
    
    # Check if code_executor has output
    ce_output = memory.get("code_executor", {}).get("output", "")
    if not ce_output or "empty" in str(ce_output).lower():
        score = 0
        decision = "abort"
        logger.info("[MINI_EVALUATOR_POST_BUILD] Code executor sem output: score=%d, decision=%s", score, decision)
    
    latency_ms = (time.time() - start_time) * 1000.0
    
    return {
        "output": f"Mini-evaluation (build): score={score}, decision={decision}",
        "score": score,
        "decision": decision,
        "execution_metrics": {
            "model": "mini_evaluator_post_build",
            "success": True,
            "latency": latency_ms,
            "cost": 0.0
        }
    }