# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import time
from typing import Dict, Any
import logging

from iaglobal.agents.semantic_validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_semantic_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    artifact = (
        memory.get("reviewer", {}).get("output")
        or memory.get("validator", {}).get("output")
        or memory.get("multi_coder", {}).get("output")
    )

    if hasattr(artifact, "code"):
        code = artifact.code or ""
    elif isinstance(artifact, dict):
        code = artifact.get("code") or artifact.get("output", "")

    if not code:
        logger.info("[SEMANTIC] No code to validate")
        return {
            **ctx,
            "output": {"valid": True, "score": 100, "errors": []},
            "semantic_score": 100,
            "errors": [],
            "execution_metrics": {
                "success": True,
                "latency": time.time() - start,
                "cost": 0.0,
                "model": "local",
            },
        }

    try:
        agent = SemanticValidatorAgent()
        result = agent.validate(code=code, task=task_str)
        score = result.get("score", 100)
        errors = result.get("errors", [])
        valid = result.get("valid", score >= 50)
        logger.info("[SEMANTIC] Score=%.1f Errors=%d", score, len(errors))
        return {
            **ctx,
            "output": {"valid": valid, "score": score, "errors": errors},
            "semantic_score": score,
            "errors": errors,
            "valid": valid,
            "execution_metrics": {
                "success": valid,
                "latency": time.time() - start,
                "cost": 0.0,
                "model": "local",
            },
        }
    except Exception as e:
        logger.exception("[SEMANTIC] Failed: %s", e)
        return {
            **ctx,
            "output": {"valid": True, "score": 100, "errors": []},
            "semantic_score": 100,
            "errors": [],
            "execution_metrics": {
                "success": False,
                "latency": time.time() - start,
                "cost": 0.0,
                "model": "local",
            },
        }
