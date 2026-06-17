"""Evolution Skill Executor — Executa skills registradas de forma isolada."""
from typing import Dict, Any
import logging

from iaglobal.evolution.skills.skill_executor import SkillExecutor, SkillExecutionError
from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)
_executor = SkillExecutor()


async def run_evolution_skill_executor(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Lista skills disponíveis
    skills = list(skill_registry.skills.values())
    logger.info("[EVOLUTION_SKILL_EXECUTOR] %d skills registradas", len(skills))

    # Executa skills que têm tag 'auto_execute'
    executed = 0
    results = []
    for skill in skills:
        if "auto_execute" in skill.tags:
            try:
                logger.info("[EVOLUTION_SKILL_EXECUTOR] Executando skill: %s", skill.name)
                result = _executor.execute(skill, ctx)
                executed += 1
                results.append({"skill": skill.name, "result": str(result)[:200]})
            except SkillExecutionError as e:
                logger.warning("[EVOLUTION_SKILL_EXECUTOR] Falha ao executar %s: %s", skill.name, e)
                results.append({"skill": skill.name, "error": str(e)})

    logger.info("[EVOLUTION_SKILL_EXECUTOR] %d skills executadas automaticamente", executed)

    return {
        **ctx,
        "output": f"{executed} skills executadas",
        "evolution_skill_executor": {
            "total_skills": len(skills),
            "executed": executed,
            "results": results,
        },
    }