# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_evolution_dynamic_registry.py

"""
Evolution Dynamic Registry — Registry de skills dinâmicas com persistência SQLite.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

logger = logging.getLogger(__name__)


async def run_evolution_dynamic_registry(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Carrega as habilidades dinâmicas mutadas do SQLite de forma assíncrona.
    Mapeia latência e contagem de mutações para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "dynamic_registry_deterministic_db_infrastructure"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    logger.info("[EVOLUTION_DYNAMIC_REGISTRY] Iniciando carregamento assíncrono de skills mutadas no SQLite...")

    try:
        # Como o carregamento e parsing de schemas do SQLite realizam I/O síncrono de disco,
        # desviamos a execução inteira do registry para uma thread pool isolada
        await asyncio.to_thread(dynamic_registry.load_dynamic_skills)

        # Estatísticas obtidas em memória de forma segura
        dynamic_skills = dynamic_registry.list_dynamic_skills() or []
        
        stats = {
            "total_dynamic_skills": len(dynamic_skills),
            "active_skills": sum(1 for s in dynamic_skills if isinstance(s, dict) and s.get("active", 0)),
        }

        logger.info("[EVOLUTION_DYNAMIC_REGISTRY] Sucesso! %d skills dinâmicas carregadas para o ecossistema.", 
                    stats["total_dynamic_skills"])

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": f"{stats['total_dynamic_skills']} skills dinâmicas ativas",
            "evolution_dynamic_registry": {
                "stats": stats,
                "skills": [{"name": s["name"], "description": s.get("description", "")[:100]} for s in dynamic_skills[:10] if isinstance(s, dict)],
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Transações de infraestrutura puramente locais e offline
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[EVOLUTION_DYNAMIC_REGISTRY] Falha crítica ao ler repositório de skills dinâmicas: %s", e)
        
        return {
            "output": "0 skills dinâmicas ativas",
            "evolution_dynamic_registry": {
                "stats": {"total_dynamic_skills": 0, "active_skills": 0},
                "skills": []
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

