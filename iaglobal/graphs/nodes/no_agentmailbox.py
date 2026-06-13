from typing import Dict, Any, List
import logging

from iaglobal.graphs.communication.agent_mailbox import AgentMailbox, MailboxManager
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
from iaglobal.graphs.nodes import NODE_REGISTRY, ALL_NODE_NAMES

logger = logging.getLogger(__name__)

_mailbox_manager: MailboxManager = None
_bus: AcetylcholineBus = None


def _ensure_initialized():
    global _mailbox_manager, _bus
    if _mailbox_manager is None:
        _mailbox_manager = MailboxManager()
    if _bus is None:
        _bus = AcetylcholineBus()
    return _mailbox_manager, _bus


def _register_all_agents():
    manager, bus = _ensure_initialized()
    registered = 0
    for agent_name in ALL_NODE_NAMES:
        mailbox = manager.get_or_create(agent_name)
        bus.subscribe(agent_name, mailbox.receive)
        registered += 1
    logger.debug("[AGENTMAILBOX] %d agentes registrados no barramento", registered)
    return registered


def _route_pending():
    manager, _ = _ensure_initialized()
    for agent_name in list(manager._mailboxes.keys()):
        mailbox = manager._mailboxes[agent_name]
        pending = mailbox.pending_sent()
        if pending > 0:
            sent = mailbox.process_inbox(max_messages=50)
            logger.debug("[AGENTMAILBOX] %s: %d mensagens roteadas", agent_name, len(sent))


async def run_agentmailbox(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    manager, bus = _ensure_initialized()
    count = _register_all_agents()
    _route_pending()

    logger.info("[AGENTMAILBOX] Barramento ativo: %d agentes, %d mailboxes",
                count, manager.count())

    return {
        **ctx,
        "_mailbox_manager": manager,
        "_agent_bus": bus,
        "output": f"AgentMailbox ativo para {count} agentes",
        "agentmailbox": {
            "registered_agents": count,
            "mailboxes": manager.count(),
            "conversation_log": bus.conversation_log,
        },
    }
