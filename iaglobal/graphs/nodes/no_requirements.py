# iaglobal/graphs/nodes/no_requirements.py

"""
Requirements Node — Refina, classifica e prioriza os requisitos operacionais do sistema.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.requirements_agent import RequirementsAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

# Instanciação única do agente especializado em requisitos
_requirements_agent = RequirementsAgent()


async def run_requirements(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a refinação assíncrona de requisitos de forma não-bloqueante.
    Mapeia latência, custos e sucesso de classificação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "requirements_agent_llm_core"
    
    req_inputs = ctx.get("requirements_inputs") or ctx.get("memory", {}).get("pm", {}).get("requirements_inputs", {})
    
    logger.info("[REQUIREMENTS] Iniciando refinação cognitiva e priorização de requisitos...")

    try:
        # Desvia o processamento e inferência síncrona de requisitos para a Thread Pool isolada
        if asyncio.iscoroutinefunction(_requirements_agent.refine):
            requirements = await _requirements_agent.refine(req_inputs)
        else:
            requirements = await asyncio.to_thread(_requirements_agent.refine, req_inputs)

        requirements = requirements or {}
        classification = requirements.get("classification", "medium")
        priorities = requirements.get("priorities", ["medium"])
        
        functional_reqs = requirements.get("functional", []) or []
        non_functional_reqs = requirements.get("non_functional", []) or []
        total_reqs = len(functional_reqs) + len(non_functional_reqs)

        logger.info(
            "[REQUIREMENTS] Refinação concluída: classificação=%s | prioridades=%s | total=%d",
            classification, priorities, total_reqs
        )

        memory = ctx.get("memory", {}) or {}
        ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
        bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
        inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

        # Processamento seguro e não-bloqueante da caixa de entrada em thread pool
        if bus is not None and inbox is not None:
            def _consume_inbox():
                mailbox = inbox.get_or_create("requirements")
                return mailbox.process_inbox(max_messages=5)
            
            msgs = await asyncio.to_thread(_consume_inbox)
            if msgs:
                for msg in msgs:
                    logger.info("[REQUIREMENTS] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

        # Publicação assíncrona reativa no AcetylcholineBus para alertar o Arquiteto (architect)
        if bus is not None:
            msg = AgentMessage(
                sender="requirements",
                receiver="architect",
                type="requirements_refined",
                payload={
                    "classification": classification,
                    "priorities": priorities,
                    "total": total_reqs,
                },
            )
            if asyncio.iscoroutinefunction(bus.publish):
                await bus.publish(msg)
            else:
                await asyncio.to_thread(bus.publish, msg)
            logger.info("[REQUIREMENTS] Evento 'requirements_refined' despachado com sucesso via barramento.")

        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(requirements, dict) and bool(requirements)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": f"Refinados {total_reqs} requisitos com prioridade {priorities}",
            "requirements": requirements,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo de inferência estimado para refinação
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[REQUIREMENTS] Falha crítica no pipeline de refinação de requisitos: %s", e)
        
        return {
            "output": "Falha no refinamento de requisitos",
            "requirements": {"functional": [], "non_functional": [], "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

