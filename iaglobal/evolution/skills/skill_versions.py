# iaglobal/evolution/skills/skill_versions.py

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone

from iaglobal.utils.logger import logger
from iaglobal.utils.hash_utils import LineageID
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

    # --------------------------------------------------
    # REGISTER VERSION
    # --------------------------------------------------

    def register_version(
        self,
        skill: Skill,
        changelog: str = "",
    ) -> SkillVersion:
        """Registra uma nova versão de skill de forma atómica."""
        checksum = LineageID.compute_skill_checksum(
            name=skill.name,
            version=skill.version,
            payload=skill.to_dict(),
        )

        version_entry = SkillVersion(
            skill=skill,
            changelog=changelog,
            checksum=checksum,
        )

        with self._lock:
            if skill.name not in self._versions:
                self._versions[skill.name] = []
            
            # Evita duplicar exatamente a mesma entrada de versão
            if any(v.skill.version == skill.version for v in self._versions[skill.name]):
                logger.debug(f"[SKILL-VER] Versão {skill.name} v{skill.version} já rastreada.")
                return version_entry

            self._versions[skill.name].append(version_entry)
            self._active[skill.name] = skill.version

        logger.info(
            f"[SKILL-VER] Nova versão registada: {skill.name} v{skill.version} "
            f"(checksum={checksum})"
        )
        return version_entry

    # --------------------------------------------------
    # QUERY
    # --------------------------------------------------

    def get_active_version(self, skill_name: str) -> Optional[Skill]:
        """Retorna a skill na versão marcada atualmente como ativa."""
        with self._lock:
            active_ver = self._active.get(skill_name)
            if not active_ver:
                return None
            versions = self._versions.get(skill_name, [])
            for v in versions:
                if v.skill.version == active_ver:
                    return v.skill
            return None

    def get_version(self, skill_name: str, version: str) -> Optional[Skill]:
        """Retorna uma versão específica do histórico histórico."""
        with self._lock:
            versions = self._versions.get(skill_name, [])
            for v in versions:
                if v.skill.version == version:
                    return v.skill
            return None

    def list_versions(self, skill_name: str) -> List[SkillVersion]:
        with self._lock:
            return list(self._versions.get(skill_name, []))

    def list_all_skills(self) -> List[str]:
        with self._lock:
            return list(self._versions.keys())

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
                logger.warning(f"[SKILL-VER] Versão '{version}' não encontrada para '{skill_name}'")
                return False

            self._active[skill_name] = version
        
        # 🔥 SINCRONIZAÇÃO CRUCIAL: Comunica a reversão ao Skill Registry central
        from .skill_registry import skill_registry
        # Atualiza a referência ativa que o executor consome em tempo real
        skill_registry.register_or_update(target.skill)
        
        logger.warn(f"[SKILL-VER] ROLLBACK EXECUTADO: {skill_name} revertida para v{version}")
        return True

    def rollback_previous(self, skill_name: str) -> bool:
        """Rollback seguro para a versão imediatamente anterior na árvore cronológica."""
        with self._lock:
            versions = self._versions.get(skill_name, [])
            if len(versions) < 2:
                logger.warning(f"[SKILL-VER] Sem histórico suficiente para reverter '{skill_name}'")
                return False

            current_active = self._active.get(skill_name)
            
            # Encontra a posição da versão atual no histórico
            idx = -1
            for i, v in enumerate(versions):
                if v.skill.version == current_active:
                    idx = i
                    break

            # Se for a primeira versão ou não encontrada, pega a penúltima da lista com segurança
            if idx <= 0:
                target_version = versions[-2].skill.version
            else:
                target_version = versions[idx - 1].skill.version

        # Executa fora do lock interno para evitar deadlock com a sincronização do registry
        return self.rollback(skill_name, target_version)

    # --------------------------------------------------
    # COMPARE & DIAGNOSTICS
    # --------------------------------------------------

    def diff(self, skill_name: str, v1: str, v2: str) -> Dict[str, Any]:
        """Compara de forma isolada as mudanças estruturais de contrato entre duas versões."""
        skill_v1 = self.get_version(skill_name, v1)
        skill_v2 = self.get_version(skill_name, v2)

        if not skill_v1 or not skill_v2:
            return {"error": f"Uma ou ambas as versões ({v1}, {v2}) não foram localizadas."}

        changes = {}
        if skill_v1.inputs != skill_v2.inputs:
            changes["inputs"] = {"from": skill_v1.inputs, "to": skill_v2.inputs}
        if skill_v1.outputs != skill_v2.outputs:
            changes["outputs"] = {"from": skill_v1.outputs, "to": skill_v2.outputs}
        if skill_v1.constraints != skill_v2.constraints:
            changes["constraints"] = {"from": skill_v1.constraints, "to": skill_v2.constraints}
        if skill_v1.execution_policy != skill_v2.execution_policy:
            changes["execution_policy"] = {"from": skill_v1.execution_policy.value, "to": skill_v2.execution_policy.value}

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
