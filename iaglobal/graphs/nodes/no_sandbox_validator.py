import logging
from typing import Dict, Any
from iaglobal.agents.semantic_validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)

async def run_sandbox_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing sandbox_validator handler")
    agent = SemanticValidatorAgent()
    code = ctx.get("coder", {}).get("output", "")
    task = ctx.get("task", "")
    result = await agent.validate_async(code=code, task=task)
    ctx["sandbox_validator"] = result.to_legacy_dict()
    return ctx
