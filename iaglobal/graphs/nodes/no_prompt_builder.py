from typing import Dict, Any
import logging

from iaglobal.memory.memory_error import record_error

logger = logging.getLogger(__name__)


async def run_prompt_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    search_sources = ["search"]

    sections = []
    sections.append("=== TAREFA ORIGINAL ===\n" + task)

    for src in search_sources:
        src_data = memory.get(src, {})
        src_output = src_data.get("output", "")
        if src_output and len(src_output) > 20:
            label = src.replace("search_", "search ").title()
            sections.append(f"=== {label.upper()} ===\n{src_output[:2000]}")

    knowledge_data = memory.get("knowledge", {})
    knowledge_summary = knowledge_data.get("summary", "")
    if knowledge_summary:
        sections.append("=== CONHECIMENTO EXTRAIDO ===\n" + knowledge_summary)

    knowledge_concepts = knowledge_data.get("concepts", [])
    if knowledge_concepts:
        concept_lines = [f"  - {c['name']} (freq: {c['frequency']})" for c in knowledge_concepts[:10]]
        sections.append("=== CONCEITOS IDENTIFICADOS ===\n" + "\n".join(concept_lines))

    built_prompt = "\n\n".join(sections)

    if not built_prompt or len(built_prompt) < 50:
        record_error("prompt_builder", "Prompt built too short", {"task": task[:100], "len": len(built_prompt)})
        built_prompt = task

    logger.info("[PROMPT_BUILDER] Prompt construido: %d chars, %d secoes", len(built_prompt), len(sections))

    return {
        **ctx,
        "output": built_prompt,
        "built_prompt": built_prompt,
        "prompt_sections": {src: bool(memory.get(src, {}).get("output")) for src in search_sources},
        "success": True,
    }
