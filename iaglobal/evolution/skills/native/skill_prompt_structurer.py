# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/evolution/skills/skill_prompt_structurer.py

import json
import logging
from typing import Dict, Any

from iaglobal.evolution.skills.native.skill import Skill, ExecutionPolicy
from iaglobal.evolution.skills.native.skill_registry import skill_registry
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """<thought>
You must reason step-by-step before producing the final answer.
Analyze the request, break it down, verify your logic.
</thought>

CRITICAL INSTRUCTION:
Your output MUST be strictly a valid JSON object mapping the requested fields.
No introductory text, no explanations, no markdown formatting outside the JSON.
Only the raw JSON object as output."""


async def run_prompt_structurer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = ctx.get("task", "")
    system_prompt = ctx.get("system_prompt", "")
    user_prompt = ctx.get("user_prompt", "")
    original_prompt = system_prompt or user_prompt or task

    structured_system = SYSTEM_PROMPT_TEMPLATE
    if system_prompt:
        structured_system = system_prompt + "\n\n" + SYSTEM_PROMPT_TEMPLATE

    result = {
        "system_prompt": structured_system,
        "user_prompt": user_prompt or task,
        "original_length": len(original_prompt),
        "structured_length": len(structured_system) + len(user_prompt or task),
        "added_thought_tag": True,
        "added_json_instruction": True,
    }

    logger.info(
        "[PROMPT_STRUCTURER] Prompt enriquecido com CoT + JSON constraint (%d chars -> %d chars)",
        result["original_length"],
        result["structured_length"],
    )

    # Tenta validar se o output do provedor já veio no contexto (apenas se houver provider_output)
    provider_output = ctx.get("provider_output", "")
    if provider_output:
        try:
            parsed = json.loads(provider_output)
            result["parsed_successfully"] = True
            result["parsed_output"] = parsed
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "[PROMPT_STRUCTURER] Provider output não é JSON válido. Acionando autocorreção."
            )
            result["parsed_successfully"] = False
            result["needs_autocorrect"] = True
    else:
        result["parsed_successfully"] = None
        result["needs_autocorrect"] = False

    return {"structured_prompt": result}


skill_prompt_structurer = Skill(
    name="structured_prompt_generator",
    version="v1",
    description="Injeta Chain-of-Thought e validação JSON no prompt do sistema. Adiciona tag <thought> e força saída JSON estruturada.",
    run_fn=run_prompt_structurer,
    inputs=["task"],
    outputs=["structured_prompt"],
    constraints=["deterministic", "no_llm"],
    execution_policy=ExecutionPolicy.ON_DEMAND,
    author="applied-ai-engineer",
    tags=["applied-ai", "prompt", "structuring"],
)

skill_registry.register(skill_prompt_structurer)
