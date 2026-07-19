# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SkillModelRouter — Roteador Inteligente de Modelos LLM.
Decide se uma tarefa roda em modelo local (Ollama) ou nuvem (Groq).

Critérios:
1. Keywords críticas → nuvem (segurança, MHC, pathogen)
2. Raciocínio complexo + IVM baixo → nuvem
3. Caso contrário → local (ATP preservation)

Uso:
    from iaglobal.evolution.skills.native.skill_model_router import (
        CRITICAL_KEYWORDS, REASONING_KEYWORDS, IVM_REASONING_THRESHOLD,
        run_model_router, SkillModelRouter, model_router,
    )
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from iaglobal.evolution.skills.native.skill import Skill
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.skill_model_router")

# ─── Keywords e thresholds exportados (para testes e EvoAgent) ────────────────

CRITICAL_KEYWORDS = frozenset(
    {
        "mhc",
        "vulnerability",
        "security",
        "apoptosis",
        "emergency",
        "attack",
        "injection",
        "pathogen",
        "toxic",
        "threat",
        "critical",
    }
)

REASONING_KEYWORDS = frozenset(
    {
        "analise",
        "análise",
        "analisar",
        "arquitetura",
        "refator",
        "refactor",
        "design",
        "otimiz",
        "optimiz",
        "diagnóstico",
        "diagnostico",
        "gargalo",
        "complexo",
        "complexa",
        "estratégia",
        "planejamento",
    }
)

IVM_REASONING_THRESHOLD = 0.5
SCORE_ELEVATION_THRESHOLD = 0.25
WEIGHT_PRECISION = 0.6
WEIGHT_LATENCY = 0.2
WEIGHT_COST = 0.2

LOCAL_MODEL = "qwen2.5:0.5b"
CLOUD_MODEL = "groq-mixtral-8x7b"
CLOUD_PROVIDER = "groq"
LOCAL_PROVIDER = "ollama"

MODEL_CONFIG = {
    "local": {"precision": 0.65, "latency_ms": 200.0, "token_cost": 0.001},
    "cloud": {"precision": 0.90, "latency_ms": 1200.0, "token_cost": 0.05},
}


# ─── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class RouterDecision:
    selected_model: str
    provider: str
    reason: str
    confidence: float = 1.0
    ivm: float = 1.0
    task: str = ""


