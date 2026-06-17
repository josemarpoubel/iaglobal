import logging
from typing import Dict, Any
from iaglobal.agents.critic_agent import CriticAgent

logger = logging.getLogger(__name__)

async def run_evaluator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing evaluator handler")
    agent = CriticAgent()
    task = ctx.get("task", "")
    prompt = ctx.get("prompt", "")
    output = ctx.get("coder", {}).get("output", "")
    result = await agent.avaliar(task, prompt, output)
    ctx["evaluator"] = result
    return ctx
