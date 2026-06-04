# iaglobal/providers/provider_router.py

import time
from typing import Callable, Optional

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.provider_state import ProviderState
from iaglobal.providers.provider_load_balancer import load_balancer as lb
from iaglobal.providers.provider_scorer import score_provider
from iaglobal.providers.provider_metrics import metrics, estimate_cost
from iaglobal.providers.token_usage import TokenCollector

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.telemetry import ExecutionEvent

from iaglobal.utils.logger import logger

from iaglobal.providers.ollama_provider import generate as ollama_generate
from iaglobal.providers.groq_provider import generate as groq_generate
from iaglobal.providers.openrouter_provider import generate as openrouter_generate
from iaglobal.providers.nvidia_provider import generate as nvidia_generate
from iaglobal.providers.opencode_provider import generate as opencode_generate
from iaglobal.providers.gemini_provider import generate as gemini_generate

from iaglobal.providers.ollama_provider import async_generate as ollama_async_generate
from iaglobal.providers.groq_provider import async_generate as groq_async_generate
from iaglobal.providers.openrouter_provider import async_generate as openrouter_async_generate
from iaglobal.providers.nvidia_provider import async_generate as nvidia_async_generate
from iaglobal.providers.opencode_provider import async_generate as opencode_async_generate
from iaglobal.providers.gemini_provider import async_generate as gemini_async_generate


# Timeouts por provider
PROVIDER_TIMEOUT = {
    "ollama": 30,
    "groq": 30,
    "openrouter": 30,
    "nvidia": 30,
    "opencode": 30,
    "gemini": 30,
}

PROVIDERS = {
    "ollama": ollama_generate,
    "groq": groq_generate,
    "openrouter": openrouter_generate,
    "nvidia": nvidia_generate,
    "opencode": opencode_generate,
    "gemini": gemini_generate,
}

ASYNC_PROVIDERS = {
    "ollama": ollama_async_generate,
    "groq": groq_async_generate,
    "openrouter": openrouter_async_generate,
    "nvidia": nvidia_async_generate,
    "opencode": opencode_async_generate,
    "gemini": gemini_async_generate,
}


def CREDIT_CANDIDATES():
    return [
        ("ollama", "ollama/qwen2.5:0.5b"),
        ("groq", "groq/llama-3.1-8b-instant"),
        ("openrouter", "openrouter/meta-llama/llama-3.1-8b-instruct"),
        ("nvidia", "nvidia/meta/llama-3.3-70b-instruct"),
        ("opencode", "opencode/nemotron-3-super-free"),
    ]


_credit = CreditAssignmentEngine()
_bandit = BanditPolicy(_credit)
BANDIT_NODE = "model_router"


def _safe_call(provider: str, func: Callable, prompt: str, model: str, task_type: str = "general") -> Optional[str]:
    start = time.time()
    timeout = PROVIDER_TIMEOUT.get(provider, 30)

    prompt_preview = prompt[:80].replace("\n", " ")
    logger.debug("[ROUTER] _safe_call provider=%s model=%s timeout=%ds task_type=%s prompt=%.80s",
                 provider, model, timeout, task_type, prompt_preview)

    prompt_tokens = completion_tokens = total_tokens = 0
    usage_data = {}

    def token_collector(pt, ct):
        nonlocal prompt_tokens, completion_tokens, total_tokens
        prompt_tokens = pt
        completion_tokens = ct
        total_tokens = pt + ct

    try:
        result = func(prompt=prompt, model=model, timeout=timeout, token_collector=token_collector)
        latency = time.time() - start
        result_len = len(result) if result else 0
        logger.debug("[ROUTER] _safe_call OK provider=%s latency=%.2fs result=%d chars",
                     provider, latency, result_len)

        lb.report(provider, True, latency)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        _credit.record(ExecutionEvent(
            node=BANDIT_NODE,
            success=True,
            latency=latency,
            model=model,
            strategy=task_type,
        ))
        metrics.record(provider, model, prompt, True, latency * 1000, 
                     prompt_tokens, completion_tokens, total_tokens, cost, task_type)

        return result

    except Exception as e:
        latency = time.time() - start
        logger.warning("[ROUTER] _safe_call FAIL provider=%s latency=%.2fs error=%s",
                       provider, latency, str(e)[:120])

        lb.report(provider, False, latency)
        _credit.record(ExecutionEvent(
            node=BANDIT_NODE,
            success=False,
            latency=latency,
            model=model,
            strategy=task_type,
            error=str(e),
        ))
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        metrics.record(provider, model, prompt, False, latency * 1000, 
                     prompt_tokens, completion_tokens, total_tokens, cost, task_type)

        return None


