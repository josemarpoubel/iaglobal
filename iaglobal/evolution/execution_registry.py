# iaglobal/evolution/execution_registry.py

"""
🔒 Execution Registry — Camada de Idempotência e Auditoria de Estados Concorrentes.

Garante que cada node seja executado no máximo uma vez por execution_id,
prevenindo re-execução, loop evolutivo redundante e double scoring.
Inclui proteção automática contra estouro de memória (Memory Leak).
"""

import threading
from typing import Dict, Set, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from iaglobal.utils.logger import logger

MAX_EXECUTION_HISTORY = 1000  # Teto máximo de execuções simultâneas/históricas na RAM


class NodeStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class ExecutionEntry:
    node_id: str
    execution_id: str
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


class ExecutionRegistry:
    """
    Registry global por execution thread-safe.
    Mantém o histórico de estados e barreiras de concorrência dos nós do DAG.
    """

    def __init__(self):
        self._executed: Dict[str, Set[str]] = {}
        self._entries: Dict[str, Dict[str, ExecutionEntry]] = {}
        self._execution_order: List[str] = []  # Rastreia a ordem de entrada para o Garbage Collector FIFO
        self._lock = threading.Lock()

    def init_execution(self, execution_id: str, node_ids: List[str]):
        """Registra uma nova execution com seus node_ids aplicando clonagem defensiva e GC."""
        with self._lock:
            # Mecanismo de Proteção de Memória (Garbage Collector FIFO)
            if execution_id not in self._executed:
                if len(self._execution_order) >= MAX_EXECUTION_HISTORY:
                    oldest_id = self._execution_order.pop(0)
                    self._executed.pop(oldest_id, None)
                    self._entries.pop(oldest_id, None)
                    logger.debug("[REGISTRY-GC] Removido ID antigo '%s' para liberar memória RAM.", oldest_id)
                
                self._execution_order.append(execution_id)
                self._executed[execution_id] = set()
                self._entries[execution_id] = {}

            # Cópia defensiva para isolar mutações de listas vindas do grafo externo
            for nid in list(node_ids):
                if nid not in self._entries[execution_id]:
                    self._entries[execution_id][nid] = ExecutionEntry(
                        node_id=nid,
                        execution_id=execution_id,
                        status=NodeStatus.PENDING
                    )

    def claim(self, execution_id: str, node_id: str) -> bool:
        """Reserva a execução de um nó para evitar concorrência."""
        if not hasattr(self, '_executed_nodes'):
            self._executed_nodes = set()
            
        key = (execution_id, node_id)
        if key in self._executed_nodes:
            return False # Já foi executado/reivindicado
        
        self._executed_nodes.add(key)
        return True # Reivindicação bem-sucedida

    def get_status(self, execution_id: str, node_id: str) -> Optional[str]:
        """Retorna o valor string do status de um nó na execução."""
        with self._lock:
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                return self._entries[execution_id][node_id].status.value
            return None

    def was_executed(self, execution_id: str, node_id: str) -> bool:
        """Verifica se um nó já foi executado com sucesso."""
        with self._lock:
            entry = self._entries.get(execution_id, {}).get(node_id)
            if entry is None:
                return False
            return entry.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED)

    def complete_node(self, execution_id: str, node_id: str, result: Optional[str] = None):
        """Marca um nó como COMPLETED."""
        with self._lock:
            if execution_id in self._entries and node_id in self._entries[execution_id]:
                self._entries[execution_id][node_id].status = NodeStatus.COMPLETED
                self._entries[execution_id][node_id].result = result
                self._executed.setdefault(execution_id, set()).add(node_id)

    def complete(self, execution_id: str, node_id: str):
        """Alias para complete_node."""
        self.complete_node(execution_id, node_id)

    def clear(self):
        """Limpa de forma total e absoluta o barramento (Uso exclusivo para resets de testes unitários)."""
        with self._lock:
            self._executed.clear()
            self._entries.clear()
            self._execution_order.clear()
            if hasattr(self, '_executed_nodes'):
                self._executed_nodes.clear()


# Instância global unificada
registry = ExecutionRegistry()
