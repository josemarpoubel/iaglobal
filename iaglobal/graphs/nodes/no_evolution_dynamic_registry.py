"""Evolution Dynamic Registry — Registry de skills dinâmicas com persistência SQLite."""
from typing import Dict, Any
import logging

from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

logger = logging.getLogger(__name__)


async def run_evolution_dynamic_registry(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Carrega skills dinâmicas do SQLite
    dynamic_registry.load_dynamic_skills()

    # Estatísticas
    dynamic_skills = dynamic_registry.list_dynamic_skills()
    stats = {
        "total_dynamic_skills": len(dynamic_skills),
        "active_skills": sum(1 for s in dynamic_skills if s.get("active", 0)),
    }

    logger.info("[EVOLUTION_DYNAMIC_REGISTRY] %d skills dinâmicas carregadas", stats["total_dynamic_skills"])

    return {
        **ctx,
        "output": f"{stats['total_dynamic_skills']} skills dinâmicas ativas",
        "evolution_dynamic_registry": {
            "stats": stats,
            "skills": [{"name": s["name"], "description": s["description"][:100]} for s in dynamic_skills[:10]],
        },
    }