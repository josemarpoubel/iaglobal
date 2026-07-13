# iaglobal/evolution/skills/utils/__init__.py
"""Utils — Utilitários de skills (sem imports circulares)."""


# Imports lazy para evitar circularidade
def load_skill_template(skill_name: str):
    from iaglobal.evolution.skills.utils.template_loader import (
        load_skill_template as _load,
    )

    return _load(skill_name)


__all__ = ["load_skill_template"]
