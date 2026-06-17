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
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)
_ltm = None
_stm = None
_consolidation = None


def _get_ltm():
    global _ltm
    if _ltm is None:
        try:
            _ltm = LongTermMemory(db_path=CORE_DB)
        except Exception as e:
            logger.warning("[MEMORY_WRITER] Falha ao inicializar LTM: %s", e)
            _ltm = LongTermMemory(db_path=":memory:")
    return _ltm


def _get_stm():
    global _stm
    if _stm is None:
        _stm = ShortTermMemory()
    return _stm


def _get_consolidation():
    global _consolidation
    if _consolidation is None:
        _consolidation = ConsolidationEngine(_get_ltm())
    return _consolidation


async def run_memory_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("memory_writer")
        msgs = mailbox.process_inbox(max_messages=5)
        for msg in msgs:
            logger.info("[MEMORY_WRITER] Mensagem recebida de %s: type=%s", msg.sender, msg.type)
            if msg.type == "review_done":
                logger.info("[MEMORY_WRITER] Recebido review_done do critic via bus")
                memory["critic"] = msg.payload

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
            _get_ltm().store(
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
            _get_ltm().store(
                content=f"[REJEITADO] Task: {task}\nMotivo: {reason}\nScore: {score}",
                metadata={"source": "pipeline", "score": score, "rejected": True, "timestamp": datetime.now(timezone.utc).isoformat()},
                source="pipeline"
            )
            stored_count += 1
        except Exception as e:
            logger.debug("[MEMORY_WRITER] Falha ao salvar rejeitado: %s", e)

    _get_stm().add(
        {"task": task, "score": score, "approved": approved, "built_prompt": (built_prompt or "")[:500]},
        metadata={"source": "pipeline"}
    )
    stored_count += 1

    try:
        _get_ltm().store(
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
            summaries = _get_consolidation().consolidate(search_insights)
            stored_count += len(summaries)
        except Exception:
            pass

    logger.info("[MEMORY_WRITER] %d itens persistidos (score=%.1f, approved=%s)", stored_count, score, approved)

    if bus is not None:
        msg = AgentMessage(
            sender="memory_writer", receiver="result_agent",
            type="memory_persisted",
            payload={"stored_count": stored_count, "score": score, "approved": approved},
        )
        bus.publish(msg)
        logger.info("[MEMORY_WRITER] Mensagem enviada para result_agent via bus")

    return {**ctx, "output": f"{stored_count} itens", "stored": True, "stored_count": stored_count, "success": True}
