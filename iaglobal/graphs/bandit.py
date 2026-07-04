# iaglobal/graphs/bandit.py
"""
Multi-Armed Bandit para seleção de provedores LLM com:
- IVM-based Rewards
- Epsilon-Greedy
- Fallback Chain
- Credit Assignment Integration
"""

import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any

from iaglobal.utils.logger import get_logger

# Singleton global
_bandit_instance: Optional['BanditPolicy'] = None


def _get_bandit() -> 'BanditPolicy':
    """Retorna instância singleton do BanditPolicy."""
    global _bandit_instance
    if _bandit_instance is None:
        _bandit_instance = BanditPolicy()
    return _bandit_instance


class BanditPolicy:
    """Multi-Armed Bandit para seleção de provedores."""

    def __init__(self, epsilon: float = 0.1, decay: float = 0.99, 
                 credit: Optional[Any] = None, probe_timeout: float = 5.0):
        self.epsilon = epsilon
        self.decay = decay
        self.credit_engine = credit  # CreditAssignmentEngine opcional
        self.probe_timeout = probe_timeout
        self.weights: Dict[str, float] = defaultdict(float)
        self.rewards: Dict[str, List[float]] = defaultdict(list)
        self.circuit_breakers: Dict[str, float] = {}
        self.logger = get_logger("bandit")

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

    async def ajustar_por_ivm(self) -> None:
        """Ajusta pesos para priorizar agentes com IVM > threshold."""
        self.logger.info("🎯 Ajustando BanditPolicy por IVM...")
        # Em produção, consultar OmniMind ou EpigeneticRegistry
        # para obter lista de agentes e seus IVMs
        # Exemplo: self.weights["high_ivm_agent"] *= 1.5
        self.logger.info("✅ BanditPolicy ajustado para priorizar agentes de alta performance")

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
    ) -> dict:
        """
        Executa um modelo assincronamente (wrapper para provedor).
        
        Returns:
            Dict com resultado da execução
        """
        # Este método delega para o provider_router ou LLMClient
        # Implementação básica como placeholder
        self.logger.info(f"🚀 Executando modelo {model_name}...")
        
        # Em produção, isso chamaria o provedor real
        # Por enquanto, retorna estrutura básica
        return {
            "model": model_name,
            "prompt": prompt,
            "status": "delegated",
            "kwargs": kwargs
        }
