# iaglobal/graphs/policy.py

from collections import defaultdict
from typing import Dict, List, Optional, Any

from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
from iaglobal.evolution.epigenetic import get_max_iterations, adapt_bandit_policy


class PolicyRegistry:
    """
    Registro de Políticas de Domínio.
    Garante que todos os domínios utilizem a MESMA inteligência do BanditPolicy.
    Isso é vital para que o CircuitBreaker e os Probes de latência sejam globais
    (se um provedor cair no domínio 'coder', o domínio 'critic' saberá imediatamente).
    """

    def __init__(self):
        # 1. FIX ARQUITETURAL: Usa o motor Global unificado em vez de instanciar novos.
        # O BanditPolicy já tem suporte interno para separar histórico por node/contexto
        # através da sua propriedade 'self.context_memory'.
        self._global_bandit = _get_bandit()
    
    def get(self, domain: str) -> BanditPolicy:
        """
        Retorna o motor de política. 
        Mantemos a assinatura por retrocompatibilidade, mas a inteligência é unificada.
        """
        # Em sistemas avançados, o domain pode ser injetado para logging, 
        # mas a classe motor deve ser a mesma para compartilhar o cache de rede.
        return self._global_bandit
    
    def all_domains(self) -> List[str]:
        """
        Retorna todos os domínios mapeados no histórico global.
        """
        return list(self._global_bandit.context_memory.keys())
    
    def apply_epigenetic_adjustments(self):
        """Apply epigenetic flags to the shared bandit policy."""
        self._global_bandit._apply_epigenetic_adjustments()

    @staticmethod
    def compute_node_policy(node: Any) -> Optional[Dict[str, str]]:
        """
        🧠 Decide dinamicamente a estratégia de evolução de um nó.
        [FIX]: Definido como estático para evitar TypeError ao ser invocado.
        """
        try:
            score = node.success_rate()
            latency = node.avg_latency()
        except AttributeError:
            # Proteção contra nós que ainda não possuem as propriedades populadas
            return None

        # CASO CRÍTICO: Nó falhando (Taxa de sucesso menor que 40%)
        if score < 0.4:
            return {
                "strategy": "safe",
                "model_hint": "none"  # Removemos o viés, forçando o Bandit a reavaliar opções seguras
            }

        # CASO EXCELENTE: Nó com alta resiliência e velocidade
        # LLMs demoram, uma latência de 5.0s a 8.0s é considerada 'fast' no estado da arte.
        if score > 0.8 and latency < 8.0:
            return {
                "strategy": "fast",
                "model_hint": getattr(node, "model_hint", "none")
            }

        # CASO NEUTRO: Mantém a estratégia padrão configurada
        return None
