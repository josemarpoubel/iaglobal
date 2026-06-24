# iaglobal/graphs/nodes/no_agentmailbox.py

"""
Agent Mailbox Node — Gerencia caixas de correio e assinaturas no AcetylcholineBus.
Integrado de forma totalmente assíncrona cumprindo o AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any, List

from iaglobal.graphs.communication.agent_mailbox import AgentMailbox, MailboxManager
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage

logger = logging.getLogger(__name__)

# Singletons de controle interno
_mailbox_manager: MailboxManager = None
_bus: AcetylcholineBus = None


def _ensure_initialized():
    global _mailbox_manager, _bus
    if _mailbox_manager is None:
        _mailbox_manager = MailboxManager()
    if _bus is None:
        _bus = AcetylcholineBus()
        # Inicializa o purger automático em background para evitar vazamento de memória
        _bus.start_background_purger(interval_sec=10.0)
    return _mailbox_manager, _bus


async def run_agentmailbox(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó de controle do ecossistema de mensageria.
    Medido e auditado conforme Seções 2, 3 e 5 do AGENTS.md.
    """
    start_time = time.time()
    memory = ctx.get("memory", {})
    
    # Extrai os nomes dos nós do contexto ou usa fallback
    from iaglobal.graphs.nodes import Nodes
    node_names = list(Nodes().nodes.keys()) if hasattr(Nodes(), 'nodes') else []
    
    manager, bus = _ensure_initialized()
    
    # Registra agentes no barramento
    for agent_name in node_names:
        mailbox = manager.get_or_create(agent_name)
        bus.unsubscribe(agent_name, mailbox.receive)
        bus.subscribe(agent_name, mailbox.receive)
    
    logger.info("[AGENTMAILBOX] Barramento de Comunicação Ativo: %d mailboxes operando", manager.count())
    
    latency_ms = (time.time() - start_time) * 1000.0
    resolved_model = "deterministic_mailbox_infrastructure"
    
    # Captura o log de conversação se o método existir no seu barramento original
    conv_log = bus.conversation_log() if callable(getattr(bus, "conversation_log", None)) else "Log indisponível"
    
    return {
        "mailbox_manager": manager,
        "agent_bus": bus,
        "output": f"AgentMailbox ativo para {len(node_names)} agentes",
        "agentmailbox": {
            "registered_agents": len(node_names),
            "mailboxes": manager.count(),
            "conversation_log": conv_log,
        },
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency_ms,
            "cost": 0.0  # Infraestrutura puramente local
        }
    }

