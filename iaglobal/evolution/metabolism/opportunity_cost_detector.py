# iaglobal/evolution/metabolism/opportunity_cost_detector.py
"""
OpportunityCostDetector — Detecta 'simbiontes negativos' (parasitas digitais).

Um parasita digital é um agente/processo que:
1. Consome recursos acima do esperado
2. NÃO gera reward_signal positivo

Classifica como: simbionte_negativo → apoptose programada.
"""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from iaglobal.feedback.reward_aggregator import RewardAggregator
from iaglobal.feedback.reward_signal import RewardSignal, RewardSource

logger = logging.getLogger(__name__)


@dataclass
class MetabolicProfile:
    """Perfil metabólico de um agente/skill."""
    agent_name: str
    cpu_seconds_consumed: float = 0.0
    memory_mb_peak: float = 0.0
    file_ops: int = 0
    reward_signals: List[RewardSignal] = None
    last_activity: str = None
    parasite_score: float = 0.0  # 0.0 = saudável, 1.0 = parasita confirmado
    
    def __post_init__(self):
        if self.reward_signals is None:
            self.reward_signals = []
        if self.last_activity is None:
            self.last_activity = datetime.now(timezone.utc).isoformat()


class OpportunityCostDetector:
    """
    Detector de custo de oportunidade (parasitas digitais).
    
    Operação:
    1. Monitora recursos consumidos por agente
    2. Correlaciona com reward_signals
    3. Calcula 'custo-benefício'
    4. Se custo > benefício persistentemente → marca como parasita
    """

    _instance: Optional["OpportunityCostDetector"] = None
    _lock = threading.Lock()

    # Limiares para classificação de parasita
    CPU_COST_THRESHOLD = 5.0  # segundos
    MEMORY_COST_THRESHOLD = 100.0  # MB
    FILE_OPS_COST_THRESHOLD = 100  # operações
    MIN_REWARD_FOR_SYMBIOSIS = 0.3  # reward mínimo para não ser parasita
    PARASITE_SCORE_LIMIT = 0.7  # limiar para apoptose

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._profiles: Dict[str, MetabolicProfile] = {}
        self._rlock = threading.RLock()
        self._aggregator = RewardAggregator()

    def record_consumption(
        self,
        agent_name: str,
        cpu_seconds: float = 0,
        memory_mb: float = 0,
        file_ops: int = 0,
    ) -> None:
        """Registra consumo de recursos pelo agente."""
        with self._rlock:
            if agent_name not in self._profiles:
                self._profiles[agent_name] = MetabolicProfile(agent_name=agent_name)
            
            profile = self._profiles[agent_name]
            profile.cpu_seconds_consumed += cpu_seconds
            profile.memory_mb_peak = max(profile.memory_mb_peak, memory_mb)
            profile.file_ops += file_ops
            profile.last_activity = datetime.now(timezone.utc).isoformat()

    def record_reward(self, agent_name: str, signal: RewardSignal) -> None:
        """Registra reward signal do agente."""
        with self._rlock:
            if agent_name not in self._profiles:
                self._profiles[agent_name] = MetabolicProfile(agent_name=agent_name)
            
            self._profiles[agent_name].reward_signals.append(signal)

    def calculate_opportunity_cost(self, agent_name: str) -> Dict[str, Any]:
        """
        Calcula custo de oportunidade vs benefício.
        
        Returns:
            {
                "is_parasite": bool,
                "cost_score": float,
                "reward_score": float,
                "parasite_score": float,
                "reason": str
            }
        """
        with self._rlock:
            profile = self._profiles.get(agent_name)
            if not profile:
                return {"is_parasite": False, "cost_score": 0, "reward_score": 0.5, "parasite_score": 0}

            # Calcular custo total normalizado
            cost_score = (
                min(1.0, profile.cpu_seconds_consumed / self.CPU_COST_THRESHOLD) * 0.4 +
                min(1.0, profile.memory_mb_peak / self.MEMORY_COST_THRESHOLD) * 0.3 +
                min(1.0, profile.file_ops / self.FILE_OPS_COST_THRESHOLD) * 0.3
            )

            # Calcular reward médio
            reward_score = self._aggregator.aggregate(profile.reward_signals) if profile.reward_signals else 0.0

            # Calcular parasite score
            parasite_score = max(0.0, cost_score - reward_score)
            profile.parasite_score = parasite_score

            # Determinar se é parasita
            is_parasite = parasite_score >= self.PARASITE_SCORE_LIMIT

            reason = ""
            if is_parasite:
                reason = f"Parasite: custo={cost_score:.2f}, reward={reward_score:.2f}"

            return {
                "is_parasite": is_parasite,
                "cost_score": round(cost_score, 2),
                "reward_score": reward_score,
                "parasite_score": round(parasite_score, 2),
                "reason": reason,
                "cpu_consumed": profile.cpu_seconds_consumed,
                "memory_peak_mb": profile.memory_mb_peak,
                "file_ops": profile.file_ops,
            }

    def classify_symbiont(self, agent_name: str) -> str:
        """
        Classifica agente como:
        - 'simbionte_positivo' (custo-benefício favorável)
        - 'simbionte_neutro' (custo≈benefício)
        - 'simbionte_negativo' (parasita)
        """
        result = self.calculate_opportunity_cost(agent_name)
        
        if result["is_parasite"]:
            return "simbionte_negativo"
        
        if result["reward_score"] > result["cost_score"]:
            return "simbionte_positivo"
        return "simbionte_neutro"

    def reset_profile(self, agent_name: str) -> None:
        """Reseta perfil após auditoria/metabolismo positivo."""
        with self._rlock:
            if agent_name in self._profiles:
                del self._profiles[agent_name]

    def get_all_profiles(self) -> Dict[str, MetabolicProfile]:
        """Retorna cópia de todos os perfis metabólicos."""
        with self._rlock:
            return dict(self._profiles)


# Singleton global
opportunity_cost_detector = OpportunityCostDetector()