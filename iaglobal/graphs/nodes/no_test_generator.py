import logging
from typing import Dict, Any
from iaglobal.agents.tester_agent import TesterAgent

logger = logging.getLogger(__name__)

async def run_test_generator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing test_generator handler")
    agent = TesterAgent()
    code = ctx.get("coder", {}).get("output", "")
    task = ctx.get("task", "")
    result = await agent.gerar_testes(code, task)
    ctx["test_generator"] = {"output": result}
    return ctx
