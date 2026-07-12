# iaglobal/evolution/skills/skill_registry.py

"""
🎯 Skill Registry — registro global de skills versionadas com segurança concorrente.
"""

import threading
from typing import Dict, Optional, List
from dataclasses import dataclass

from iaglobal.utils.logger import logger
from .skill import Skill, ExecutionPolicy


@dataclass
class SkillEntry:
    skill: Skill
    active: bool = True
    usage_count: int = 0


class SkillRegistry:
    """
    Registry global de skills (Thread-Safe).
    """

    def __init__(self):
        self._skills: Dict[str, SkillEntry] = {}
        self._version_history: Dict[str, List[Skill]] = {}
        self._lock = threading.Lock()  # Protege o estado global contra concorrência

    # --------------------------------------------------
    # REGISTER (Corrigido para Rigor de Evolução)
    # --------------------------------------------------

    def register(self, skill: Skill) -> bool:
        with self._lock:
            if skill.name in self._skills:
                return False
            
            # Se não for callable, tenta injetar via factory ANTES de falhar
            if not callable(skill.run_fn):
                try:
                    from iaglobal.evolution.skills.run_fn_factory import make_dynamic_run_fn
                except ImportError:
                    make_dynamic_run_fn = None
                
                if make_dynamic_run_fn is not None:
                    injected_fn = make_dynamic_run_fn(
                        skill.name, 
                        getattr(skill, 'template_type', 'llm'), 
                        getattr(skill, 'template_prompt', '')
                    )
                    
                    if callable(injected_fn):
                        skill.run_fn = injected_fn
                    else:
                        logger.error(f"[SKILL] Falha crítica: Impossível injetar run_fn na skill '{skill.name}'")
                        return False
            
            self._skills[skill.name] = SkillEntry(skill=skill)
            self._version_history[skill.name] = [skill]
            logger.debug(f"[SKILL] Registrada: {skill.name} v{skill.version}")
            return True

    def register_or_update(self, skill: Skill) -> bool:
        """Registra ou atualiza incluindo corretamente a nova versão no histórico."""
        # Validação preventiva antes de travar o registro
        if not callable(skill.run_fn):
            logger.warning(f"[SKILL] Tentativa de registro de skill inválida: {skill.name}")
            return False

        with self._lock:
            if skill.name in self._skills:
                entry = self._skills[skill.name]
                
                # Se a versão for idêntica, apenas atualiza a instância
                if entry.skill.version == skill.version:
                    entry.skill = skill
                    return True

                # Atualiza histórico se a versão for nova
                if skill.name not in self._version_history:
                    self._version_history[skill.name] = []
                
                entry.skill = skill
                self._version_history[skill.name].append(skill)
                
                logger.info(f"[SKILL] Atualizada: {skill.name} → v{skill.version}")
                return True
            
            # Se não existia, seguimos para o registro padrão (já protegido pelo lock acima)
            self._skills[skill.name] = SkillEntry(skill=skill)
            self._version_history[skill.name] = [skill]
            logger.debug(f"[SKILL] Registrada: {skill.name} v{skill.version}")
            return True

    # --------------------------------------------------
    # QUERY
    # --------------------------------------------------

    def get(self, name: str) -> Optional[Skill]:
        with self._lock:
            entry = self._skills.get(name)
            if entry and entry.active:
                return entry.skill
            return None

    def get_version(self, name: str, version: str) -> Optional[Skill]:
        with self._lock:
            history = self._version_history.get(name, [])
            for skill in history:
                if skill.version == version:
                    return skill
            return None

    def list_skills(self, active_only: bool = True) -> List[Skill]:
        with self._lock:
            if active_only:
                return [e.skill for e in self._skills.values() if e.active]
            return [e.skill for e in self._skills.values()]

    # --------------------------------------------------
    # USAGE TRACKING
    # --------------------------------------------------

    def increment_usage(self, name: str):
        with self._lock:
            entry = self._skills.get(name)
            if entry:
                entry.usage_count += 1

    def get_usage_count(self, name: str) -> int:
        with self._lock:
            entry = self._skills.get(name)
            return entry.usage_count if entry else 0

    # --------------------------------------------------
    # ALTERNATIVES (skill routing)
    # --------------------------------------------------

    MIN_ALTERNATIVE_SCORE = 0.60

    def find_alternatives(self, skill_name: str, available_inputs: set, visited: set = None) -> List[Skill]:
        if visited is None:
            visited = set()

        # Copia dados necessários sob lock rápido para não travar a busca pesada externa
        with self._lock:
            target_entry = self._skills.get(skill_name)
            if not target_entry:
                return []
            target = target_entry.skill
            all_entries = list(self._skills.values())

        target_outputs = set(target.outputs)
        if not target_outputs:
            return []

        candidates = []
        for entry in all_entries:
            if not entry.active:
                continue
            alt = entry.skill
            if alt.name == skill_name or alt.name in visited:
                continue
            if not callable(alt.run_fn):
                continue
            if self.is_quarantined(alt.name):
                continue

            alt_outputs = set(alt.outputs)
            output_overlap = target_outputs & alt_outputs
            if not output_overlap:
                continue

            alt_inputs = set(alt.inputs)
            if not alt_inputs.issubset(available_inputs):
                continue

            score = len(output_overlap) / max(len(target_outputs), 1)
            if score < self.MIN_ALTERNATIVE_SCORE:
                continue
            candidates.append((score, alt))

        candidates.sort(key=lambda x: (-x[0], x[1].name))
        return [alt for _, alt in candidates]

    # --------------------------------------------------
    # RESET
    # --------------------------------------------------

    def clear(self):
        with self._lock:
            self._skills.clear()
            self._version_history.clear()
            logger.info("[SKILL] Registry limpo")

    def is_quarantined(self, name: str) -> bool:
        # Import dinâmico mantido para evitar acoplamento circular em cascata
        from ..skill_quarantine import quarantine
        return quarantine.is_quarantined(name)


# Instância global utilizada pelo sistema
skill_registry = SkillRegistry()

# Registro eager das skills built-in (seguro: skill.py não importa skill_registry em módulo)
from .skill import register_builtin_skills
register_builtin_skills()
