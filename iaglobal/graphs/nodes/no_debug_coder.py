import logging
from typing import Dict, Any
from iaglobal.agents.debugger_agent import DebuggerAgent

logger = logging.getLogger(__name__)

async def run_debug_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Executing debug_coder handler")
    agent = DebuggerAgent()
    code = ctx.get("coder", {}).get("output", ctx.get("multi_coder", {}).get("output", ""))
    task = ctx.get("task", "")
    result = await agent.corrigir_codigo_async(codigo=code, erro="", task=task)
    ctx["debug_coder"] = {"output": result}
    return ctx
