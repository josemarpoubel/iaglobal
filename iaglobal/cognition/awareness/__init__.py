# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Awareness Cache v3.2 — Camada de Consciência de Execução

Exportações públicas do módulo. Apenas AwarenessCache é a fachada pública.
Engines são importados diretamente para testes e mockagem.
"""

from .models import (
    AgentActivity,
    NodeDomain,
    NodeStatus,
    CausalChain,
    DomainSnapshot,
    EpisodicMemory,
    ConfidenceTrace,
    ArtifactConfidence,
    ConfidenceSnapshot,
    AwarenessExecutionContext,
    compute_confidence,
    effective_confidence,
)
from .awareness_cache import AwarenessCache
from .awareness_persistence import AwarenessPersistence
from .awareness_schema import (
    init_schema,
    serialize_metadata,
    deserialize_metadata,
    serialize_json,
    deserialize_json,
)
from .time_provider import ClockProvider, SystemClock, FakeClock
from .storage_backend import PersistenceBackend, SQLiteBackend
from .storage_repository import StorageRepository
from .awareness_context import AwarenessContext
from .confidence_engine import ConfidenceEngine
from .history_engine import HistoryEngine
from .query_engine import QueryEngine
from .causal_engine import CausalEngine
from .episodic_engine import EpisodicEngine

__all__ = [
    # Models v1
    "AgentActivity",
    # Models v2 - Causal Awareness
    "NodeDomain",
    "NodeStatus",
    "CausalChain",
    "DomainSnapshot",
    # Models v2 - Episodic Memory
    "EpisodicMemory",
    # Models v3.1 - Epistemologia Operacional
    "ConfidenceTrace",
    "ArtifactConfidence",
    "ConfidenceSnapshot",
    "AwarenessExecutionContext",
    "compute_confidence",
    "effective_confidence",
    # Core (fachada pública)
    "AwarenessCache",
    "AwarenessPersistence",
    # Time provider
    "ClockProvider",
    "SystemClock",
    "FakeClock",
    # Persistence
    "PersistenceBackend",
    "SQLiteBackend",
    "StorageRepository",
    # Context
    "AwarenessContext",
    # Engines (opcionais — para testes/mock)
    "ConfidenceEngine",
    "HistoryEngine",
    "QueryEngine",
    "CausalEngine",
    "EpisodicEngine",
    # Schema helpers
    "init_schema",
    "serialize_metadata",
    "deserialize_metadata",
    "serialize_json",
    "deserialize_json",
]

__version__ = "3.2.0"
