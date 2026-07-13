# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_memory_writer.py

"""
Memory Writer Node — Gerencia e persiste de forma não-bloqueante as memórias aprovadas e rejeitadas.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.memory.consolidation import ConsolidationEngine
from iaglobal.memory.memory_vector import store as mem_vector_store
from iaglobal.memory.memory_error import record_error
from iaglobal._paths import CORE_DB
from iaglobal.graphs.comms.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

# Singletons controlados de infraestrutura de memória
_ltm = None
_stm = None
_consolidation = None


def _get_ltm():
    global _ltm
    if _ltm is None:
        try:
            _ltm = LongTermMemory(db_path=CORE_DB)
        except Exception as e:
            logger.warning(
                "[MEMORY_WRITER] Falha ao inicializar LTM: %s, usando fallback em memória.",
                e,
            )
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


def _execute_sync_persistence(
    task: str,
    built_prompt: str,
    coder_output: str,
    critic_data: dict,
    search_insights: list,
) -> int:
    """Função enclausurada para executar todas as gravações físicas de I/O em thread pool."""
    stored_count = 0
    approved = critic_data.get("approved", False)
    score = critic_data.get("score", 0)

    # 1. Fluxo condicional de aprovação/rejeição
    if approved and coder_output:
        try:
            content = f"Task: {task}\n\nPrompt:\n{built_prompt[:1000]}\n\nOutput:\n{coder_output[:2000]}"
            _get_ltm().store(
                content=content,
                metadata={
                    "source": "pipeline",
                    "score": score,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                source="pipeline",
            )
            stored_count += 1

            mem_vector_store(
                text=f"[APROVADO] Task: {task[:200]}\n{coder_output[:500]}",
                mtype="pipeline_output",
            )
            stored_count += 1
        except Exception as e:
            logger.warning(
                "[MEMORY_WRITER] Falha ao persistir dados aprovados na LTM/Vetor: %s", e
            )
    else:
        reason = (
            critic_data.get("issues", ["score baixo"])[0]
            if not approved
            else "sem output"
        )
        try:
            _get_ltm().store(
                content=f"[REJEITADO] Task: {task}\nMotivo: {reason}\nScore: {score}",
                metadata={
                    "source": "pipeline",
                    "score": score,
                    "rejected": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                source="pipeline",
            )
            stored_count += 1
        except Exception as e:
            logger.debug("[MEMORY_WRITER] Falha ao salvar metadados rejeitados: %s", e)

    # 2. Injeção na Short-Term Memory (STM)
    try:
        _get_stm().add(
            {
                "task": task,
                "score": score,
                "approved": approved,
                "built_prompt": (built_prompt or "")[:500],
            },
            metadata={"source": "pipeline"},
        )
        stored_count += 1
    except Exception as e:
        logger.debug("[MEMORY_WRITER] Falha ao adicionar à STM: %s", e)

    # 3. Gravação de Fallback de Rastreabilidade na LTM
    try:
        _get_ltm().store(
            content=f"Task: {task}\nPrompt: {(built_prompt or '')[:500]}\nScore: {score}",
            metadata={"source": "memory_writer", "score": score, "approved": approved},
            source="pipeline",
        )
        stored_count += 1
    except Exception as e:
        logger.debug("[MEMORY_WRITER] Falha no LTM fallback: %s", e)

    # 4. Consolidação de Insights de buscas web anteriores
    if search_insights:
        try:
            summaries = _get_consolidation().consolidate(search_insights)
            stored_count += len(summaries) if summaries else 0
        except Exception as e:
            logger.debug("[MEMORY_WRITER] Falha no motor de consolidação: %s", e)

    return stored_count


async def run_memory_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consome o barramento e orquestra a persistência de memórias de forma assíncrona.
    Mapeia itens gravados, latência e sucesso operacional para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "memory_writer_deterministic_db_infrastructure"

    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

    # Consumo seguro e em background da caixa de entrada para capturar eventos em runtime
    if bus is not None and inbox is not None:

        def _consume_inbox():
            mailbox = inbox.get_or_create("memory_writer")
            return mailbox.process_inbox(max_messages=5)

        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info(
                    "[MEMORY_WRITER] Mensagem processada na inbox: de %s, tipo %s.",
                    msg.sender,
                    msg.type,
                )
                if msg.type == "review_done":
                    logger.info(
                        "[MEMORY_WRITER] Contrato 'review_done' interceptado via barramento."
                    )
                    memory["critic"] = msg.payload

    critic_data = memory.get("critic", {}) or {}
    approved = critic_data.get("approved", False)
    score = critic_data.get("score", 0)

    # FIX: se o critic foi pulado (output vazio / batch inicial), não persiste falso negativo
    if critic_data.get("_skip"):
        logger.info(
            "[MEMORY_WRITER] Critic foi pulado (sem output para avaliar) — nada a persistir"
        )
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "0 itens (skip)",
            "stored": False,
            "stored_count": 0,
            "success": True,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    built_prompt = memory.get("prompt_builder", {}).get(
        "built_prompt", ""
    ) or memory.get("prompt_builder", {}).get("output", "")
    coder_output = (
        memory.get("multi_coder", {}).get("output", "")
        or memory.get("coder", {}).get("output", "")
        or memory.get("result_agent", {}).get("output", "")
    )

    logger.info(
        "[MEMORY_WRITER] Analisando veredito do Critic: score=%.1f | approved=%s",
        score,
        approved,
    )

    # Coleta de forma preventiva insights de buscas anteriores para consolidação
    search_insights = []
    src_data = memory.get("search", {}).get("output", "")
    if src_data and len(src_data) > 100:
        search_insights.append(
            {"content": src_data[:500], "source": "search", "type": "web_search"}
        )

    try:
        # DESVIA TODO O BLCO DE I/O PESADO E SÍNCRONO PARA A THREAD POOL ISOLADA
        stored_count = await asyncio.to_thread(
            _execute_sync_persistence,
            task,
            built_prompt,
            coder_output,
            critic_data,
            search_insights,
        )

        logger.info(
            "[MEMORY_WRITER] Ciclo finalizado. Persistidos %d itens com sucesso nos bancos locais.",
            stored_count,
        )

        # Publicação reativa, não-bloqueante e assíncrona no AcetylcholineBus para alertar o result_agent
        if bus is not None:
            msg = AgentMessage(
                sender="memory_writer",
                receiver="result_agent",
                type="memory_persisted",
                payload={
                    "stored_count": stored_count,
                    "score": score,
                    "approved": approved,
                },
            )
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info(
                "[MEMORY_WRITER] Notificação 'memory_persisted' despachada com sucesso via barramento."
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": f"{stored_count} itens",
            "stored": True,
            "stored_count": stored_count,
            "success": True,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,  # Gravação offline local de banco de dados
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[MEMORY_WRITER] Falha crítica no pipeline de persistência de memórias: %s",
            e,
        )
        await asyncio.to_thread(
            record_error, "memory_writer", str(e), {"task": task[:100]}
        )

        return {
            "output": "0 itens",
            "stored": False,
            "stored_count": 0,
            "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
