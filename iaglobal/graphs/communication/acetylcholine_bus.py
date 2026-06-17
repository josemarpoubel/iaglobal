# iaglobal/graphs/communication

# AcetylcholineBus — barramento de mensagens entre agentes com pub/sub e TTL.

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

DEFAULT_TTL = 60


@dataclass
class AgentMessage:
    sender: str
    receiver: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    ttl: int = DEFAULT_TTL
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class AcetylcholineBus:
    """Barramento de mensagens entre agentes com pub/sub e TTL."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._messages: List[AgentMessage] = []

    def publish(self, message: AgentMessage):
        self._messages.append(message)
        logger.info("[ACH-BUS] %s → %s | type=%s | priority=%s | payload_keys=%s", 
                    message.sender, message.receiver, message.type, message.priority, 
                    list(message.payload.keys()) if message.payload else "none")
        self._route(message)

    def subscribe(self, topic: str, handler: Callable):
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable):
        if handler in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(handler)

    def _route(self, message: AgentMessage):
        handlers = []

        if message.receiver in self._subscribers:
            handlers.extend(self._subscribers[message.receiver])

        topic_patterns = [f"{message.type}:*", f"*:{message.receiver}", "*:*"]
        for pattern in topic_patterns:
            handlers.extend(self._subscribers.get(pattern, []))

        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                logger.warning("[ACH-BUS] Handler falhou para %s→%s: %s", message.sender, message.receiver, e)

    def purge_expired(self):
        before = len(self._messages)
        self._messages = [m for m in self._messages if not m.is_expired()]
        purged = before - len(self._messages)
        if purged:
            logger.debug("[ACH-BUS] %d mensagens expiradas removidas", purged)

    def pending_count(self) -> int:
        self.purge_expired()
        return len(self._messages)

    def message_history(self) -> List[Dict[str, Any]]:
        return [
            {
                "sender": m.sender,
                "receiver": m.receiver,
                "type": m.type,
                "priority": m.priority,
                "timestamp": m.timestamp,
                "ttl": m.ttl,
            }
            for m in self._messages
        ]

    def conversation_log(self) -> str:
        lines = ["=== AGENT CONVERSATION LOG ==="]
        for m in self._messages:
            lines.append(f"  {m.sender:20s} → {m.receiver:20s} | type={m.type:15s} | priority={m.priority}")
        lines.append(f"  Total messages: {len(self._messages)}")
        lines.append("================================")
        return "\n".join(lines)
