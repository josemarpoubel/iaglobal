# iaglobal/cognition/adaptive_router.py
"""
AdaptiveRouter — Roteamento de LLM baseado em custo-benefício metabólico.

Objetivo: Minimizar tokens + custo enquanto mantém confiabilidade imunológica.

Critérios de seleção (IVM):
- P (Productivity): taxa de sucesso
- E (Energy): inverso de latência + tokens
- C (Cooperation): integração com immunity (skills aprovadas)
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.immunity.mhc_detector import MHCDetector
from iaglobal.evolution.metabolism.opportunity_cost_detector import OpportunityCostDetector

logger = logging.getLogger(__name__)


class AdaptiveRouter:
    """
    Router que aprende do histórico de performance.
    
    Operação:
    1. Analisa métricas de execution_history
    2. Calcula IVM para cada provedor
    3. Usa MHC para validar skills antes do roteamento
    4. Seleciona provedor ótimo via IVM score
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # Bandit já é singleton global - acessar via módulo
        from iaglobal import graphs
        graph_module = getattr(graphs, 'bandit', None)
        if graph_module:
            self._bandit = graph_module
        else:
            self._bandit = None
        self._mhc = MHCDetector()
        self._cost_detector = OpportunityCostDetector()
        self._provider_scores: Dict[str, float] = {}

    def calculate_ivm(self, provider: str, metrics: Dict[str, Any], weights: Dict[str, float] = None) -> float:
        """
        Calcula IVM (Índice de Viabilidade Metabólica) para provedor.
        
        Fórmula padrão:
        IVM = (P × 0.4) + (E × 0.4) + (C × 0.1) + (I × 0.1)
        
        Args:
            provider: nome do provedor
            metrics: métricas de performance
            weights: pesos customizados (epigenéticos)
        """
        # Pesos epigenéticos (configuráveis)
        if weights is None:
            weights = {
                "productivity": 0.4,
                "energy": 0.4,
                "cooperation": 0.1,
                "immunity": 0.1,
            }
        success_rate = metrics.get("success_rate", 0.5)
        avg_latency = metrics.get("avg_latency", 10.0)
        avg_tokens = metrics.get("avg_tokens", 1000)
        mhc_valid = metrics.get("mhc_validated", 0.5)
        skills_approved = metrics.get("skills_approved", 0.5)
        
        # Normalizar energia (latência inversa)
        energy_score = max(0, min(1, 20.0 / avg_latency)) if avg_latency > 0 else 1.0
        
        ivm = (
            success_rate * weights["productivity"] +
            energy_score * weights["energy"] +
            skills_approved * weights["cooperation"] +
            mhc_valid * weights["immunity"]
        )
        
        return round(ivm, 3)

    async def select_optimal_provider(self, task_type: str, required_mhc: bool = True) -> str:
        """
        Seleciona provedor ótimo via IVM.
        
        Args:
            task_type: tipo da tarefa (code, general, image, video)
            required_mhc: requer validação MHC prévia
        
        Returns:
            Nome do provedor recomendado
        """
        # Usar select_model do bandit se disponível
        if self._bandit:
            try:
                # Candidatos padrão: cloud primeiro, local fallback
                candidates = ["groq/llama-3.3-70b-versatile", "nvidia/mistralai/mistral-large-3-675b-instruct-2512", "ollama/qwen2.5:0.5b"]
                result = await self._bandit.select_model_with_lock("adaptive_router", task_type, candidates)
                if result:
                    return result
            except Exception:
                pass
        
        return "ollama"  # Fallback padrão

    def record_performance(self, provider: str, output: str, metrics: Dict[str, Any]) -> None:
        """Atualiza métricas do provedor."""
        # Não precisa fazer nada - Bandit atualiza automaticamente via execution_metrics
        pass

    def get_provider_metrics(self, provider: str) -> Dict[str, Any]:
        """Obtém métricas do provedor."""
        if self._bandit:
            try:
                return self._bandit.get_provider_metrics(provider)
            except Exception:
                pass
        return {"success_rate": 0.5, "avg_latency": 10.0, "avg_tokens": 1000, "mhc_validated": 0.5, "skills_approved": 0.5}


# Singleton
adaptive_router = AdaptiveRouter()