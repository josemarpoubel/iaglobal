# iaglobal/evolution/execution_registry.py

"""
🔒 Execution Registry — camada de idempotência

Garante que cada node seja executado no máximo uma vez por execution_id,
prevenindo re-execução, loop evolutivo redundante e double scoring.
"""

import threading
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

from iaglobal.utils.logger import logger


@dataclass
class ExecutionEntry:
    node_id: str
    execution_id: str
    status: str = "PENDING"  # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    result: Optional[str] = None
    error: Optional[str] = None


class ExecutionRegistry:
    """
    Registry global por execution.

    Mantém um conjunto de node_ids já executados para cada execution_id.
    Antes de rodar um node, verifica se ele já foi executado — se sim, skip.
    Thread-safe via threading.Lock.
    """

    def __init__(self):
        self._executed: Dict[str, Set[str]] = {}
        self._entries: Dict[str, Dict[str, ExecutionEntry]] = {}
        self._lock = threading.Lock()

    # --------------------------------------------------
    # EXECUTION LIFECYCLE
    # --------------------------------------------------

    def init_execution(self, execution_id: str, node_ids: list[str]):
        """Registra uma nova execution com seus node_ids."""
        with self._lock:
            if execution_id not in self._executed:
                self._executed[execution_id] = set()
                self._entries[execution_id] = {}
            for nid in node_ids:
                if nid not in self._entries[execution_id]:
                    self._entries[execution_id][nid] = ExecutionEntry(
                        node_id=nid,
                        execution_id=execution_id,
                        status="PENDING",
                    )

    # --------------------------------------------------
    # CHECK & CLAIM (atômico)
    # --------------------------------------------------

    def was_executed(self, execution_id: str, node_id: str) -> bool:
        """Verifica se um node já foi executado nesta execution."""
        with self._lock:
            return (
                execution_id in self._executed
                and node_id in self._executed[execution_id]
            )

    def claim(self, execution_id: str, node_id: str) -> bool:
        """
        Tenta marcar um node como RUNNING.
        Retorna True se conseguiu (primeira vez), False se já estava executado.
        """
        with self._lock:
            if execution_id not in self._executed:
                self._executed[execution_id] = set()
                self._entries[execution_id] = {}

            if node_id in self._executed[execution_id]:
                logger.debug(f"⏭️ [REGISTRY] Node {node_id} já executado em {execution_id} — skipping")
                return False

            self._executed[execution_id].add(node_id)
            if node_id in self._entries.get(execution_id, {}):
                self._entries[execution_id][node_id].status = "RUNNING"
            return True

    # --------------------------------------------------
    # COMPLETE / FAIL
    # --------------------------------------------------

    def complete(self, execution_id: str, node_id: str, result: str = ""):
        """Marca um node como COMPLETED."""
        with self._lock:
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                self._entries[execution_id][node_id].status = "COMPLETED"
                self._entries[execution_id][node_id].result = result

    def fail(self, execution_id: str, node_id: str, error: str = ""):
        """Marca um node como FAILED."""
        with self._lock:
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                self._entries[execution_id][node_id].status = "FAILED"
                self._entries[execution_id][node_id].error = error

    def skip(self, execution_id: str, node_id: str):
        """Marca um node como SKIPPED (ex: sanity barrier)."""
        with self._lock:
            if execution_id not in self._executed:
                self._executed[execution_id] = set()
            self._executed[execution_id].add(node_id)
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                self._entries[execution_id][node_id].status = "SKIPPED"

    # --------------------------------------------------
    # QUERY
    # --------------------------------------------------

    def get_status(self, execution_id: str, node_id: str) -> Optional[str]:
        """Retorna o status de um node na execution."""
        with self._lock:
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                return self._entries[execution_id][node_id].status
            return None

    def get_executed_nodes(self, execution_id: str) -> Set[str]:
        """Retorna o conjunto de node_ids executados para uma execution."""
        with self._lock:
            return set(self._executed.get(execution_id, set()))

    def reset_execution(self, execution_id: str):
        """Remove todos os registros de uma execution."""
        with self._lock:
            self._executed.pop(execution_id, None)
            self._entries.pop(execution_id, None)

    def clear(self):
        """Limpa todos os registros."""
        with self._lock:
            self._executed.clear()
            self._entries.clear()


# Instância global
registry = ExecutionRegistry()
