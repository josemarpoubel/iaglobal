# iaglobal/graphs/bandit.py
"""
Multi-Armed Bandit para seleção de provedores LLM com:
- IVM-based Rewards
- Epsilon-Greedy
- Fallback Chain
- Credit Assignment Integration
- Semaphore para controle de concorrência por modelo
"""

import asyncio
import hashlib
import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any

from iaglobal.utils.logger import get_logger
from iaglobal.utils.life_signal_collector import instrument
from iaglobal.observability.semaphore_tracker import get_semaphore_tracker

# Logger dedicado à membrana: roteia pelo logger "iaglobal" para herdar o
# nível INFO corrigido em logger.py (observable no CLI), independente do
# logger "bandit" usado nas métricas de bandit.
_mem_logger = get_logger("iaglobal")

# Singleton global
_bandit_instance: Optional["BanditPolicy"] = None


def _get_bandit() -> "BanditPolicy":
    """Retorna instância singleton do BanditPolicy.

    Auto-injeta CreditAssignmentEngine se ainda não configurado,
    garantindo que qualquer chamador (nodes, agents, scripts) tenha
    métricas registradas mesmo sem passar pelo Orchestrator.initialize().
    """
    global _bandit_instance
    if _bandit_instance is None:
        _bandit_instance = BanditPolicy()
    # Auto-injeção: garante credit_engine sempre presente
    if _bandit_instance.credit_engine is None:
        try:
            from iaglobal.graphs.credit import CreditAssignmentEngine

            _bandit_instance.credit_engine = CreditAssignmentEngine()
        except Exception:
            pass
    return _bandit_instance


