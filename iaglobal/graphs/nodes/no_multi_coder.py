"""Multi-coder paralelo — gera backend, frontend e database em paralelo."""
from typing import Dict, Any
import logging

from iaglobal.agents.multi_coder_agent import MultiCoderAgent

logger = logging.getLogger(__name__)

_agent: MultiCoderAgent = None


def _get_agent() -> MultiCoderAgent:
    global _agent
    if _agent is None:
        _agent = MultiCoderAgent()
    return _agent


async def run_multi_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    prompt_builder_data = memory.get("prompt_builder", {})

    built_prompt = prompt_builder_data.get("built_prompt", "") or prompt_builder_data.get("output", "")
    if not built_prompt:
        built_prompt = str(ctx.get("input", {}).get("task", ""))

    if not built_prompt or len(built_prompt) < 10:
        logger.warning("[MULTI_CODER] Prompt vazio, repassando coder output")
        coder_out = memory.get("coder", {}).get("output", "")
        return {**ctx, "output": coder_out, "multi_coder": {"status": "passthrough"}}

    agent = _get_agent()
    result = await agent.generate(built_prompt)

    logger.info("[MULTI_CODER] Status=%s, falhas=%d/3, %d chars total",
                result.status, result.failures, result.total_chars)

    multi_output = "\n\n".join(
        f"# === {k.upper()} ===\n{v}" for k, v in result.parts.items() if v
    ) if any(result.parts.values()) else ""

    return {
        **ctx,
        "output": multi_output,
        "multi_coder": {
            "status": result.status,
            "parts": result.parts,
            "total_chars": result.total_chars,
            "failures": result.failures,
        },
    }
