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
import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any

from iaglobal.utils.logger import get_logger

# Singleton global
_bandit_instance: Optional['BanditPolicy'] = None


def _get_bandit() -> 'BanditPolicy':
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

    # Semáforos por modelo para evitar rate limit (cada modelo responde 1 requisição por vez)
    MODEL_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
    SEMAPHORE_LOCK = asyncio.Lock()
    
    # Configuração de concorrência máxima por tipo de modelo
    CLOUD_MODEL_CONCURRENCY = 1  # Groq, NVIDIA, etc — 1 por vez para evitar 429
    LOCAL_MODEL_CONCURRENCY = 4  # Ollama local pode lidar com mais

    def __init__(self, epsilon: float = 0.1, decay: float = 0.99, 
                 credit: Optional[Any] = None, probe_timeout: float = 5.0):
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
        self.context_memory: Dict[str, Dict] = {}  # Memória por contexto/domínio para epigenética
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
            self.logger.info(f"🎯 BanditPolicy inicializado com pesos: {dict(self.weights)}")

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
        self, node: str, model: str, strategy: str,
        success: bool, latency: float, reward: float
    ) -> None:
        self.update_reward(model, reward, ivm=1.0 if success else 0.0)
        if not success:
            self.trigger_circuit_breaker(model, cooldown=latency * 2)
    
    def update(self, action: str, reward: float) -> None:
        self.update_reward(action, reward, ivm=1.0)

    def select_arm(self, arms: List[str]) -> str:
        """Seleciona um braço usando epsilon-greedy."""
        # Verificar circuit breakers
        valid_arms = [arm for arm in arms if self.circuit_breakers.get(arm, 0) < time.time()]
        
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
        self.logger.warning(f"⚡ Circuit breaker acionado para {arm}. Cooldown: {cooldown}s")

    async def _get_model_semaphore(self, model_name: str) -> asyncio.Semaphore:
        """Obtém ou cria semáforo para o modelo específico."""
        async with self.SEMAPHORE_LOCK:
            if model_name not in self.MODEL_SEMAPHORES:
                # Modelos cloud (Groq, NVIDIA) têm concorrência 1
                # Modelos locais (Ollama) podem ter concorrência maior
                is_cloud = any(provider in model_name for provider in ["groq/", "nvidia/", "openrouter/", "gemini/"])
                concurrency = self.CLOUD_MODEL_CONCURRENCY if is_cloud else self.LOCAL_MODEL_CONCURRENCY
                self.MODEL_SEMAPHORES[model_name] = asyncio.Semaphore(concurrency)
                self.logger.info(f"🔒 Semáforo criado para {model_name} (concorrência={concurrency})")
            return self.MODEL_SEMAPHORES[model_name]

    async def acquire_model(self, model_name: str) -> bool:
        """
        Adquire semáforo para usar o modelo.
        Retorna True se conseguiu adquirir, False se timeout.
        """
        semaphore = await self._get_model_semaphore(model_name)
        try:
            # Timeout curto: 3s para cloud, 1s para local
            is_cloud = any(provider in model_name for provider in ["groq/", "nvidia/", "openrouter/", "gemini/"])
            timeout = 3.0 if is_cloud else 1.0
            
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            self._model_in_use[model_name] = True
            self.logger.debug(f"🔒 {model_name} adquirido (timeout={timeout}s)")
            return True
        except asyncio.TimeoutError:
            self.logger.debug(f"⏰ Timeout ({timeout}s) aguardando {model_name}")
            return False

    def release_model(self, model_name: str) -> None:
        """Libera o semáforo do modelo após uso."""
        if model_name in self.MODEL_SEMAPHORES:
            self.MODEL_SEMAPHORES[model_name].release()
            self._model_in_use[model_name] = False
            self.logger.debug(f"🔓 {model_name} liberado")

    def _apply_epigenetic_adjustments(self) -> None:
        """
        Aplica ajustes epigenéticos baseados em histórico de execuções.
        Método chamado pelo PolicyRegistry para sincronização.
        """
        # Placeholder para futura integração com EpigeneticRegistry
        # Por enquanto, apenas loga o estado atual
        self.logger.debug(f"[EPIGENETIC] Ajustes aplicados. Contextos: {len(self.context_memory)}")

    async def select_model_with_lock(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None
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
        self.logger.info(f"🎯 {node_id}: {model} selecionado (score={ranked[0][0]:.2f})")
        return model

    def _sync_weights_from_credit(self, candidates: List[str]) -> None:
        """
        Atualiza pesos do Bandit baseado no histórico do CreditAssignmentEngine.
        Isso permite que o Bandit aprenda com execuções passadas.
        """
        if not self.credit_engine:
            self.logger.debug("⚠️ _sync_weights_from_credit: credit_engine é None")
            return
        
        self.logger.debug(f"🔄 _sync_weights_from_credit: {len(self.credit_engine.stats)} stats no credit_engine")
        
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
                
                # Atualiza peso se houver histórico
                if self.weights[model] == 0.0 and new_weight > 0.0:
                    self.weights[model] = new_weight
                    self.logger.info(f"📈 {model}: peso atualizado para {new_weight:.2f} (success={success_rate:.2f}, reward={avg_reward:.2f})")

    def rank_models(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None
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
                score = -float('inf')  # Penaliza modelos em cooldown
            ranked.append((score, model))
        
        # Ordenar por score decrescente
        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def select_model(
        self,
        node_id: str,
        task_type: str,
        candidates: List[str],
        context: Optional[dict] = None
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
        context: Optional[dict] = None
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
        self,
        model_name: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Executa um modelo assincronamente delegando ao provider_router.
        O provider_router gerencia semáforos e rate limiting internamente.
        
        Returns:
            String com a resposta do modelo (vazia em caso de falha)
        """
        from iaglobal.providers.provider_router import async_route_generate

        task_type = kwargs.get("task_type", "general")
        self.logger.info(f"🚀 Executando modelo {model_name} (task={task_type})...")
        
        try:
            response = await async_route_generate(
                model=model_name,
                prompt=prompt,
                task_type=task_type,
            )
            if response:
                return str(response)
        except Exception as e:
            self.logger.warning(f"async_execute_model falhou: {e}")
            # Dispara circuit breaker se falhar repetidamente
            self.trigger_circuit_breaker(model_name, cooldown=30.0)
        
        return ""

    async def generate(
        self,
        node_id: str,
        prompt: str,
        candidates: List[str],
        context: Optional[dict] = None,
        task_type: str = "general",
        timeout: float = 30.0
    ) -> str:
        """
        Método completo de geração via Bandit:
        1. Seleciona melhor modelo (ε-greedy + pesos + credit assignment)
        2. Adquire semáforo do modelo (controla concorrência)
        3. Executa via provider_router
        4. Libera semáforo
        5. Registra métricas no CreditAssignmentEngine
        
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
        from datetime import datetime
        
        start_time = time.time()
        model_selected = None
        
        try:
            # 1. Seleciona modelo com semáforo
            model_selected = await self.select_model_with_lock(
                node_id=node_id,
                task_type=task_type,
                candidates=candidates,
                context=context
            )
            
            # 2. Adquire semáforo (controla concorrência por modelo)
            acquired = await self.acquire_model(model_selected)
            if not acquired:
                self.logger.warning(f"⏰ Timeout aguardando semáforo para {model_selected}")
                # Tenta fallback
                fallback_candidates = [c for c in candidates if c != model_selected]
                if fallback_candidates:
                    model_selected = fallback_candidates[0]
                    acquired = await self.acquire_model(model_selected)
            
            if not acquired:
                self.logger.error(f"❌ {node_id}: Não conseguiu adquirir semáforo para nenhum modelo")
                return ""
            
            # 3. Executa modelo
            self.logger.info(f"🚀 {node_id}: Executando {model_selected} (timeout={timeout}s)...")
            
            from iaglobal.providers.provider_router import async_route_generate
            
            response = await asyncio.wait_for(
                async_route_generate(
                    model=model_selected,
                    prompt=prompt,
                    task_type=task_type,
                ),
                timeout=timeout
            )
            
            # 4. Calcula métricas
            latency = time.time() - start_time
            success = bool(response and len(str(response).strip()) > 0)
            
            # 5. Registra no CreditAssignmentEngine
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent
                event = ExecutionEvent(
                    node=node_id,
                    model=model_selected,
                    strategy="epsilon_greedy",
                    success=success,
                    latency=latency,
                    reward=1.0 if success else 0.0
                )
                self.credit_engine.record(event)
                self.logger.debug(f"📊 {node_id}: Métrica registrada (success={success}, latency={latency:.2f}s)")
            
            # 6. Atualiza rewards do bandit
            if success:
                self.rewards[model_selected].append(1.0)
            else:
                self.rewards[model_selected].append(0.0)
                self.trigger_circuit_breaker(model_selected, cooldown=30.0)
            
            return str(response) if response else ""
            
        except asyncio.TimeoutError:
            latency = time.time() - start_time
            self.logger.error(f"⏰ {node_id}: Timeout após {latency:.2f}s para {model_selected}")
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent
                event = ExecutionEvent(
                    node=node_id,
                    model=model_selected or "unknown",
                    strategy="epsilon_greedy",
                    success=False,
                    latency=latency,
                    reward=0.0
                )
                self.credit_engine.record(event)
            return ""
            
        except Exception as e:
            latency = time.time() - start_time
            self.logger.error(f"❌ {node_id}: Erro {type(e).__name__}: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            if self.credit_engine:
                from iaglobal.graphs.telemetry import ExecutionEvent
                event = ExecutionEvent(
                    node=node_id,
                    model=model_selected or "unknown",
                    strategy="epsilon_greedy",
                    success=False,
                    latency=latency,
                    reward=0.0
                )
                self.credit_engine.record(event)
            return ""
            
        finally:
            # 7. SEMPRE libera o semáforo
            if model_selected:
                self.release_model(model_selected)
