import logging
from typing import Dict, Any
from iaglobal.agents.result_agent import ResultAgent

logger = logging.getLogger(__name__)

async def run_release(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing release handler")
    agent = ResultAgent()
    result = agent.build_result(ctx=ctx)
    ctx["release"] = result
    return ctx
