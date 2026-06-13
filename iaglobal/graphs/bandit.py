import asyncio
import secrets
import time
import os
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.providers.provider_metrics import metrics
from iaglobal.utils.logger import logger

PROBE_TIMEOUT_SECONDS: float = float(os.environ.get("IAGLOBAL_PROBE_TIMEOUT", "6.0"))
PROBE_PROMPT: str = "ping"
PROBE_TASK_TYPE: str = "probe"

# FIX CRÍTICO 1: Proteção da CPU (4 núcleos). Apenas 1 inferência local por vez.
_OLLAMA_CPU_LOCK = asyncio.Semaphore(1)

class BanditPolicy:
    """
    🧠 Motor de Decisão Híbrido (ε-greedy / Thompson Sampling).
    Agora com Circuit Breaker nativo e Proteção de Inanição de CPU.
    """

    def __init__(self, credit: CreditAssignmentEngine, probe_timeout: float = PROBE_TIMEOUT_SECONDS):
        self.credit = credit
        self.context_memory = defaultdict(lambda: defaultdict(list))
        self._probe_timeout: float = probe_timeout
        self._probe_cache: Dict[str, Tuple[Optional[float], float]] = {}
        self._probe_cache_ttl: float = 120.0  
        self._error_counts: Dict[str, int] = {}
        
        # FIX CRÍTICO 2: Circuit Breaker Permanente (Amnésia resolvida)
        self._banned_providers: Dict[str, float] = {}

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
        """Remove os provedores banidos antes de enviar para seleção."""
        now = time.monotonic()
        valid = []
        for c in candidates:
            provider_domain = c.split("/")[0] if "/" in c else c
            ban_expiry = self._banned_providers.get(provider_domain)
            if ban_expiry and now < ban_expiry:
                continue # Pula os banidos (evita spam de 402)
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
            try:
                # Se for local, entra na fila da CPU. Se for cloud, vai em paralelo.
                if model.startswith("ollama/"):
                    async with _OLLAMA_CPU_LOCK:
                        await asyncio.wait_for(self.async_execute_model(model, PROBE_PROMPT, PROBE_TASK_TYPE), timeout=effective_timeout)
                else:
                    await asyncio.wait_for(self.async_execute_model(model, PROBE_PROMPT, PROBE_TASK_TYPE), timeout=effective_timeout)
                    
                latency_ms = (time.monotonic() - start) * 1000
                return model, latency_ms
            except asyncio.TimeoutError:
                self.record_error(model.split("/")[0], 504) # Punição automática
                return model, None
            except Exception as exc:
                return model, None

        results = await asyncio.gather(*[_probe_single(m) for m in to_probe])
        for model, latency in results:
            self._probe_cache[model] = (latency, time.monotonic())

        return {**fresh, **{m: l for m, l in results}}

    def _probe_latency_score(self, model: str) -> float:
        cached = self._probe_cache.get(model)
        if not cached or cached[0] is None:
            return 0.0
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
        base_candidates = candidates or BanditPolicy.default_candidates()
        valid_candidates = self._filter_candidates(base_candidates)

        if not valid_candidates:
            logger.critical("🚨 NENHUM MODELO DISPONÍVEL! Circuit Breaker bloqueou todos. Tentando forçar Ollama.")
            return next((m for m in base_candidates if "ollama" in m), base_candidates[0])

        if self._should_fallback_local(base_candidates) and any(m.startswith("ollama/") for m in valid_candidates):
            logger.warning("🔄 [BANDIT] Fallback de Emergência Ativado: Roteando para Ollama Local.")
            return next(m for m in valid_candidates if m.startswith("ollama/"))

        scored = self._calculate_scores(node, strategy, valid_candidates)
        scored.sort(reverse=True)

        if secrets.randbelow(100) < 80 and scored: # 80% Exploit
            return scored[0][1]
        return secrets.choice(valid_candidates) # 20% Explore

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
        if model not in stats: return 0.0
        s = stats[model]
        latency_penalty = min(s.get("avg_latency", 1000) / 2000, 1.0)
        cost_penalty = min(s.get("avg_cost", 0) * 10, 1.0)
        return (s.get("success_rate", 0) * 0.7) - (latency_penalty * 0.2) - (cost_penalty * 0.1)

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
_bandit_lock = asyncio.Lock()

def _get_bandit():
    """Sync accessor for the bandit singleton (backward compat).
    Auto-initializes with a default credit engine if not yet initialized."""
    global _bandit_singleton
    if _bandit_singleton is None:
        from iaglobal.graphs.credit import CreditAssignmentEngine
        _bandit_singleton = BanditPolicy(credit=CreditAssignmentEngine())
    return _bandit_singleton

async def get_bandit(credit_engine: CreditAssignmentEngine) -> BanditPolicy:
    """Mecanismo de inicialização assíncrona thread-safe."""
    global _bandit_singleton
    
    if _bandit_singleton is None:
        async with _bandit_lock:
            # Verifica novamente após adquirir o lock (Double-Checked Locking)
            if _bandit_singleton is None:
                logger.info("[BANDIT] Inicializando motor de decisão assíncrono...")
                _bandit_singleton = BanditPolicy(credit=credit_engine)
    
    return _bandit_singleton
