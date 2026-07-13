# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_applied_ai_engineer.py

import time
import logging
from typing import Dict, Any

from iaglobal.evolution.skills.native.skill_executor import SkillExecutor
from iaglobal.evolution.skills.native.skill_registry import skill_registry
from iaglobal.evolution.skills.native.skill import Skill, ExecutionPolicy
from iaglobal.utils.logger import logger
from iaglobal.immunity.pathogen_analyzer import pathogen_analyzer
from iaglobal.obsidian.law_compliance_logger import law_compliance_logger

logger = logging.getLogger(__name__)

# Import skills to ensure registration
import iaglobal.evolution.skills.native.skill_model_router  # noqa: F401
import iaglobal.evolution.skills.native.skill_rag_optimizer  # noqa: F401
import iaglobal.evolution.skills.native.skill_prompt_structurer  # noqa: F401

IVM_THRESHOLD = 0.5

SKILL_SEQUENCE = [
    "dynamic_model_router",
    "optimize_rag_pipeline",
    "structured_prompt_generator",
]


async def run_applied_ai_engineer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    resolved_model = "applied_ai_engineer"

    ivm = ctx.get("ivm", 0.67)
    if isinstance(ivm, str):
        try:
            ivm = float(ivm)
        except (ValueError, TypeError):
            ivm = 0.67

    if ivm < IVM_THRESHOLD:
        logger.warning(
            "[APPLIED_AI] IVM=%.2f abaixo do threshold %.2f — rejeitando",
            ivm,
            IVM_THRESHOLD,
        )
        return {
            "output": {
                "status": "REJECTED",
                "reason": f"IVM {ivm:.2f} abaixo do threshold {IVM_THRESHOLD}",
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": 0.0,
                "cost": 0.0,
            },
        }

    executor = SkillExecutor(registry=skill_registry)
    last_result = {"model_decision": {}, "rag_config": {}, "structured_prompt": {}}

    try:
        for skill_name in SKILL_SEQUENCE:
            if not executor.can_execute(skill_name):
                logger.warning(
                    "[APPLIED_AI] Skill '%s' não disponível — marcando como vazia",
                    skill_name,
                )
                continue

            enriched_ctx = {**ctx, **last_result}
            result = await executor.execute(skill_name, enriched_ctx)

            if isinstance(result, dict) and not result.get("skipped"):
                last_result.update(result)

        model_decision = last_result.get("model_decision", {})
        rag_config = last_result.get("rag_config", {})
        structured_prompt = last_result.get("structured_prompt", {})

        selected_model = ""
        if isinstance(model_decision, dict):
            selected_model = model_decision.get("selected_model", "unknown")

        prompt_text = ""
        if isinstance(structured_prompt, dict):
            prompt_text = structured_prompt.get(
                "user_prompt", ""
            ) or structured_prompt.get("system_prompt", "")

        if prompt_text:
            scan = pathogen_analyzer.analyze_code(
                prompt_text, context="applied_ai_engineer"
            )
            if scan.get("is_pathogen"):
                logger.warning(
                    "[APPLIED_AI] Patógeno detectado no prompt gerado: %s",
                    scan.get("threats"),
                )
                last_result["pathogen_alert"] = scan.get("threats")

        law_compliance_logger.log_law_application(
            law="Lei da Ordem",
            context=f"Applied AI Engine: modelo={selected_model} ivm={ivm:.2f}",
            agent="applied_ai_engineer",
        )

        latency_ms = (time.time() - start_time) * 1000.0
        logger.info(
            "[APPLIED_AI] Ciclo concluído: modelo=%s ivm=%.2f latência=%.0fms",
            selected_model,
            ivm,
            latency_ms,
        )

        return {
            "output": {
                "status": "SUCCESS",
                "model_decision": model_decision,
                "rag_config": rag_config,
                "structured_prompt": structured_prompt,
            },
            "applied_ai_engineer": last_result,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[APPLIED_AI] Falha na execução: %s", e)
        return {
            "output": {"status": "FAILED", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }


# Injeta run_fn real no skill built-in (substitui o fallback LLM genérico)
_skill = Skill(
    name="applied_ai_engineer",
    version="v1",
    run_fn=run_applied_ai_engineer,
    inputs=["task"],
    outputs=["model_decision", "rag_config", "structured_prompt"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "optimization", "applied-ai"],
)
skill_registry.register_or_update(_skill)
