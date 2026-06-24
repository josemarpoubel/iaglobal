# iaglobal/graphs/nodes/no_evolution_skill_executor.py

"""
Evolution Skill Executor — Executa skills registradas de forma isolada e assíncrona.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any, List, Tuple

from iaglobal.evolution.skills.skill_executor import SkillExecutor, SkillExecutionError
from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)

# Instanciação única do motor isolado de execução de skills
_executor = SkillExecutor()


def _execute_auto_skills(skills: list, ctx: dict) -> Tuple[int, List[dict]]:
    """Função isolada para rodar códigos mutados em blocos de thread pool com segurança."""
    executed_count = 0
    execution_results = []
    
    for skill in skills:
        if skill is not None and "auto_execute" in getattr(skill, "tags", []):
            try:
                logger.info("[EVOLUTION_SKILL_EXECUTOR] Invocando runtime isolado para skill: %s", skill.name)
                
                # Executa o código da habilidade mutada
                result = _executor.execute(skill, ctx)
                executed_count += 1
                execution_results.append({"skill": skill.name, "result": str(result)[:200]})
                
            except SkillExecutionError as e:
                logger.warning("[EVOLUTION_SKILL_EXECUTOR] Falha controlada ao executar %s: %s", skill.name, e)
                execution_results.append({"skill": skill.name, "error": str(e)})
            except Exception as e:
                logger.error("[EVOLUTION_SKILL_EXECUTOR] Crash inesperado na skill %s: %s", skill.name, e)
                execution_results.append({"skill": skill.name, "error": f"Unexpected crash: {str(e)}"})
                
    return executed_count, execution_results


async def run_evolution_skill_executor(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa habilidades mutadas automáticas de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e taxa de sucesso técnico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "skill_executor_deterministic_sandbox"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    logger.info("[EVOLUTION_SKILL_EXECUTOR] Mapeando a árvore de habilidades registradas no ecossistema...")

    try:
        # Coleta de forma segura as instâncias de skills registradas
        skills = list(skill_registry.skills.values()) if skill_registry and hasattr(skill_registry, "skills") else []
        logger.info("[EVOLUTION_SKILL_EXECUTOR] %d skills detectadas no registry.", len(skills))

        # DESPACHA INTEIRAMENTE A EXECUÇÃO ITERATIVA DE CÓDIGOS MUTADOS PARA A THREAD POOL ISOLADA
        # Isso impede que códigos infinitos ou travamentos de IO derrubem o barramento central
        executed, results = await asyncio.to_thread(_execute_auto_skills, skills, ctx)

        logger.info("[EVOLUTION_SKILL_EXECUTOR] %d skills executadas automaticamente com sucesso.", executed)

        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se não houve crash do executor em si
        is_success = True

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": f"{executed} skills executadas",
            "evolution_skill_executor": {
                "total_skills": len(skills),
                "executed": executed,
                "results": results,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0  # Execução local em infraestrutura offline
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[EVOLUTION_SKILL_EXECUTOR] Falha crítica no pipeline do Skill Executor: %s", e)
        
        return {
            "output": "0 skills executadas",
            "evolution_skill_executor": {
                "total_skills": 0,
                "executed": 0,
                "results": [{"error": str(e)}]
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

