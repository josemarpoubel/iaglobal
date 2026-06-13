# iaglobal/providers/provider_router.py

import asyncio
import inspect
import os
import time
from typing import Callable, List, Optional, Tuple

from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.providers.provider_state import ProviderState
from iaglobal.providers.provider_load_balancer import load_balancer as lb
from iaglobal.providers.provider_scorer import score_provider
from iaglobal.providers.provider_metrics import metrics, estimate_cost
from iaglobal.providers.token_usage import TokenCollector

from iaglobal.evolution.reward_aggregator import reward_aggregator, RewardMetrics
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.memory import cache

from iaglobal.utils.logger import logger

from iaglobal.providers.ollama_provider import generate as ollama_generate
from iaglobal.providers.groq_provider import generate as groq_generate
from iaglobal.providers.openrouter_provider import generate as openrouter_generate
from iaglobal.providers.nvidia_provider import generate as nvidia_generate
from iaglobal.providers.opencode_provider import generate as opencode_generate
from iaglobal.providers.gemini_provider import generate as gemini_generate
from iaglobal.providers.perplexity_provider import async_generate as perplexity_async_generate
from iaglobal.providers.openai_provider import generate as openai_generate
from iaglobal.providers.huggingchat_provider import async_generate as huggingchat_async_generate
from iaglobal.providers.hf_router_provider import async_generate as hf_router_async_generate
from iaglobal.providers.hf_router_provider import generate as hf_router_generate
from iaglobal.providers.hf_router_provider import generate as hf_router_qwen_generate
from iaglobal.providers.hf_router_provider import async_generate as hf_router_qwen_async_generate
from iaglobal.providers.hf_inference_provider import async_generate

from iaglobal.providers.ollama_provider import async_generate as ollama_async_generate
from iaglobal.providers.groq_provider import async_generate as groq_async_generate
from iaglobal.providers.openrouter_provider import async_generate as openrouter_async_generate
from iaglobal.providers.nvidia_provider import async_generate as nvidia_async_generate
from iaglobal.providers.opencode_provider import async_generate as opencode_async_generate
from iaglobal.providers.gemini_provider import async_generate as gemini_async_generate
from iaglobal.providers.openai_provider import async_generate as openai_async_generate
from iaglobal.providers.poe_provider import generate as poe_generate
from iaglobal.providers.poe_provider import async_generate as poe_async_generate


# Timeouts por provider
PROVIDER_TIMEOUT = {
    "ollama": 120,
    "groq": 15,
    "openrouter": 15,
    "nvidia": 15,
    "opencode": 15,
    "gemini": 15,
    "poe": 30,
    "perplexity": 15,
    "openai": 15,
    "huggingchat": 30,
    "hf_router": 30,
    "hf_router_qwen": 30,
    "hf_router_qwenext": 30,
    "hf_router_30b": 30,
    "hf_router_32b": 30,
    "hf_router_opus": 30,
    "hf_router_llama": 30,
    "hf_router_groq": 30,
    "hf_router_groq8": 30,
    "hf_router_hermes": 30,
    "hf_router_nemotron": 30,
    "hf_router_nemo2": 30,
    "hf_router_ultra": 30,
    "hf_router_oss": 30,
    "hf_router_oss2": 30,
    "hf_router_glm": 30,
    "hf_router_glm4": 30,
    "hf_router_glm5": 30,
    "hf_router_glm45": 30,
    "hf_router_phi4": 30,
    "hf_router_qwen36": 30,
    "hf_router_v4pro": 30,
    "hf_router_r1": 30,
    "hf_router_35": 30,
    "hf_router_amelia": 30,
    "hf_router_kimi": 30,
    "hf_router_minimax": 30,
    "hf_inference": 30,
}

PROVIDERS = {
    "ollama": ollama_generate,
    "groq": groq_generate,
    "openrouter": openrouter_generate,
    "nvidia": nvidia_generate,
    "opencode": opencode_generate,
    "gemini": gemini_generate,
    "openai": openai_generate,
    "hf_router": hf_router_generate,
    "hf_router_qwen": hf_router_generate,
    "hf_router_qwenext": hf_router_generate,
    "hf_router_30b": hf_router_generate,
    "hf_router_32b": hf_router_generate,
    "hf_router_opus": hf_router_generate,
    "hf_router_llama": hf_router_generate,
    "hf_router_groq": hf_router_generate,
    "hf_router_groq8": hf_router_generate,
    "hf_router_hermes": hf_router_generate,
    "hf_router_nemotron": hf_router_generate,
    "hf_router_nemo2": hf_router_generate,
    "hf_router_ultra": hf_router_generate,
    "hf_router_oss": hf_router_generate,
    "hf_router_oss2": hf_router_generate,
    "hf_router_glm": hf_router_generate,
    "hf_router_glm4": hf_router_generate,
    "hf_router_glm5": hf_router_generate,
    "hf_router_glm45": hf_router_generate,
    "hf_router_phi4": hf_router_generate,
    "hf_router_qwen36": hf_router_generate,
    "hf_router_v4pro": hf_router_generate,
    "hf_router_r1": hf_router_generate,
    "hf_router_35": hf_router_generate,
    "hf_router_amelia": hf_router_generate,
    "hf_router_kimi": hf_router_generate,
    "hf_router_minimax": hf_router_generate,
}

