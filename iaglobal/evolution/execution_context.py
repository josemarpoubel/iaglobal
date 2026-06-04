# iaglobal/evolution/execution_context.py

"""
🔒 Execution Context Imutável

Cada execução do pipeline recebe um contexto imutável que contém:
- execution_id: identificador único da execução
- graph_snapshot: snapshot do grafo no momento da execução
- memory_snapshot: snapshot da memória no momento da execução
- seed_version: versão das seeds usadas

Nada pode mutar o contexto durante a execução — isso garante
determinismo e evita efeitos colaterais entre execuções paralelas.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from copy import deepcopy


@dataclass(frozen=True)
class ExecutionContext:
    """
    Contexto imutável de execução.

    Frozen = True garante que nenhum campo pode ser alterado
    após a criação. Qualquer tentativa de mutação levanta TypeError.
    """

    execution_id: str
    graph_snapshot: Dict[str, Any] = field(default_factory=dict)
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    seed_version: str = "v1"
    task: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Garante que dicts sejam deep-copiados na criação
        if not isinstance(self.graph_snapshot, dict):
            object.__setattr__(self, "graph_snapshot", {})
        if not isinstance(self.memory_snapshot, dict):
            object.__setattr__(self, "memory_snapshot", {})
        if not isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", {})

    @classmethod
    def create(
        cls,
        execution_id: str,
        graph: Any = None,
        memory: Any = None,
        seed_version: str = "v1",
        task: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionContext":
        """
        Factory method que cria um snapshot imutável do estado atual.
        """
        graph_snapshot = deepcopy(graph) if graph else {}
        memory_snapshot = deepcopy(memory) if memory else {}
        return cls(
            execution_id=execution_id,
            graph_snapshot=graph_snapshot,
            memory_snapshot=memory_snapshot,
            seed_version=seed_version,
            task=task,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialização segura (sempre retorna cópia)."""
        return {
            "execution_id": self.execution_id,
            "graph_snapshot": deepcopy(self.graph_snapshot),
            "memory_snapshot": deepcopy(self.memory_snapshot),
            "seed_version": self.seed_version,
            "task": self.task,
            "metadata": deepcopy(self.metadata),
        }


def make_context(
    execution_id: str,
    graph: Any = None,
    memory: Any = None,
    seed_version: str = "v1",
    task: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionContext:
    """Função utilitária para criar ExecutionContext."""
    return ExecutionContext.create(
        execution_id=execution_id,
        graph=graph,
        memory=memory,
        seed_version=seed_version,
        task=task,
        metadata=metadata,
    )
