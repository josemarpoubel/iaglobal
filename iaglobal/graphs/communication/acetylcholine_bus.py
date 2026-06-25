# iaglobal/graphs/communication

# AcetylcholineBus — barramento de mensagens entre agentes com pub/sub e TTL.

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set, Coroutine
from collections import defaultdict

from iaglobal.graphs.communication.membrane_key import MembraneKey

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
    """Barramento assíncrono e não-bloqueante de mensagens entre agentes com TTL."""

    def __init__(self):
        # Suporta tanto funções síncronas comuns quanto corrotinas (async def)
        self._subscribers: Dict[str, List[Callable[[AgentMessage], Any]]] = defaultdict(list)
        self._messages: List[AgentMessage] = []
        self._lock = asyncio.Lock()
        self._purge_task: Optional[asyncio.Task] = None

    def start_background_purger(self, interval_sec: float = 10.0):
        """Inicia um worker em background para evitar vazamento de memória por TTL."""
        if self._purge_task is None or self._purge_task.done():
            self._purge_task = asyncio.create_task(self._periodic_purge(interval_sec))

    async def _periodic_purge(self, interval_sec: float):
        while True:
            await asyncio.sleep(interval_sec)
            await self.purge_expired()

    async def publish(self, message: AgentMessage):
        """Publica uma mensagem de forma assíncrona e dispara handlers em paralelo."""
        async with self._lock:
            self._messages.append(message)
            
        logger.info("[ACH-BUS] %s → %s | type=%s | priority=%s", 
                    message.sender, message.receiver, message.type, message.priority)
        
        # Dispara o roteamento sem bloquear o fluxo principal de quem publicou
        asyncio.create_task(self._route(message))

    def subscribe(self, topic: str, handler: Callable):
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable):
        if handler in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(handler)

    async def _route(self, message: AgentMessage):
        """Coleta handlers correspondentes sem duplicidade e os executa de forma concorrente."""
        # Validar chave de membrana se presente
        if "membrane_key" in message.payload:
            mk = MembraneKey()
            if not mk.validate_key(message.sender, message.payload["membrane_key"]):
                logger.warning(f"[ACH-BUS] Membrane key invalid for {message.sender} - rejecting")
                return
        
        # Conjunto (Set) evita que o mesmo handler seja chamado duas vezes na mesma mensagem
        unique_handlers: Set[Callable] = set()

        if message.receiver in self._subscribers:
            unique_handlers.update(self._subscribers[message.receiver])

        topic_patterns = [f"{message.type}:*", f"*:{message.receiver}", "*:*"]
        for pattern in topic_patterns:
            if pattern in self._subscribers:
                unique_handlers.update(self._subscribers[pattern])

        # Agenda a execução de todos os handlers em paralelo (não bloqueante)
        tasks = [self._execute_handler(handler, message) for handler in unique_handlers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Callable, message: AgentMessage):
        """Garante que a falha de um agente receptor não propague ou quebre o barramento."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                # Se o handler for síncrono, roda no thread pool para não travar o loop de eventos
                await asyncio.to_thread(handler, message)
        except Exception as e:
            logger.error("[ACH-BUS] Falha crítica no handler de %s para %s: %s", 
                         message.sender, message.receiver, e, exc_info=True)

    async def purge_expired(self):
        """Remove mensagens expiradas de forma thread-safe."""
        async with self._lock:
            before = len(self._messages)
            now = time.time()
            self._messages = [m for m in self._messages if now - m.timestamp <= m.ttl]
            purged = before - len(self._messages)
            if purged > 0:
                logger.debug("[ACH-BUS] %d mensagens expiradas expurgadas automaticamente", purged)

    async def pending_count(self) -> int:
        await self.purge_expired()
        return len(self._messages)

