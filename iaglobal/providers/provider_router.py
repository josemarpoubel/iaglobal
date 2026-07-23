# iaglobal/providers/provider_router.py

import asyncio
import inspect
import os
import time
from collections import deque
from typing import Callable, List, Optional, Tuple

from iaglobal.providers.provider_metrics import metrics, estimate_cost

from iaglobal.evolution.reward_aggregator import reward_aggregator, RewardMetrics
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.memory import cache
from iaglobal.immunity.metabolic_immune_barrier import barrier

from iaglobal.utils.logger import logger
from iaglobal.utils.life_signal_collector import instrument

# Import opcional da BanditPolicy Evolutiva (Geração 2)
try:
    from iaglobal.policy import BanditPolicyEvolutiva

    EVOLUTIVA_DISPONIVEL = True
    logger.info("🧬 [GERAÇÃO 2] BanditPolicyEvolutiva carregada com sucesso!")
except ImportError:
    BanditPolicyEvolutiva = None
    EVOLUTIVA_DISPONIVEL = False
    logger.warning(
        "⚠️  BanditPolicyEvolutiva não disponível, usando BanditPolicy clássica"
    )

from iaglobal.providers.ollama_provider import async_generate as ollama_async_generate
from iaglobal.providers.contract import registry


# Bootstrap: importa cada módulo provider para disparar registry.register()
def _bootstrap_providers() -> None:
    import importlib

    _provider_modules = [
        "groq",
        "openrouter",
        "nvidia",
        "opencode",
        "gemini",
        "openai",
        "perplexity",
        "huggingchat",
        "poe",
        "hf_router",
        "hf_video",
    ]
    for _name in _provider_modules:
        try:
            importlib.import_module(f"iaglobal.providers.{_name}_provider")
        except ImportError:
            logger.debug("[ROUTER] Provider %s_nao_provider nao encontrado", _name)
    logger.debug(
        "[ROUTER] Bootstrap de providers concluido (ollama registrado via import direto)"
    )


_bootstrap_providers()

# ── CognitiveRouter: Tribunal Cognitivo de 3 Camadas ──────────────────────
# Mapeia tipo de tarefa → rota metabólica, extraindo capacidade do
# ProviderConfig.  Desacoplado do gerenciamento de buckets (Passo 3).
from iaglobal.providers.provider_config import (
    ProviderConfig,
    CognitiveRole,
    get_model_config,
    get_role_by_model_id,
)

from iaglobal.metabolism.bucket_manager import BucketManager


GLM4_MODEL_ID = get_model_config(CognitiveRole.JUIZ)["model_id"]
LFM_MODEL_ID = get_model_config(CognitiveRole.SENTINELA)["model_id"]
QWEN_MODEL_ID = get_model_config(CognitiveRole.OPERARIO)["model_id"]


async def _ollama_glm4_async(prompt: str, **kwargs) -> str:
    """Wrapper que roteia para o modelo Juiz (GLM4-1.2B)."""
    kwargs.pop("model", None)
    return await ollama_async_generate(prompt, model=GLM4_MODEL_ID, **kwargs)


async def _ollama_lfm_async(prompt: str, **kwargs) -> str:
    """Wrapper que roteia para o modelo Sentinela (LFM-230M)."""
    kwargs.pop("model", None)
    return await ollama_async_generate(prompt, model=LFM_MODEL_ID, **kwargs)


class CognitiveRouter:
    """Arbítrio de Custo Cognitivo — decide qual área do córtex ativar.

    Separa a intenção da tarefa (task_type / node_id) da capacidade do
    provedor.  O BucketManager (Passo 3) consumirá as mesmas chaves de
    rota para controlar concorrência por tier.
    """

    ROUTE_MAP: dict[str, str] = {
        # Layer 1 — Juiz (GLM4-1.2B): raciocínio profundo
        "critic": "ollama_glm4",
        "failure_analysis": "ollama_glm4",
        "arbitrar_geracao": "ollama_glm4",
        "pipeline.requirement_correction": "ollama_glm4",
        "system_design": "ollama_glm4",
        # Layer 2 — Operário (Qwen2.5-0.5B): geração e escrita
        "coder": "ollama",
        "multi_coder": "ollama",
        "backend_builder": "ollama",
        "frontend_builder": "ollama",
        "database_builder": "ollama",
        "api_builder": "ollama",
        "planner": "ollama",
        "pm": "ollama",
        "requirements": "ollama",
        "technology_selection": "ollama",
        "enhancement": "ollama",
        "doc_writer": "ollama",
        "artifact_writer": "ollama",
        "knowledge_writer": "ollama",
        "deployment_plan": "ollama",
        "task_breakdown": "ollama",
        "documentation": "ollama",
        # Layer 3 — Sentinela (LFM-230M): validação rápida
        "sandbox_validator": "ollama_lfm",
        "lsp_validator": "ollama_lfm",
        "semantic_validator": "ollama_lfm",
        "fix_validator": "ollama_lfm",
        "security_audit": "ollama_lfm",
        "performance_audit": "ollama_lfm",
        "compliance_audit": "ollama_lfm",
        "system_analysis": "ollama_lfm",
        "metrics": "ollama_lfm",
        "pipeline_updater": "ollama_lfm",
        "evolution_trigger": "ollama_lfm",
        "retrospective": "ollama_lfm",
        "gap_analyzer": "ollama_lfm",
        "evaluator": "ollama_lfm",
        "memory_cleaner": "ollama_lfm",
    }

    ROUTE_TO_MODEL: dict[str, str] = {
        "ollama_glm4": GLM4_MODEL_ID,
        "ollama": QWEN_MODEL_ID,
        "ollama_lfm": LFM_MODEL_ID,
    }

    @classmethod
    def resolve_route(cls, node_id: str, task_type: str = "general") -> str:
        """Retorna o nome da rota (ollama, ollama_glm4, ollama_lfm)."""
        route = cls.ROUTE_MAP.get(node_id)
        if route:
            return route
        # Heurística: validação vai para Sentinela, o resto para Operário
        if "valid" in task_type or "audit" in task_type or "monitor" in task_type:
            return "ollama_lfm"
        return "ollama"

    @classmethod
    def resolve_model_id(cls, route: str) -> str:
        """Retorna o model_id para uma rota."""
        return cls.ROUTE_TO_MODEL.get(route, QWEN_MODEL_ID)

    @classmethod
    def get_route_config(cls, route: str) -> dict | None:
        """Retorna a configuração metabólica completa de uma rota."""
        role = get_role_by_model_id(cls.ROUTE_TO_MODEL.get(route, ""))
        if role:
            return get_model_config(role)
        return None

    @classmethod
    def build_candidates(cls, route: str) -> list[str]:
        """Monta lista de candidatos para o BanditPolicy a partir de uma rota.

        Inclui fallback: se a rota principal falhar, tenta o fallback_role
        definido no ProviderConfig.  Ex: juiz → operario.
        """
        candidates = [f"ollama/{cls.ROUTE_TO_MODEL.get(route, QWEN_MODEL_ID)}"]
        config = cls.get_route_config(route)
        if config and config.get("fallback_role"):
            fallback_model = get_model_config(config["fallback_role"])["model_id"]
            candidates.append(f"ollama/{fallback_model}")
        return candidates


