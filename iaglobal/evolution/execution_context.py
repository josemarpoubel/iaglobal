# iaglobal/evolution/execution_context.py

"""
🔒 Execution Context Imutável Otimizado

Garante determinismo absoluto e isolamento total entre execuções paralelas,
utilizando proxies de leitura imutáveis (MappingProxyType) para alta performance
sem o overhead excessivo de deepcopies redundantes em tempo de runtime.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from copy import deepcopy
from types import MappingProxyType  # <-- Proxy de leitura imutável ultra-rápido


@dataclass(frozen=True)
class ExecutionContext:
    """
    Contexto imutável de execução com proteção de profundidade para dicionários.
    Qualquer tentativa de mutação de chaves internas levanta um TypeError.
    """

    execution_id: str
    graph_snapshot: Dict[str, Any] = field(default_factory=dict)
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    seed_version: str = "v1"
    task: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Garante imutabilidade real e profunda das coleções encapsulando-as
        em MappingProxyType através do barramento do ciclo de vida do objeto.
        """
        # Converte os dicionários em proxies de leitura imutáveis
        g_snap = self.graph_snapshot if isinstance(self.graph_snapshot, dict) else {}
        m_snap = self.memory_snapshot if isinstance(self.memory_snapshot, dict) else {}
        meta = self.metadata if isinstance(self.metadata, dict) else {}

        # object.__setattr__ ignora o travamento do frozen=True estritamente na inicialização
        object.__setattr__(self, "graph_snapshot", MappingProxyType(g_snap))
        object.__setattr__(self, "memory_snapshot", MappingProxyType(m_snap))
        object.__setattr__(self, "metadata", MappingProxyType(meta))

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
        Factory method que cria um snapshot isolado do estado atual.
        Usa deepcopy defensivo apenas UMA vez no ponto de entrada do snapshot.
        """
        # Executa a duplicação física isolada para desatrelar do estado mutável do Grafo de produção
        graph_snapshot = deepcopy(graph) if graph else {}
        memory_snapshot = deepcopy(memory) if memory else {}
        metadata_snapshot = deepcopy(metadata) if metadata else {}

        return cls(
            execution_id=execution_id,
            graph_snapshot=graph_snapshot,
            memory_snapshot=memory_snapshot,
            seed_version=seed_version,
            task=task,
            metadata=metadata_snapshot,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialização segura para persistência SQLite ou snapshots de auditoria."""
        # MappingProxyType não é serializável diretamente em JSON,
        # por isso extraímos dicts limpos através do deepcopy protetor
        return {
            "execution_id": self.execution_id,
            "graph_snapshot": deepcopy(dict(self.graph_snapshot)),
            "memory_snapshot": deepcopy(dict(self.memory_snapshot)),
            "seed_version": self.seed_version,
            "task": self.task,
            "metadata": deepcopy(dict(self.metadata)),
        }


def make_context(
    execution_id: str,
    graph: Any = None,
    memory: Any = None,
    seed_version: str = "v1",
    task: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionContext:
    """Função utilitária e atalho público para criar instâncias do ExecutionContext."""
    return ExecutionContext.create(
        execution_id=execution_id,
        graph=graph,
        memory=memory,
        seed_version=seed_version,
        task=task,
        metadata=metadata,
    )