ASYNC_PROVIDERS = {
    "ollama": ollama_async_generate,
    "groq": groq_async_generate,
    "openrouter": openrouter_async_generate,
    "nvidia": nvidia_async_generate,
    "opencode": opencode_async_generate,
    "gemini": gemini_async_generate,
    "poe": poe_async_generate,
    "perplexity": perplexity_async_generate,
    "openai": openai_async_generate,
    "huggingchat": huggingchat_async_generate,
    "hf_router": hf_router_async_generate,
    "hf_router_qwen": hf_router_async_generate,
    "hf_router_qwenext": hf_router_async_generate,
    "hf_router_30b": hf_router_async_generate,
    "hf_router_32b": hf_router_async_generate,
    "hf_router_opus": hf_router_async_generate,
    "hf_router_llama": hf_router_async_generate,
    "hf_router_groq": hf_router_async_generate,
    "hf_router_groq8": hf_router_async_generate,
    "hf_router_hermes": hf_router_async_generate,
    "hf_router_nemotron": hf_router_async_generate,
    "hf_router_nemo2": hf_router_async_generate,
    "hf_router_ultra": hf_router_async_generate,
    "hf_router_oss": hf_router_async_generate,
    "hf_router_oss2": hf_router_async_generate,
    "hf_router_glm": hf_router_async_generate,
    "hf_router_glm4": hf_router_async_generate,
    "hf_router_glm5": hf_router_async_generate,
    "hf_router_glm45": hf_router_async_generate,
    "hf_router_phi4": hf_router_async_generate,
    "hf_router_qwen36": hf_router_async_generate,
    "hf_router_v4pro": hf_router_async_generate,
    "hf_router_r1": hf_router_async_generate,
    "hf_router_35": hf_router_async_generate,
    "hf_router_amelia": hf_router_async_generate,
    "hf_router_kimi": hf_router_async_generate,
    "hf_router_minimax": hf_router_async_generate,
}


def CREDIT_CANDIDATES():
    return [
        ("nvidia", "nvidia/mistralai/mistral-small-4-119b-2603"),
        ("opencode", "opencode/deepseek-v4-flash-free"),
        ("openrouter", "openrouter/meta-llama/llama-3.1-8b-instruct"),
        ("groq", "groq/llama-3.3-70b-versatile"),
        ("poe", "poe/GLM-5-T"),
        ("ollama", "ollama/qwen2.5:0.5b"),
    ]


_credit = CreditAssignmentEngine()
BANDIT_NODE = "model_router"

# Providers com chave de API válida no .env — podem ser desbanidos
_PROVIDERS_WITH_KEYS = {
    "ollama", "groq", "openrouter", "nvidia", "opencode",
    "gemini", "openai", "poe", "hf_router", "hf_inference",
}

_BANS_CLEARED = False


def _clear_circuit_breaker_bans():
    """Limpa bans de providers que têm API key, dando-lhes uma chance."""
    global _BANS_CLEARED
    if _BANS_CLEARED:
        return
    bandit = _get_bandit()
    cleared = []
    for provider in list(bandit._banned_providers.keys()):
        if provider in _PROVIDERS_WITH_KEYS:
            del bandit._banned_providers[provider]
            cleared.append(provider)
    if cleared:
        logger.info("[ROUTER] Bans limpos para %d providers com API key: %s", len(cleared), cleared)
    _BANS_CLEARED = True


def _get_bandit():
    """Retorna instância singleton do BanditPolicy."""
    from iaglobal.graphs.bandit import _get_bandit as get_global_bandit
    return get_global_bandit()

