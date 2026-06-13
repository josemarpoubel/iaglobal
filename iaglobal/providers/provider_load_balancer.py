# 📦 iaglobal/providers/provider_load_balancer.py

"""
Módulo de Load Balancing [DEPRECATED / FACADE]
----------------------------------------------
NOTA DE ARQUITETURA: O balanceamento de carga tradicional foi desativado.
A responsabilidade de roteamento inteligente, resiliência e failover agora
pertence exclusivamente ao motor de Reinforcement Learning (BanditPolicy).

Esta classe atua apenas como um "Pass-Through" (Túnel) para manter a 
retrocompatibilidade da estrutura de diretórios e evitar quebras de importação.
"""

from typing import List, Optional, Any
from iaglobal.utils.logger import logger

class ProviderLoadBalancerFacade:
    
    def __init__(self):
        pass

    def select_provider(self, node: str, strategy: str, candidates: Optional[List[str]] = None) -> str:
        from iaglobal.graphs.bandit import _get_bandit
        return _get_bandit().select_model(node, strategy, candidates)

    def select_top_providers(self, node: str, strategy: str, n: int = 3, candidates: Optional[List[str]] = None) -> List[str]:
        from iaglobal.graphs.bandit import _get_bandit
        return _get_bandit().select_top_n(node, strategy, n, candidates)

    # =========================================================
    # BURACO NEGRO DE RETROCOMPATIBILIDADE (LEGACY HANDLERS)
    # Absorvem e ignoram chamadas antigas sem gerar erro
    # =========================================================
    
    def report(self, *args, **kwargs):
        """Ignorado. A telemetria agora é feita via CreditAssignmentEngine e Metrics."""
        pass

    def add_provider(self, provider: Any):
        pass 
        
    def remove_provider(self, provider: str):
        pass 
        
    def get_all_active(self) -> List[str]:
        from iaglobal.graphs.bandit import BanditPolicy
        return BanditPolicy.default_candidates()

load_balancer = ProviderLoadBalancerFacade()

