# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ColonyQueen — Rainha da Colônia: decompõe tarefas grandes em subtarefas
e distribui para worker organisms via AcetylcholineBus.
"""

import asyncio
import uuid
from typing import Optional

from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus,
    AgentMessage,
    bus,
)
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.communication.queen")


class ColonyQueen:
    """Rainha da colônia — divide tarefas grandes e orquestra workers."""

    def __init__(
        self, organism_id: str = "queen", message_bus: Optional[AcetylcholineBus] = None
    ):
        self.organism_id = organism_id
        self.bus = message_bus or bus
        self._pending: dict[str, list[dict]] = {}
        self._completed: dict[str, list[dict]] = {}
        self._results_event: dict[str, asyncio.Event] = {}

    async def decompose(self, super_task: dict) -> list[dict]:
        """Decompõe tarefa grande em subtarefas atômicas baseado no tipo."""
        task_type = super_task.get("type", "generic")
        description = super_task.get("description", "")
        subtasks = []

        if task_type == "analysis":
            subtasks = [
                {
                    "id": _uid(),
                    "type": "search",
                    "description": f"Coletar dados: {description}",
                    "parent": super_task.get("id"),
                },
                {
                    "id": _uid(),
                    "type": "code_review",
                    "description": f"Revisar código: {description}",
                    "parent": super_task.get("id"),
                },
                {
                    "id": _uid(),
                    "type": "report",
                    "description": f"Gerar relatório: {description}",
                    "parent": super_task.get("id"),
                },
            ]
        elif task_type == "development":
            subtasks = [
                {
                    "id": _uid(),
                    "type": "planner",
                    "description": f"Planejar: {description}",
                    "parent": super_task.get("id"),
                },
                {
                    "id": _uid(),
                    "type": "coder",
                    "description": f"Codificar: {description}",
                    "parent": super_task.get("id"),
                },
                {
                    "id": _uid(),
                    "type": "tester",
                    "description": f"Testar: {description}",
                    "parent": super_task.get("id"),
                },
                {
                    "id": _uid(),
                    "type": "documenter",
                    "description": f"Documentar: {description}",
                    "parent": super_task.get("id"),
                },
            ]
        else:
            subtasks.append(
                {
                    "id": _uid(),
                    "type": "generic",
                    "description": description,
                    "parent": super_task.get("id"),
                }
            )

        task_id = super_task.get("id", _uid())
        self._pending[task_id] = subtasks
        self._completed[task_id] = []
        self._results_event[task_id] = asyncio.Event()

        logger.info("[QUEEN] Decompus %s em %d subtarefas", task_id, len(subtasks))
        return subtasks

    async def assign(self, subtasks: list[dict], workers: list[str]):
        """Distribui subtarefas via task_offer nos workers disponíveis."""
        for i, subtask in enumerate(subtasks):
            worker = workers[i % len(workers)]
            msg = AgentMessage(
                sender=self.organism_id,
                recipient=worker,
                organism_id=self.organism_id,
                message_type="task_offer",
                payload={
                    "task_id": subtask["id"],
                    "type": subtask["type"],
                    "description": subtask["description"],
                    "parent": subtask.get("parent"),
                },
                priority=2,
            )
            await self.bus.emit(msg)
            logger.info("[QUEEN] task_offer %s → %s", subtask["id"], worker)

    async def collect(self, task_id: str, timeout: float = 30.0) -> list[dict]:
        """Aguarda todos os resultados das subtarefas."""
        event = self._results_event.get(task_id)
        if event:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("[QUEEN] Timeout aguardando resultados de %s", task_id)

        results = self._completed.pop(task_id, [])
        self._results_event.pop(task_id, None)
        self._pending.pop(task_id, None)
        return results

    async def on_result_share(self, message: AgentMessage):
        """Callback para receber result_share dos workers."""
        task_id = message.payload.get("task_id", "")
        parent = message.payload.get("parent", "")

        if parent in self._completed:
            self._completed[parent].append(message.payload)
            logger.info(
                "[QUEEN] result_share recebido: %s → %s (%d/%d)",
                task_id,
                parent,
                len(self._completed[parent]),
                len(self._pending.get(parent, [])),
            )

            pending = self._pending.get(parent, [])
            if len(self._completed[parent]) >= len(pending):
                event = self._results_event.get(parent)
                if event:
                    event.set()


def _uid() -> str:
    return uuid.uuid4().hex[:12]