async def _async_safe_call(provider: str, func: Callable, prompt: str, model: str, task_type: str = "general") -> Optional[str]:
    """
    Executa a chamada HTTP real com enforce de timeout via asyncio.wait_for,
    cache em nível de roteador e coleta de métricas.
    """
    cache_key = f"{provider}:{model}:{prompt}"
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"[ROUTER] Cache HIT: {provider} ({model})")
        return cached

    start = time.time()
    timeout = PROVIDER_TIMEOUT.get(provider, 30)

    prompt_tokens = completion_tokens = total_tokens = 0
    def token_collector(pt, ct):
        nonlocal prompt_tokens, completion_tokens, total_tokens
        prompt_tokens, completion_tokens, total_tokens = pt, ct, pt + ct

    try:
        sig = inspect.signature(func)
        call_kwargs = {'prompt': prompt}
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

        if 'model' in sig.parameters or has_kwargs:
            call_kwargs['model'] = model
        if 'timeout' in sig.parameters or has_kwargs:
            call_kwargs['timeout'] = timeout
        if 'token_collector' in sig.parameters or has_kwargs:
            call_kwargs['token_collector'] = token_collector

        result = await asyncio.wait_for(func(**call_kwargs), timeout=timeout)

        latency = time.time() - start

        if not result:
            raise ValueError("Resposta vazia do provedor.")

        cache.set(cache_key, result)

        logger.info(f"[ROUTER] Sucesso: {provider} ({latency:.2f}s, {len(result)} chars)")

        lb.report(provider, True, latency)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(RewardMetrics(success=True, latency_ms=latency*1000, cost_usd=cost, token_count=total_tokens))
        _credit.record(ExecutionEvent(node=BANDIT_NODE, success=True, latency=latency, model=model, strategy=task_type, reward=reward))
        metrics.record(provider, model, prompt, True, latency*1000, prompt_tokens, completion_tokens, total_tokens, cost, task_type)

        return result

    except asyncio.CancelledError:
        raise

    except asyncio.TimeoutError:
        latency = time.time() - start
        logger.warning(f"[ROUTER] Timeout: {provider} ({latency:.2f}s)")
        lb.report(provider, False, latency)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(RewardMetrics(success=False, latency_ms=latency*1000, cost_usd=cost, error_type="timeout"))
        _credit.record(ExecutionEvent(node=BANDIT_NODE, success=False, latency=latency, model=model, strategy=task_type, error="timeout", reward=reward))
        return None

    except Exception as e:
        latency = time.time() - start
        error_str = str(e)
        logger.warning(f"[ROUTER] Falha: {provider} ({latency:.2f}s). Erro: {error_str[:100]}")

        lb.report(provider, False, latency)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(RewardMetrics(success=False, latency_ms=latency*1000, cost_usd=cost, error_type="execution_error"))
        _credit.record(ExecutionEvent(node=BANDIT_NODE, success=False, latency=latency, model=model, strategy=task_type, error=error_str, reward=reward))
        return None

async def _async_race_round(prompt: str, candidates: List[Tuple[str, str]], task_type: str, parallel_count: int) -> Optional[Tuple[str, str]]:
    """
    🏁 Dispara provedores em paralelo. Aguarda TODOS completarem e retorna o primeiro sucesso.
    """
    async def _race_one(provider: str, model: str):
        func = ASYNC_PROVIDERS.get(provider)
        if not func: return None
        res = await _async_safe_call(provider, func, prompt, model, task_type)
        if res:
            return provider, res
        return None

    tasks = [asyncio.create_task(_race_one(p, m), name=f"race_{p}") for p, m in candidates[:parallel_count]]
    if not tasks: return None

    try:
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=180)
            for t in done:
                try:
                    prov, text = t.result()
                    if prov and text:
                        for pt in pending:
                            pt.cancel()
                        return prov, text
                except Exception:
                    pass
            tasks = list(pending)
    except Exception as e:
        logger.error(f"[RACE] Erro fatal na corrida paralela: {e}")
        for t in tasks:
            t.cancel()

    return None