# ── Cognitive Dispatch: Router + Bucket + Provider ──────────────────────
# Integra o Tribunal Cognitivo (CognitiveRouter) com o Sistema Endócrino
# (BucketManager) para executar uma inferência no tier correto, respeitando
# os limites metabólicos e aplicando fallback se necessário.

_ROUTE_TIMEOUT: dict[str, float] = {
    "ollama_glm4": 120.0,  # Juiz: cold-load ~59s, margin 2x
    "ollama": 30.0,  # Operário: cold-load menor
    "ollama_lfm": 15.0,  # Sentinela: espera curta, depois bypass
}

_ESTIMATED_TOKENS: dict[str, int] = {
    "ollama_glm4": 2048,
    "ollama": 1024,
    "ollama_lfm": 512,
}


async def cognitive_dispatch(
    node_id: str,
    prompt: str,
    task_type: str = "general",
) -> str:
    """Roteia uma requisição LLM pelo Tribunal Cognitivo completo.

    1. CognitiveRouter.resolve_route(node_id, task_type) → nome da rota
    2. BucketManager.acquire_with_fallback(route) → concede recurso
    3. async_route_generate(model, prompt, ...) → executa
    4. BucketManager.release() → libera slot

    Se o Sentinela estiver exausto, o timeout curto (0.5s) faz o bypass
    automático — o Operário processa sem validação prévia.
    """
    bucket_mgr = await BucketManager.get_instance()
    route = CognitiveRouter.resolve_route(node_id, task_type)
    route_timeout = _ROUTE_TIMEOUT.get(route, 0.5)
    estimated = _ESTIMATED_TOKENS.get(route, 512)

    granted_route = await bucket_mgr.acquire_with_fallback(
        route,
        estimated_tokens=estimated,
        timeout=route_timeout,
    )

    if not granted_route:
        # Todos os níveis exaustos — degradação graciosa:
        # bypass completo, retorna fallback vazio.
        logger.warning(
            "[COGNITIVE] %s (%s): todos os tiers exaustos — bypass",
            node_id,
            route,
        )
        return ""

    try:
        raw_model = CognitiveRouter.resolve_model_id(granted_route)
        model = f"ollama/{raw_model}"
        logger.info(
            "[COGNITIVE] dispatch node=%s route=%s granted=%s model=%s",
            node_id,
            route,
            granted_route,
            model,
        )
        result = await async_route_generate(
            model=model,
            prompt=prompt,
            task_type=task_type,
            node_id=node_id,
        )
        return result or ""
    finally:
        await bucket_mgr.release(granted_route)


# Timeouts por provider (aumentados para evitar falhas prematuras)
PROVIDER_TIMEOUT = {
    "ollama": 180,
    "ollama_glm4": 300,
    "ollama_lfm": 120,
    "groq": 60,
    "openrouter": 90,
    "nvidia": 120,
    "opencode": 90,
    "gemini": 90,
    "poe": 240,
    "perplexity": 90,
    "openai": 90,
    "huggingchat": 90,
    "hf_router": 90,
    "hf_video": 300,
    "hf_router_qwen": 90,
    "hf_router_qwenext": 90,
    "hf_router_30b": 90,
    "hf_router_32b": 90,
    "hf_router_opus": 90,
    "hf_router_llama": 90,
    "hf_router_groq": 90,
    "hf_router_groq8": 90,
    "hf_router_hermes": 90,
    "hf_router_nemotron": 90,
    "hf_router_nemo2": 60,
    "hf_router_ultra": 60,
    "hf_router_oss": 60,
    "hf_router_oss2": 60,
    "hf_router_glm": 60,
    "hf_router_glm4": 60,
    "hf_router_glm5": 60,
    "hf_router_glm45": 60,
    "hf_router_glm5f": 60,
    "hf_router_phi4": 60,
    "hf_router_qwen36": 60,
    "hf_router_v4pro": 60,
    "hf_router_r1": 60,
    "hf_router_35": 60,
    "hf_router_amelia": 60,
    "hf_router_kimi": 60,
    "hf_router_minimax": 60,
    "hf_inference": 60,
}

