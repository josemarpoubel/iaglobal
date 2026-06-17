"""Evolution Knowledge Agent — Memória operacional de longo prazo para o pipeline."""
from typing import Dict, Any
import logging

from iaglobal.evolution.agents.knowledge_agent import KnowledgeAgent

logger = logging.getLogger(__name__)
_knowledge_agent = KnowledgeAgent()


async def run_evolution_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Recupera conhecimento relevante para a tarefa
    entries = _knowledge_agent.query(task, limit=5)

    # Armazena no contexto para outros agentes
    knowledge_summary = "\n".join([
        f"[{e.get('category', 'general')}] {e.get('title', '')}: {e.get('content', '')[:200]}"
        for e in entries
    ])

    logger.info("[EVOLUTION_KNOWLEDGE] %d entradas recuperadas para: %s", len(entries), task[:60])

    return {
        **ctx,
        "output": knowledge_summary,
        "evolution_knowledge": {
            "entries": entries,
            "count": len(entries),
        },
    }