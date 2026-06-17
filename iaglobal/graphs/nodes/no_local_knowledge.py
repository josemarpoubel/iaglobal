"""Local Knowledge — consulta LTM + knowledge.json + cbor2 ANTES de buscar na web."""
from typing import Dict, Any, List
import logging

from iaglobal.evolution.agents.knowledge_agent import knowledge
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal._paths import CORE_DB

logger = logging.getLogger(__name__)
_ltm = LongTermMemory(db_path=CORE_DB)
_stm = ShortTermMemory()
_MIN_KNOWLEDGE_CHARS = 200


def _query_local(task: str) -> List[Dict]:
    results = []

    entries = knowledge.retrieve_relevant(task, max_results=3)
    for e in entries:
        content = e.get("content", "")[:500]
        if len(content) > 30:
            results.append({"source": "knowledge.json", "content": content, "relevance": 1.0})

    ltm_results = _ltm.retrieve(task, top_k=3)
    for m in ltm_results:
        content = m.get("content", "")[:500]
        if len(content) > 30:
            results.append({"source": "ltm", "content": content, "relevance": 0.9})

    try:
        from iaglobal.memory.memory_vector import MemoryVector
        _mem_vec = MemoryVector()
        vec_results = _mem_vec.search(task, top_k=3)
        for m in vec_results:
            content = m if isinstance(m, str) else m.get("content", "")
            if len(content) > 30:
                results.append({"source": "cbor2", "content": str(content)[:500], "relevance": 0.8})
    except Exception:
        pass

    recent = _stm.get_recent(5)
    for m in recent:
        content = str(m)[:500]
        if len(content) > 30:
            results.append({"source": "stm", "content": content, "relevance": 0.7})

    return results


async def run_local_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    if not task or len(task) < 5:
        return {**ctx, "output": "", "local_found": False, "total_chars": 0}

    results = _query_local(task)
    total_chars = sum(len(r["content"]) for r in results)

    if results:
        lines = []
        for r in results:
            lines.append(f"• [{r['source']}] {r['content']}")
        combined = "\n\n".join(lines)

        logger.info("[LOCAL_KNOWLEDGE] %d entradas encontradas, %d chars", len(results), total_chars)

        return {
            **ctx,
            "output": combined,
            "local_knowledge": results,
            "local_found": True,
            "total_chars": total_chars,
        }

    logger.info("[LOCAL_KNOWLEDGE] Nenhum conhecimento local encontrado")
    return {**ctx, "output": "", "local_found": False, "total_chars": 0}
