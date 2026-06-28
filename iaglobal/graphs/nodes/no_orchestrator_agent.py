# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_orchestrator_agent.py

"""
Orchestrator Agent Node — O maestro do fluxo de execução do iaglobal.
Gerencia roteamento de fases e ativação de nós com telemetria ativa para o Bandit.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.orchestrator_agent import OrchestratorAgent
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)

# Instanciação única do agente core
_orchestrator_agent = OrchestratorAgent()


async def run_orchestrator_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente orquestrador de forma assíncrona e não-bloqueante.
    Mapeia o sucesso do roteamento estratégico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "orchestrator_agent_llm"
    
    enhancement = ctx.get("enhancement") or {}
    requirements = ctx.get("requirements") or {}

    logger.info("[ORCHESTRATOR] Calculando rotas estratégicas do pipeline...")
    
    # Executa o roteamento core. Se for um método síncrono e pesado, desvia para thread pool
    if asyncio.iscoroutinefunction(_orchestrator_agent.route):
        orch = await _orchestrator_agent.route(enhancement, requirements)
    else:
        orch = await asyncio.to_thread(_orchestrator_agent.route, enhancement, requirements)

    next_phase = orch.get("next_phase", "definition")
    active_nodes = orch.get("active_nodes", [])

    logger.info(
        "[ORCHESTRATOR] Roteamento concluído: next_phase=%s | active_nodes=%d",
        next_phase,
        len(active_nodes),
    )

    memory = ctx.get("memory", {})
    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")

    # Consumo seguro e em background da caixa de entrada
    if bus is not None and inbox is not None:
        def _consume_inbox():
            mailbox = inbox.get_or_create("orchestrator_agent")
            return mailbox.process_inbox(max_messages=5)
            
        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info("[ORCHESTRATOR] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    # Publicação reativa e assíncrona no AcetylcholineBus para alertar o PM (Project Manager)
    if bus is not None:
        msg = AgentMessage(
            sender="orchestrator_agent",
            receiver="pm",
            type="orchestration_ready",
            payload={
                "next_phase": next_phase,
                "active_nodes": active_nodes,
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
        logger.info("[ORCHESTRATOR] Evento 'orchestration_ready' despachado com sucesso para o PM.")

    latency_ms = (time.time() - start_time) * 1000.0

    # Retorno higienizado cumprindo as Regras 1 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
    return {
        "output": f"Orquestração definida para a fase: {next_phase}",
        "orchestration": orch,
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency_ms,
            "cost": ctx.get("estimated_cost", 0.004)  # Custo estimado de tokens do roteamento
        }
    }

