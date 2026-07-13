# iaglobal/evolution/skill_quarantine.py

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class QuarantinedSkill:
    skill_name: str
    reason: str
    failure_count: int = 0
    impact_score: int = 0
    quarantined_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    requires_review: bool = False  # Inicia False até ser ativada de facto


class SkillQuarantine:
    """
    Gestor Imunitário de Quarentena (Thread-Safe e Auto-Ativável).
    Isola skills instáveis para proteger a integridade do Grafo de Execução.
    """

    _instance: Optional["SkillQuarantine"] = None
    _lock = threading.Lock()  # Lock para inicialização segura do Singleton

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
        self._quarantined: Dict[str, QuarantinedSkill] = {}
        self._rlock = (
            threading.RLock()
        )  # 🔒 Reentrant Lock para proteção concorrente dos métodos

    def record_failure(self, skill_name: str, error: str, impact: int = 1) -> bool:
        """
        Regista a falha de uma skill e ativa automaticamente a quarentena se elegível.
        """
        with self._rlock:
            if skill_name in self._quarantined:
                q = self._quarantined[skill_name]
                q.failure_count += 1
                q.impact_score = max(q.impact_score, impact)
                # Atualiza o motivo com o erro mais recente
                q.reason = error
            else:
                self._quarantined[skill_name] = QuarantinedSkill(
                    skill_name=skill_name,
                    reason=error,
                    failure_count=1,
                    impact_score=impact,
                )

            # 🔥 RESOLUÇÃO DO BUG 2: Ativação explícita se os limites forem atingidos
            if self._should_quarantine(skill_name):
                self._quarantine(skill_name)
                return True

            return False

    def _should_quarantine(self, skill_name: str) -> bool:
        """Valida internamente os limites de isolamento da skill."""
        q = self._quarantined.get(skill_name)
        if not q:
            return False
        # Regra de ativação: pelo menos 3 falhas AND impacto severo (>= 2)
        return q.failure_count >= 3 and q.impact_score >= 2

    def _quarantine(self, skill_name: str) -> None:
        """Modifica o estado e isola a skill de forma definitiva no sistema."""
        q = self._quarantined[skill_name]
        if not q.requires_review:  # Evita logs duplicados em falhas subsequentes
            q.requires_review = True
            logger.warning(
                f"🚫 [QUARANTINE] Skill '{skill_name}' foi colocada em quarentena! "
                f"Falhas: {q.failure_count}, Impacto Máximo: {q.impact_score}. Motivo: {q.reason}"
            )
            # 💡 Integração futura opcional: Persistir no SQLite local (CORE_DB) via dynamic_registry aqui

    def is_quarantined(self, skill_name: str) -> bool:
        """
        Consulta rápida (Thread-Safe) se uma skill está impedida de rodar.
        """
        with self._rlock:
            q = self._quarantined.get(skill_name)
            if q and q.requires_review:
                return True
            return False


# Instância global atómica para exportação do barramento
quarantine = SkillQuarantine()
