import logging
from typing import Dict, Any
from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)

async def run_frontend_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing frontend_builder handler")
    agent = CoderAgent()
    task = ctx.get("task", "")
    artifact = await agent.generate(task=task, contexto="frontend only")
    ctx["frontend_builder"] = {"output": artifact.code, "files": artifact.files}
    return ctx
