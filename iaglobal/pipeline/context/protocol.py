# iaglobal/pipeline/context/protocol.py
"""
Protocolo base do sistema de contexto.

Contextos especializados (Mission, Runtime, History, Memory, Metrics)
→ NodeSection com conteúdo tipado
→ ContextProvider (protocol)
→ TokenBudget + TokenEstimator
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)


# ==============================================================================
# CONTEXTOS ESPECIALIZADOS (frozen, cada um com responsabilidade única)
# ==============================================================================


@dataclass(frozen=True)
class MissionContext:
    objective: str = ""
    domain: str = "unknown"
    project_type: str = "unknown"
    language: str = "python"
    complexity: str = "medium"
    architecture: str = ""
    entities: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    priorities: Tuple[str, ...] = ()
    confidence: float = 0.0
    skip_nodes: Tuple[str, ...] = ()
    required_nodes: Tuple[str, ...] = ()

    def updated(self, **kwargs) -> MissionContext:
        for k in kwargs:
            if k not in self.__dataclass_fields__:
                raise ValueError(f"MissionContext não tem campo '{k}'")
        return MissionContext(**{**self.__dict__, **kwargs})

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MissionContext:
        field_names = cls.__dataclass_fields__
        return cls(
            **{
                k: _to_tuple(v) if isinstance(v, list) else v
                for k, v in d.items()
                if k in field_names
            }
        )


@dataclass(frozen=True)
class RuntimeContext:
    graph_state: Dict[str, Any] = field(default_factory=dict)
    current_stage: str = ""
    task_id: str = ""

    @staticmethod
    def empty() -> RuntimeContext:
        return RuntimeContext()


@dataclass(frozen=True)
class HistoryContext:
    entries: Tuple[Dict[str, Any], ...] = ()

    @staticmethod
    def empty() -> HistoryContext:
        return HistoryContext()


@dataclass(frozen=True)
class MemoryContext:
    knowledge: str = ""
    stm: Tuple[Dict[str, Any], ...] = ()
    ltm: Tuple[Dict[str, Any], ...] = ()

    @staticmethod
    def empty() -> MemoryContext:
        return MemoryContext()


@dataclass(frozen=True)
class MetricsContext:
    ivm: float = 0.0
    latency_ms: float = 0.0
    score: float = 0.0
    custom: Dict[str, float] = field(default_factory=dict)

    @staticmethod
    def empty() -> MetricsContext:
        return MetricsContext()


# ==============================================================================
# EXECUTION CONTEXT (composição, não herança)
# ==============================================================================


from .memory_snapshot import MemorySnapshot
from .security_snapshot import SecuritySnapshot
from .performance_snapshot import PerformanceSnapshot


@dataclass(frozen=True)
class PipelineExecutionContext:
    mission: MissionContext = field(default_factory=MissionContext)
    runtime: RuntimeContext = field(default_factory=RuntimeContext)
    history: HistoryContext = field(default_factory=HistoryContext)
    memory: MemoryContext = field(default_factory=MemoryContext)
    metrics: MetricsContext = field(default_factory=MetricsContext)
    memory_snapshot: MemorySnapshot = field(default_factory=MemorySnapshot)
    security_snapshot: SecuritySnapshot = field(default_factory=SecuritySnapshot)
    performance_snapshot: PerformanceSnapshot = field(
        default_factory=PerformanceSnapshot
    )


# ==============================================================================
# NODE SECTION — conteúdo estruturado (AST), não texto
# ==============================================================================


@dataclass(frozen=True)
class NodeSection:
    id: str
    title: str
    content: Tuple[Any, ...] = ()
    priority: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.content or all(
            str(c).strip() == "" or c is None for c in self.content
        )


@dataclass(frozen=True)
class NodeContext:
    node_name: str = ""
    sections: Tuple[NodeSection, ...] = ()
    budget: TokenBudget = field(default_factory=lambda: TokenBudget())


# ==============================================================================
# TOKEN BUDGET — orçamento por seção em tokens
# ==============================================================================


@dataclass(frozen=True)
class TokenBudget:
    objective: int = 60
    domain: int = 15
    entities: int = 40
    constraints: int = 50
    architecture: int = 80
    technologies: int = 40
    artifacts: int = 80
    success_criteria: int = 50
    other: int = 80

    def for_section(self, section_id: str) -> int:
        return getattr(self, section_id, self.other)

    @property
    def total(self) -> int:
        return (
            self.objective
            + self.domain
            + self.entities
            + self.constraints
            + self.architecture
            + self.technologies
            + self.artifacts
            + self.success_criteria
            + self.other
        )


class TokenEstimator(Protocol):
    def estimate(self, text: str) -> int: ...


class CharTokenEstimator:
    """Fallback: 1 token ≈ 4 caracteres (estimativa conservadora)."""

    CHARS_PER_TOKEN = 4

    def estimate(self, text: str) -> int:
        return max(1, len(text) // self.CHARS_PER_TOKEN)


# ==============================================================================
# CONTEXT PROVIDER — protocolo com requires tipado
# ==============================================================================


_CONTEXT_REGISTRY: Dict[type, str] = {
    MissionContext: "mission",
    RuntimeContext: "runtime",
    HistoryContext: "history",
    MemoryContext: "memory",
    MetricsContext: "metrics",
}


@runtime_checkable
class ContextProvider(Protocol):
    requires: Tuple[type, ...] = ()

    def build(
        self,
        ctx: ExecutionContext,
        node_name: str,
        budget: Optional[TokenBudget] = None,
    ) -> NodeContext: ...


# ==============================================================================
# UTILITÁRIOS
# ==============================================================================


def _to_tuple(v: list) -> tuple:
    return tuple(v)