def _filter_blacklist(candidates: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Remove provedores banidos pelo Circuit Breaker do BanditPolicy."""
    bandit = _get_bandit()
    valid = []
    for p, m in candidates:
        provider_domain = m.split("/")[0] if "/" in m else p
        ban_expiry = bandit._banned_providers.get(provider_domain)
        if ban_expiry and time.monotonic() < ban_expiry:
            continue
        valid.append((p, m))
    return valid


async def async_route_generate_parallel(prompt: str, task_type: str = "general") -> str:
    """
    Ponto de Entrada Principal: Obtém ranking do Bandit e executa corridas paralelas por lotes (Batches).
    """
    logger.info(f"[ROUTER] 🏁 Iniciando Roteamento Paralelo (Task: {task_type})")
    
    _clear_circuit_breaker_bans()
    
    bandit = _get_bandit()
    # O BanditPolicy já removeu os modelos em Blacklist (Circuit Breaker)!
    candidates = CREDIT_CANDIDATES()
    ranked_models = bandit.rank_models(BANDIT_NODE, task_type, candidates)
    
    if not ranked_models:
        raise RuntimeError("Nenhum provedor sobreviveu ao Circuit Breaker. Abortando.")

    RACE_SIZE = int(os.environ.get("RACE_SIZE", "3"))
    
    # Processamento por lotes (Ex: Tenta os Top 3. Se todos falharem, tenta os próximos 3).
    for i in range(0, len(ranked_models), RACE_SIZE):
        batch = ranked_models[i:i + RACE_SIZE]
        logger.info(f"[ROUTER] 🏎️  Disparando Batch {i//RACE_SIZE + 1} com: {[p for p, m in batch]}")
        
        result = await _async_race_round(prompt, batch, task_type, parallel_count=RACE_SIZE)
        
        if result:
            provider, text = result
            logger.info(f"[ROUTER] 🏆 VENCEDOR DA CORRIDA: {provider}!")
            return text

    logger.warning("[ROUTER] Todos os provedores cloud falharam. Tentando Ollama como último recurso...")
    enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
    result = await _async_safe_call("ollama", ollama_async_generate, enriched, "ollama/qwen2.5:0.5b", task_type)
    if result:
        return result

    raise RuntimeError("Todos os lotes da corrida falharam. Nenhum provedor disponível.")

# ==============================================================================
# RETROCOMPATIBILIDADE SÍNCRONA (WRAPPER)
# ==============================================================================

def route_generate(model: str, prompt: str, task_type: str = "general") -> str:
    """Invólucro para chamadas legadas que não usam 'await'."""
    return asyncio.run(async_route_generate_parallel(prompt, task_type=task_type))

def escolher_modelo(prompt: str = "") -> str:
    """Delegado ao Bandit."""
    return _get_bandit().select_model(BANDIT_NODE, "general", [m for _, m in CREDIT_CANDIDATES()])


async def _enrich_prompt_with_learned_knowledge(prompt: str, task_type: str) -> str:
    """Busca exemplos aprendidos na KB e injeta no prompt quando for fallback local."""
    if task_type not in ("coding", "general"):
        return prompt
    try:
        from iaglobal.agents.knowledge_writer_agent import KnowledgeWriterAgent
        kw = KnowledgeWriterAgent()
        learned = kw.search_kb(task_type, limit=3)
        if learned and len(learned) > 0:
            examples = []
            for entry in learned[:3]:
                content = entry.get("content", "")[:500]
                if content and len(content) > 30:
                    examples.append(f"--- Exemplo aprendido ---\n{content}")
            if examples:
                enriched = prompt + "\n\n[EXEMPLOS APRENDIDOS PELO MODELO LOCAL]\n" + "\n\n".join(examples)
                logger.info("[RAG] Injetados %d exemplos aprendidos no prompt local", len(examples))
                return enriched
    except Exception as e:
        logger.debug("[RAG] Fallback RAG nao disponivel: %s", e)
    return prompt


async def _async_fallback_chain(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    _clear_circuit_breaker_bans()
    if os.environ.get("OLLAMA_ONLY", "").lower() in ("1", "true", "yes"):
        logger.info("[ROUTER] OLLAMA_ONLY ativo — async fallback chain direto para ollama")
        enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
        result = await _async_safe_call("ollama", ollama_async_generate, enriched, "ollama/qwen2.5:0.5b", task_type)
        if result:
            return result
        raise RuntimeError("Ollama falhou mesmo em modo OLLAMA_ONLY.")

    # Modo paralelo é o default. Para forçar sequencial: SEQUENTIAL_FALLBACK=yes
    sequential = os.environ.get("SEQUENTIAL_FALLBACK", "").lower() in ("1", "true", "yes")
    if sequential:
        return await _async_sequential_fallback(prompt, exclude, task_type)
    return await _async_parallel_fallback(prompt, exclude, task_type)


async def _async_sequential_fallback(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    """Fallback sequencial original: tenta um provider por vez."""
    candidates = _filter_blacklist([c for c in CREDIT_CANDIDATES() if c[0] != exclude])
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    ranked_remote = _get_bandit().rank_models(BANDIT_NODE, task_type, remote)
    ranked = ranked_remote + local
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)
    logger.info("[ROUTER] _async_sequential_fallback exclude=%s chain=%s", exclude, [p for p, _ in ranked])
    for provider, model in ranked:
        func = ASYNC_PROVIDERS.get(provider)
        if not func:
            continue
        final_prompt = prompt
        if provider == "ollama":
            final_prompt = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
        result = await _async_safe_call(provider, func, final_prompt, model, task_type)
        if result:
            logger.info("[ROUTER] _async_sequential_fallback succeeded provider=%s", provider)
            return result
        logger.info("[ROUTER] _async_sequential_fallback failed provider=%s trying next", provider)
    raise RuntimeError("Todos os providers falharam.")

async def _async_parallel_fallback(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    """🏁 Fallback paralelo: dispara N providers simultaneamente, pega o primeiro sucesso."""
    candidates = _filter_blacklist([c for c in CREDIT_CANDIDATES() if c[0] != exclude])
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    ranked_remote = _get_bandit().rank_models(BANDIT_NODE, task_type, remote)
    ranked = ranked_remote + local
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)

    RACE_SIZE = int(os.environ.get("RACE_SIZE", "3"))
    logger.info("[ROUTER] _async_parallel_fallback exclude=%s RACE_SIZE=%d pool=%d", exclude, RACE_SIZE, len(ranked))

    for i in range(0, len(ranked), RACE_SIZE):
        batch = ranked[i:i + RACE_SIZE]
        logger.info("[ROUTER] Race batch %d/%d: %s", i // RACE_SIZE + 1, (len(ranked) + RACE_SIZE - 1) // RACE_SIZE, [p for p, _ in batch])
        result = await _async_race_round(prompt, batch, task_type, parallel_count=RACE_SIZE)
        if result:
            provider, text = result
            logger.info("[ROUTER] _async_parallel_fallback succeeded provider=%s batch=%d", provider, i // RACE_SIZE + 1)
            return text

    raise RuntimeError("Todos os providers falharam mesmo em modo paralelo.")

def resolve_model(model: str) -> str:
    return model or "auto"

async def async_route_generate(model: str, prompt: str, task_type: str = "general") -> str:
    if os.environ.get("OLLAMA_ONLY", "").lower() in ("1", "true", "yes"):
        logger.info("[ROUTER] OLLAMA_ONLY ativo — roteando direto para ollama (async)")
        enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
        result = await _async_safe_call("ollama", ollama_async_generate, enriched, "ollama/qwen2.5:0.5b", task_type)
        if result:
            return result
        raise RuntimeError("Ollama falhou mesmo em modo OLLAMA_ONLY.")
    original = str(model or "").strip()
    if not original or original == "auto":
        return await async_route_generate_parallel(prompt, task_type=task_type)
    provider = original.split("/")[0]
    logger.info("[ROUTER] async_route_generate model=%s provider=%s task_type=%s", original, provider, task_type)
    func = ASYNC_PROVIDERS.get(provider)
    if not func:
        logger.info("[ROUTER] async_route_generate provider=%s not found in ASYNC_PROVIDERS -> fallback", provider)
        return await _async_fallback_chain(prompt, task_type=task_type)
    result = await _async_safe_call(provider, func, prompt, original, task_type)
    if result:
        return result
    logger.info("[ROUTER] async_route_generate primary=%s failed -> fallback", provider)
    return await _async_fallback_chain(prompt, exclude=provider, task_type=task_type)


def _fallback_chain(prompt: str, exclude: str = None, task_type: str = "general") -> str:
    _clear_circuit_breaker_bans()
    if os.environ.get("OLLAMA_ONLY", "").lower() in ("1", "true", "yes"):
        logger.info("[ROUTER] OLLAMA_ONLY ativo — sync fallback chain direto para ollama")
        result = _safe_call("ollama", ollama_generate, prompt, "ollama/qwen2.5:0.5b", task_type)
        if result:
            return result
        raise RuntimeError("Ollama falhou mesmo em modo OLLAMA_ONLY.")
    candidates = _filter_blacklist([c for c in CREDIT_CANDIDATES() if c[0] != exclude])
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    ranked_remote = _get_bandit().rank_models(BANDIT_NODE, task_type, remote)
    ranked = ranked_remote + local
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)
    logger.info("[ROUTER] _fallback_chain exclude=%s chain=%s", exclude, [p for p, _ in ranked])
    for provider, model in ranked:
        func = PROVIDERS.get(provider)
        if not func:
            continue
        result = _safe_call(provider, func, prompt, model, task_type)
        if result:
            logger.info("[ROUTER] _fallback_chain succeeded provider=%s", provider)
            return result
        logger.info("[ROUTER] _fallback_chain failed provider=%s trying next", provider)
    raise RuntimeError("Todos os providers falharam.")