class BanditPolicy:
    """Multi-Armed Bandit para seleção de provedores."""

    DEFAULT_WEIGHT = 0.0

    # Semáforos por modelo para evitar rate limit (cada modelo responde 1 requisição por vez)
    MODEL_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
    SEMAPHORE_LOCK = asyncio.Lock()

    # Configuração de concorrência máxima por tipo de modelo
    CLOUD_MODEL_CONCURRENCY = 1  # Groq, NVIDIA, etc — 1 por vez para evitar 429
    LOCAL_MODEL_CONCURRENCY = 4  # Ollama local pode lidar com mais

    def __init__(
        self,
        epsilon: float = 0.1,
        decay: float = 0.99,
        credit: Optional[Any] = None,
        probe_timeout: float = 5.0,
    ):
        import os

        self.epsilon = epsilon
        self.decay = decay
        self.credit_engine = credit
        # Garante inicialização do CreditAssignmentEngine
        if self.credit_engine is None:
            from iaglobal.graphs.credit import CreditAssignmentEngine

            self.credit_engine = CreditAssignmentEngine()
        # CreditAssignmentEngine opcional
        self.probe_timeout = probe_timeout
        self.weights: Dict[str, float] = defaultdict(float)
        self.rewards: Dict[str, List[float]] = defaultdict(list)
        self.circuit_breakers: Dict[str, float] = {}
        self._offline: Dict[str, float] = {}
        self._model_in_use: Dict[str, bool] = {}  # Rastreamento de modelos em uso
        self.context_memory: Dict[
            str, Dict
        ] = {}  # Memória por contexto/domínio para epigenética
        self._epigenetic_flags: Dict[str, bool] = {}  # Flags epigenéticas

        # Inicializa pesos a partir de variável de ambiente
        initial_weights = os.getenv("BANDIT_INITIAL_WEIGHTS", "")
        if initial_weights:
            for pair in initial_weights.split(","):
                if ":" in pair:
                    # Split apenas no último ':' (peso está sempre no final)
                    parts = pair.rsplit(":", 1)
                    if len(parts) == 2:
                        model, weight = parts
                        self.weights[model.strip()] = float(weight.strip())

        self.logger = get_logger("bandit")

        if initial_weights and self.weights:
            self.logger.info(
                f"🎯 BanditPolicy inicializado com pesos: {dict(self.weights)}"
            )

    # ── Backward compatibility aliases ──

    @property
    def _banned_providers(self) -> Dict[str, float]:
        return self.circuit_breakers

    @_banned_providers.setter
    def _banned_providers(self, value: Dict[str, float]) -> None:
        self.circuit_breakers = value

    def _is_offline(self, provider: str) -> bool:
        expiry = self._offline.get(provider, 0)
        return time.monotonic() < expiry

    def update_policy(
        self,
        node: str,
        model: str,
        strategy: str,
        success: bool,
        latency: float,
        reward: float,
    ) -> None:
        self.update_reward(model, reward, ivm=1.0 if success else 0.0)
        if not success:
            self.trigger_circuit_breaker(model, cooldown=latency * 2)

    def update(self, action: str, reward: float) -> None:
        self.update_reward(action, reward, ivm=1.0)

    def select_arm(self, arms: List[str]) -> str:
        """Seleciona um braço usando epsilon-greedy."""
        # Verificar circuit breakers
        valid_arms = [
            arm for arm in arms if self.circuit_breakers.get(arm, 0) < time.time()
        ]

        if not valid_arms:
            return arms[0]  # Fallback

        # Exposição
        if random.random() < self.epsilon:
            return random.choice(valid_arms)

        # Exploração
        return max(valid_arms, key=lambda arm: self.weights.get(arm, 0))

    def update_reward(self, arm: str, reward: float, ivm: float) -> None:
        """Atualiza o peso do braço com base no reward + IVM."""
        self.rewards[arm].append(reward)
        # Reward ponderado pelo IVM
        self.weights[arm] = (self.weights[arm] + (reward * ivm)) / 2
        self.epsilon *= self.decay

    def trigger_circuit_breaker(self, arm: str, cooldown: float) -> None:
        """Dispara um circuit breaker para o braço."""
        self.circuit_breakers[arm] = time.time() + cooldown
        self.logger.warning(
            f"⚡ Circuit breaker acionado para {arm}. Cooldown: {cooldown}s"
        )

    async def _get_model_semaphore(self, model_name: str) -> asyncio.Semaphore:
        """Obtém ou cria semáforo para o modelo específico.

        A concorrência respeita max_concurrent_requests do provider_config.py
        para modelos locais (Juiz=1, Operário=3, Sentinela=5). Modelos cloud
        usam concorrência 1 para evitar 429 rate limit.
        """
        async with self.SEMAPHORE_LOCK:
            if model_name not in self.MODEL_SEMAPHORES:
                is_cloud = any(
                    provider in model_name
                    for provider in ["groq/", "nvidia/", "openrouter/", "gemini/"]
                )
                if is_cloud:
                    concurrency = self.CLOUD_MODEL_CONCURRENCY
                else:
                    concurrency = self._resolve_local_concurrency(model_name)
                self.MODEL_SEMAPHORES[model_name] = asyncio.Semaphore(concurrency)
                self.logger.info(
                    f"🔒 Semáforo criado para {model_name} (concorrência={concurrency})"
                )
            return self.MODEL_SEMAPHORES[model_name]

    def _resolve_local_concurrency(self, model_name: str) -> int:
        """Resolve a concorrência para um modelo local baseado no papel cognitivo."""
        raw = model_name.replace("ollama/", "", 1)
        try:
            from iaglobal.providers.provider_config import (
                COGNITIVE_MODELS,
                CognitiveRole,
            )

            for role, cfg in COGNITIVE_MODELS.items():
                if cfg["model_id"] == raw:
                    return cfg.get(
                        "max_concurrent_requests", self.LOCAL_MODEL_CONCURRENCY
                    )
        except Exception:
            pass
        return self.LOCAL_MODEL_CONCURRENCY

    async def acquire_model(
        self, model_name: str, node_id: str = "", execution_id: str = ""
    ) -> bool:
        """
        Adquire semáforo para usar o modelo.
        Retorna True se conseguiu adquirir, False se timeout.

        Para modelos locais, consulta primeiro o LocalModelGate (token bucket
        com priorização por IVM). Se o gate negar, retorna False imediatamente
        sem bloquear — o chamador deve usar synthetic_success.

        Em caso de timeout no semáforo, libera automaticamente o token do
        LocalModelGate (se consumido) para evitar vazamento.
        """
        _st = get_semaphore_tracker()
        _st.record_acquire_start(model_name, node_id, execution_id=execution_id)
        _acquire_start = time.time()

        semaphore = await self._get_model_semaphore(model_name)
        _gate_token_consumed = False
        try:
            is_cloud = any(
                provider in model_name
                for provider in ["groq/", "nvidia/", "openrouter/", "gemini/"]
            )

            # Gate do token bucket para modelos locais
            if not is_cloud:
                from iaglobal.execution.token_bucket import LocalModelGate

                gate = await LocalModelGate.get_instance()
                if not await gate.try_acquire(node_id, model_name=model_name):
                    self.logger.info(
                        "🔒 %s rejeitado pelo LocalModelGate (synthetic_success fallback)",
                        model_name,
                    )
                    _st.record_gate_rejected(
                        model_name, node_id, execution_id=execution_id
                    )
                    return False
                _gate_token_consumed = True

            # Timeout de aquisição: cloud é rápido (3s), local precisa de
            # margem para fila — cada modelo tem latência diferente:
            # GLM4 (Juiz, 1.2B)  ~90s cold / ~15-50s warm
            # LFM  (Sentinela)   ~10-30s
            # Qwen (Operário)    ~3-10s
            if is_cloud:
                timeout = 3.0
            elif "glm4" in model_name.lower() or "glm" in model_name.lower():
                timeout = 180.0
            elif "lfm" in model_name.lower():
                timeout = 60.0
            else:
                timeout = 30.0

            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            self._model_in_use[model_name] = True
            _wait_ms = (time.time() - _acquire_start) * 1000
            _st.record_acquired(
                model_name, node_id, _wait_ms, execution_id=execution_id
            )
            self.logger.debug(
                f"🔒 {model_name} adquirido (timeout={timeout}s, wait={_wait_ms:.0f}ms)"
            )
            return True
        except asyncio.TimeoutError:
            _wait_ms = (time.time() - _acquire_start) * 1000
            _st.record_timeout(model_name, node_id, _wait_ms, execution_id=execution_id)
            # Libera token do gate local se foi consumido antes do semáforo
            if _gate_token_consumed:
                try:
                    from iaglobal.execution.token_bucket import LocalModelGate

                    gate = await LocalModelGate.get_instance()
                    await gate.release(node_id, model_name=model_name)
                except Exception:
                    pass
            self.logger.debug(
                f"⏰ Timeout ({timeout}s, wait={_wait_ms:.0f}ms) aguardando {model_name}"
            )
            return False

    def release_model(
        self, model_name: str, node_id: str = "", execution_id: str = ""
    ) -> None:
        """Libera o semáforo do modelo após uso."""
        if model_name in self.MODEL_SEMAPHORES:
            self.MODEL_SEMAPHORES[model_name].release()
            self._model_in_use[model_name] = False
            _st = get_semaphore_tracker()
            _st.record_released(model_name, node_id, execution_id=execution_id)
            self.logger.debug(f"🔓 {model_name} liberado")

    def _apply_epigenetic_adjustments(self) -> None:
        """
        Aplica ajustes epigenéticos baseados em histórico de execuções.
        Método chamado pelo PolicyRegistry para sincronização.
        """
        # Placeholder para futura integração com EpigeneticRegistry
        # Por enquanto, apenas loga o estado atual
        self.logger.debug(
            f"[EPIGENETIC] Ajustes aplicados. Contextos: {len(self.context_memory)}"
        )

    async def select_model_with_lock(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None,
    ) -> str:
        """
        Seleciona o melhor modelo baseado no ranking.
        Antes de ranquear, sincroniza pesos com CreditAssignmentEngine se disponível.
        """
        # Sincroniza pesos com CreditAssignmentEngine
        self._sync_weights_from_credit(candidates)

        ranked = self.rank_models(node_id, task_type, candidates, context)

        if not ranked:
            fallback = candidates[0] if candidates else "ollama/qwen2.5:0.5b"
            self.logger.info(f"🎯 {node_id}: {fallback} selecionado (sem histórico)")
            return fallback

        # Retorna o modelo com maior score
        model = ranked[0][1]
        self.logger.info(
            f"🎯 {node_id}: {model} selecionado (score={ranked[0][0]:.2f})"
        )
        return model

    def _sync_weights_from_credit(self, candidates: List[str]) -> None:
        """
        Atualiza pesos do Bandit baseado no histórico do CreditAssignmentEngine.
        Isso permite que o Bandit aprenda com execuções passadas.
        """
        if not self.credit_engine:
            self.logger.debug("⚠️ _sync_weights_from_credit: credit_engine é None")
            return

        self.logger.debug(
            f"🔄 _sync_weights_from_credit: {len(self.credit_engine.stats)} stats no credit_engine"
        )

        for model in candidates:
            # Extrai provider e model_name
            if "/" in model:
                provider, model_name = model.split("/", 1)
            else:
                provider, model_name = model, model

            # Busca histórico no Credit para este modelo
            # Nota: Credit armazena por (node, model, strategy)
            # Vamos agregar através de todos os nodes/strategies
            total_success = 0
            total_fail = 0
            total_reward = 0.0
            reward_count = 0

            for (node, mdl, strategy), stats in self.credit_engine.stats.items():
                if mdl == model or mdl.endswith(model_name):
                    total_success += stats["success"]
                    total_fail += stats["fail"]
                    if stats["reward_count"] > 0:
                        total_reward += stats["reward_total"]
                        reward_count += stats["reward_count"]

            # Calcula score baseado em sucesso + reward
            total = total_success + total_fail
            if total > 0:
                success_rate = total_success / total
                avg_reward = total_reward / reward_count if reward_count > 0 else 0.0
                new_weight = (success_rate * 0.7) + (avg_reward * 0.3)

                # Atualização contínua com suavização — não apenas quando weight == 0
                current = self.weights.get(model, 0.0)
                if current == 0.0 and new_weight > 0.0:
                    self.weights[model] = new_weight
                    self.logger.info(
                        f"📈 {model}: peso inicial {new_weight:.2f} (success={success_rate:.2f}, reward={avg_reward:.2f})"
                    )
                elif current > 0.0:
                    smoothed = current * 0.7 + new_weight * 0.3
                    if abs(smoothed - current) > 0.005:
                        self.weights[model] = smoothed
                        self.logger.info(
                            f"📊 {model}: peso ajustado {current:.4f} → {smoothed:.4f} (success={success_rate:.2f}, reward={avg_reward:.2f})"
                        )

    def get_provider_weight(
        self, provider_name: str, task_type: str = "general"
    ) -> float:
        """
        Retorna o peso médio de todos os modelos de um provider.

        Percorre self.weights agregando por prefixo do provider.
        Útil para testes e observabilidade (ex.: monitorar degradação).
        """
        models = [m for m in self.weights if m.split("/", 1)[0] == provider_name]
        if not models:
            return self.DEFAULT_WEIGHT
        return sum(self.weights[m] for m in models) / len(models)

    def get_provider_circuit_state(self, provider_name: str) -> dict:
        """
        Retorna estado do circuit breaker para o provider.

        Returns:
            dict com 'state' ('open'|'closed'), 'remaining_cooldown' (segundos),
            e 'models' com detalhe por modelo.
        """
        now = time.time()
        models = {}
        any_open = False
        for model, cooldown_until in self.circuit_breakers.items():
            if model.split("/", 1)[0] == provider_name:
                remaining = max(0.0, cooldown_until - now)
                is_open = remaining > 0
                if is_open:
                    any_open = True
                models[model] = {
                    "state": "open" if is_open else "closed",
                    "remaining_cooldown": round(remaining, 1),
                }
        return {
            "state": "open" if any_open else "closed",
            "remaining_cooldown": max(
                (m["remaining_cooldown"] for m in models.values()), default=0.0
            ),
            "models": models,
        }

    def rank_models(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None,
    ) -> List[tuple]:
        """
        Ranqueia modelos candidatos baseado nos pesos do bandit.

        Returns:
            Lista de tuplas (score, model_name) ordenada decrescente
        """
        ranked = []
        for model in candidates:
            weight = self.weights.get(model, 0.0)
            # Verificar circuit breaker
            if self.circuit_breakers.get(model, 0) < time.time():
                score = weight
            else:
                score = -float("inf")  # Penaliza modelos em cooldown
            ranked.append((score, model))

        # Ordenar por score decrescente
        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def select_model(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None,
    ) -> str:
        """
        Seleciona o melhor modelo baseado no ranking.

        Returns:
            Nome do modelo selecionado
        """
        if not candidates:
            raise ValueError("Nenhum candidato disponível")

        ranked = self.rank_models(node_id, task_type, candidates, context)
        if not ranked:
            return candidates[0]  # Fallback

        # Retorna o modelo com maior score
        return ranked[0][1]

    def select_top_n(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        n: int = 3,
        context: Optional[dict] = None,
    ) -> List[str]:
        """
        Seleciona os top N modelos baseado no ranking.

        Returns:
            Lista de nomes dos top N modelos
        """
        ranked = self.rank_models(node_id, task_type, candidates, context)
        top_n = ranked[:n]
        return [model for _, model in top_n]

    async def async_execute_model(
        self, model_name: str, prompt: str, node_id: str = "provider_router", **kwargs
    ) -> str:
        """
        Executa um modelo assincronamente delegando ao provider_router.
        O provider_router gerencia semáforos e rate limiting internamente.

        Antes de executar, o SearchMiddleware enriquece o prompt com
        contexto web para agentes não-críticos (Coder, Debugger, etc.),
        reduzindo a dependência do conhecimento limitado do modelo local.

        Returns:
            String com a resposta do modelo (vazia em caso de falha)
        """
        from iaglobal.providers.provider_router import async_route_generate

        task_type = kwargs.get("task_type", "general")

        # SearchMiddleware: injeta contexto web para agentes não-críticos
        try:
            from iaglobal.search.search_middleware import SearchMiddleware

            prompt = await SearchMiddleware.enrich(prompt, node_id)
        except Exception:
            pass  # Nunca deixar busca quebrar chamadas LLM

        self.logger.info(f"🚀 Executando modelo {model_name} (task={task_type})...")

        try:
            response = await async_route_generate(
                model=model_name,
                prompt=prompt,
                task_type=task_type,
                node_id=node_id,
            )
            if response:
                return str(response)
        except Exception as e:
            self.logger.warning(f"async_execute_model falhou: {e}")
            # Dispara circuit breaker se falhar repetidamente
            self.trigger_circuit_breaker(model_name, cooldown=30.0)

        return ""

    async def _report_phospholipid(
        self, success: bool, latency: float, model_name: str
    ) -> None:
        """Reporta métricas ao PhospholipidRegistry. Best-effort."""
        try:
            from iaglobal.observability.phospholipid_bridge import bridge as _pbridge

            _pbridge.auto_report(model_name, success, latency * 1000)
        except Exception:
            pass

    async def _report_ivm(
        self, node_id: str, success: bool, latency: float, model: str
    ) -> None:
        """Registra custo metabólico (IVM) no IVMAxiom canônico.

        O BanditPolicy é o portão universal de todo acesso a modelo de IA
        (ARCHITECTURE §2), logo é o ponto único correto para telemetria IVM:
        captura AgentBase e chamadas diretas de nós indistintamente, eliminando
        o split-brain de observabilidade (agentes alimentavam um singleton em
        memória que nenhum observador lia). Nunca deve quebrar a geração.
        """
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
                total_latency_ms=latency * 1000.0,
                skills_exchanged=0,
                mhc_validation_score=0.9 if success else 0.5,
            )
        except Exception:
            # Telemetria metabólica é best-effort; nunca interrompe a geração.
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Membrana seletiva no chokepoint do BanditPolicy
    # ─────────────────────────────────────────────────────────────────────
    # ARCHITECTURE §2: todo acesso a modelo de IA passa por BanditPolicy.
    # O ponto único correto para aplicar a membrana seletiva é AQUI, não em
    # AgentBase._call_llm (evitaria um 2º caminho paralelo ao Bandit — a
    # categoria de problema já resolvida em "Bandit/LoadBalancer isolados").
    #
    # POLÍTICA INTRÍNSECA fail-closed: só o nó crítico tem direito a nuvem;
    # node_id ausente/não reconhecido é CONFINADO a Ollama local. É
    # independente do gate global EXTERNAL_ACCESS_ONLY_CRITIC (que rege a
    # membrana em provider_router), para que o modo shadow revele o que
    # *seria* confinado mesmo com o gate global desligado.
    def _membrane_is_critic(self, node_id: str) -> bool:
        if not node_id:
            return False
        return node_id.lower() in {"critic", "critic_batch"}

    def _membrane_filter_candidates(
        self, node_id: str, candidates: List[str]
    ) -> List[str]:
        """Reduz candidatos a Ollama local se o nó não for crítico. Fail-closed."""
        if self._membrane_is_critic(node_id):
            return candidates
        try:
            from iaglobal.providers.provider_router import _LOCAL_PROVIDERS
        except Exception:
            _LOCAL_PROVIDERS = {"ollama"}
        local = [c for c in candidates if c.split("/", 1)[0] in _LOCAL_PROVIDERS]
        # Fail-closed: se nenhum candidato local, injeta Ollama p/ NÃO liberar nuvem.
        return local if local else ["ollama/qwen2.5:0.5b"]

    def _membrane_mode(self) -> str:
        """'off' | 'shadow' | 'enforce'. Env MEMBRANA_MODE tem precedência.

        Default é 'enforce': o BanditPolicy é o portão universal de todo
        acesso a modelo de IA (ARCHITECTURE §2) — a membrana seletiva deve
        estar ativa por padrão, não o GATE 2 no provider_router.
        """
        import os

        env = os.getenv("MEMBRANA_MODE", "").strip().lower()
        if env in ("off", "shadow", "enforce"):
            return env
        try:
            from iaglobal.evolution import is_flag_enabled

            if is_flag_enabled("membrana_enforce"):
                return "enforce"
            if is_flag_enabled("membrana_shadow"):
                return "shadow"
        except Exception:
            pass
        return "enforce"

    # ── PSC Protocolo de Soberania do Crítico ──
    class SecurityViolation(Exception):
        """Apenas CriticAgent possui autoridade para escalonamento externo."""

    def _psc_verify_caller(self, node_id: str) -> None:
        """PSC §1: Trava de segurança — verifica identidade do chamador.

        Se violação, dispara apoptose contratual via OmniMind + registra ancestry.
        """
        if not self._membrane_is_critic(node_id):
            # OmniMind enforcement — apoptose contratual (Lei da Obediência)
            try:
                from iaglobal.obsidian.omnimind import omni_mind

                omni_mind.emitir_gatilho_apoptose(
                    node_id, "PSC: acesso cloud sem autorizacao do CriticAgent"
                )
            except Exception as exc:
                self.logger.debug("[PSC] OmniMind nao disponivel: %s", exc)

            # Registra no ancestry como violação
            try:
                self._psc_register_ancestry(
                    node_id,
                    "BLOCKED",
                    0.0,
                    False,
                    extra={"violation": "psc_blocked", "reason": "non_critic_caller"},
                )
            except Exception:
                pass

            raise self.SecurityViolation(
                f"PSC BLOQUEADO: node_id='{node_id}' não é CriticAgent. "
                "Apenas o CriticAgent possui autoridade para escalonamento externo."
            )

    def _psc_ivm_green(self) -> bool:
        """PSC §1.2: Semáforo IVM — se homocisteína alta, bloqueia cloud."""
        try:
            from iaglobal.metabolism.homocysteine_pool import homocysteine_pool

            level = homocysteine_pool.get_current_level()
            threshold = homocysteine_pool.get_threshold()
            if level > threshold * 0.7:
                self.logger.warning(
                    "[PSC] Homocisteina alta (%.2f/%.2f) — bloqueando acesso cloud",
                    level,
                    threshold,
                )
                return False
        except Exception:
            pass
        return True

    def _psc_register_ancestry(
        self,
        node_id: str,
        model: str,
        latency: float,
        success: bool,
        extra: Optional[dict] = None,
    ) -> None:
        """PSC §1.3: Registra ancestralidade de escalonamento cognitivo.

        Inclui lineage_marker do genesis + lei de Holliwell aplicada.
        """
        try:
            from datetime import datetime, timezone

            # Lineage marker do genesis oficial
            lineage = ""
            try:
                from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

                lineage = GENESIS_HASH_OFFICIAL[:16]
            except Exception:
                lineage = "unknown"
            record = {
                "type": extra.get("violation", "Cognitive_Escalation")
                if extra
                else "Cognitive_Escalation",
                "node_id": node_id,
                "model": model,
                "latency_ms": round(latency * 1000, 2),
                "success": success,
                "lineage_marker": lineage,
                "omni_law": "Lei do Suprimento" if success else "Lei da Obediencia",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if extra:
                record.update(extra)
            ancestry_path = None
            try:
                from iaglobal._paths import DATA_DIR

                ancestry_path = DATA_DIR / "ancestry_tree.jsonl"
            except Exception:
                import tempfile

                ancestry_path = (
                    Path(tempfile.gettempdir()) / "iaglobal_ancestry_tree.jsonl"
                )
            ancestry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(ancestry_path), "a") as f:
                import json

                f.write(json.dumps(record) + "\n")
            self.logger.debug(
                "[PSC] Ancestry registrada: %s -> %s (ok=%s)", node_id, model, success
            )
        except Exception as e:
            self.logger.debug("[PSC] Falha no ancestry: %s", e)

    @instrument(name="bandit.generate")
    async def generate(
        self,
        node_id: str,
        prompt: str,
        candidates: List[str],
        context: Optional[dict] = None,
        task_type: str = "general",
        timeout: float = 600.0,
        execution_id: str = "",
    ) -> str:
        """
        Método completo de geração via Bandit:
        1. PSC: Verifica identidade do chamador (só CriticAgent passa)
        2. PSC: Verifica semáforo IVM (homocisteína baixa?)
        3. Seleciona melhor modelo (ε-greedy + pesos + credit assignment)
        4. Adquire semáforo do modelo (controla concorrência)
        5. Executa via provider_router
        6. Libera semáforo
        7. Registra métricas no CreditAssignmentEngine
        8. PSC: Registra ancestralidade

        Args:
            node_id: ID do nó/agente executando
            prompt: Prompt para o LLM
            candidates: Lista de modelos candidatos
            context: Contexto opcional para seleção epigenética
            task_type: Tipo de tarefa (general, code, analysis, etc)
            timeout: Timeout em segundos

        Returns:
            Resposta do LLM ou string vazia em caso de falha
        """
        import traceback

        # Identidade efetiva pra aprendizado/auditoria — NUNCA usada em decisão
        # de acesso. Se veio de arbitrar_geracao(), node_id="critic" satisfaz a
        # PSC mas o crédito real vai para context["delegate_for"].
        effective_agent = (context or {}).get("delegate_for", node_id)

        # ── PSC §1.1: Trava de identidade — continua com node_id CRU ──
        self._psc_verify_caller(node_id)

        start_time = time.time()
        model_selected = None
        latency = 0.0
        success = False
        _sem_acquired = False  # guard para finally: só libera se adquiriu

        try:
            # ── Membrana seletiva (shadow/enforce) no chokepoint ──
            # Política intrínseca fail-closed: não-crítico -> só Ollama local.
            mode = self._membrane_mode()
            if mode != "off":
                filtered = self._membrane_filter_candidates(node_id, candidates)
                if filtered != candidates:
                    _mem_logger.info(
                        "[MEMBRANA] node_id='%s' confinaria %d candidato(s) a %s (modo=%s)",
                        node_id,
                        len(candidates) - len(filtered),
                        filtered,
                        mode,
                    )
                    try:
                        from iaglobal.providers.provider_router import (
                            record_membrane_decision,
                        )

                        record_membrane_decision(
                            node_id,
                            "confined_local"
                            if mode == "enforce"
                            else "shadow_confined",
                            filtered,
                        )
                    except Exception:
                        pass
                else:
                    try:
                        from iaglobal.providers.provider_router import (
                            record_membrane_decision,
                        )

                        record_membrane_decision(
                            node_id, "authorized_cloud", candidates
                        )
                    except Exception:
                        pass
                if mode == "enforce":
                    candidates = filtered

            # ── PSC §1.2: Semáforo IVM antes de cloud ──
            if any("ollama" not in c for c in candidates):
                if not self._psc_ivm_green():
                    self.logger.warning("[PSC] IVM vermelho — forçando fallback local")
                    try:
                        from iaglobal.providers.provider_router import _LOCAL_PROVIDERS
                    except Exception:
                        _LOCAL_PROVIDERS = {"ollama"}
                    candidates = [
                        c for c in candidates if c.split("/", 1)[0] in _LOCAL_PROVIDERS
                    ] or ["ollama/qwen2.5:0.5b"]

            # ── Tribunal Cognitivo: resolve tier para o agente real ──
            # Usa effective_agent (delegate_for) quando disponível, pois
            # node_id pode ser "critic" (fixo da PSC) mas o agente real
            # que precisa de geração é outro (ex: "coder", "planner").
            # Primeiro tenta CognitiveRouter.ROUTE_MAP (match exato),
            # depois TaskRouter (regex patterns).
            try:
                from iaglobal.providers.provider_router import CognitiveRouter
                from iaglobal.providers.task_router import get_task_router

                _route_node = effective_agent if effective_agent != node_id else node_id
                route = CognitiveRouter.ROUTE_MAP.get(_route_node)
                if route:
                    route = CognitiveRouter.ROUTE_TO_MODEL.get(route, route)
                    tier_timeout = 600.0
                else:
                    router = get_task_router()
                    tier = router.get_role_for_node(_route_node)
                    route = router.route_for_tier(tier)
                    route = CognitiveRouter.ROUTE_TO_MODEL.get(route, route)
                    tier_timeout = router.get_timeout_for_tier(tier)
                route_candidate = route
                if route_candidate not in candidates:
                    namespaced_route = f"ollama/{route_candidate}"
                    if namespaced_route in candidates:
                        route_candidate = namespaced_route
                if route_candidate in candidates or any(
                    route_candidate.split("_")[0] in c for c in candidates
                ):
                    candidates = [route_candidate] + [
                        c for c in candidates if c != route_candidate
                    ]
                timeout = min(timeout, tier_timeout) if timeout else tier_timeout
                self.logger.debug(
                    "[TRIBUNAL] node_id=%s tier=%s route=%s timeout=%.1fs",
                    node_id,
                    _route_node,
                    route,
                    timeout,
                )
            except Exception:
                pass

            # 1. Seleciona modelo com semáforo
            model_selected = await self.select_model_with_lock(
                node_id=node_id,
                task_type=task_type,
                candidates=candidates,
                context=context,
            )

            # 2. Adquire semáforo (controla concorrência por modelo)
            #    Tenta todos os candidatos em ordem de ranking, com retry
            #    e backoff exponencial se todos estiverem ocupados.
            #    acquire_model faz autocleanup do token bucket em caso de
            #    timeout — não chamar release_model() sem acquire.
            acquired = False
            for retry_round in range(3):
                for _candidate in candidates:
                    acquired = await self.acquire_model(
                        _candidate, node_id, execution_id=execution_id
                    )
                    if acquired:
                        model_selected = _candidate
                        _sem_acquired = True
                        break
                    self.logger.warning(
                        f"⏰ Tentativa {retry_round + 1}/3: timeout "
                        f"aguardando semáforo para {_candidate}"
                    )
                if acquired:
                    break
                if retry_round < 2:
                    backoff = 2.0 * (2**retry_round)
                    self.logger.info(
                        f"⏳ {node_id}: todos os {len(candidates)} candidato(s) "
                        f"ocupados — backoff {backoff:.1f}s "
                        f"(rodada {retry_round + 1}/3)"
                    )
                    await asyncio.sleep(backoff)

            if not acquired:
                self.logger.error(
                    f"❌ {node_id}: Não conseguiu adquirir semáforo "
                    f"para nenhum modelo após 3 tentativas"
                )
                _st = get_semaphore_tracker()
                _st.record_starvation(node_id, candidates, 3, execution_id=execution_id)
                return ""

            # 2.5 SearchMiddleware — enriquece prompt com contexto web via RAG
            # Todos os agentes (exceto critic, que avalia código) recebem
            # contexto web para reduzir dependência do conhecimento do modelo.
            try:
                from iaglobal.search.search_middleware import SearchMiddleware

                prompt = await SearchMiddleware.enrich(prompt, node_id, context=context)
            except Exception:
                pass

            # 3. Executa modelo
            self.logger.info(
                f"🚀 {node_id}: Executando {model_selected} (timeout={timeout}s)..."
            )

            from iaglobal.providers.provider_router import async_route_generate

            response = await asyncio.wait_for(
                async_route_generate(
                    model=model_selected,
                    prompt=prompt,
                    task_type=task_type,
                    node_id=node_id,
                ),
                timeout=timeout,
            )

            # 4. Calcula métricas
            latency = time.time() - start_time
            success = bool(response and len(str(response).strip()) > 0)

            # 5. Registra no CreditAssignmentEngine
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent

                event = ExecutionEvent(
                    node=effective_agent,
                    model=model_selected,
                    strategy="epsilon_greedy",
                    success=success,
                    latency=latency,
                    reward=1.0 if success else 0.0,
                )
                self.credit_engine.record(event)
                self.logger.debug(
                    f"📊 {effective_agent}: Métrica registrada (success={success}, latency={latency:.2f}s)"
                )

            # 6. Atualiza rewards do bandit
            if success:
                self.rewards[model_selected].append(1.0)
            else:
                self.rewards[model_selected].append(0.0)
                self.trigger_circuit_breaker(model_selected, cooldown=30.0)

            # JOL: Sincroniza pesos com aprendizado contínuo
            try:
                from iaglobal.metabolism.joint_optimization import (
                    joint_optimization_loop,
                )

                await joint_optimization_loop.sync_bandit_weights(self, candidates)
                await joint_optimization_loop.apply_decay(self.credit_engine)
            except Exception:
                pass

            # ── PSC §1.3: Ancestry tracking ──
            task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:16]
            self._psc_register_ancestry(
                effective_agent,
                model_selected or "unknown",
                latency,
                success,
                extra={"task_hash": task_hash, "task_summary": prompt[:80]},
            )

            return str(response) if response else ""

        except asyncio.TimeoutError:
            latency = time.time() - start_time
            self.logger.error(
                f"⏰ {node_id}: Timeout após {latency:.2f}s para {model_selected}"
            )
            task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:16]
            self._psc_register_ancestry(
                effective_agent,
                model_selected or "unknown",
                latency,
                False,
                extra={"task_hash": task_hash, "task_summary": prompt[:80]},
            )
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent

                event = ExecutionEvent(
                    node=effective_agent,
                    model=model_selected or "unknown",
                    strategy="epsilon_greedy",
                    success=False,
                    latency=latency,
                    reward=0.0,
                )
                self.credit_engine.record(event)
            return ""

        except Exception as e:
            latency = time.time() - start_time
            self.logger.error(f"❌ {node_id}: Erro {type(e).__name__}: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:16]
            self._psc_register_ancestry(
                effective_agent,
                model_selected or "unknown",
                latency,
                False,
                extra={"task_hash": task_hash, "task_summary": prompt[:80]},
            )
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent

                event = ExecutionEvent(
                    node=effective_agent,
                    model=model_selected or "unknown",
                    strategy="epsilon_greedy",
                    success=False,
                    latency=latency,
                    reward=0.0,
                )
                self.credit_engine.record(event)
            return ""

        finally:
            # 7. Libera semáforo + token bucket APENAS se foi adquirido
            if _sem_acquired and model_selected:
                self.release_model(
                    model_selected, node_id=effective_agent, execution_id=execution_id
                )
                if not any(
                    p in model_selected
                    for p in ("groq/", "nvidia/", "openrouter/", "gemini/")
                ):
                    try:
                        from iaglobal.execution.token_bucket import LocalModelGate

                        gate = await LocalModelGate.get_instance()
                        await gate.release(effective_agent, model_name=model_selected)
                    except Exception:
                        pass
            # 8. Telemetria metabólica (IVM) — portão universal de todo acesso a
            # modelo de IA. Captura AgentBase e chamadas diretas de nós sem
            # distinção, curando o split-brain de observabilidade do IVMAxiom.
            await self._report_ivm(
                effective_agent, success, latency, model_selected or "unknown"
            )
            # 8b. Reporta métricas ao PhospholipidRegistry para adaptive decay
            await self._report_phospholipid(
                success, latency, model_selected or "unknown"
            )
            # 9. Reporta latência ao LocalModelGate para ajuste dinâmico do
            # token bucket e circuit breaker (apenas modelos locais).
            # Só reporta se o semáforo foi realmente adquirido — latência 0.0
            # numa falha de aquisição inflaria artificialmente o fill_rate.
            if (
                _sem_acquired
                and model_selected
                and not any(
                    p in model_selected
                    for p in ("groq/", "nvidia/", "openrouter/", "gemini/")
                )
            ):
                try:
                    from iaglobal.execution.token_bucket import LocalModelGate

                    gate = await LocalModelGate.get_instance()
                    gate.report_latency(latency * 1000.0)
                except Exception:
                    pass