# Constrói PROVIDERS e ASYNC_PROVIDERS dinamicamente a partir do Registry
# Aliases não-padrão (ollama_glm4, ollama_lfm, hf_router_*) são adicionados explicitamente.
_HF_ROUTER_ALIASES = [
    "hf_router_qwen",
    "hf_router_qwenext",
    "hf_router_30b",
    "hf_router_32b",
    "hf_router_opus",
    "hf_router_llama",
    "hf_router_groq",
    "hf_router_groq8",
    "hf_router_hermes",
    "hf_router_nemotron",
    "hf_router_nemo2",
    "hf_router_ultra",
    "hf_router_oss",
    "hf_router_oss2",
    "hf_router_glm",
    "hf_router_glm4",
    "hf_router_glm5",
    "hf_router_glm45",
    "hf_router_glm5f",
    "hf_router_phi4",
    "hf_router_qwen36",
    "hf_router_v4pro",
    "hf_router_r1",
    "hf_router_35",
    "hf_router_amelia",
    "hf_router_kimi",
    "hf_router_minimax",
]

PROVIDERS: dict[str, Callable] = dict(registry.sync)
ASYNC_PROVIDERS: dict[str, Callable] = dict(registry.async_)

# Aliases sync — ollama_glm4/lfm + hf_router_*
if "ollama" in PROVIDERS:
    _o_sync = PROVIDERS["ollama"]
    PROVIDERS.setdefault(
        "ollama_glm4", lambda p, **k: _o_sync(p, model=GLM4_MODEL_ID, **k)
    )
    PROVIDERS.setdefault(
        "ollama_lfm", lambda p, **k: _o_sync(p, model=LFM_MODEL_ID, **k)
    )
if "hf_router" in PROVIDERS:
    _hfr_sync = PROVIDERS["hf_router"]
    for _a in _HF_ROUTER_ALIASES:
        PROVIDERS.setdefault(_a, _hfr_sync)

# Aliases async — wrappers + hf_router_*
if "ollama" in ASYNC_PROVIDERS:
    ASYNC_PROVIDERS.setdefault("ollama_glm4", _ollama_glm4_async)
    ASYNC_PROVIDERS.setdefault("ollama_lfm", _ollama_lfm_async)
if "hf_router" in ASYNC_PROVIDERS:
    _hfra = ASYNC_PROVIDERS["hf_router"]
    for _a in _HF_ROUTER_ALIASES:
        ASYNC_PROVIDERS.setdefault(_a, _hfra)


# ==============================================================================
# MEMBRANA SELETIVA — ACESSO A MODELOS EXTERNOS (APENAS O AGENTE CRÍTICO)
# ==============================================================================
# Pressão seletiva evolutiva (intenção do arquiteto): os agentes só atingem
# modelos cloud (Groq/NVIDIA/OpenRouter/Gemini/...) quando são o agente crítico,
# que aponta correções. Todos os demais usam Ollama local, forçando-os a evoluir
# com o próprio substrato (Lei da Evolução: adaptar ou perecer).
_LOCAL_PROVIDERS = {"ollama", "ollama_glm4", "ollama_lfm"}


# Sinal estruturado de membrana — INDEPENDENTE de nível de log (observabilidade
# não deve depender de WARNING/INFO, como o bug de suppressão de INFO no CLI
# já demonstrou). Guardas E2E e operadores leem este deque sem parsear logs.
_MEMBRANE_DECISIONS: "deque" = deque(maxlen=512)


def record_membrane_decision(node_id: str, action: str, candidates) -> None:
    """Registra uma decisão de membrana de forma estruturada e nível-independente.

    action: 'confined_local' | 'authorized_cloud' | 'redirected_local'
    """
    _MEMBRANE_DECISIONS.append(
        {
            "node_id": node_id,
            "action": action,
            "candidates": [c if isinstance(c, str) else c[1] for c in candidates],
            "ts": time.time(),
        }
    )


def _external_gate_enabled() -> bool:
    """Portão de modelo externo ativo? Env tem precedência sobre flag epigenética."""
    import os

    env = os.getenv("EXTERNAL_ACCESS_ONLY_CRITIC")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    try:
        from iaglobal.evolution import is_flag_enabled

        if is_flag_enabled("external_access_only_critic"):
            return True
    except Exception:
        pass
    return False


def _authorized_external_agents() -> set:
    import os

    auth = {"critic"}
    env = os.getenv("EXTERNAL_AUTHORIZED_AGENTS")
    if env:
        for a in env.split(","):
            a = a.strip().lower()
            if a:
                auth.add(a)
    return auth


def _is_external_authorized(node_id: str) -> bool:
    if not _external_gate_enabled():
        return True
    if not node_id:
        return False
    nid = node_id.lower()
    if nid in _authorized_external_agents():
        return True
    # Robustez a nomes (critic_agent, no_critic, CriticAgent, evo-critic...)
    if "critic" in nid:
        return True
    return False


def _force_local_model(node_id: str) -> bool:
    """True se o chamador NÃO tem direito a modelo externo (deve usar Ollama)."""
    return not _is_external_authorized(node_id)


def _policy_candidates(task_type: str, node_id: str) -> List[Tuple[str, str]]:
    """Candidatos respeitando a membrana seletiva: remove cloud se não autorizado."""
    cands = CREDIT_CANDIDATES(task_type)
    if _force_local_model(node_id):
        local = [c for c in cands if c[0] in _LOCAL_PROVIDERS]
        if local:
            logger.info(
                "[MEMBRANA] node_id='%s' sem direito a modelo externo — "
                "restrito a Ollama local (pressão evolutiva)",
                node_id,
            )
            record_membrane_decision(node_id, "confined_local", local)
            return local
    record_membrane_decision(node_id, "authorized_cloud", cands)
    return cands