def _fallback_chain(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    candidates = [c for c in CREDIT_CANDIDATES() if c[0] != exclude]
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    ranked_remote = _bandit.rank_models(BANDIT_NODE, task_type, remote)
    ranked = local + ranked_remote
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)
    logger.info("[ROUTER] Fallback chain: %s", [p for p, _ in ranked])
    for provider, model in ranked:
        func = PROVIDERS.get(provider)
        if not func:
            continue
        result = _safe_call(provider, func, prompt, model, task_type)
        if result:
            return result
    raise RuntimeError("Todos os providers falharam.")


def route_generate(model: str, prompt: str, task_type: str = "general") -> str:
    model = str(model or "").strip().lower()
    if not model or model == "auto":
        best = lb.select(task_type)
        if best:
            func = PROVIDERS.get(best)
            if func:
                best_model = next((m for p, m in CREDIT_CANDIDATES() if p == best), "unknown-model")
                if best_model:
                    result = _safe_call(best, func, prompt, best_model, task_type)
                    if result:
                        return result
        return _fallback_chain(prompt, exclude=best, task_type=task_type)
    provider = model.split("/")[0]
    func = PROVIDERS.get(provider)
    if not func:
        return _fallback_chain(prompt, task_type=task_type)
    result = _safe_call(provider, func, prompt, model, task_type)
    if result:
        return result
    return _fallback_chain(prompt, exclude=provider, task_type=task_type)


async def _async_safe_call(provider: str, func: Callable, prompt: str, model: str, task_type: str = "general") -> Optional[str]:
    start = time.time()
    timeout = PROVIDER_TIMEOUT.get(provider, 30)
    logger.debug("[ROUTER] _async_safe_call provider=%s model=%s timeout=%ds", provider, model, timeout)

    prompt_tokens = completion_tokens = total_tokens = 0

    def token_collector(pt, ct):
        nonlocal prompt_tokens, completion_tokens, total_tokens
        prompt_tokens = pt
        completion_tokens = ct
        total_tokens = pt + ct

    try:
        result = await func(prompt=prompt, model=model, timeout=timeout, token_collector=token_collector)
        latency = time.time() - start
        result_len = len(result) if result else 0
        logger.debug("[ROUTER] _async_safe_call OK provider=%s latency=%.2fs result=%d chars",
                     provider, latency, result_len)

        lb.report(provider, True, latency)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        _credit.record(ExecutionEvent(node=BANDIT_NODE, success=True, latency=latency, model=model, strategy=task_type))
        metrics.record(provider, model, prompt, True, latency * 1000,
                     prompt_tokens, completion_tokens, total_tokens, cost, task_type)

        return result

    except Exception as e:
        latency = time.time() - start
        logger.warning("[ROUTER] _async_safe_call FAIL provider=%s latency=%.2fs error=%s",
                       provider, latency, str(e)[:120])
        lb.report(provider, False, latency)
        _credit.record(ExecutionEvent(node=BANDIT_NODE, success=False, latency=latency, model=model, strategy=task_type, error=str(e)))
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        metrics.record(provider, model, prompt, False, latency * 1000,
                     prompt_tokens, completion_tokens, total_tokens, cost, task_type)
        return None


async def _async_fallback_chain(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    candidates = [c for c in CREDIT_CANDIDATES() if c[0] != exclude]
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    ranked_remote = _bandit.rank_models(BANDIT_NODE, task_type, remote)
    ranked = local + ranked_remote
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)
    for provider, model in ranked:
        func = ASYNC_PROVIDERS.get(provider)
        if not func:
            continue
        result = await _async_safe_call(provider, func, prompt, model, task_type)
        if result:
            return result
    raise RuntimeError("Todos os providers falharam.")


def resolve_model(model: str) -> str:
    return model or "auto"


def escolher_modelo(prompt: str = "") -> str:
    """Seleciona modelo via BanditPolicy (eficiência/score). Deprecated: CognitiveProxy usa bandit próprio."""
    try:
        candidates = CREDIT_CANDIDATES()
        models = [m for _, m in candidates]
        return _bandit.select_model(BANDIT_NODE, "general", models)
    except Exception:
        return "auto"


async def async_route_generate(model: str, prompt: str, task_type: str = "general") -> str:
    model = str(model or "").strip().lower()
    if not model or model == "auto":
        best = lb.select(task_type)
        if best:
            func = ASYNC_PROVIDERS.get(best)
            if func:
                best_model = next((m for p, m in CREDIT_CANDIDATES() if p == best), None)
                if best_model:
                    result = await _async_safe_call(best, func, prompt, best_model, task_type)
                    if result:
                        return result
        return await _async_fallback_chain(prompt, exclude=best, task_type=task_type)
    provider = model.split("/")[0]
    func = ASYNC_PROVIDERS.get(provider)
    if not func:
        return await _async_fallback_chain(prompt, task_type=task_type)
    result = await _async_safe_call(provider, func, prompt, model, task_type)
    if result:
        return result
    return await _async_fallback_chain(prompt, exclude=provider, task_type=task_type)