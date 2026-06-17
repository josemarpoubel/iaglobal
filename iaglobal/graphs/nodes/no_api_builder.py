import logging
from typing import Dict, Any
from iaglobal.agents.coder_agent import CoderAgent

logger = logging.getLogger(__name__)

async def run_api_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing api_builder handler")
    agent = CoderAgent()
    task = ctx.get("task", "")
    artifact = await agent.generate(task=task, contexto="API design")
    ctx["api_builder"] = {"output": artifact.code, "files": artifact.files}
    return ctx
