# iaglobal/graphs/comms/acetylcholine_bus.py
# Barramento de Sinalização Celular — Pub/Sub + filas por task_id.
# Combina o sistema de broadcast (subscribers) com filas isoladas
# (defaultdict[asyncio.Queue]) para que o motor principal leia eventos
# sem bloqueio via consume_event(task_id).

import asyncio
import collections
import dataclasses
import datetime
import logging
from typing import Any, Callable, Dict, List, Set, Optional

from iaglobal.utils.life_signal_collector import instrument

logger = logging.getLogger("iaglobal.graphs.communication.acetylcholine_bus")

COLONY_MESSAGE_TYPES = {"task_offer", "result_share", "skill_handshake"}


@dataclasses.dataclass
class AgentMessage:
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
    priority: int = 1

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
    """Barramento de sinalização celular com pub/sub + filas por task_id.

    Duas camadas de comunicação:
      - **Broadcast (pub/sub)**: subscribers por channel/recipient — usado
        para sinais globais (ex: colony intelligence).
      - **Fila por task_id**: `consume_event(task_id)` — polling não
        bloqueante, ideal para o pipeline verificar intervenções sem travar.
    """

    def __init__(self, max_history: int = 500):
        self._subscribers: Dict[str, Set[Callable[[AgentMessage], Any]]] = (
            collections.defaultdict(set)
        )
        self._history: collections.deque = collections.deque(maxlen=max_history)
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    # ── Pub/Sub (broadcast) ──────────────────────────────────────────────

    def subscribe(self, channel_or_recipient: str, callback: Callable[[AgentMessage], Any]):
        self._subscribers[channel_or_recipient].add(callback)

    def unsubscribe(self, channel_or_recipient: str, callback: Callable[[AgentMessage], Any]):
        if channel_or_recipient in self._subscribers:
            self._subscribers[channel_or_recipient].discard(callback)

    async def emit(self, message: AgentMessage):
        await self._enqueue_for_task(message)
        async with self._lock:
            self._history.append(message)
        listeners = (
            list(self._subscribers.get(message.recipient, set()))
            + list(self._subscribers.get(message.message_type, set()))
            + list(self._subscribers.get(f"org:{message.organism_id}", set()))
            + list(self._subscribers.get("*", set()))
        )
        if not listeners:
            return
        tasks = [self._execute_callback(cb, message) for cb in listeners]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def publish(self, message: AgentMessage):
        await self.emit(message)

    async def _execute_callback(self, callback, message):
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error("Falha ao entregar mensagem no barramento: %s", e)

    # ── Fila por task_id (consume_event) ─────────────────────────────────

    def register_task(self, task_id: str):
        """Cria uma fila isolada para a task."""
        self._queues.setdefault(task_id, asyncio.Queue())

    def unregister_task(self, task_id: str):
        """Remove a fila da task — coleta de lixo metabólica."""
        self._queues.pop(task_id, None)

    async def _enqueue_for_task(self, message: AgentMessage) -> None:
        """Se a mensagem tiver task_id no content/payload, enfileira."""
        task_id = None
        if isinstance(message.content, dict):
            task_id = message.content.get("task_id")
        if not task_id and isinstance(message.payload, dict):
            task_id = message.payload.get("task_id")
        if task_id and task_id in self._queues:
            await self._queues[task_id].put(message)

    def consume_event(self, task_id: str, event_type: str = "") -> Optional[AgentMessage]:
        """Lê o evento mais recente da fila da task, sem bloqueio.

        Retorna o AgentMessage ou None se a fila estiver vazia.
        Se event_type for fornecido, filtra por message_type.
        """
        queue = self._queues.get(task_id)
        if queue is None or queue.empty():
            return None
        try:
            msg = queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        if event_type and msg.message_type != event_type:
            return None
        return msg

    def consume_event_payload(self, task_id: str, event_type: str = "") -> Optional[dict]:
        """Conveniência: retorna apenas o payload dict do evento."""
        msg = self.consume_event(task_id, event_type)
        if msg is None:
            return None
        if isinstance(msg.content, dict):
            return msg.content
        return msg.payload

    # ── Histórico ────────────────────────────────────────────────────────

    def get_history(self) -> List[AgentMessage]:
        return list(self._history)


bus = AcetylcholineBus()
