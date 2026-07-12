import asyncio
import collections
import dataclasses
import datetime
import logging
from typing import Any, Callable, Dict, List, Set, Optional

logger = logging.getLogger("iaglobal.graphs.communication.acetylcholine_bus")

COLONY_MESSAGE_TYPES = {"task_offer", "result_share", "skill_handshake"}


@dataclasses.dataclass
class AgentMessage:
    """
    Representa a estrutura de mensagem de alta prioridade enviada entre 
    os agentes do grafo de execução do iaglobal.

    Estendido para Colony Intelligence:
    - organism_id: identifica o organismo de origem (padrão "iaglobal")
    - message_type aceita novos tipos: task_offer, result_share, skill_handshake
    """
    id: Optional[str] = None
    sender: str = "system"
    recipient: str = "all"
    organism_id: str = "iaglobal"
    content: Any = None
    message_type: str = "generic"
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    )
    
    payload: dict = dataclasses.field(default_factory=dict)
    priority: int = 1  # Aceita explicitamente o parâmetro de prioridade dos nós de grafos
    
    # InitVars de compatibilidade
    receiver: dataclasses.InitVar[Optional[str]] = None
    type: dataclasses.InitVar[Optional[str]] = None

    def __post_init__(self, receiver, type):
        if receiver is not None:
            self.recipient = receiver
        if type is not None:
            self.message_type = type
        if self.content is not None and not self.payload:
            if isinstance(self.content, dict):
                self.payload = self.content
        elif self.payload and self.content is None:
            self.content = self.payload

class AcetylcholineBus:
    def __init__(self, max_history: int = 500):
        self._subscribers: Dict[str, Set[Callable[[AgentMessage], Any]]] = collections.defaultdict(set)
        self._history: collections.deque = collections.deque(maxlen=max_history)
        self._lock = asyncio.Lock()
        self._purge_task: Optional[asyncio.Task] = None

    def subscribe(self, channel_or_recipient: str, callback: Callable[[AgentMessage], Any]):
        self._subscribers[channel_or_recipient].add(callback)

    def unsubscribe(self, channel_or_recipient: str, callback: Callable[[AgentMessage], Any]):
        if channel_or_recipient in self._subscribers:
            self._subscribers[channel_or_recipient].discard(callback)

    async def emit(self, message: AgentMessage):
        async with self._lock:
            self._history.append(message)

        listeners = (
            list(self._subscribers[message.recipient]) +
            list(self._subscribers[message.message_type]) +
            list(self._subscribers.get(f"org:{message.organism_id}", set())) +
            list(self._subscribers["*"])
        )
        if not listeners:
            return

        tasks = [self._execute_callback(cb, message) for cb in listeners]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def publish(self, message: AgentMessage):
        await self.emit(message)

    async def _execute_callback(self, callback: Callable[[AgentMessage], Any], message: AgentMessage):
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error(f"❌ Falha ao entregar mensagem no barramento: {e}")

    async def _periodic_purge(self, interval: float = 10.0):
        try:
            while True:
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    def get_history(self) -> List[AgentMessage]:
        return list(self._history)

bus = AcetylcholineBus()
