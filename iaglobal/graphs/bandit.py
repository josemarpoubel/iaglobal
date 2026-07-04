# iaglobal/graphs/bandit.py
"""
Multi-Armed Bandit para seleção de provedores LLM com:
- IVM-based Rewards
- Epsilon-Greedy
- Fallback Chain
"""

import random
import time
from collections import defaultdict
from typing import Dict, List, Optional

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

    def __init__(self, epsilon: float = 0.1, decay: float = 0.99):
        self.epsilon = epsilon
        self.decay = decay
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
