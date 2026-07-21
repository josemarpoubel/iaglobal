# iaglobal/memory/cognitive/__init__.py
"""Cognitive Memory Foundation — Domínio puro (sem backends)."""

from iaglobal.memory.cognitive.foundation import (
    AttentionManager,
    EpisodicMemory,
    ExternalMemory,
    MemoryChunk,
    MemoryType,
    MEMORY_TYPE_REGISTRY,
    ProceduralMemory,
    SemanticMemory,
    WorkingMemory,
)

__all__ = [
    "MemoryChunk",
    "MemoryType",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "ExternalMemory",
    "AttentionManager",
    "MEMORY_TYPE_REGISTRY",
]
