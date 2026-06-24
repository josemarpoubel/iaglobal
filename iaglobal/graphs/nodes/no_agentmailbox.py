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
_initialized_agents = False


def _ensure_initialized():
    global _mailbox_manager, _bus
    if _mailbox_manager is None:
        _mailbox_manager = MailboxManager()
    if _bus is None:
        _bus = AcetylcholineBus()
        # Inicializa o purger automático em background para evitar vazamento de memória
        _bus.start_background_purger(interval_sec=10.0)
    return _mailbox_manager, _bus


async def _register_all_agents_idempotent(self):
    """
    Registra os agentes no barramento de forma segura e sem duplicações.
    Busca os nomes dinamicamente do Singleton 'self' para quebrar o import circular.
    """
    global _initialized_agents
    if _initialized_agents:
        return _mailbox_manager.count()

    manager, bus = _ensure_initialized()
    registered = 0
    
    # Extrai a lista de nós direto do Singleton (Nodes) em runtime
    # Isso evita o import circular de iaglobal.graphs.nodes
    all_node_names = [name[len("run_"):] for name in dir(self) if name.startswith("run_")]
    if not all_node_names:
        # Fallback de segurança se dir(self) ainda estiver populando
        all_node_names = ["orchestrator_agent", "coder", "debugger", "tester", "integrator"]

    for agent_name in all_node_names:
        mailbox = manager.get_or_create(agent_name)
        # Garante assinatura limpa
        bus.unsubscribe(agent_name, mailbox.receive)
        bus.subscribe(agent_name, mailbox.receive)
        registered += 1
        
    logger.debug("[AGENTMAILBOX] %d agentes registrados de forma única no barramento", registered)
    _initialized_agents = True
    return registered


async def _route_pending_async():
    """Roteia mensagens pendentes respeitando a natureza assíncrona do ecossistema."""
    manager, _ = _ensure_initialized()
    for agent_name in list(manager._mailboxes.keys()):
        mailbox = manager._mailboxes[agent_name]
        pending = mailbox.pending_sent() if hasattr(mailbox, "pending_sent") else 0
        if pending > 0:
            # Se process_inbox for síncrono na biblioteca, desvia para thread pool
            if asyncio.iscoroutinefunction(mailbox.process_inbox):
                sent = await mailbox.process_inbox(max_messages=50)
            else:
                sent = await asyncio.to_thread(mailbox.process_inbox, max_messages=50)
            logger.debug("[AGENTMAILBOX] %s: %d mensagens processadas na inbox", agent_name, len(sent) if sent else 0)


async def run_agentmailbox(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó de controle do ecossistema de mensageria.
    Medido e auditado conforme Seções 2, 3 e 4 do AGENTS.md.
    """
    start_time = time.time()
    memory = ctx.get("memory", {})

    manager, bus = _ensure_initialized()
    
    # Executa registros e roteamentos de forma assíncrona e não-bloqueante
    count = await _register_all_agents_idempotent(self)
    await _route_pending_async()

    logger.info("[AGENTMAILBOX] Barramento de Comunicação Ativo: %d mailboxes operando", manager.count())

    latency_ms = (time.time() - start_time) * 1000.0
    resolved_model = "deterministic_mailbox_infrastructure"

    # Captura o log de conversação se o método existir no seu barramento original
    conv_log = bus.conversation_log() if callable(getattr(bus, "conversation_log", None)) else "Log indisponível"

    return {
        "mailbox_manager": manager,
        "agent_bus": bus,
        "output": f"AgentMailbox ativo para {count} agentes",
        "agentmailbox": {
            "registered_agents": count,
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

