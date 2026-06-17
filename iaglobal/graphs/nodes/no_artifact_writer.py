import logging
from typing import Dict, Any
from iaglobal.agents.result_agent import ResultAgent

logger = logging.getLogger(__name__)

async def run_artifact_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing artifact_writer handler")
    agent = ResultAgent()
    result = agent.build_result(ctx=ctx)
    ctx["artifact_writer"] = result
    return ctx
