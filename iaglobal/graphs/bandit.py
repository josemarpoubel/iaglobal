import asyncio
import secrets
import threading
import time
import os
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.providers.provider_metrics import metrics
from iaglobal.utils.logger import logger
from iaglobal.evolution.epigenetic import adapt_bandit_policy
from iaglobal.evolution.homeostasis_controller import homeostasis_controller
from iaglobal.providers.ollama_provider import OLLAMA_CPU_LOCK

PROBE_TIMEOUT_SECONDS: float = float(os.environ.get("IAGLOBAL_PROBE_TIMEOUT", "6.0"))
PROBE_PROMPT: str = "ping"
PROBE_TASK_TYPE: str = "probe"

# Lock compartilhado com ollama_provider.py — apenas 1 inferência local por vez.
_OLLAMA_CPU_LOCK = OLLAMA_CPU_LOCK

class BanditPolicy:
    """
    🧠 Motor de Decisão Híbrido (ε-greedy / Thompson Sampling).
    Agora com Circuit Breaker nativo e Proteção de Inanição de CPU.
    """

    _DEBOUNCE_MS: float = 50.0

    def __init__(self, credit: CreditAssignmentEngine, probe_timeout: float = PROBE_TIMEOUT_SECONDS):
        self.credit = credit
        self.context_memory = defaultdict(lambda: defaultdict(list))
        self._probe_timeout: float = probe_timeout
        self._probe_cache: Dict[str, Tuple[Optional[float], float]] = {}
        self._probe_cache_ttl: float = 120.0  
        self._error_counts: Dict[str, int] = {}
        self._epsilon = float(os.getenv("BANDIT_EPSILON", "0.2"))  # Epigenetic: configurable
        
        # FIX CRÍTICO 2: Circuit Breaker Permanente (Amnésia resolvida)
        self._banned_providers: Dict[str, float] = {}

        # FIX BURST: debounce cache para select_model
        self._select_debounce: Dict[str, Tuple[float, str]] = {}

        # FIX OLLAMA OFFLINE: cache de endpoints offline com TTL curto
        self._offline_endpoints: Dict[str, float] = {}
        self._offline_ttl: float = 30.0  # 30s de exclusão temporária
    
    def _is_offline(self, endpoint: str) -> bool:
        """Verifica se endpoint está marcado como offline."""
        expiry = self._offline_endpoints.get(endpoint)
        if expiry and time.monotonic() < expiry:
            return True
        if expiry:
            del self._offline_endpoints[endpoint]
        return False
    
    def _mark_offline(self, endpoint: str):
        """Marca endpoint como offline por _offline_ttl segundos."""
        self._offline_endpoints[endpoint] = time.monotonic() + self._offline_ttl
        logger.warning("[BANDIT] Endpoint offline por %.1fs: %s", self._offline_ttl, endpoint)
    
    def _check_homeostasis(self):
        """Periodicamente verifica SLA e ajusta flags epigeneticas."""
        try:
            execs = homeostasis_controller.metrics.total_executions
            if execs > 0 and execs % 5 == 0:
                sla = homeostasis_controller.check_sla()
                if not sla["in_compliance"]:
                    adj = homeostasis_controller.apply_adjustments(sla)
                    if adj["adjusted"] and adj["epsilon_before"] != adj["epsilon_after"]:
                        logger.info("[BANDIT-HOMEOSTASIS] SLA violado — epsilon %.3f→%.3f (%d violacoes)",
                                    adj["epsilon_before"], adj["epsilon_after"], adj["violations"])
        except Exception as e:
            logger.debug("[BANDIT-HOMEOSTASIS] Erro no check: %s", e)

    def _apply_epigenetic_adjustments(self):
        """Apply epigenetic flag adjustments to bandit configuration."""
        adjustments = adapt_bandit_policy()
        if "epsilon" in adjustments:
            self._epsilon = adjustments["epsilon"]
            logger.debug(f"[EPIGENETIC-BANDIT] Epsilon adjusted to {self._epsilon}")

    def record_error(self, provider: str, error_code: int):
        """Registra erro e aplica punição drástica no Circuit Breaker."""
        self._error_counts[provider] = self._error_counts.get(provider, 0) + 1
        
        if error_code in (401, 402, 403):
            # Erro financeiro/Auth -> Banido por 1 hora
            self._banned_providers[provider] = time.monotonic() + 3600.0
            logger.error(f"🛑 [CIRCUIT BREAKER] {provider} BANIDO por 1h (Erro {error_code}).")
        elif error_code in (429, 503, 504):
            # Rate limit ou Timeout -> Banido por 2 minutos
            self._banned_providers[provider] = time.monotonic() + 120.0
            logger.warning(f"⚠️ [CIRCUIT BREAKER] {provider} em Cooldown por 2m (Erro {error_code}).")
            
    def _filter_candidates(self, candidates: List[str]) -> List[str]:
        """Remove os provedores banidos e offline antes de enviar para seleção."""
        now = time.monotonic()
        valid = []
        for c in candidates:
            provider_domain = c.split("/")[0] if "/" in c else c
            ban_expiry = self._banned_providers.get(provider_domain)
            if ban_expiry and now < ban_expiry:
                continue # Pula os banidos (evita spam de 402)
            if self._is_offline(provider_domain):
                continue # Pula endpoints offline
            valid.append(c)
        return valid

    async def probe_providers_online(self, candidates: Optional[List[str]] = None, timeout: Optional[float] = None) -> Dict[str, Optional[float]]:
        candidates = self._filter_candidates(candidates or BanditPolicy.default_candidates())
        effective_timeout = timeout if timeout is not None else self._probe_timeout
        now = time.monotonic()

        fresh: Dict[str, Optional[float]] = {}
        to_probe: List[str] = []

        for model in candidates:
            cached = self._probe_cache.get(model)
            if cached is not None and (now - cached[1]) < self._probe_cache_ttl:
                fresh[model] = cached[0]
            else:
                to_probe.append(model)

        if not to_probe:
            return fresh

        async def _probe_single(model: str) -> Tuple[str, Optional[float]]:
            start = time.monotonic()
            provider_domain = model.split("/")[0] if "/" in model else model

            # Skip probe se endpoint estiver marcado como offline
            if self._is_offline(provider_domain):
                self._probe_cache[model] = (None, time.monotonic())
                return model, None

            try:
                await asyncio.wait_for(self.async_execute_model(model, PROBE_PROMPT, PROBE_TASK_TYPE), timeout=effective_timeout)
                    
                latency_ms = (time.monotonic() - start) * 1000
                return model, latency_ms
            except asyncio.TimeoutError:
                self.record_error(model.split("/")[0], 504) # Punição automática
                return model, None
            except Exception as exc:
                exc_str = str(exc).lower()
                if "connectorror" in exc_str.replace(" ", "") or "refused" in exc_str or "cannot connect" in exc_str:
                    self._mark_offline(provider_domain)
                return model, None

        results = await asyncio.gather(*[_probe_single(m) for m in to_probe])
        for model, latency in results:
            self._probe_cache[model] = (latency, time.monotonic())

        return {**fresh, **{m: l for m, l in results}}

    def _probe_latency_score(self, model: str) -> float:
        cached = self._probe_cache.get(model)
        if not cached or cached[0] is None:
            # Sem probe: assume latência boa para cloud, ruim para ollama
            return 0.8 if not model.startswith("ollama/") else 0.0
        latency = cached[0]
        excellent_ms = 800.0
        if latency <= excellent_ms:
            return 1.0
        max_ms = self._probe_timeout * 1000
        return max(0.0, 1.0 - ((latency - excellent_ms) / (max_ms - excellent_ms)))

    def _should_fallback_local(self, candidates: List[str]) -> bool:
        """Força local se >50% da cloud estiver banida ou se a SAMe esgotar."""
        from iaglobal.core.evolution_controller import evolution_controller
        if evolution_controller.is_exhausted():
            return True
            
        now = time.monotonic()
        banned_clouds = sum(1 for p, exp in self._banned_providers.items() if exp > now and p != "ollama")
        total_clouds = len(set(c.split("/")[0] for c in candidates if not c.startswith("ollama/")))
        
        # Se mais da metade da nuvem caiu/falhou pagamento
        return total_clouds > 0 and (banned_clouds / total_clouds) >= 0.5

    @staticmethod
    def default_candidates() -> List[str]:
        from iaglobal.providers.provider_router import CREDIT_CANDIDATES
        models = [m for _, m in CREDIT_CANDIDATES()]
        ollama = [c for c in models if c.startswith("ollama/")]
        remote = [c for c in models if not c.startswith("ollama/")]
        return remote + ollama

    def select_model(self, node: str, strategy: str, candidates: Optional[List[str]] = None) -> str:
        # FIX BURST: debounce de 50ms — retorna cache se chamado no mesmo frame de tempo
        now = time.monotonic()
        cache_key = f"{node}:{strategy}"
        last = self._select_debounce.get(cache_key)
        if last and (now - last[0]) * 1000 < self._DEBOUNCE_MS:
            return last[1]

        base_candidates = candidates or BanditPolicy.default_candidates()
        valid_candidates = self._filter_candidates(base_candidates)

        # Prioriza cloud providers sobre ollama SEMPRE (latência melhor)
        remote_candidates = [m for m in valid_candidates if not m.startswith("ollama/")]
        if remote_candidates:
            valid_candidates = remote_candidates + [m for m in valid_candidates if m.startswith("ollama/")]

        if not valid_candidates:
            logger.critical("🚨 NENHUM MODELO DISPONÍVEL! Circuit Breaker bloqueou todos. Tentando forçar Ollama.")
            return next((m for m in base_candidates if "ollama" in m), base_candidates[0])

        scored = self._calculate_scores(node, strategy, valid_candidates)
        scored.sort(reverse=True)

        # Homeostasis: check SLA periodically e ajusta flags epigeneticas
        self._check_homeostasis()

        # Epigenetic: apply epsilon from config
        self._apply_epigenetic_adjustments()
        # epsilon=0.2 = 20% exploit (usar melhor), 80% explore (random)
        exploit_pct = int(self._epsilon * 100) if self._epsilon <= 1 else 80
        
        if secrets.randbelow(100) < exploit_pct and scored: # epsilon Exploit
            result = scored[0][1]
        else:
            logger.debug(f"[BANDIT] Exploring with epsilon={self._epsilon}")
            # Prioriza cloud também no exploration
            if remote_candidates:
                result = secrets.choice(remote_candidates)
            else:
                result = secrets.choice(valid_candidates) # epsilon Explore

        # FIX BURST: atualiza cache de debounce
        self._select_debounce[cache_key] = (time.monotonic(), result)
        return result

    def select_top_n(self, node: str, strategy: str, n: int = 7, candidates: Optional[List[str]] = None) -> List[str]:
        base_candidates = candidates or BanditPolicy.default_candidates()
        valid_candidates = self._filter_candidates(base_candidates)

        if not valid_candidates:
            return [m for m in base_candidates if "ollama" in m][:n]

        if self._should_fallback_local(base_candidates):
            ollamas = [m for m in valid_candidates if m.startswith("ollama/")]
            if ollamas: return ollamas

        scored = self._calculate_scores(node, strategy, valid_candidates)
        scored.sort(reverse=True)
        return [m for _, m in scored[:n]]

    def _calculate_scores(self, node: str, strategy: str, candidates: List[str]) -> List[Tuple[float, str]]:
        """Calcula o vetor matemático de decisão para a lista de candidatos."""
        scored = []
        for model in candidates:
            base_score = self.credit.score(node, model, strategy)
            metric_score = self._metrics_score(model)
            probe_score = self._probe_latency_score(model)
            try:
                from iaglobal.cognition.reputation_engine import reputation_engine
                reputation = reputation_engine.score(model)
            except Exception:
                reputation = 0.0

            # Fórmula Central de Tomada de Decisão
            score = (base_score * 0.40) + (metric_score * 0.20) + (reputation * 0.20) + (probe_score * 0.20)
            scored.append((score, model))
        return scored

    def rank_models(self, node: str, strategy: str, candidates: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        model_ids = [m for _, m in candidates]
        valid_ids = set(self._filter_candidates(model_ids))
        
        valid_candidates = [(p, m) for p, m in candidates if m in valid_ids]
        
        if not valid_candidates:
            return [(p, m) for p, m in candidates if m.startswith("ollama/")]

        scored = []
        for provider, model in valid_candidates:
            base_score = self.credit.score(node, model, strategy)
            context_score = self._context_score(node, model)
            task_score = self._task_aware_score(model, strategy)
            
            final_score = (base_score * 0.4) + (context_score * 0.2) + (task_score * 0.4)
            scored.append((final_score, provider, model))

        scored.sort(reverse=True)
        return [(p, m) for _, p, m in scored]

    async def async_execute_model(self, model: str, prompt: str, task_type: str = "general") -> str:
        from iaglobal.providers.provider_router import async_route_generate
        # Se for Ollama, a trava protege a CPU em tempo de execução real também
        if model.startswith("ollama/"):
            async with _OLLAMA_CPU_LOCK:
                return await async_route_generate(model=model, prompt=prompt, task_type=task_type)
        return await async_route_generate(model=model, prompt=prompt, task_type=task_type)

    def update_policy(self, node: str, model: str, strategy: str, success: bool, latency: float, reward: float) -> None:
        from iaglobal.graphs.telemetry import ExecutionEvent
        self.credit.record(ExecutionEvent(
            node=node, success=success, latency=latency, model=model, strategy=strategy,
        ))

    def _metrics_score(self, model: str) -> float:
        stats = metrics.get_model_stats()
        if model not in stats:
            return 0.3 if not model.startswith("ollama/") else 0.2
        s = stats[model]
        success = s.get("success_rate", 0)
        latency = s.get("avg_latency", 1000)
        cost = s.get("avg_cost", 0)
        # Normalize latency (0-5s = score 1, 5s+ = score 0)
        latency_score = max(0, 1 - (latency / 5000))
        cost_score = max(0, 1 - (cost * 100))
        return (success * 0.5) + (latency_score * 0.3) + (cost_score * 0.2)

    def _task_aware_score(self, model: str, task_type: str) -> float:
        task_stats = metrics.get_task_model_stats().get(model, {}).get(task_type)
        if not task_stats: return 0.0
        latency_penalty = min(task_stats.get("avg_latency", 1000) / 2000, 1.0)
        cost_penalty = min(task_stats.get("avg_cost", 0) * 10, 1.0)
        return (task_stats.get("success_rate", 0) * 0.75) - (latency_penalty * 0.2) - (cost_penalty * 0.05)

    def _thompson_boost(self, provider: str, model: str) -> float:
        import random
        stats = metrics.get_model_stats().get(model, {})
        s_count, f_count = stats.get("success_count", 0), stats.get("fail_count", 0)
        try:
            return random.betavariate(s_count + 1, f_count + 1)
        except Exception:
            return s_count / (s_count + f_count + 2)

    def select_model_thompson(self, node: str, strategy: str, candidates: Optional[List[str]] = None) -> str:
        if os.environ.get("THOMPSON_SAMPLING", "0") != "1":
            return self.select_model(node, strategy, candidates)
            
        valid = self._filter_candidates(candidates or BanditPolicy.default_candidates())
        if not valid: return self.select_model(node, strategy, candidates)

        sampled = []
        for model in valid:
            base = self.credit.score(node, model, strategy)
            thompson = self._thompson_boost(model.split("/")[0], model)
            sampled.append(((base * 0.5 + thompson * 0.5), model))
        sampled.sort(reverse=True)
        return sampled[0][1]

    def _context_score(self, context: str, model: str) -> float:
        values = self.context_memory[context][model]
        return sum(values) / len(values) if values else 0.0

    def update_context(self, context: str, model: str, reward: float):
        self.context_memory[context][model].append(reward)

    def get_error_count(self, provider: str) -> int:
        return self._error_counts.get(provider, 0)

# Instância Global Única (Singleton) garantindo que o CB funcione para toda a aplicação.

# No final do seu bandit.py

_bandit_singleton = None
_bandit_init_lock = asyncio.Lock()
_bandit_singleton_lock = threading.Lock()

def _get_bandit():
    """Sync accessor for the bandit singleton (backward compat).
    Auto-initializes with a default credit engine if not yet initialized.
    Thread-safe via threading.Lock."""
    global _bandit_singleton
    if _bandit_singleton is None:
        with _bandit_singleton_lock:
            if _bandit_singleton is None:
                from iaglobal.graphs.credit import CreditAssignmentEngine
                _bandit_singleton = BanditPolicy(credit=CreditAssignmentEngine())
    return _bandit_singleton

async def get_bandit(credit_engine: CreditAssignmentEngine) -> BanditPolicy:
    """Mecanismo de inicialização assíncrona thread-safe."""
    global _bandit_singleton
    
    if _bandit_singleton is None:
        async with _bandit_init_lock:
            # Verifica novamente após adquirir o lock (Double-Checked Locking)
            if _bandit_singleton is None:
                logger.info("[BANDIT] Inicializando motor de decisão assíncrono...")
                _bandit_singleton = BanditPolicy(credit=credit_engine)
    
    return _bandit_singleton
