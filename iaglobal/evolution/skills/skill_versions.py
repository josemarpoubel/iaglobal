# iaglobal/evolution/skills/skill_versions.py

"""
🎯 Skill Version Manager — controle de versão e migração de skills

Gerencia:
- Versionamento semântico de skills
- Migração entre versões
- Histórico de mudanças por versão
- Rollback para versões anteriores
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone

from iaglobal.utils.logger import logger
from .skill import Skill


@dataclass
class SkillVersion:
    """Representa uma versão específica de uma skill."""

    skill: Skill
    changelog: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    checksum: str = ""


class VersionManager:
    """
    Gerencia versões de skills.

    Mantém histórico completo de versões e permite:
    - Listar versões
    - Fazer rollback
    - Comparar versões
    - Migrar entre versões
    """

    def __init__(self):
        self._versions: Dict[str, List[SkillVersion]] = {}
        self._active: Dict[str, str] = {}  # skill_name → version

    # --------------------------------------------------
    # REGISTER VERSION
    # --------------------------------------------------

    def register_version(
        self,
        skill: Skill,
        changelog: str = "",
    ) -> SkillVersion:
        """Registra uma nova versão de skill."""
        import hashlib

        checksum = hashlib.sha3_256(
            f"{skill.name}:{skill.version}:{skill.to_dict()}".encode()
        ).hexdigest()[:16]

        version = SkillVersion(
            skill=skill,
            changelog=changelog,
            checksum=checksum,
        )

        if skill.name not in self._versions:
            self._versions[skill.name] = []

        self._versions[skill.name].append(version)
        self._active[skill.name] = skill.version

        logger.info(
            f"[SKILL-VER] Nova versão: {skill.name} v{skill.version} "
            f"(checksum={checksum})"
        )
        return version

    # --------------------------------------------------
    # QUERY
    # --------------------------------------------------

    def get_active_version(self, skill_name: str) -> Optional[Skill]:
        """Retorna a skill na versão ativa."""
        active_ver = self._active.get(skill_name)
        if not active_ver:
            return None
        versions = self._versions.get(skill_name, [])
        for v in versions:
            if v.skill.version == active_ver:
                return v.skill
        return None

    def get_version(self, skill_name: str, version: str) -> Optional[Skill]:
        """Retorna uma versão específica."""
        versions = self._versions.get(skill_name, [])
        for v in versions:
            if v.skill.version == version:
                return v.skill
        return None

    def list_versions(self, skill_name: str) -> List[SkillVersion]:
        """Lista todas as versões de uma skill."""
        return list(self._versions.get(skill_name, []))

    def list_all_skills(self) -> List[str]:
        """Lista todos os nomes de skills com versões registradas."""
        return list(self._versions.keys())

    # --------------------------------------------------
    # ROLLBACK
    # --------------------------------------------------

    def rollback(self, skill_name: str, version: str) -> bool:
        """
        Faz rollback para uma versão específica.
        Retorna True se bem-sucedido.
        """
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
        logger.info(f"[SKILL-VER] Rollback: {skill_name} → v{version}")
        return True

    def rollback_previous(self, skill_name: str) -> bool:
        """Rollback para a versão anterior (se houver)."""
        versions = self._versions.get(skill_name, [])
        if len(versions) < 2:
            return False

        current_active = self._active.get(skill_name)
        for i, v in enumerate(versions):
            if v.skill.version == current_active and i > 0:
                return self.rollback(skill_name, versions[i - 1].skill.version)

        # Se a atual não foi encontrada, pega a penúltima
        return self.rollback(skill_name, versions[-2].skill.version)

    # --------------------------------------------------
    # COMPARE
    # --------------------------------------------------

    def diff(self, skill_name: str, v1: str, v2: str) -> Dict[str, Any]:
        """Compara duas versões de uma skill."""
        skill_v1 = self.get_version(skill_name, v1)
        skill_v2 = self.get_version(skill_name, v2)

        if not skill_v1 or not skill_v2:
            return {"error": "Versão não encontrada"}

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


# Instância global
version_manager = VersionManager()
