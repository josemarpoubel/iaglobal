"""Memory Writer — persiste em LTM/STM + cbor2 + SQLite apenas se aprovado pelo Critic."""
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.memory.consolidation import ConsolidationEngine
from iaglobal.memory.memory_vector import store as mem_vector_store
from iaglobal.memory.memory_error import record_error
from iaglobal._paths import CORE_DB

logger = logging.getLogger(__name__)
_ltm = LongTermMemory(db_path=CORE_DB)
_stm = ShortTermMemory()
_consolidation = ConsolidationEngine(_ltm)


async def run_memory_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    ctx_memory = ctx.get("memory", {})
    # Extrair critic do barramento (se msg do tipo review_done)
    if isinstance(ctx.get("type"), str) and ctx.get("type") == "review_done":
        logger.info("[MEMORY_WRITER] Recebido review_done — populando memory do critic")
        ctx_memory["critic"] = ctx.get("payload", {})
    task = str(ctx.get("input", {}).get("task", ""))

    critic_data = memory.get("critic", {})
    approved = critic_data.get("approved", False)
    score = critic_data.get("score", 0)

    built_prompt = memory.get("prompt_builder", {}).get("built_prompt", "") or memory.get("prompt_builder", {}).get("output", "")
    coder_output = memory.get("multi_coder", {}).get("output", "") or memory.get("coder", {}).get("output", "") or memory.get("result_agent", {}).get("output", "")

    logger.info("[MEMORY_WRITER] Critic score=%.1f approved=%s", score, approved)

    stored_count = 0

    if approved and coder_output:
        try:
            content = f"Task: {task}\n\nPrompt:\n{built_prompt[:1000]}\n\nOutput:\n{coder_output[:2000]}"
            _ltm.store(
                content=content,
                metadata={"source": "pipeline", "score": score, "timestamp": datetime.now(timezone.utc).isoformat()},
                source="pipeline"
            )
            stored_count += 1

            mem_vector_store(text=f"[APROVADO] Task: {task[:200]}\n{coder_output[:500]}", mtype="pipeline_output")
            stored_count += 1

            logger.info("[MEMORY_WRITER] Score=%.1f — persistido em LTM + cbor2/SQLite", score)
        except Exception as e:
            logger.warning("[MEMORY_WRITER] Falha ao persistir aprovado: %s", e)
    else:
        reason = critic_data.get("issues", ["score baixo"])[0] if not approved else "sem output"
        logger.info("[MEMORY_WRITER] Nao aprovado (score=%.1f: %s) — apenas metadados", score, reason)
        try:
            _ltm.store(
                content=f"[REJEITADO] Task: {task}\nMotivo: {reason}\nScore: {score}",
                metadata={"source": "pipeline", "score": score, "rejected": True, "timestamp": datetime.now(timezone.utc).isoformat()},
                source="pipeline"
            )
            stored_count += 1
        except Exception as e:
            logger.debug("[MEMORY_WRITER] Falha ao salvar rejeitado: %s", e)

    _stm.add(
        {"task": task, "score": score, "approved": approved, "built_prompt": (built_prompt or "")[:500]},
        metadata={"source": "pipeline"}
    )
    stored_count += 1

    try:
        _ltm.store(
            content=f"Task: {task}\nPrompt: {(built_prompt or '')[:500]}\nScore: {score}",
            metadata={"source": "memory_writer", "score": score, "approved": approved},
            source="pipeline",
        )
        stored_count += 1
    except Exception as e:
        logger.debug("[MEMORY_WRITER] LTM fallback: %s", e)

    search_insights = []
    for src in ["search"]:
        src_data = memory.get(src, {}).get("output", "")
        if src_data and len(src_data) > 100:
            search_insights.append({"content": src_data[:500], "source": src, "type": "web_search"})

    if search_insights:
        try:
            summaries = _consolidation.consolidate(search_insights)
            stored_count += len(summaries)
        except Exception:
            pass

    logger.info("[MEMORY_WRITER] %d itens persistidos (score=%.1f, approved=%s)", stored_count, score, approved)
    return {**ctx, "output": f"{stored_count} itens", "stored": True, "stored_count": stored_count, "success": True}
