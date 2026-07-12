# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/evolution/skills/skill_model_router.py

import logging
from typing import Dict, Any

from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)

CRITICAL_KEYWORDS = {"mhc", "vulnerability", "security", "apoptosis", "emergency", "attack", "injection", "pathogen"}
REASONING_KEYWORDS = {"analise", "análise", "analisar", "arquitetura", "refator", "refactor",
                      "design", "otimiz", "optimiz", "diagnóstico", "diagnostico", "gargalo"}
IVM_REASONING_THRESHOLD = 0.5
LOCAL_MODEL = "qwen2.5:0.5b"
CLOUD_MODEL_DEFAULT = "groq-mixtral-8x7b"

SCORE_PRECISION_LOCAL = 0.65
SCORE_PRECISION_CLOUD = 0.90
LATENCY_LOCAL_MS = 200.0
LATENCY_CLOUD_MS = 1200.0
TOKEN_COST_LOCAL = 0.001
TOKEN_COST_CLOUD = 0.05

def _compute_score(precision: float, latency_ms: float, token_cost: float) -> float:
    return (precision * 0.6) - (latency_ms / 1000.0 * 0.2) - (token_cost * 0.2)

async def run_model_router(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("task", ""))
    task_lower = task.lower()
    ivm = ctx.get("ivm", 1.0)

    has_critical = any(kw in task_lower for kw in CRITICAL_KEYWORDS)
    critical_flag = ctx.get("critical", False) or ctx.get("threats_detected", False)

    has_reasoning = any(kw in task_lower for kw in REASONING_KEYWORDS)
    low_ivm_reasoning = has_reasoning and ivm < IVM_REASONING_THRESHOLD

    # Tarefas com keyword crítica OU de raciocínio entram na avaliação de score
    needs_evaluation = has_critical or critical_flag or has_reasoning

    if needs_evaluation:
        score_local = _compute_score(SCORE_PRECISION_LOCAL, LATENCY_LOCAL_MS, TOKEN_COST_LOCAL)
        score_cloud = _compute_score(SCORE_PRECISION_CLOUD, LATENCY_CLOUD_MS, TOKEN_COST_CLOUD)

        if low_ivm_reasoning:
            reason = "reasoning_low_ivm_elevation"
        elif has_critical:
            reason = "critical_task_elevation"
        elif critical_flag:
            reason = "critical_flag_elevation"
        else:
            reason = "reasoning_high_ivm"

        if score_local < 0.4 or score_cloud > score_local:
            decision = {
                "selected_model": CLOUD_MODEL_DEFAULT,
                "provider": "groq",
                "reason": reason,
                "score_local": round(score_local, 3),
                "score_cloud": round(score_cloud, 3),
            }
            logger.info(
                "[MODEL_ROUTER] Elevado para nuvem: reason=%s score_local=%.3f score_cloud=%.3f",
                reason, score_local, score_cloud,
            )
        else:
            decision = {
                "selected_model": LOCAL_MODEL,
                "provider": "ollama",
                "reason": "local_sufficient",
                "score_local": round(score_local, 3),
                "score_cloud": round(score_cloud, 3),
            }
            logger.info("[MODEL_ROUTER] Mantido local: reason=%s score_local=%.3f", reason, score_local)
    else:
        decision = {
            "selected_model": LOCAL_MODEL,
            "provider": "ollama",
            "reason": "default_local_atp_preservation",
            "score_local": round(_compute_score(SCORE_PRECISION_LOCAL, LATENCY_LOCAL_MS, TOKEN_COST_LOCAL), 3),
            "score_cloud": 0.0,
        }
        logger.info("[MODEL_ROUTER] Modo ATP: roteado para %s por padrão", LOCAL_MODEL)

    return {"model_decision": decision}

skill_model_router = Skill(
    name="dynamic_model_router",
    version="v1",
    description="Roteador de provedores por custo-benefício matemático. Analisa criticidade da tarefa e decide entre modelo local (ATP) ou nuvem.",
    run_fn=run_model_router,
    inputs=["task"],
    outputs=["model_decision"],
    constraints=["deterministic", "no_llm"],
    execution_policy=ExecutionPolicy.ON_DEMAND,
    author="applied-ai-engineer",
    tags=["applied-ai", "routing", "optimization"],
)

skill_registry.register(skill_model_router)
