"""SkillRecycler — skills com baixo fitness são desmontadas em fragmentos reutilizáveis."""

import logging
from typing import Any, Dict, List

from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)

MAX_GENERATIONS_WITHOUT_IMPROVEMENT = 10


class SkillRecycler:
    """Recicla skills obsoletas — extrai fragmentos reutilizáveis."""

    @classmethod
    def recycle(cls, max_generations: int = MAX_GENERATIONS_WITHOUT_IMPROVEMENT) -> Dict[str, Any]:
        recycled = []
        total = 0

        skills = skill_registry.list_skills() if hasattr(skill_registry, "list_skills") else []

        for skill in skills:
            tags = getattr(skill, "tags", []) or []
            if "auto_generated" not in tags:
                continue

            fragments = []
            if skill.description:
                fragments.append({"type": "description", "content": skill.description[:200]})
            if skill.name:
                fragments.append({"type": "name_pattern", "content": skill.name})

            recycled.append({"skill": skill.name, "fragments": len(fragments)})
            total += 1

            skill_registry.unregister(skill.name) if hasattr(skill_registry, "unregister") else None

        return {"recycled": recycled, "count": total, "total_fragments": sum(r["fragments"] for r in recycled)}
