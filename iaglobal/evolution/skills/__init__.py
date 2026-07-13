# iaglobal/evolution/skills/__init__.py
"""
Skills — Módulo centralizado de skills do iaglobal.

Uso:
    from iaglobal.evolution.skills import (
        Skill,
        SkillRegistry,
        SkillExecutor,
        SkillModelRouter,
        model_router,
        load_skill_template,
    )
"""

# Base
from iaglobal.evolution.skills.native.skill import Skill

# Core
from iaglobal.evolution.skills.native.skill_registry import SkillRegistry
from iaglobal.evolution.skills.native.skill_executor import SkillExecutor

# Router
from iaglobal.evolution.skills.native.skill_model_router import (
    SkillModelRouter,
    model_router,
)

# Templates
from iaglobal.evolution.skills.utils.template_loader import load_skill_template

# Re-export common names from native.skill for backward-compatible imports
from iaglobal.evolution.skills.native import skill as _native_skill  # noqa: E402

for _n in dir(_native_skill):
    if not _n.startswith("_"):
        globals()[_n] = getattr(_native_skill, _n)

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillExecutor",
    "SkillModelRouter",
    "model_router",
    "load_skill_template",
]
