# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_knowledge.py

"""
Knowledge Node — Centraliza a fusão, extração e persistência do Grafo de Conhecimento.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any, List

from iaglobal.graphs.artifact import SolutionArtifact
from iaglobal.evolution.evolution_agents.knowledge_agent import knowledge
from iaglobal.memory.fusion_engine import KnowledgeGraph

logger = logging.getLogger(__name__)

# Instanciação lazy controlada do Grafo de Conhecimento
_kgraph: KnowledgeGraph = None


def _get_kgraph() -> KnowledgeGraph:
    global _kgraph
    if _kgraph is None:
        _kgraph = KnowledgeGraph()
    return _kgraph


async def run_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a consolidação e extração do Grafo de Conhecimento de forma assíncrona.
    Mapeia latência, conceitos e sucesso operacional para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "knowledge_deterministic_graph_engine"

    task = str(ctx.get("input", {}).get("task", ""))
    memory = ctx.get("memory", {})

    local_result = memory.get("local_knowledge", {}).get("output", "")
    search_result = memory.get("search", {}).get("output", "")

    # Consolida e limpa de forma resiliente as fontes de conhecimento anteriores
    if local_result and not search_result:
        logger.info(
            "[KNOWLEDGE] Usando conhecimento local (%d chars), sem busca web",
            len(local_result),
        )
        search_result = local_result
    elif local_result and search_result:
        logger.info(
            "[KNOWLEDGE] Merge de conhecimento: local (%d) + web (%d)",
            len(local_result),
            len(search_result),
        )
        search_result = f"{local_result}\n\n=== BUSCA WEB ===\n{search_result}"

    if isinstance(search_result, SolutionArtifact):
        search_result = (
            search_result.security_report
            or search_result.code
            or str(search_result.critique)
            or ""
        )
    elif not isinstance(search_result, str):
        search_result = str(search_result)

    logger.info("[KNOWLEDGE] Iniciando ciclo de ingestão e indexação cognitiva...")

    try:
        if search_result and len(search_result) > 50:
            # Isolamento 1: Gravação síncrona no KnowledgeAgent desviada para Thread Pool
            def _store_agent_knowledge():
                knowledge.extract_and_store(task, search_result)

            try:
                await asyncio.to_thread(_store_agent_knowledge)
                logger.info(
                    "[KNOWLEDGE] KnowledgeAgent armazenado com sucesso: %d chars.",
                    len(search_result),
                )
            except Exception as e:
                logger.warning(
                    "[KNOWLEDGE] Falha controlada no armazenamento do KnowledgeAgent: %s",
                    e,
                )

            # Isolamento 2: Gravação e indexação síncrona no KnowledgeGraph desviada para Thread Pool
            def _store_graph_knowledge():
                kg = _get_kgraph()
                return kg.extract_and_store(search_result, source=task)

            try:
                concepts = await asyncio.to_thread(_store_graph_knowledge)
                logger.info(
                    "[KNOWLEDGE] KnowledgeGraph indexou %d novos conceitos.",
                    len(concepts) if concepts else 0,
                )
            except Exception as e:
                logger.warning(
                    "[KNOWLEDGE] Falha controlada na indexação do KnowledgeGraph: %s", e
                )

        # Isolamento 3: Recuperação e busca de termos relevantes via Thread Pool
        relevant = await asyncio.to_thread(_get_relevant, task)

        # Isolamento 4: Sumarização síncrona de entradas desviada para Thread Pool
        knowledge_summary = ""
        try:
            knowledge_summary = await asyncio.to_thread(
                knowledge.summarize, max_entries=5
            )
        except Exception as e:
            logger.warning(
                "[KNOWLEDGE] Falha ao computar o resumo de conhecimento: %s", e
            )

        # Isolamento 5: Coleta de termos mais frequentes no Grafo desviada para Thread Pool
        kg_concepts = []
        try:

            def _fetch_top_concepts():
                kg = _get_kgraph()
                return kg.get_top_concepts(limit=10)

            kg_concepts = await asyncio.to_thread(_fetch_top_concepts)
        except Exception as e:
            logger.warning(
                "[KNOWLEDGE] Falha ao coletar conceitos no topo do grafo: %s", e
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": knowledge_summary,
            "knowledge": {
                "relevant": relevant,
                "summary": knowledge_summary,
                "concepts": kg_concepts,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,  # Processamento de infraestrutura local de indexação
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[KNOWLEDGE] Falha crítica no pipeline do Knowledge Node: %s", e
        )

        return {
            "output": "",
            "knowledge": {
                "relevant": [],
                "summary": "",
                "concepts": [],
                "error": str(e),
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }


def _get_relevant(task: str) -> List[Dict[str, Any]]:
    """Função auxiliar mantida isolada para execução segura em thread pool."""
    try:
        retrieved = knowledge.retrieve_relevant(task, max_results=5)
        entries = []
        for item in retrieved:
            if isinstance(item, dict):
                entries.append(
                    {
                        "content": item.get("content", "")[:500],
                        "score": item.get("score"),
                        "source": item.get("source"),
                    }
                )
            else:
                entries.append({"content": str(item)[:500]})
        return entries
    except Exception:
        return []