def _provider_has_key(provider: str) -> bool:
    """Verifica se um provider cloud tem API key configurada.
    Providers locais (ollama) sempre retornam True.
    """
    if provider == "ollama":
        return True
    try:
        from iaglobal.providers.provider_config import ProviderConfig

        key_map = {
            "groq": ProviderConfig.GROQ_API_KEY,
            "nvidia": ProviderConfig.NVIDIA_API_KEY,
            "openrouter": ProviderConfig.OPENROUTER_API_KEY,
            "gemini": ProviderConfig.GEMINI_API_KEY,
            "poe": ProviderConfig.POE_API_KEY,
            "opencode": ProviderConfig.OPENCODE_API_KEY,
            "perplexity": ProviderConfig.PERPLEXITY_API_KEY,
            "hf_router": ProviderConfig.HUGGINGFACE_API_KEY,
        }
        return bool(key_map.get(provider))
    except Exception:
        return False


def CREDIT_CANDIDATES(task_type: str = "general"):
    """Retorna modelos candidatos baseados no tipo de tarefa.

    task_type: "general", "image", "video", "code", etc.
    Filtra providers cloud que não têm API key configurada.
    """
    if task_type == "image":
        return [
            ("hf_router", "hf_router/stable-diffusion-xl"),
            ("hf_router", "hf_router/flux-schnell"),
        ]
    if task_type == "video":
        return [
            ("hf_video", "hf_video/wan2.1"),
            ("hf_video", "hf_video/ltx"),
            ("hf_video", "hf_video/hunyuan"),
        ]
    candidates = [
        ("groq", "groq/llama-3.3-70b-versatile"),
        ("nvidia", "nvidia/mistralai/mistral-large-3-675b-instruct-2512"),
        ("ollama", "ollama/qwen2.5:0.5b"),
    ]
    return [(p, m) for p, m in candidates if _provider_has_key(p)]


_credit = None  # Inicializado lazy em _get_credit() para usar singleton do Bandit
BANDIT_NODE = "model_router"

# Sinaliza se a resposta servida veio de cache (hit) dentro da task corrente.
# Usado para NÃO inflacionar a Produtividade (P) e a Eficiência (E) do IVM:
# servir do cache não é geração real do agente (evita métrica falsa de "bom").
from contextvars import ContextVar

_SERVED_FROM_CACHE: ContextVar[bool] = ContextVar("served_from_cache", default=False)


def _get_credit() -> CreditAssignmentEngine:
    """Retorna CreditAssignmentEngine singleton (compartilhado com BanditPolicy)."""
    global _credit
    if _credit is None:
        _credit = _get_bandit().credit_engine
    return _credit


