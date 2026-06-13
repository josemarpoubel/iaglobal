from typing import Dict, Any, List
import logging

from iaglobal.graphs.artifact import SolutionArtifact
from iaglobal.evolution.agents.knowledge_agent import knowledge
from iaglobal.memory.fusion_engine import KnowledgeGraph

logger = logging.getLogger(__name__)
_kgraph: KnowledgeGraph = None


def _get_kgraph() -> KnowledgeGraph:
    global _kgraph
    if _kgraph is None:
        _kgraph = KnowledgeGraph()
    return _kgraph


async def run_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    memory = ctx.get("memory", {})

    local_result = memory.get("local_knowledge", {}).get("output", "")
    search_result = memory.get("search", {}).get("output", "")

    if local_result and not search_result:
        logger.info("[KNOWLEDGE] Usando conhecimento local (%d chars), sem busca web", len(local_result))
        search_result = local_result
    elif local_result and search_result:
        logger.info("[KNOWLEDGE] Merge local (%d) + web (%d)", len(local_result), len(search_result))
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

    if search_result and len(search_result) > 50:
        try:
            knowledge.extract_and_store(task, search_result)
            logger.info("[KNOWLEDGE] KnowledgeAgent armazenado: %d chars", len(search_result))
        except Exception as e:
            logger.warning("[KNOWLEDGE] KnowledgeAgent falha: %s", e)

        try:
            kg = _get_kgraph()
            concepts = kg.extract_and_store(search_result, source=task)
            logger.info("[KNOWLEDGE] KnowledgeGraph extraiu %d conceitos", len(concepts))
        except Exception as e:
            logger.warning("[KNOWLEDGE] KnowledgeGraph falha: %s", e)

    relevant = _get_relevant(task)
    knowledge_summary = ""
    try:
        knowledge_summary = knowledge.summarize(max_entries=5)
    except Exception as e:
        logger.warning("[KNOWLEDGE] Falha no resumo: %s", e)

    kg_concepts = []
    try:
        kg = _get_kgraph()
        kg_concepts = kg.get_top_concepts(limit=10)
    except Exception as e:
        logger.warning("[KNOWLEDGE] Falha busca conceitos: %s", e)

    return {
        **ctx,
        "knowledge": {
            "relevant": relevant,
            "summary": knowledge_summary,
            "concepts": kg_concepts,
        },
        "output": knowledge_summary,
    }


def _get_relevant(task: str) -> List[Dict[str, Any]]:
    try:
        retrieved = knowledge.retrieve_relevant(task, max_results=5)
        entries = []
        for item in retrieved:
            if isinstance(item, dict):
                entries.append({
                    "content": item.get("content", "")[:500],
                    "score": item.get("score"),
                    "source": item.get("source"),
                })
            else:
                entries.append({"content": str(item)[:500]})
        return entries
    except Exception:
        return []
