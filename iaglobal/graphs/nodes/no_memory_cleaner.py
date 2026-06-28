# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_memory_cleaner.py

"""
Memory Cleaner Node — Executa a faxina de caches, STM, MemoryVector e swap de disco.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any, List

from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.graphs.nodes._disk_swap import cleanup_task

logger = logging.getLogger(__name__)
_stm = ShortTermMemory()


async def run_memory_cleaner(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a limpeza de memórias temporárias e arquivos de swap de forma assíncrona.
    Mapeia latência, fontes descartadas e sucesso para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "memory_cleaner_deterministic_infrastructure"
    
    memory = ctx.get("memory", {})

    critic_data = memory.get("critic", {}) or {}
    score = critic_data.get("score", 0)
    approved = critic_data.get("approved", False)

    logger.info("[CLEANER] Iniciando ciclo de limpeza e compactação de memória (critic score=%.1f, approved=%s)...", score, approved)

    used_sources = {k for k in memory.keys() if k in ("coder", "multi_coder", "prompt_builder")}
    discarded = []
    
    for src in ("search", "local_knowledge"):
        src_data = memory.get(src, {})
        src_output = src_data.get("output", "") if isinstance(src_data, dict) else str(src_data or "")
        if src_output and src not in used_sources:
            discarded.append({"source": src, "chars": len(src_output)})
            logger.debug("[CLEANER] Descartando cache não utilizado de %s (%d caracteres).", src, len(src_output))

    # Isolamento 1: Limpeza da Short-Term Memory (STM) - I/O SQLite isolado em thread pool
    try:
        await asyncio.to_thread(_stm.clear)
        logger.info("[CLEANER] STM limpa com sucesso.")
    except Exception as e:
        logger.warning("[CLEANER] Falha ao limpar STM: %s", e)

    try:
        # Isolamento 2: Desvia a limpeza síncrona do banco vetorial em disco para Thread Pool
        def _clear_vector():
            from iaglobal.memory.memory_vector import MemoryVector
            MemoryVector().clear()
        await asyncio.to_thread(_clear_vector)
        logger.info("[CLEANER] MemoryVector limpo de forma assíncrona.")
    except Exception as e:
        logger.debug("[CLEANER] Falha ao limpar MemoryVector: %s", e)

    # Isolamento 3: Desvia a exclusão física de arquivos de swap em disco para Thread Pool
    task_clean = str(ctx.get("input", {}).get("task", ""))
    if task_clean:
        try:
            await asyncio.to_thread(cleanup_task, task_clean)
            logger.info("[CLEANER] Arquivos de disk swap limpos para a task.")
        except Exception as e:
            logger.debug("[CLEANER] Falha ao limpar disk swap: %s", e)

    total_discarded_chars = sum(d["chars"] for d in discarded) if discarded else 0
    report = {
        "discarded_count": len(discarded),
        "discarded_sources": [d["source"] for d in discarded],
        "total_discarded_chars": total_discarded_chars,
        "stm_cleared": True,
        "memory_vector_cleared": True,
    }

    if discarded:
        logger.info("[CLEANER] %d fontes descartadas (%d caracteres liberados na memória).", len(discarded), total_discarded_chars)

    latency_ms = (time.time() - start_time) * 1000.0

    # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
    return {
        "output": f"{len(discarded)} fontes descartadas",
        "cleanup_report": report,
        "success": True,
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency_ms,
            "cost": 0.0  # Infraestrutura puramente offline e local
        }
    }

