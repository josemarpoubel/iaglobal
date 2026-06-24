# iaglobal/graphs/nodes/no_evolution_homocysteine.py

"""
Evolution Homocysteine Pool — Pool de skills candidatas aguardando validação.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.evolution.metabolism.homocysteine_pool import homocysteine_pool

logger = logging.getLogger(__name__)


def _seed_candidates_from_skill_generator(memory: Dict[str, Any]) -> None:
    skill_result = memory.get("skill_generator", {}).get("output", {})
    if not isinstance(skill_result, dict):
        return

    generated = skill_result.get("generated_skills", []) or []
    if not generated:
        return

    existing = {c.skill.name for c in homocysteine_pool.candidates}
    for item in generated:
        skill_name = item.get("skill_name")
        if not skill_name or skill_name in existing:
            continue

        from iaglobal.evolution.skills.skill import Skill
        from iaglobal.evolution.skills.skill_registry import skill_registry
        from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill

        skill = skill_registry.get(skill_name)
        if skill is None:
            skill = Skill(
                name=skill_name,
                description=f"Skill gerada por metacognição: {skill_name}",
                inputs=["task"],
                outputs=["fix_result"],
                constraints=[],
                run_fn=None,
                version="1.0.0",
                author="evolution_homocysteine",
                tags=["auto_generated", "metacognition"],
            )

        severity = item.get("severity", "low")
        scores = {"critical": 0.95, "high": 0.85, "medium": 0.70, "low": 0.55}
        candidate = CandidateSkill(
            skill=skill,
            score=float(item.get("score", scores.get(severity, 0.55))),
            source_gap=f"skill_generator:{skill_name}",
        )
        homocysteine_pool.add(candidate)
        existing.add(skill_name)


async def run_evolution_homocysteine(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monitora e filtra as skills mutadas pendentes no pool de homocisteína de forma assíncrona.
    Mapeia latência e contagem de candidatos para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "homocysteine_pool_deterministic_infrastructure"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    logger.info("[EVOLUTION_HOMOCYSTEINE] Analisando o pool metabólico de skills candidatas...")

    try:
        # Garante que skills geradas pelo nó anterior cheguem ao pool antes da estatística.
        _seed_candidates_from_skill_generator(memory)

        # Enclausura as operações de filtros e conversões síncronas para rodarem de forma não-bloqueante
        def _process_pool_metadata():
            all_candidates = homocysteine_pool.candidates or []
            pending = homocysteine_pool.get_pending() or []
            production_ready = homocysteine_pool.get_ready_for_methylation() or []
            
            # Converte de forma segura os objetos das skills candidatas para dicionários (evita KeyErrors)
            candidates_info = [
                c.to_dict() if hasattr(c, "to_dict") else dict(c) 
                for c in all_candidates[:10] if c is not None
            ]
            
            pool_stats = {
                "total_candidates": len(all_candidates),
                "pending_review": len(pending),
                "ready_for_methylation": len(production_ready),
            }
            return pool_stats, candidates_info

        # Despacha o processamento analítico pesado para a Thread Pool isolada
        stats, candidates_info = await asyncio.to_thread(_process_pool_metadata)

        logger.info("[EVOLUTION_HOMOCYSTEINE] Ciclo concluído: %d total | %d pendentes | %d prontos para metilação.",
                    stats["total_candidates"], stats["pending_review"], stats["ready_for_methylation"])

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": f"Pool: {stats['total_candidates']} candidatas, {stats['ready_for_methylation']} prontas",
            "evolution_homocysteine": {
                "stats": stats,
                "candidates": candidates_info,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Estrutura puramente local e offline
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[EVOLUTION_HOMOCYSTEINE] Falha crítica no pipeline do Homocysteine Pool: %s", e)
        
        return {
            "output": "Pool: 0 candidatas, 0 prontas",
            "evolution_homocysteine": {
                "stats": {"total_candidates": 0, "pending_review": 0, "ready_for_methylation": 0},
                "candidates": []
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

