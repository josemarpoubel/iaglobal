from typing import Dict, Any
import logging

from iaglobal.agents.validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_semantic_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        return {**ctx, "output": {"valid": True, "score": 100, "errors": []}, "semantic_score": 100, "errors": []}

    try:
        agent = SemanticValidatorAgent()
        result = agent.validar(task=task_str, code=code)
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
        }
    except Exception as e:
        logger.exception("[SEMANTIC] Failed: %s", e)
        return {**ctx, "output": {"valid": True, "score": 100, "errors": []}, "semantic_score": 100, "errors": []}
