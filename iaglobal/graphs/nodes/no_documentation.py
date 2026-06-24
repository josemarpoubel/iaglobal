# iaglobal/graphs/nodes/no_documentation.py

"""
Documentation Node — Redator técnico do ecossistema iaglobal.
Gera relatórios, manuais e documentos formatados com telemetria ativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.providers.provider_router import async_route_generate
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


async def run_documentation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de documentação técnica de forma assíncrona e não-bloqueante.
    Mapeia latência, custo de tokens e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "documentation_agent_llm"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")
    
    # Consumo seguro e em background da caixa de entrada
    if bus is not None and inbox is not None:
        def _consume_inbox():
            mailbox = inbox.get_or_create("documentation")
            return mailbox.process_inbox(max_messages=5)
            
        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info("[DOCUMENTATION] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    # Coleta de forma resiliente as saídas dos nós anteriores para contextualização
    coder_output = memory.get("coder", {}).get("output", "") or memory.get("multi_coder", {}).get("output", "")
    built_prompt = memory.get("prompt_builder", {}).get("built_prompt", "") or memory.get("prompt_builder", {}).get("output", "")

    if not task and not coder_output and not built_prompt:
        await asyncio.to_thread(record_error, "documentation", "Empty task context", {"task": task})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "document": "",
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    specialization = ctx.get("input", {}).get("_specialization", {}).get("coder", "")
    base_content = coder_output or built_prompt or task

    system = (
        "Voce e um redator tecnico gerando documentos formatados e prontos para publicacao.\n"
        "Formate o documento de forma limpa, bem estruturada, com secoes claras.\n"
        "Nao gere codigo — gere o documento final completo.\n"
        "Se o formato solicitado for PDF, inclua a estrutura completa do documento "
        "(titulo, introducao, secoes, conclusao) em formato texto rico."
    )
    if specialization:
        system = specialization

    prompt = (
        f"{system}\n\n"
        f"Tarefa original: {task}\n\n"
        f"Conteudo base:\n{base_content}\n\n"
        f"Gere o documento final completo e formatado, pronto para ser salvo como PDF. "
        f"Inclua titulo, secoes, listas e todo o conteudo necessario."
    )

    try:
        logger.info("[DOCUMENTATION] Disparando inferência assíncrona para redação técnica do documento...")
        
        # Chamada assíncrona do provider core
        doc = await async_route_generate(
            model="", prompt=prompt, task_type="documentation"
        )
        
        # Portão de segurança: validação de tamanho mínimo da documentação gerada
        is_success = bool(doc and len(doc) > 100)
        
        if is_success:
            logger.info("[DOCUMENTATION] Documento técnico gerado com sucesso: %d caracteres.", len(doc))
            
            # Publicação reativa e assíncrona no AcetylcholineBus para alertar o result_agent
            if bus is not None:
                msg = AgentMessage(
                    sender="documentation", 
                    receiver="result_agent",
                    type="doc_ready",
                    payload={"document": doc, "task": task},
                )
                if asyncio.iscoroutinefunction(bus.publish):
                    await bus.publish(msg)
                else:
                    await asyncio.to_thread(bus.publish, msg)
                logger.info("[DOCUMENTATION] Evento 'doc_ready' injetado no barramento com sucesso.")
                
            latency_ms = (time.time() - start_time) * 1000.0
            
            return {
                "output": doc,
                "document": doc,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": ctx.get("estimated_cost", 0.008)  # Custo de inferência estimado para redação rica
                }
            }
            
        # Caso a IA retorne um documento em branco ou excessivamente curto
        await asyncio.to_thread(record_error, "documentation", "Empty/short document", {"task": task[:100]})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "document": "",
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": ctx.get("estimated_cost", 0.002)}
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DOCUMENTATION] Falha crítica no pipeline do Documentation Agent: %s", e)
        await asyncio.to_thread(record_error, "documentation", str(e), {"task": task[:100]})
        
        return {
            "output": "",
            "document": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

