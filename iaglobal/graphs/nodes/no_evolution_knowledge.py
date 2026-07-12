# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_evolution_knowledge.py

"""
Evolution Knowledge Agent — Memória operacional de longo prazo para o pipeline.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent

logger = logging.getLogger(__name__)

# Instanciação única controlada do agente de conhecimento evolutivo
_knowledge_agent = KnowledgeAgent()


async def run_evolution_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recupera memórias operacionais profundas de longo prazo de forma assíncrona.
    Mapeia latência e acertos de busca histórica para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "evolution_knowledge_deterministic_engine"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    logger.info("[EVOLUTION_KNOWLEDGE] Iniciando varredura assíncrona na base de memórias operacionais...")

    try:
        # Como consultas a índices e varreduras analíticas de texto realizam I/O síncrono de banco/disco,
        # desviamos a execução inteira da query para uma thread pool isolada
        entries = await asyncio.to_thread(_knowledge_agent.query, task, limit=5)
        entries = entries or []

        # Enclausura a formatação de strings em background para poupar a thread principal se a lista for densa
        def _build_summary(entries_list):
            return "\n".join([
                f"[{e.get('category', 'general')}] {e.get('title', '')}: {e.get('content', '')[:200]}"
                for e in entries_list if isinstance(e, dict)
            ])

        knowledge_summary = await asyncio.to_thread(_build_summary, entries)

        logger.info("[EVOLUTION_KNOWLEDGE] Sucesso! %d entradas recuperadas para a tarefa: %s", 
                    len(entries), task[:60])

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": knowledge_summary,
            "evolution_knowledge": {
                "entries": entries,
                "count": len(entries),
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Estrutura e processamento offline puramente locais
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[EVOLUTION_KNOWLEDGE] Falha crítica no pipeline do Evolution Knowledge Node: %s", e)
        
        return {
            "output": "",
            "evolution_knowledge": {
                "entries": [],
                "count": 0
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

