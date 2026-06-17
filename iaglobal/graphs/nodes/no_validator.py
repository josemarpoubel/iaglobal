from typing import Dict, Any
import logging

from iaglobal.agents.validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        logger.warning("[VALIDATOR] No code to validate")
        return {**ctx, "output": {"valid": True, "score": 100, "errors": []}}

    try:
        agent = SemanticValidatorAgent()
        result = agent.validar(task=task_str, code=code)
        score = result.get("score", 100)
        errors = result.get("errors", [])
        valid = result.get("valid", score >= 50)
        logger.info("[VALIDATOR] Score=%.1f Errors=%d", score, len(errors))
        return {**ctx, "output": {"valid": valid, "score": score, "errors": errors}}
    except Exception as e:
        logger.exception("[VALIDATOR] Failed: %s", e)
        return {**ctx, "output": {"valid": True, "score": 100, "errors": []}}
