# iaglobal/evolution/skills/skill_versions.py

import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone

from iaglobal.utils.logger import logger
from .skill import Skill


@dataclass
class SkillVersion:
    """Representa uma versão específica de uma skill com auditoria de hash."""

    skill: Skill
    changelog: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    checksum: str = ""


class VersionManager:
    """
    Gerencia o histórico semântico de versões de skills (Thread-Safe).
    """

    def __init__(self):
        self._versions: Dict[str, List[SkillVersion]] = {}
        self._active: Dict[str, str] = {}  # skill_name → version
        self._lock = threading.Lock()  # Proteção contra concorrência multi-agente

    def get_version(self, skill_name: str, version: str) -> Optional[Skill]:
        """Retorna uma versão específica do histórico histórico."""
        with self._lock:
            versions = self._versions.get(skill_name, [])
            for v in versions:
                if v.skill.version == version:
                    return v.skill
            return None

    # --------------------------------------------------
    # ROLLBACK
    # --------------------------------------------------

    def rollback(self, skill_name: str, version: str) -> bool:
        """
        Faz o rollback local e sincroniza a alteração diretamente no Registry Global.
        """
        with self._lock:
            versions = self._versions.get(skill_name, [])
            target = None
            for v in versions:
                if v.skill.version == version:
                    target = v
                    break

            if not target:
                logger.warning(
                    f"[SKILL-VER] Versão '{version}' não encontrada para '{skill_name}'"
                )
                return False

            self._active[skill_name] = version

        # 🔥 SINCRONIZAÇÃO CRUCIAL: Comunica a reversão ao Skill Registry central
        from .skill_registry import skill_registry

        # Atualiza a referência ativa que o executor consome em tempo real
        skill_registry.register_or_update(target.skill)

        logger.warn(
            f"[SKILL-VER] ROLLBACK EXECUTADO: {skill_name} revertida para v{version}"
        )
        return True

    # --------------------------------------------------
    # COMPARE & DIAGNOSTICS
    # --------------------------------------------------

    def diff(self, skill_name: str, v1: str, v2: str) -> Dict[str, Any]:
        """Compara de forma isolada as mudanças estruturais de contrato entre duas versões."""
        skill_v1 = self.get_version(skill_name, v1)
        skill_v2 = self.get_version(skill_name, v2)

        if not skill_v1 or not skill_v2:
            return {
                "error": f"Uma ou ambas as versões ({v1}, {v2}) não foram localizadas."
            }

        changes = {}
        if skill_v1.inputs != skill_v2.inputs:
            changes["inputs"] = {"from": skill_v1.inputs, "to": skill_v2.inputs}
        if skill_v1.outputs != skill_v2.outputs:
            changes["outputs"] = {"from": skill_v1.outputs, "to": skill_v2.outputs}
        if skill_v1.constraints != skill_v2.constraints:
            changes["constraints"] = {
                "from": skill_v1.constraints,
                "to": skill_v2.constraints,
            }
        if skill_v1.execution_policy != skill_v2.execution_policy:
            changes["execution_policy"] = {
                "from": skill_v1.execution_policy.value,
                "to": skill_v2.execution_policy.value,
            }

        return {
            "skill": skill_name,
            "v1": v1,
            "v2": v2,
            "changes": changes,
            "has_changes": len(changes) > 0,
        }

    def clear(self):
        with self._lock:
            self._versions.clear()
            self._active.clear()


# Instância global unificada
version_manager = VersionManager()
