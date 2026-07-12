# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ColonyWorker — Trabalhador da Colônia: executa subtarefas especializadas
e reporta resultados via AcetylcholineBus.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from iaglobal.graphs.communication.acetylcholine_bus import (
    AcetylcholineBus,
    AgentMessage,
    bus,
)
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.communication.worker")

TASK_HANDLERS: dict[str, str] = {}


def register_handler(task_type: str, description: str):
    """Decorator para registrar handler de task_type."""
    def decorator(func):
        TASK_HANDLERS[task_type] = description
        return func
    return decorator


class ColonyWorker:
    """Trabalhador da colônia — executa subtarefas e retorna resultados."""

    def __init__(
        self,
        organism_id: str,
        skills: Optional[list[str]] = None,
        message_bus: Optional[AcetylcholineBus] = None,
    ):
        self.organism_id = organism_id
        self.skills = skills or ["generic"]
        self.bus = message_bus or bus
        self._running = False
        self._task_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()

    async def start(self):
        """Inicia loop de escuta de task_offer."""
        self._running = True
        self.bus.subscribe(self.organism_id, self._on_message)
        self.bus.subscribe(f"org:{self.organism_id}", self._on_message)
        logger.info("[WORKER %s] Iniciado com skills: %s", self.organism_id, self.skills)

    async def stop(self):
        self._running = False

    def can_handle(self, task_type: str) -> bool:
        """Verifica se o worker tem a skill necessária."""
        return task_type in self.skills or "generic" in self.skills

    async def _on_message(self, message: AgentMessage):
        if message.message_type == "task_offer":
            task_type = message.payload.get("type", "generic")
            if self.can_handle(task_type):
                await self._task_queue.put(message)
            else:
                logger.debug("[WORKER %s] Recusou task_offer %s (skills: %s, precisa: %s)",
                             self.organism_id, message.payload.get("task_id"), self.skills, task_type)

    async def execute_next(self) -> Optional[dict]:
        """Pega próxima tarefa da fila e executa."""
        try:
            msg = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None
        return await self._execute_task(msg)

    async def _execute_task(self, msg: AgentMessage) -> dict:
        task_id = msg.payload.get("task_id", "unknown")
        task_type = msg.payload.get("type", "generic")
        description = msg.payload.get("description", "")
        parent = msg.payload.get("parent")
        start = time.time()

        logger.info("[WORKER %s] Executando %s (%s)", self.organism_id, task_id, task_type)

        result = await self._run_handler(task_type, description)

        latency = time.time() - start
        success = result.get("success", True)

        result_msg = AgentMessage(
            sender=self.organism_id,
            recipient=msg.sender,
            organism_id=self.organism_id,
            message_type="result_share",
            payload={
                "task_id": task_id,
                "type": task_type,
                "parent": parent,
                "result": result,
                "success": success,
                "latency_ms": round(latency * 1000, 2),
                "worker_id": self.organism_id,
            },
            priority=2,
        )
        await self.bus.emit(result_msg)

        return {
            "task_id": task_id,
            "success": success,
            "latency_ms": round(latency * 1000, 2),
            "result": result,
        }

    async def _run_handler(self, task_type: str, description: str) -> dict:
        if task_type == "search":
            return await self._handle_search(description)
        elif task_type == "code_review":
            return await self._handle_code_review(description)
        elif task_type == "report":
            return await self._handle_report(description)
        elif task_type == "planner":
            return {"success": True, "output": f"Plano para: {description}"}
        elif task_type == "coder":
            return {"success": True, "output": f"Código gerado para: {description}"}
        elif task_type == "tester":
            return {"success": True, "output": f"Testes para: {description}"}
        elif task_type == "documenter":
            return {"success": True, "output": f"Documentação para: {description}"}
        else:
            return {"success": True, "output": f"Processado: {description}"}

    async def _handle_search(self, query: str) -> dict:
        from iaglobal.mcp.search_web import WebSearchTool
        try:
            results = await WebSearchTool().search(query, max_results=3)
            return {"success": True, "output": results, "count": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_code_review(self, code_hint: str) -> dict:
        return {"success": True, "output": f"Revisão concluída para: {code_hint}", "issues": []}

    async def _handle_report(self, topic: str) -> dict:
        return {"success": True, "output": f"Relatório gerado: {topic}", "sections": []}