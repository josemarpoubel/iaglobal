"""Knowledge Analyzer — filtra, extrai e persiste conhecimento útil do cache."""
from typing import Dict, Any, List
import json
import re
import logging
from pathlib import Path

from iaglobal.evolution.agents.knowledge_agent import knowledge
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.memory_vector import store as mem_vector_store
from iaglobal.graphs.nodes._disk_swap import load_all_for_task
from iaglobal._paths import CORE_DB

logger = logging.getLogger(__name__)
_ltm = LongTermMemory(db_path=CORE_DB)

_GARBAGE_PATTERNS = [
    r"Philistine city.state", r"was a.*city.state", r"page not found",
    r"404 Not Found", r"Mário Coluna", r"CSV Apeldoorn",
    r"Uma ilha e um amor", r"book\)",
]

_RELEVANCE_KEYWORDS = {
    "python": 3, "código": 3, "codigo": 3, "code": 3, "script": 3,
    "função": 3, "funcao": 3, "function": 3, "def ": 3, "import ": 3,
    "csv": 3, "pandas": 3, "numpy": 3, "api": 2, "rest": 2,
    "tutorial": 2, "exemplo": 2, "example": 2, "guide": 2,
    "documentação": 2, "documentation": 2, "como": 1, "how to": 1,
    "erro": 2, "error": 2, "solução": 2, "solution": 2,
}


def _is_garbage(text: str) -> bool:
    for pat in _GARBAGE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _calc_relevance(text: str) -> float:
    text_lower = text.lower()
    score = 0
    for kw, weight in _RELEVANCE_KEYWORDS.items():
        if kw in text_lower:
            score += weight
    return min(score / 5.0, 1.0)


def _extract_useful(text: str, max_len: int = 500) -> str:
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    lines = [l.strip() for l in cleaned.split("\n") if len(l.strip()) > 30]
    return "\n".join(lines[:5])[:max_len]


async def run_knowledge_analyzer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    if not task:
        return {**ctx, "output": "", "entries_kept": 0, "success": True}

    all_results = load_all_for_task(task)
    if not all_results:
        logger.info("[ANALYZER] Nada no cache para analisar")
        return {**ctx, "output": "", "entries_kept": 0, "success": True}

    total_input = sum(len(v) for v in all_results.values())
    kept = []
    rejected = 0

    for source, content in all_results.items():
        if not content or len(content) < 50:
            rejected += 1
            continue
        if _is_garbage(content):
            logger.debug("[ANALYZER] Rejeitado (lixo): %s", source)
            rejected += 1
            continue

        relevance = _calc_relevance(content)
        if relevance < 0.3:
            logger.debug("[ANALYZER] Rejeitado (baixa relevancia: %.2f): %s", relevance, source)
            rejected += 1
            continue

        extracted = _extract_useful(content)
        if len(extracted) > 50:
            kept.append({"source": source, "content": extracted, "relevance": relevance})

    kept.sort(key=lambda x: x["relevance"], reverse=True)

    saved = 0
    for entry in kept[:5]:
        try:
            knowledge.store(
                category="best_practice" if entry["relevance"] > 0.6 else "pattern",
                title=entry["content"][:60],
                content=entry["content"],
                tags=["auto_extracted", f"src_{entry['source']}"],
                source=task,
            )
            saved += 1

            mem_vector_store(text=entry["content"], mtype="web_search_filtered")

            _ltm.store(
                content=entry["content"],
                metadata={"source": f"analyzer_{entry['source']}", "relevance": entry["relevance"]},
                source="knowledge_analyzer",
            )
            saved += 1

            logger.debug("[ANALYZER] Salvo em knowledge.json + LTM + cbor2: %.60s", entry["content"])
        except Exception as e:
            logger.debug("[ANALYZER] Erro ao salvar: %s", e)

    logger.info(
        "[ANALYZER] %d/%d entradas uteis | %d rejeitadas | %d saves | relevancia media: %.2f",
        len(kept), len(all_results), rejected, saved,
        sum(e["relevance"] for e in kept) / len(kept) if kept else 0,
    )

    summary = "\n\n".join(f"• [{e['source']}] {e['content'][:200]}" for e in kept[:3])

    return {
        **ctx,
        "output": summary,
        "analyzed": {
            "total_input": total_input,
            "total_sources": len(all_results),
            "kept": len(kept),
            "rejected": rejected,
            "saved": saved,
        },
        "success": True,
    }
