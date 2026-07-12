# iaglobal/immunity/mhc_detector.py
"""
MHC (Major Histocompatibility Complex) — Reconhecimento de "Self" vs "Non-Self" para Skills.

Na biologia, o MHC apresenta peptídeos para células T — aqui, age como:
- Detector de fingerprints de integridade
- Validador de comportamento esperado
- Gatilho automático de quarentena para "parasitas digitais"
"""
import hashlib
import logging
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

from iaglobal.evolution.skill_quarantine import quarantine
from iaglobal._paths import WORK_DIR

logger = logging.getLogger(__name__)


@dataclass
class SkillMHCProfile:
    """Perfil imunológico de uma skill - assinatura de integridade."""
    skill_name: str
    fingerprint: str  # sha3_512 do bytecode/canonical form
    expected_behavior: Dict[str, Any]  # CPU limit, memory pattern, file access pattern
    lineage_hash: str  # Hash da cadeia de herança (DNA preservado)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    anomaly_score: float = 0.0  # Acúmulo de comportamentos anômalos


class MHCDetector:
    """
    Detector de MHC para identificar 'parasitas digitais' (skills não-self).
    
    Operação:
    1. Gera fingerprint sha3_512 da skill
    2. Monitora comportamento em runtime (CPU, I/O, network)
    3. Detecta desvios significativos
    4. Auto-quarentena via SkillQuarantine
    """

    _instance: Optional["MHCDetector"] = None
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
        self._profiles: Dict[str, SkillMHCProfile] = {}
        self._rlock = threading.RLock()
        self._ANOMALY_THRESHOLD = 0.7  # Score para ativar quarentena

    def register_skill(self, skill_name: str, skill_code: str, parent_hash: str = "") -> str:
        """
        Registra skill com fingerprint MHC.
        
        Returns: fingerprint sha3_512
        """
        fingerprint = hashlib.sha3_512(skill_code.encode()).hexdigest()[:32]
        
        with self._rlock:
            self._profiles[skill_name] = SkillMHCProfile(
                skill_name=skill_name,
                fingerprint=fingerprint,
                expected_behavior={
                    "max_cpu_seconds": 5,
                    "allowed_paths": [str(WORK_DIR)],
                    "max_file_ops": 100,
                },
                lineage_hash=parent_hash or fingerprint[:16],
            )
        
        logger.info(f"[MHC] Skill '{skill_name}' registrada com fingerprint {fingerprint[:8]}...")
        return fingerprint

    def validate_execution(self, skill_name: str, metrics: Dict[str, Any]) -> bool:
        """
        Valida comportamento de execução contra perfil esperado.
        
        metrics = {"cpu_seconds": float, "file_ops": int, "network_calls": int, "error": bool}
        
        Returns: True se comportamento é 'self', False se 'non-self' (anômalo)
        """
        with self._rlock:
            profile = self._profiles.get(skill_name)
            if not profile:
                return True  # Não registrada = assume self

            score = 0.0
            expected = profile.expected_behavior

            # CPU anomaly detection
            if metrics.get("cpu_seconds", 0) > expected.get("max_cpu_seconds", 5) * 2:
                score += 0.3
                logger.warning(f"[MHC] CPU anomaly for {skill_name}: {metrics['cpu_seconds']}s")

            # File access anomaly
            if metrics.get("file_ops", 0) > expected.get("max_file_ops", 100) * 2:
                score += 0.2
                logger.warning(f"[MHC] File ops anomaly for {skill_name}: {metrics['file_ops']} ops")

            # Network calls (T-cell activation)
            if metrics.get("network_calls", 0) > 50:
                score += 0.15
                logger.warning(f"[MHC] Network anomaly for {skill_name}: {metrics['network_calls']} calls")

            # Error behavior
            if metrics.get("error", False):
                score += 0.25

            # Acumular score
            profile.anomaly_score = min(1.0, profile.anomaly_score + score)

            # Auto-quarentena se limiar atingido
            if profile.anomaly_score >= self._ANOMALY_THRESHOLD:
                quarantine.record_failure(
                    skill_name,
                    f"MHC anomaly score {profile.anomaly_score:.2f}",
                    impact=3
                )
                return False

            return profile.anomaly_score < 0.3  # Limiar de 'normal'

    def get_fingerprint(self, skill_name: str) -> Optional[str]:
        """Retorna fingerprint MHC da skill."""
        with self._rlock:
            profile = self._profiles.get(skill_name)
            return profile.fingerprint if profile else None

    def reset_anomaly(self, skill_name: str) -> None:
        """Reseta score de anomalia após auditoria positiva."""
        with self._rlock:
            if skill_name in self._profiles:
                self._profiles[skill_name].anomaly_score = 0.0

    def whitelist_origin(self, origin: str, allowed_path_prefixes: Optional[list] = None) -> None:
        """Registra uma origem confiável que não passará por quarentena MHC.

        Args:
            origin: Identificador da origem (ex: "ToolLibrary", "ArtifactFactory")
            allowed_path_prefixes: Lista de prefixos de path permitidos para escrita
        """
        with self._rlock:
            if not hasattr(self, "_whitelist"):
                self._whitelist = {}
            self._whitelist[origin] = {
                "allowed_paths": allowed_path_prefixes or [],
            }
            logger.info("[MHC] Origem whitelisted: %s (paths=%s)", origin, allowed_path_prefixes)

    def _is_whitelisted(self, evidence: Dict[str, Any]) -> bool:
        origin = evidence.get("origin", "")
        if not origin or not hasattr(self, "_whitelist"):
            return False
        whitelisted = self._whitelist.get(origin)
        if not whitelisted:
            return False
        path = evidence.get("unauthorized_path") or ""
        if path and whitelisted.get("allowed_paths"):
            for prefix in whitelisted["allowed_paths"]:
                if str(path).startswith(str(prefix)):
                    logger.debug("[MHC] Path whitelisted: %s (prefix=%s)", path, prefix)
                    return True
        return bool(path) is False  # Se não tem path, aceita pela origem

    def quarantine_if_parasite(self, skill_name: str, evidence: Dict[str, Any]) -> bool:
        """
        Verifica se skill é 'parasita' e coloca em quarentena imediatamente.
        
        evidence = {"unauthorized_path": str, "unexpected_output": bool, "memory_leak": bool}
        """
        # Verificar whitelist antes de qualquer ação
        if self._is_whitelisted(evidence):
            logger.info("[MHC] %s whitelisted — evoluçao legitima ignorada", skill_name)
            return False

        should_quarantine = (
            evidence.get("unauthorized_path") is not None or
            evidence.get("unexpected_output", False) or
            evidence.get("memory_leak", False) or
            evidence.get("cpu_spike", 0) > 10
        )

        if should_quarantine:
            # Capturar stack trace para rastreabilidade
            error_trace = traceback.format_stack()
            
            # Usar impact=3 e 3 falhas mínimas para ativar quarentena
            quarantine.record_failure(
                skill_name,
                f"MHC detected parasite behavior: {evidence}",
                impact=3
            )
            # Forçar quarentena imediata
            with quarantine._rlock:
                if skill_name in quarantine._quarantined:
                    quarantine._quarantined[skill_name].failure_count = 3
                    quarantine._quarantined[skill_name].requires_review = True
            
            logger.error(f"[MHC] PARASITE DETECTED: {skill_name} - {evidence}")
            logger.error(f"Origin Trace: {''.join(error_trace[-5:])}")
            return True

        return False


# Singleton global
mhc_detector = MHCDetector()