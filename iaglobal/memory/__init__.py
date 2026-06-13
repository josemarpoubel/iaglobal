"""Memory module for caching, storage, vector, and term memory operations."""

from .cache import Cache
from .memory import Memory
from .memory_storage import MemoryStorage
from .memory_vector import MemoryVector
from .persistence import Persistence
from .term_short import ShortTermMemory
from .term_long import LongTermMemory
from .consolidation import ConsolidationEngine
from .ranking import CognitiveRanking
from .fusion_engine import (
    FusionEngine,
    WebCacheInteligente,
    AntiRedundanciaGlobal,
    FakeNoiseDetector,
    KnowledgeGraph,
    AtualizacaoIncremental,
)
from .semantic_cache import SemanticCache

__all__ = [
    'Cache', 'Memory', 'MemoryStorage', 'MemoryVector',
    'Persistence', 'ShortTermMemory', 'LongTermMemory',
    'ConsolidationEngine', 'CognitiveRanking',
    'FusionEngine', 'WebCacheInteligente', 'AntiRedundanciaGlobal',
    'FakeNoiseDetector', 'KnowledgeGraph', 'AtualizacaoIncremental',
    'SemanticCache',
]
