"""AgentMailbox — caixa postal por agente com inbox/outbox."""

import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


class AgentMailbox:
    """Caixa postal por agente — inbox (recebidas) e outbox (enviadas)."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._inbox: List[AgentMessage] = []
        self._outbox: List[AgentMessage] = []

    def receive(self, message: AgentMessage):
        self._inbox.append(message)

    def send(self, message: AgentMessage):
        self._outbox.append(message)

    def process_inbox(self, max_messages: int = 10) -> List[AgentMessage]:
        batch = self._inbox[:max_messages]
        self._inbox = self._inbox[max_messages:]
        return batch

    def pending_received(self) -> int:
        return len(self._inbox)

    def pending_sent(self) -> int:
        return len(self._outbox)

    def clear(self):
        self._inbox.clear()
        self._outbox.clear()


class MailboxManager:
    """Gerencia caixas postais de múltiplos agentes."""

    def __init__(self):
        self._mailboxes: Dict[str, AgentMailbox] = {}

    def get_or_create(self, agent_name: str) -> AgentMailbox:
        if agent_name not in self._mailboxes:
            self._mailboxes[agent_name] = AgentMailbox(agent_name)
        return self._mailboxes[agent_name]

    def route_to_mailbox(self, message: AgentMessage):
        mailbox = self.get_or_create(message.receiver)
        mailbox.receive(message)
        sender_mailbox = self.get_or_create(message.sender)
        sender_mailbox.send(message)

    def count(self) -> int:
        return len(self._mailboxes)
