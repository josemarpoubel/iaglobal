# iaglobal/immunity/immune_orchestrator.py
"""
ImmuneOrchestrator — Orquestrador imunológico que integra todas as defesas.

Camadas de defesa:
1. LoopDetector - Anti-loops infinitos
2. RegressionDetector - Anti-regressões
3. HallucinationDetector - Anti-alucinações
4. MHCDetector - Anti-parasitas
5. GlutathioneGuardrails - Anti-estresse oxidativo
6. SkillQuarantine - Quarentena automática
"""
import logging
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional

from iaglobal.immunity.loop_detector import LoopDetector
from iaglobal.immunity.regression_detector import RegressionDetector
from iaglobal.immunity.hallucination_detector import HallucinationDetector
from iaglobal.immunity.mhc_detector import MHCDetector, mhc_detector
from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
from iaglobal.evolution.skill_quarantine import quarantine

logger = logging.getLogger(__name__)


@dataclass
class ImmuneReport:
    threat_detected: bool
    threats: Dict[str, Any]
    quarantine_activated: list[str]


class ImmuneOrchestrator:
    """
    Sistema imunológico central do iaGlobal.
    
    Operação:
    - Monitora execuções de skills
    - Aplica múltiplas camadas de defesa
    - Auto-quarentena para "parasitas digitais"
    """

    _instance: Optional["ImmuneOrchestrator"] = None
    _lock = threading.Lock()

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
        self._loop_detector = LoopDetector()
        self._regression_detector = RegressionDetector()
        self._hallucination_detector = HallucinationDetector()
        self._mhc = mhc_detector
        self._guardrails = GlutathioneGuardrails()

    def scan_execution(
        self,
        skill_name: str,
        execution_context: Dict[str, Any],
        output: str,
        metrics: Dict[str, Any],
    ) -> ImmuneReport:
        """
        Escaneia execução completa e retorna relatório imunológico.
        """
        threats = {}
        quarantine_list = []

        # 1. Loop detection
        loops = self._loop_detector.detect()
        for loop in loops:
            threats[f"loop_{loop['node']}"] = loop
            
        # 2. Regression detection - usar check()
        reg = self._regression_detector.check(skill_name, 1.0)  # score padrão
        if reg.get("regression"):
            threats["regression"] = {"detected": True, "node": skill_name}
            
        # 3. Hallucination detection
        hall = self._hallucination_detector.check(output)
        if hall.get("hallucinating"):
            threats["hallucination"] = {"detected": True}
            
        # 4. MHC behavior validation
        mhc_valid = self._mhc.validate_execution(skill_name, metrics)
        if not mhc_valid:
            threats["behavior_anomaly"] = {"score": metrics.get("anomaly_score", 0)}
            quarantine_list.append(skill_name)

        # 5. Glutathione stress guardrails (valida código gerado)
        # Retorna stress_level baixo se código é 'safe'
        guard_result = self._guardrails.validate(str(metrics.get("generated_code", "")), skill_name)
        if not guard_result.get("safe", True):
            stress = 0.8
            threats["oxidative_stress"] = {"level": stress, "issues": guard_result.get("issues", [])}

        threat_detected = len(threats) > 0

        if threat_detected:
            logger.warning(f"[IMMUNE] Threats detected in {skill_name}: {threats}")

        return ImmuneReport(
            threat_detected=threat_detected,
            threats=threats,
            quarantine_activated=quarantine_list,
        )

    def register_skill(self, skill_name: str, skill_code: str, parent_hash: str = "") -> str:
        """Proxy para registro MHC de skill."""
        return self._mhc.register_skill(skill_name, skill_code, parent_hash)

    def health_check(self) -> Dict[str, Any]:
        """Status imunológico geral."""
        return {
            "active_detectors": 5,
            "quarantined_skills": len(quarantine._quarantined),
            "loop_counts": dict(self._loop_detector._execution_count),
            "regression_history_size": len(self._regression_detector._history),
        }


# Singleton global
immune_orchestrator = ImmuneOrchestrator()