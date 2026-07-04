# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_pm.py

"""
PM Node — Product Manager do iaglobal.
Analisa e extrai requisitos com telemetria nativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.pm_agent import PMAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

# Instanciação única do agente PM
_pm_agent = PMAgent()


async def run_pm(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente PM de forma assíncrona e não-bloqueante.
    Mapeia a latência e o custo da análise de requisitos para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "pm_agent_llm"
    
    enhancement = ctx.get("enhancement") or {}
    prompt = ctx.get("prompt") or {}
    raw = prompt.get("normalized", "") if isinstance(prompt, dict) else str(prompt)

    logger.info("[PM] Iniciando extração cognitiva de requisitos a partir do prompt...")

    # Executa a extração. Se for um método síncrono que consome LLM, desvia para thread pool
    if asyncio.iscoroutinefunction(_pm_agent.extract_requirements):
        req_inputs = await _pm_agent.extract_requirements(raw, enhancement)
    else:
        req_inputs = await asyncio.to_thread(_pm_agent.extract_requirements, raw, enhancement)

    functional_reqs = req_inputs.get("functional", []) or []
    non_functional_reqs = req_inputs.get("non_functional", []) or []
    priority = req_inputs.get("priority", "medium")

    logger.info(
        "[PM] Extração concluída: funcionais=%d | não-funcionais=%d | prioridade=%s",
        len(functional_reqs),
        len(non_functional_reqs),
        priority,
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

    # Consumo seguro e em background da caixa de entrada
    if bus is not None and inbox is not None:
        def _consume_inbox():
            mailbox = inbox.get_or_create("pm")
            return mailbox.process_inbox(max_messages=5)
            
        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info("[PM] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    # Publicação reativa e assíncrona no AcetylcholineBus para alertar o nó de requisitos
    if bus is not None:
        msg = AgentMessage(
            sender="pm",
            receiver="requirements",
            type="requirements_ready",
            payload={
                "functional_count": len(functional_reqs),
                "non_functional_count": len(non_functional_reqs),
                "priority": priority,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": (time.time() - start_time) * 1000.0,
                    "cost": ctx.get("estimated_cost", 0.002)
                }
            },
        )
        
        if asyncio.iscoroutinefunction(bus.publish):
            await bus.publish(msg)
        else:
            await asyncio.to_thread(bus.publish, msg)
            
        logger.info("[PM] Evento 'requirements_ready' despachado com sucesso via barramento.")

    latency_ms = (time.time() - start_time) * 1000.0

    # Retorno higienizado cumprindo as Regras 1 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
    return {
        "output": f"Requisitos extraídos com sucesso. Prioridade: {priority}",
        "requirements_inputs": req_inputs,
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency_ms,
            "cost": ctx.get("estimated_cost", 0.005)  # Custos estimados de tokens para a análise do PM
        }
    }

