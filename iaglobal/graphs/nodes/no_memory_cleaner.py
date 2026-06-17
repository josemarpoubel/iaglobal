from typing import Dict, Any, List
import logging

from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.graphs.nodes._disk_swap import cleanup_task

logger = logging.getLogger(__name__)
_stm = ShortTermMemory()


async def run_memory_cleaner(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})

    critic_data = memory.get("critic", {})
    score = critic_data.get("score", 0)
    approved = critic_data.get("approved", False)
    issues = critic_data.get("issues", [])

    logger.info("[CLEANER] Iniciando limpeza (critic score=%.1f, approved=%s)", score, approved)

    used_sources = {k for k in memory.keys() if k in ("coder", "multi_coder", "prompt_builder")}
    discarded = []
    for src in ("search", "local_knowledge"):
        src_data = memory.get(src, {})
        src_output = src_data.get("output", "")
        if src_output and src not in used_sources:
            discarded.append({"source": src, "chars": len(src_output)})
            logger.debug("[CLEANER] Descartando %s (%d chars) — nao utilizado no prompt", src, len(src_output))

    try:
        _stm.clear()
        logger.info("[CLEANER] STM limpa")
    except Exception as e:
        logger.warning("[CLEANER] Falha ao limpar STM: %s", e)

    try:
        from iaglobal.memory.memory_vector import MemoryVector
        MemoryVector().clear()
        logger.info("[CLEANER] MemoryVector limpo")
    except Exception as e:
        logger.debug("[CLEANER] Falha ao limpar MemoryVector: %s", e)

    try:
        task_clean = str(ctx.get("input", {}).get("task", ""))
        if task_clean:
            cleanup_task(task_clean)
            logger.info("[CLEANER] Disk swap limpo para task")
    except Exception as e:
        logger.debug("[CLEANER] Falha ao limpar disk swap: %s", e)

    report = {
        "discarded_count": len(discarded),
        "discarded_sources": [d["source"] for d in discarded],
        "total_discarded_chars": sum(d["chars"] for d in discarded),
        "stm_cleared": True,
        "memory_vector_cleared": True,
    }

    if discarded:
        logger.info("[CLEANER] %d fontes descartadas (%d chars)", len(discarded), report["total_discarded_chars"])

    return {
        **ctx,
        "output": f"{len(discarded)} fontes descartadas",
        "cleanup_report": report,
        "success": True,
    }
