"""Prompt Improver — ativa o PromptImprover de 5 estágios na pipeline."""
from typing import Dict, Any
import logging

from iaglobal.agents.prompt_improver import PromptImprover, PromptMode

logger = logging.getLogger(__name__)
_improver = PromptImprover()


async def run_prompt_improver(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    raw_prompt = ""

    prompt_data = memory.get("prompt_intake", {})
    if isinstance(prompt_data, dict):
        raw_prompt = prompt_data.get("prompt", {}).get("normalized", "") or prompt_data.get("output", "")
    if not raw_prompt:
        raw_prompt = memory.get("enhancement", {}).get("output", "")

    task = str(ctx.get("input", {}).get("task", ""))
    if not raw_prompt:
        raw_prompt = task
    if not raw_prompt or len(raw_prompt) < 5:
        logger.warning("[PROMPT_IMPROVER] Prompt muito curto, repassando task original")
        return {**ctx, "output": task, "improved_prompt": task}

    knowledge_data = memory.get("knowledge", {})
    knowledge_context = knowledge_data.get("summary", "") if isinstance(knowledge_data, dict) else ""

    try:
        improved, report = _improver.improve_with_report(
            raw_prompt=raw_prompt,
            domain="",
            knowledge_context=knowledge_context,
            mode=PromptMode.FULL,
        )
        logger.info(
            "[PROMPT_IMPROVER] %d→%d chars | mod=%s | dominios=%s | constraints=%d",
            report.original_length, report.final_length,
            report.mode.value if hasattr(report.mode, 'value') else report.mode,
            [d for d, _ in report.detected_domains],
            report.constraints_applied,
        )
        return {
            **ctx,
            "output": improved,
            "improved_prompt": improved,
            "prompt_improver_report": report.to_dict() if hasattr(report, 'to_dict') else {},
        }
    except Exception as e:
        logger.warning("[PROMPT_IMPROVER] Falha: %s, usando prompt original", e)
        return {**ctx, "output": raw_prompt, "improved_prompt": raw_prompt}