# Providers com chave de API válida no .env — podem ser desbanidos
_PROVIDERS_WITH_KEYS = {
    "ollama",
    "groq",
    "openrouter",
    "nvidia",
    "opencode",
    "gemini",
    "openai",
    "poe",
    "hf_router",
    "hf_video",
    "hf_router_glm5f",
    "hf_inference",
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

    # Também limpa os bloqueios no nível HTTP (async_http._BLOCKED_PROVIDERS)
    from iaglobal.providers.async_http import _BLOCKED_PROVIDERS

    http_cleared = []
    if isinstance(_BLOCKED_PROVIDERS, dict):
        for provider in list(_BLOCKED_PROVIDERS.keys()):
            if provider in _PROVIDERS_WITH_KEYS:
                del _BLOCKED_PROVIDERS[provider]
                http_cleared.append(provider)
    elif isinstance(_BLOCKED_PROVIDERS, list):
        # Lista de providers bloqueados — limpa apenas os que têm key
        for provider in list(_BLOCKED_PROVIDERS):
            if provider in _PROVIDERS_WITH_KEYS:
                _BLOCKED_PROVIDERS.remove(provider)
                http_cleared.append(provider)
    if http_cleared:
        logger.info(
            "[ROUTER] Bans HTTP limpos para %d providers: %s",
            len(http_cleared),
            http_cleared,
        )

    if cleared:
        logger.info(
            "[ROUTER] Bans limpos para %d providers com API key: %s",
            len(cleared),
            cleared,
        )
    _BANS_CLEARED = True


def _registrar_evolucao(
    provider: str, ivm: float, latencia_ms: float, custo: float, sucesso: bool
):
    """
    Registra execução na BanditPolicyEvolutiva para aprendizado contínuo.

    Esta função conecta o IVM do agent com o fitness do provider,
    criando o feedback loop evolutivo da Geração 2.
    """
    if not EVOLUTIVA_DISPONIVEL:
        return

    try:
        bandit = _get_bandit()
        if isinstance(bandit, BanditPolicyEvolutiva):
            # Registra de forma assíncrona (não bloqueia)
            asyncio.create_task(
                bandit.registrar_execucao(
                    provider_id=provider,
                    ivm=ivm,
                    latencia_ms=latencia_ms,
                    custo_creditos=custo,
                    sucesso=sucesso,
                ),
                name=f"evolucao_{provider}",
            )
            logger.debug(f"🧬 [EVOLUÇÃO] {provider}: IVMA={ivm:.3f}, sucesso={sucesso}")
    except Exception as e:
        logger.error(f"[EVOLUÇÃO] Erro ao registrar: {e}")


def _get_bandit():
    """
    Retorna instância singleton do BanditPolicy.

    Se EVOLUTIVA_DISPONIVEL=True e USE_BANDIT_EVOLUTIVA=True, retorna BanditPolicyEvolutiva.
    Caso contrário, retorna BanditPolicy clássica.
    """
    from iaglobal.graphs.bandit import _get_bandit as get_global_bandit

    # Verifica se deve usar versão evolutiva
    use_evolutiva = os.getenv("USE_BANDIT_EVOLUTIVA", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    if use_evolutiva and EVOLUTIVA_DISPONIVEL:
        # Retorna instância singleton da BanditPolicyEvolutiva
        if not hasattr(_get_bandit, "_bandit_evolutiva_instance"):
            from pathlib import Path

            _get_bandit._bandit_evolutiva_instance = BanditPolicyEvolutiva(
                epsilon=float(os.getenv("BANDIT_EPSILON", "0.2")),
                decay=float(os.getenv("BANDIT_DECAY", "0.995")),
                db_path=Path("iaglobal/memory/bandit_evolutivo.json"),
            )
            logger.info("🧬 [GERAÇÃO 2] BanditPolicyEvolutiva inicializada!")

        bandit = _get_bandit._bandit_evolutiva_instance
        logger.debug("[ROUTER] Usando BanditPolicy EVOLUTIVA")
        return bandit

    # Fallback para BanditPolicy clássica
    logger.debug("[ROUTER] Usando BanditPolicy CLÁSSICA")
    return get_global_bandit()


async def _async_safe_call(
    provider: str,
    func: Callable,
    prompt: str,
    model: str,
    task_type: str = "general",
    retry_count: int = 0,
    max_retries: int = 2,
) -> Optional[str]:
    """
    Executa a chamada HTTP real com enforce de timeout via asyncio.wait_for,
    cache em nível de roteador e coleta de métricas.
    """
    cache_key = f"{provider}:{model}:{prompt}"
    entry = cache.get_entry(cache_key)
    if entry:
        cached = entry["value"]
        logger.debug(f"[ROUTER] Cache HIT (válido): {provider} ({model})")
        # Telemetria honesta: preserva o token_count real (antes hardcoded 0),
        # cumprindo a Lei 1 (a célula sente seu próprio estado metabólico).
        latency = 0.001  # ~1ms para cache hit
        cost = 0.0
        real_tokens = entry.get("tokens", 0)
        reward = reward_aggregator.calculate_reward(
            RewardMetrics(
                success=True, latency_ms=1, cost_usd=0.0, token_count=real_tokens
            )
        )
        _get_credit().record(
            ExecutionEvent(
                node=BANDIT_NODE,
                success=True,
                latency=latency,
                model=model,
                strategy=task_type,
                reward=reward,
            )
        )
        metrics.record(
            provider,
            model,
            prompt,
            True,
            latency * 1000,
            0,
            0,
            real_tokens,
            cost,
            task_type,
        )
        barrier.record(
            "cache_valid_hit",
            detail=f"{provider}/{model} tokens={real_tokens}",
            agent=provider,
        )
        _SERVED_FROM_CACHE.set(True)  # marca para o IVM não creditar produtividade
        return cached

    start = time.time()
    timeout = PROVIDER_TIMEOUT.get(provider, 30)

    prompt_tokens = completion_tokens = total_tokens = 0

    def token_collector(pt, ct):
        nonlocal prompt_tokens, completion_tokens, total_tokens
        prompt_tokens, completion_tokens, total_tokens = pt, ct, pt + ct

    try:
        sig = inspect.signature(func)
        call_kwargs = {"prompt": prompt}
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

        if "model" in sig.parameters or has_kwargs:
            call_kwargs["model"] = model
        if "timeout" in sig.parameters or has_kwargs:
            call_kwargs["timeout"] = timeout
        if "token_collector" in sig.parameters or has_kwargs:
            call_kwargs["token_collector"] = token_collector

        result = await asyncio.wait_for(func(**call_kwargs), timeout=timeout)

        latency = time.time() - start

        if not result:
            if retry_count < max_retries:
                logger.warning(
                    f"[ROUTER] Resposta vazia de {provider}. Tentando retry #{retry_count + 1}/{max_retries}"
                )
                await asyncio.sleep(1 * (retry_count + 1))  # Backoff exponencial
                return await _async_safe_call(
                    provider,
                    func,
                    prompt,
                    model,
                    task_type,
                    retry_count + 1,
                    max_retries,
                )
            raise ValueError("Resposta vazia do provedor.")

        cache.set(cache_key, result, total_tokens)

        logger.info(
            f"[ROUTER] Sucesso: {provider} ({latency:.2f}s, {len(result)} chars)"
        )

        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(
            RewardMetrics(
                success=True,
                latency_ms=latency * 1000,
                cost_usd=cost,
                token_count=total_tokens,
            )
        )
        _get_credit().record(
            ExecutionEvent(
                node=BANDIT_NODE,
                success=True,
                latency=latency,
                model=model,
                strategy=task_type,
                reward=reward,
            )
        )
        metrics.record(
            provider,
            model,
            prompt,
            True,
            latency * 1000,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost,
            task_type,
        )

        return result

    except asyncio.CancelledError:
        raise

    except asyncio.TimeoutError:
        latency = time.time() - start
        logger.warning(f"[ROUTER] Timeout: {provider} ({latency:.2f}s)")
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(
            RewardMetrics(
                success=False,
                latency_ms=latency * 1000,
                cost_usd=cost,
                error_type="timeout",
            )
        )
        _get_credit().record(
            ExecutionEvent(
                node=BANDIT_NODE,
                success=False,
                latency=latency,
                model=model,
                strategy=task_type,
                error="timeout",
                reward=reward,
            )
        )
        return None

    except Exception as e:
        latency = time.time() - start
        error_str = str(e)
        logger.warning(
            f"[ROUTER] Falha: {provider} ({latency:.2f}s). Erro: {error_str[:100]}"
        )

        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        reward = reward_aggregator.calculate_reward(
            RewardMetrics(
                success=False,
                latency_ms=latency * 1000,
                cost_usd=cost,
                error_type="execution_error",
            )
        )
        _get_credit().record(
            ExecutionEvent(
                node=BANDIT_NODE,
                success=False,
                latency=latency,
                model=model,
                strategy=task_type,
                error=error_str,
                reward=reward,
            )
        )
        return None


async def _async_race_round(
    prompt: str, candidates: List[Tuple[str, str]], task_type: str, parallel_count: int
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    🏁 Dispara provedores em paralelo. Aguarda TODOS completarem e retorna o primeiro sucesso.
    """

    async def _race_one(provider: str, model: str):
        func = ASYNC_PROVIDERS.get(provider)
        if not func:
            return None, None, False
        res = await _async_safe_call(provider, func, prompt, model, task_type)
        if res:
            return provider, res, _SERVED_FROM_CACHE.get()
        return None, None, False

    tasks = [
        asyncio.create_task(_race_one(p, m), name=f"race_{p}")
        for p, m in candidates[:parallel_count]
    ]
    if not tasks:
        return None

    try:
        while tasks:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED, timeout=180
            )
            for t in done:
                try:
                    prov, text, hit = t.result()
                    if prov and text:
                        for pt in pending:
                            pt.cancel()
                        return prov, text, hit
                except Exception:
                    pass
            tasks = list(pending)
    except Exception as e:
        logger.error(f"[RACE] Erro fatal na corrida paralela: {e}")
        for t in tasks:
            t.cancel()

    return None, None, False


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


async def async_route_generate_parallel(
    prompt: str, task_type: str = "general", node_id: str = "provider_router"
) -> str:
    """
    Ponto de Entrada Principal: Obtém ranking do Bandit e executa corridas paralelas por lotes (Batches).
    """
    start = time.time()
    result = None
    _SERVED_FROM_CACHE.set(
        False
    )  # reset por chamada; marcado se vencedor veio de cache
    try:
        logger.info(f"[ROUTER] 🏁 Iniciando Roteamento Paralelo (Task: {task_type})")

        _clear_circuit_breaker_bans()

        bandit = _get_bandit()
        # O BanditPolicy já removeu os modelos em Blacklist (Circuit Breaker)!
        # Membrana seletiva: agentes não-críticos só enxergam Ollama local.
        candidates = _policy_candidates(task_type, node_id)
        model_names = [m for _, m in candidates]
        ranked_models = bandit.rank_models(BANDIT_NODE, task_type, model_names)

        if not ranked_models:
            raise RuntimeError(
                "Nenhum provedor sobreviveu ao Circuit Breaker. Abortando."
            )

        # Skip precoce: se Ollama está offline, nem tenta fallback local
        _ollama_offline = bandit._is_offline("ollama")
        if _ollama_offline:
            logger.warning("[ROUTER] Ollama offline — pulando fallback local")

        RACE_SIZE = int(os.environ.get("RACE_SIZE", "3"))

        # Processamento por lotes (Ex: Tenta os Top 3. Se todos falharem, tenta os próximos 3).
        for i in range(0, len(ranked_models), RACE_SIZE):
            batch_ranked = ranked_models[i : i + RACE_SIZE]
            # Converte (score, model_name) de volta para (provider, model) para _async_race_round
            batch = []
            for _, model_name in batch_ranked:
                for provider, candidate_model in candidates:
                    if candidate_model == model_name:
                        batch.append((provider, candidate_model))
                        break
            logger.info(
                f"[ROUTER] 🏎️  Disparando Batch {i // RACE_SIZE + 1} com: {[p for p, m in batch]}"
            )

            winner = await _async_race_round(
                prompt, batch, task_type, parallel_count=RACE_SIZE
            )

            if winner and winner[1]:
                provider, text, winner_cache_hit = winner
                logger.info(f"[ROUTER] 🏆 VENCEDOR DA CORRIDA: {provider}!")
                result = text
                _SERVED_FROM_CACHE.set(winner_cache_hit)  # propaga para o IVM
                return result

        if _ollama_offline:
            raise RuntimeError(
                "Todos os provedores falharam e Ollama está offline. Nenhum provedor disponível."
            )

        logger.warning(
            "[ROUTER] Todos os provedores cloud falharam. Tentando Ollama como último recurso..."
        )
        enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
        result = await _async_safe_call(
            "ollama", ollama_async_generate, enriched, "ollama/qwen2.5:0.5b", task_type
        )
        if result:
            return result

        raise RuntimeError(
            "Todos os lotes da corrida falharam. Nenhum provedor disponível."
        )
    finally:
        success = bool(result and str(result).strip())
        await _report_ivm_telemetry(
            node_id,
            success,
            time.time() - start,
            "parallel",
            cache_hit=_SERVED_FROM_CACHE.get(),
        )


# ==============================================================================
# RETROCOMPATIBILIDADE SÍNCRONA (WRAPPER)
# ==============================================================================


async def route_generate(
    model: str,
    prompt: str,
    task_type: str = "general",
    node_id: str = "provider_router",
) -> str:
    """Roteia para o provider adequado via bandit."""
    return await async_route_generate(
        model, prompt, task_type=task_type, node_id=node_id
    )


def escolher_modelo(prompt: str = "", task_type: str = "general") -> str:
    """Delegado ao Bandit com task_type awareness."""
    return _get_bandit().select_model(
        BANDIT_NODE, task_type, [m for _, m in CREDIT_CANDIDATES(task_type)]
    )


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
                enriched = (
                    prompt
                    + "\n\n[EXEMPLOS APRENDIDOS PELO MODELO LOCAL]\n"
                    + "\n\n".join(examples)
                )
                logger.info(
                    "[RAG] Injetados %d exemplos aprendidos no prompt local",
                    len(examples),
                )
                return enriched
    except Exception as e:
        logger.debug("[RAG] Fallback RAG nao disponivel: %s", e)
    return prompt


async def _async_fallback_chain(
    prompt: str,
    exclude: str = None,
    task_type: str = "general",
    node_id: str = "provider_router",
) -> str:
    _clear_circuit_breaker_bans()
    if os.environ.get("OLLAMA_ONLY", "").lower() in ("1", "true", "yes"):
        logger.info(
            "[ROUTER] OLLAMA_ONLY ativo — async fallback chain direto para ollama"
        )
        enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
        # Tenta CognitiveRouter primeiro para respeitar a role do node_id
        try:
            route = CognitiveRouter.resolve_route(node_id, task_type)
            fallback_model = f"ollama/{CognitiveRouter.resolve_model_id(route)}"
        except Exception:
            fallback_model = "ollama/qwen2.5:0.5b"
        result = await _async_safe_call(
            "ollama", ollama_async_generate, enriched, fallback_model, task_type
        )
        if result:
            return result
        raise RuntimeError(
            f"Ollama falhou mesmo em modo OLLAMA_ONLY (model={fallback_model})."
        )

    # Modo paralelo é o default. Para forçar sequencial: SEQUENTIAL_FALLBACK=yes
    sequential = os.environ.get("SEQUENTIAL_FALLBACK", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if sequential:
        return await _async_sequential_fallback(
            prompt, exclude, task_type, node_id=node_id
        )
    return await _async_parallel_fallback(prompt, exclude, task_type, node_id=node_id)


def _reconcile_ranked(ranked_scores: list, candidates: list) -> list:
    """Converte [(score, model_name)] de volta para [(provider, model)]."""
    result = []
    seen = set()
    for _, model_name in ranked_scores:
        for provider, candidate_model in candidates:
            if candidate_model == model_name and model_name not in seen:
                result.append((provider, candidate_model))
                seen.add(model_name)
                break
    # Append any candidates not in ranked_scores
    for provider, model in candidates:
        if model not in seen:
            result.append((provider, model))
            seen.add(model)
    return result


async def _async_sequential_fallback(
    prompt: str,
    exclude: str = None,
    task_type: str = "general",
    node_id: str = "provider_router",
) -> str:
    """Fallback sequencial original: tenta um provider por vez."""
    candidates = _filter_blacklist(
        [c for c in _policy_candidates(task_type, node_id) if c[0] != exclude]
    )
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    remote_model_names = [m for _, m in remote]
    ranked_scores = _get_bandit().rank_models(
        BANDIT_NODE, task_type, remote_model_names
    )
    ranked = _reconcile_ranked(ranked_scores, remote) + local
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)
    logger.info(
        "[ROUTER] _async_sequential_fallback exclude=%s chain=%s",
        exclude,
        [p for p, _ in ranked],
    )
    for provider, model in ranked:
        func = ASYNC_PROVIDERS.get(provider)
        if not func:
            continue
        final_prompt = prompt
        if provider == "ollama":
            final_prompt = await _enrich_prompt_with_learned_knowledge(
                prompt, task_type
            )
        result = await _async_safe_call(provider, func, final_prompt, model, task_type)
        if result:
            logger.info(
                "[ROUTER] _async_sequential_fallback succeeded provider=%s", provider
            )
            return result
        logger.info(
            "[ROUTER] _async_sequential_fallback failed provider=%s trying next",
            provider,
        )
    raise RuntimeError("Todos os providers falharam.")


async def _async_parallel_fallback(
    prompt: str,
    exclude: str = None,
    task_type: str = "general",
    node_id: str = "provider_router",
) -> str:
    """🏁 Fallback paralelo: dispara N providers simultaneamente, pega o primeiro sucesso."""
    candidates = _filter_blacklist(
        [c for c in _policy_candidates(task_type, node_id) if c[0] != exclude]
    )
    local = [c for c in candidates if c[0] == "ollama"]
    remote = [c for c in candidates if c[0] != "ollama"]
    remote_model_names = [m for _, m in remote]
    ranked_scores = _get_bandit().rank_models(
        BANDIT_NODE, task_type, remote_model_names
    )
    ranked = _reconcile_ranked(ranked_scores, remote) + local
    ollama_entry = next((c for c in CREDIT_CANDIDATES() if c[0] == "ollama"), None)
    if ollama_entry and ollama_entry not in ranked:
        ranked.append(ollama_entry)

    RACE_SIZE = int(os.environ.get("RACE_SIZE", "3"))
    logger.info(
        "[ROUTER] _async_parallel_fallback exclude=%s RACE_SIZE=%d pool=%d",
        exclude,
        RACE_SIZE,
        len(ranked),
    )

    for i in range(0, len(ranked), RACE_SIZE):
        batch = ranked[i : i + RACE_SIZE]
        logger.info(
            "[ROUTER] Race batch %d/%d: %s",
            i // RACE_SIZE + 1,
            (len(ranked) + RACE_SIZE - 1) // RACE_SIZE,
            [p for p, _ in batch],
        )
        result = await _async_race_round(
            prompt, batch, task_type, parallel_count=RACE_SIZE
        )
        if result and result[1]:
            provider, text, _hit = result
            logger.info(
                "[ROUTER] _async_parallel_fallback succeeded provider=%s batch=%d",
                provider,
                i // RACE_SIZE + 1,
            )
            return text

    raise RuntimeError("Todos os providers falharam mesmo em modo paralelo.")


def resolve_model(model: str) -> str:
    return model or "auto"


@instrument(name="provider_router.async_route_generate")
async def async_route_generate(
    model: str,
    prompt: str,
    task_type: str = "general",
    node_id: str = "provider_router",
) -> str:
    """Roteia para o provider adequado via bandit (gateway universal de LLM).

    node_id permite atribuir custo metabólico (IVM) ao agente/nó originário.
    """
    # PSC §1 (tertiary defense): se não for crítico e pediu cloud, bloqueia
    if (
        node_id
        and "critic" not in node_id.lower()
        and model
        and model.split("/")[0] not in _LOCAL_PROVIDERS
    ):
        logger.warning(
            "[PSC] node_id='%s' nao critico tentou cloud '%s' — rebaixando para local",
            node_id,
            model,
        )
        model = f"ollama/{model.split('/')[-1] if '/' in model else 'qwen2.5:0.5b'}"

    start = time.time()
    delegated = False
    result = None
    _SERVED_FROM_CACHE.set(False)
    original = str(model or "").strip()
    try:
        if os.environ.get("OLLAMA_ONLY", "").lower() in ("1", "true", "yes"):
            effective = (
                original if original and original != "auto" else "ollama/qwen2.5:0.5b"
            )
            effective = CognitiveRouter.ROUTE_TO_MODEL.get(effective, effective)
            logger.info(
                "[ROUTER] OLLAMA_ONLY ativo — roteando direto para ollama (model=%s)",
                effective,
            )
            enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
            result = await _async_safe_call(
                "ollama",
                ollama_async_generate,
                enriched,
                effective,
                task_type,
            )
            if result:
                return result
            raise RuntimeError(
                f"Ollama falhou mesmo em modo OLLAMA_ONLY (model={effective})."
            )
        if not original or original == "auto":
            delegated = True
            return await async_route_generate_parallel(
                prompt, task_type=task_type, node_id=node_id
            )
        provider = original.split("/")[0] if "/" in original else "ollama"
        logger.info(
            "[ROUTER] async_route_generate model=%s provider=%s task_type=%s",
            original,
            provider,
            task_type,
        )

        # Membrana seletiva: agente não-crítico solicitou modelo externo →
        # redireciona para Ollama local (força evolução com substrato próprio).
        if _force_local_model(node_id) and provider not in _LOCAL_PROVIDERS:
            logger.info(
                "[MEMBRANA] node_id='%s' solicitou modelo externo '%s' — "
                "redirecionando para Ollama local (evolutivo)",
                node_id,
                original,
            )
            record_membrane_decision(node_id, "redirected_local", [original])
            enriched = await _enrich_prompt_with_learned_knowledge(prompt, task_type)
            # Preserva o model_id do original (ex: ollama/yasserrmd/GLM4.7-...)
            redirected = (
                original if original.startswith("ollama/") else f"ollama/{original}"
            )
            result = await _async_safe_call(
                "ollama",
                ollama_async_generate,
                enriched,
                redirected,
                task_type,
            )
            if result:
                return result
            raise RuntimeError(
                f"Ollama falhou sob restrição de membrana (model={redirected})."
            )

        func = ASYNC_PROVIDERS.get(provider)
        if not func:
            logger.info(
                "[ROUTER] async_route_generate provider=%s not found in ASYNC_PROVIDERS -> fallback",
                provider,
            )
            result = await _async_fallback_chain(
                prompt, task_type=task_type, node_id=node_id
            )
        else:
            result = await _async_safe_call(provider, func, prompt, original, task_type)
            if not result:
                logger.info(
                    "[ROUTER] async_route_generate primary=%s failed -> fallback",
                    provider,
                )
                result = await _async_fallback_chain(
                    prompt, exclude=provider, task_type=task_type, node_id=node_id
                )
        return result
    finally:
        # Telemetria IVM: reporta apenas quando este gateway executou a geração
        # (delegação para o paralelo reporta por conta própria, evitando dupla contagem).
        if not delegated:
            success = bool(result and str(result).strip())
            was_cache_hit = _SERVED_FROM_CACHE.get()
            await _report_ivm_telemetry(
                node_id,
                success,
                time.time() - start,
                model or "auto",
                cache_hit=was_cache_hit,
            )
            _SERVED_FROM_CACHE.set(False)


async def _report_ivm_telemetry(
    node_id: str,
    success: bool,
    latency_s: float,
    model: str,
    *,
    cache_hit: bool = False,
) -> None:
    """Registra custo metabólico (IVM) no IVMAxiom canônico. Best-effort.

    Este é o portão universal real de todo acesso a modelo de IA (ARCHITECTURE §2):
    agentes e nós que chamam async_route_generate diretamente (ex.: critic_agent,
    evo_agent, neuro_orchestrator) só são observados aqui.

    Se `cache_hit=True`, a resposta foi servida do cache — NÃO é geração real do
    agente, logo não incrementa Produtividade (P) nem Eficiência (E). Creditar
    cache hit como "tarefa concluída" é a métrica falsa que saturava o IVM em
    0.89 para todos os agentes (Lei 1: a célula sente seu próprio estado).
    """
    if cache_hit:
        # Cache hit: não conta como produtividade nem como latência de geração.
        # O hit já é registrado na barreira imunológica (cache_valid_hit).
        return
    try:
        from iaglobal.chappie import _get_chappie

        ivm = _get_chappie().get("ivm")
        if ivm is None:
            from iaglobal.chappie.ivm_axiom import get_ivm_axiom

            ivm = get_ivm_axiom()
        if ivm is None:
            return
        await ivm.atualizar_metricas(
            agent_name=node_id,
            tasks_completed=1 if success else 0,
            tasks_failed=0 if success else 1,
            total_latency_ms=latency_s * 1000.0,
            skills_exchanged=0,
            mhc_validation_score=0.9 if success else 0.5,
        )
    except Exception:
        # Telemetria metabólica nunca interrompe a geração.
        pass


# Injetado automaticamente para resolver assinaturas ausentes
def _fallback_chain(*args, **kwargs):
    pass
