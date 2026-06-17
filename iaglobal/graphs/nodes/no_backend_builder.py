import logging
from typing import Dict, Any
from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)

async def run_backend_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing backend_builder handler")
    agent = CoderAgent()
    task = ctx.get("task", "")
    artifact = await agent.generate(task=task, contexto="backend only")
    ctx["backend_builder"] = {"output": artifact.code, "files": artifact.files}
    return ctx
