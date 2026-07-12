# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_critic.py

"""
Critic Node — Avalia a qualidade do output gerado e despacha vereditos via barramento.
Totalmente em conformidade com as diretrizes e regras estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.core.critic_batch_queue import CriticBatchQueue
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_critic(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a crítica e avaliação de código gerado medindo performance
    e notificando o ecossistema de forma transparente e assíncrona.
    """
    start_time = time.time()
    resolved_model = "critic_agent_llm"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Recupera instâncias de barramento injetadas na memória ou direto pelo contexto
    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")
    
    # Processamento seguro da inbox na thread pool caso o método seja síncrono
    if bus is not None and inbox is not None:
        def _consume_inbox():
            mailbox = inbox.get_or_create("critic")
            return mailbox.process_inbox(max_messages=5)
            
        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info("[CRITIC] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    # Coleta de forma resiliente os outputs dos programadores anteriores
    coder_output = (
        memory.get("multi_coder", {}).get("output", "") or 
        memory.get("coder", {}).get("output", "") or 
        memory.get("result_agent", {}).get("output", "")
    )

    if not coder_output:
        logger.warning("[CRITIC] Nada para avaliar — output dos programadores está vazio")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "",
            "critic": {
                "approved": True, "score": 0.0, "issues": ["Sem output para avaliar"],
                "fix_suggestions": [], "_skip": True,
            },
            "execution_metrics": {"model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0}
        }

    prompt_built = memory.get("prompt_builder", {}).get("built_prompt", "") or task

    try:
        logger.info("[CRITIC] Iniciando avaliação com validação cruzada...")
        queue = await CriticBatchQueue.get_instance()
        result = await queue.evaluate_with_context(
            memory=memory, task=task, coder_output=coder_output,
            prompt_built=prompt_built,
        )
            
        approved = result.get("approved", False)
        score = result.get("score", 0)
        issues = result.get("issues", [])

        logger.info("[CRITIC] score=%.1f approved=%s issues=%d", score, approved, len(issues))
        if issues:
            for iss in issues[:3]:
                logger.info("[CRITIC] Alerta de issue: %s", iss)

        if score < 30:
            await asyncio.to_thread(record_error, "critic", f"Baixa qualidade detectada: score={score}", {"task": task[:100]})

        # Publicação assíncrona e não-bloqueante de veredito no AcetylcholineBus
        if bus is not None:
            msg = AgentMessage(
                sender="critic", 
                receiver="result_agent",
                type="review_done",
                payload={
                    "approved": approved,
                    "score": score,
                    "issues": issues,
                    "fix_suggestions": result.get("fix_suggestions", []),
                    "output": coder_output,
                    # Injeta a telemetria na própria mensagem para auditorias reativas do barramento
                    "execution_metrics": {
                        "model": resolved_model,
                        "success": True,
                        "latency": (time.time() - start_time) * 1000.0,
                        "cost": ctx.get("estimated_cost", 0.003)
                    }
                },
            )
            
            # Se o método publish adaptado for assíncrono, aguarda. Caso contrário, create_task lida.
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info("[CRITIC] Notificação 'review_done' injetada no barramento com sucesso.")
        
        # Processamento tardio da inbox limpo de travas
        if bus is not None and inbox is not None:
            await asyncio.to_thread(_consume_inbox)

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo a Seção 1 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": coder_output,
            "critic": {
                "approved": approved,
                "score": score,
                "issues": issues,
                "fix_suggestions": result.get("fix_suggestions", []),
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Custos de inferência do Critic Agent
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[CRITIC] Falha severa durante ciclo analítico do Critic: %s", e)
        await asyncio.to_thread(record_error, "critic", str(e), {"task": task[:100]})
        
        return {
            "output": coder_output,
            "critic": {"approved": False, "score": 0, "issues": [str(e)]},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