@dataclass
class RouterMetrics:
    total_decisions: int = 0
    cloud_decisions: int = 0
    local_decisions: int = 0
    cached_decisions: int = 0
    total_elapsed_ms: float = 0.0

    @property
    def cloud_ratio(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return (self.cloud_decisions / self.total_decisions) * 100

    @property
    def cache_hit_rate(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return (self.cached_decisions / self.total_decisions) * 100

    @property
    def avg_elapsed_ms(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.total_elapsed_ms / self.total_decisions


# ─── Core Router ─────────────────────────────────────────────────────────────


class SkillModelRouter:
    """Roteador inteligente de modelos LLM.

    Uso:
        router = SkillModelRouter()
        decision = await router.route(task="analise de segurança", ivm=0.3)
        if decision.provider == "groq":
            result = await call_groq(...)
        else:
            result = await call_ollama(...)
    """

    WEIGHT_PRECISION = 0.6
    WEIGHT_LATENCY = 0.2
    WEIGHT_COST = 0.2

    def __init__(self, cache_size: int = 1024):
        self.metrics = RouterMetrics()
        self._decision_cache = lru_cache(maxsize=cache_size)(
            self._compute_decision_uncached
        )
        self._learning_history: list[Dict] = []

        logger.info("[SkillModelRouter] Inicializado | cache_size=%d", cache_size)

    def _compute_score(
        self, precision: float, latency_ms: float, token_cost: float
    ) -> float:
        return (
            (precision * SkillModelRouter.WEIGHT_PRECISION)
            - (latency_ms / 1000.0 * SkillModelRouter.WEIGHT_LATENCY)
            - (token_cost * SkillModelRouter.WEIGHT_COST)
        )

    def _hash_task(self, task: str, ivm: float) -> str:
        key = f"{task.lower().strip()}:{ivm:.2f}"
        return hashlib.sha3_256(key.encode()).hexdigest()[:16]

    def _needs_evaluation(self, task: str, ivm: float, critical_flag: bool) -> bool:
        task_lower = task.lower()
        has_critical = any(kw in task_lower for kw in CRITICAL_KEYWORDS)
        has_reasoning = any(kw in task_lower for kw in REASONING_KEYWORDS)
        low_ivm_reasoning = has_reasoning and ivm < IVM_REASONING_THRESHOLD
        return has_critical or critical_flag or low_ivm_reasoning

    def _determine_reason(self, task: str, ivm: float, critical_flag: bool) -> str:
        task_lower = task.lower()
        has_critical = any(kw in task_lower for kw in CRITICAL_KEYWORDS)
        has_reasoning = any(kw in task_lower for kw in REASONING_KEYWORDS)

        if has_critical:
            return "critical_task_elevation"
        if critical_flag:
            return "critical_flag_elevation"
        if has_reasoning and ivm < IVM_REASONING_THRESHOLD:
            return "reasoning_low_ivm_elevation"
        if has_reasoning:
            return "reasoning_high_ivm"
        return "default_local_atp_preservation"

    def _compute_decision_uncached(
        self, task: str, ivm: float, critical_flag: bool = False
    ) -> RouterDecision:
        reason = self._determine_reason(task, ivm, critical_flag)

        if reason in (
            "critical_task_elevation",
            "critical_flag_elevation",
            "reasoning_low_ivm_elevation",
        ):
            provider = CLOUD_PROVIDER
            model = CLOUD_MODEL
        else:
            provider = LOCAL_PROVIDER
            model = LOCAL_MODEL

        return RouterDecision(
            selected_model=model,
            provider=provider,
            reason=reason,
            confidence=1.0,
            ivm=ivm,
            task=task,
        )

    async def route(
        self,
        task: str,
        ivm: float = 1.0,
        critical_flag: bool = False,
        skill: Optional[Skill] = None,
    ) -> RouterDecision:
        start = time.monotonic()
        task_hash = self._hash_task(task, ivm)

        if self._needs_evaluation(task, ivm, critical_flag):
            decision = self._decision_cache(task, ivm, critical_flag)
            self.metrics.cached_decisions += 1
        else:
            decision = self._compute_decision_uncached(task, ivm, critical_flag)

        elapsed = (time.monotonic() - start) * 1000
        self.metrics.total_decisions += 1
        self.metrics.total_elapsed_ms += elapsed
        if decision.provider == CLOUD_PROVIDER:
            self.metrics.cloud_decisions += 1
        else:
            self.metrics.local_decisions += 1

        logger.debug(
            "[SkillModelRouter] task=%r ivm=%.2f provider=%s reason=%s %.1fms",
            task[:60],
            ivm,
            decision.provider,
            decision.reason,
            elapsed,
        )
        return decision


# ─── Module-level singleton (backward compat) ─────────────────────────────────

model_router = SkillModelRouter()


# Expose a async wrapper so existing callers that `await model_router.route(...)` still work
async def route(
    task: str, ivm: float = 1.0, critical_flag: bool = False
) -> RouterDecision:
    return await model_router.route(task=task, ivm=ivm, critical_flag=critical_flag)


# ─── Async convênio para executor (no_task) ──────────────────────────────────
# Async convenio para executor (no_task)


async def run_model_router(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = ctx.get("task", "")
    ivm = float(ctx.get("ivm", ctx.get("ivm_score", 1.0)))
    critical = bool(
        ctx.get(
            "critical", ctx.get("critical_flag", ctx.get("threats_detected", False))
        )
    )
    decision = await model_router.route(task=task, ivm=ivm, critical_flag=critical)
    cloud_score = model_router._compute_score(
        precision=MODEL_CONFIG["cloud"]["precision"],
        latency_ms=MODEL_CONFIG["cloud"]["latency_ms"],
        token_cost=MODEL_CONFIG["cloud"]["token_cost"],
    )
    return {
        "model_decision": {
            "selected_model": decision.selected_model,
            "provider": decision.provider,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "ivm": decision.ivm,
            "score_cloud": cloud_score,
        }
    }
