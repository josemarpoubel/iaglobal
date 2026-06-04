# iaglobal/evolution/skills/skill_registry.py

"""
🎯 Skill Registry — registro global de skills versionadas

Gerencia o ciclo de vida das skills:
- Registro
- Busca por nome/versão
- Versionamento
- Ativação/desativação
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field

from iaglobal.utils.logger import logger
from .skill import Skill, ExecutionPolicy


@dataclass
class SkillEntry:
    skill: Skill
    active: bool = True
    usage_count: int = 0


class SkillRegistry:
    """
    Registry global de skills.

    Skills são registradas por nome (único). Cada skill pode ter
    múltiplas versões, mas apenas uma ativa por vez.
    """

    def __init__(self):
        self._skills: Dict[str, SkillEntry] = {}
        self._version_history: Dict[str, List[Skill]] = {}

    # --------------------------------------------------
    # REGISTER
    # --------------------------------------------------

    def register(self, skill: Skill) -> bool:
        """Registra uma skill. Retorna False se já existir com mesmo nome."""
        if skill.name in self._skills:
            logger.warning(f"[SKILL] Skill '{skill.name}' já registrada")
            return False

        self._skills[skill.name] = SkillEntry(skill=skill)
        self._version_history[skill.name] = [skill]
        logger.info(f"[SKILL] Registrada: {skill.name} v{skill.version}")
        return True

    def register_or_update(self, skill: Skill) -> bool:
        """Registra ou atualiza (nova versão) uma skill."""
        if skill.name in self._skills:
            entry = self._skills[skill.name]
            # Salva versão anterior no histórico
            if skill.name not in self._version_history:
                self._version_history[skill.name] = []
            self._version_history[skill.name].append(entry.skill)
            # Atualiza
            entry.skill = skill
            logger.info(f"[SKILL] Atualizada: {skill.name} → v{skill.version}")
            return True
        return self.register(skill)

    # --------------------------------------------------
    # QUERY
    # --------------------------------------------------

    def get(self, name: str) -> Optional[Skill]:
        """Retorna skill ativa pelo nome."""
        entry = self._skills.get(name)
        if entry and entry.active:
            return entry.skill
        return None

    def get_version(self, name: str, version: str) -> Optional[Skill]:
        """Retorna versão específica de uma skill."""
        history = self._version_history.get(name, [])
        for skill in history:
            if skill.version == version:
                return skill
        entry = self._skills.get(name)
        if entry and entry.skill.version == version:
            return entry.skill
        return None

    def list_skills(self, active_only: bool = True) -> List[Skill]:
        """Lista todas as skills (ou apenas as ativas)."""
        if active_only:
            return [e.skill for e in self._skills.values() if e.active]
        return [e.skill for e in self._skills.values()]

    def list_by_policy(self, policy: ExecutionPolicy) -> List[Skill]:
        """Lista skills por política de execução."""
        return [
            e.skill
            for e in self._skills.values()
            if e.active and e.skill.execution_policy == policy
        ]

    # --------------------------------------------------
    # ACTIVATION
    # --------------------------------------------------

    def activate(self, name: str) -> bool:
        """Ativa uma skill."""
        entry = self._skills.get(name)
        if entry:
            entry.active = True
            return True
        return False

    def deactivate(self, name: str) -> bool:
        """Desativa uma skill."""
        entry = self._skills.get(name)
        if entry:
            entry.active = False
            return True
        return False

    def is_active(self, name: str) -> bool:
        entry = self._skills.get(name)
        return entry is not None and entry.active

    # --------------------------------------------------
    # USAGE TRACKING
    # --------------------------------------------------

    def increment_usage(self, name: str):
        entry = self._skills.get(name)
        if entry:
            entry.usage_count += 1

    def get_usage_count(self, name: str) -> int:
        entry = self._skills.get(name)
        return entry.usage_count if entry else 0

    # --------------------------------------------------
    # VERSION HISTORY
    # --------------------------------------------------

    def get_version_history(self, name: str) -> List[Skill]:
        return list(self._version_history.get(name, []))

    # --------------------------------------------------
    # ALTERNATIVES (skill routing)
    # --------------------------------------------------

    def find_alternatives(self, skill_name: str, available_inputs: set) -> List[Skill]:
        """
        Encontra skills alternativas para substituir 'skill_name' quando
        seus inputs não estão disponíveis.

        Estratégia:
        1. Pega os outputs da skill original
        2. Busca skills ativas com outputs compatíveis (intersecção)
        3. Filtra para aquelas cujos inputs estão todos disponíveis
        4. Ordena por grau de compatibilidade (mais outputs em comum primeiro)

        Args:
            skill_name: Nome da skill que não pôde executar
            available_inputs: Conjunto de inputs disponíveis no contexto

        Returns:
            Lista de skills alternativas ordenadas por relevância
        """
        target = self.get(skill_name)
        if not target:
            return []

        target_outputs = set(target.outputs)
        if not target_outputs:
            return []

        candidates = []
        for entry in self._skills.values():
            if not entry.active:
                continue
            alt = entry.skill
            if alt.name == skill_name:
                continue

            alt_outputs = set(alt.outputs)
            output_overlap = target_outputs & alt_outputs
            if not output_overlap:
                continue

            alt_inputs = set(alt.inputs)
            if not alt_inputs.issubset(available_inputs):
                continue

            score = len(output_overlap) / max(len(target_outputs), 1)
            candidates.append((score, alt))

        candidates.sort(key=lambda x: (-x[0], x[1].name))

        if candidates:
            logger.info("[SKILL] Alternativas para '%s' (%d candidatos):", skill_name, len(candidates))
            for score, alt in candidates:
                logger.info("  -> %s (score=%.2f, inputs=%s, outputs=%s)",
                            alt.name, score, alt.inputs, alt.outputs)

        return [alt for _, alt in candidates]

    # --------------------------------------------------
    # RESET
    # --------------------------------------------------

    def clear(self):
        self._skills.clear()
        self._version_history.clear()
        logger.info("[SKILL] Registry limpo")


# Instância global
skill_registry = SkillRegistry()
