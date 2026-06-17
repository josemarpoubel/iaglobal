from typing import Dict, Any
import logging

from iaglobal.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)


async def run_enhancement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    prompt = ctx.get("prompt")
    if not prompt or not isinstance(prompt, dict) or not prompt.get("normalized"):
        task = str(ctx.get("input", {}).get("task", ""))
        prompt = {"raw": task, "normalized": task, "tokens": len(task.split()), "intents": ["unknown"]}

    raw = prompt["normalized"]
    intake = {
        "raw": raw,
        "normalized": raw,
        "domain": ctx.get("input", {}).get("domain", "unknown"),
    }
    knowledge_context = str(ctx.get("knowledge_context", ""))
    error_context = str(ctx.get("error_context", ""))

    agent = EnhancementAgent()
    result = agent.enhance(
        task=raw,
        intake=intake,
        knowledge_context=knowledge_context,
        error_context=error_context,
    )

    intents = ["analysis", "planning"]
    entities = []

    enhancement_def = {
        "intents_detected": intents,
        "entities": entities,
        "scope": {
            "phases": ["definition"],
            "complexity": "medium",
        },
        "specialization_instructions": None,
        "enhanced_task": result.get("enhanced_task", ""),
        "approach": result.get("approach", []),
        "prerequisites": result.get("prerequisites", []),
        "suggested_libs": result.get("suggested_libs", []),
    }

    out = {**ctx, "enhancement": enhancement_def}
    return out
