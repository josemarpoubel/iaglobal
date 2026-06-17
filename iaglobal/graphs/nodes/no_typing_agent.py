from typing import Dict, Any
import logging

from iaglobal.agents.typing_agent import TypingAgent

logger = logging.getLogger(__name__)


async def run_typing_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    text = str(ctx.get("input", {}).get("task", ""))
    if not text:
        logger.warning("[TYPING_AGENT] No text to type")
        return {**ctx, "output": ""}

    try:
        agent = TypingAgent()
        chars_typed = []
        agent.simulate_typing(text, on_char=lambda c: chars_typed.append(c))
        result = "".join(chars_typed)
        logger.info("[TYPING_AGENT] Typed %d chars", len(result))
        return {**ctx, "output": result, "typing_result": result}
    except Exception as e:
        logger.exception("[TYPING_AGENT] Failed: %s", e)
        return {**ctx, "output": ""}
