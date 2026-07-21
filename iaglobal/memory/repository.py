# iaglobal/memory/repository.py
"""
MemoryRepository — Contrato de persistência para memórias cognitivas.

Este módulo define a interface de INFRAESTRUTURA para acesso a memórias.
É uma camada ACIMA de backends concretos (SQLite, Obsidian, Qdrant, Redis).

Diferente de MemoryBackend (que era uma abstração muito baixa), o Repository
é uma interface rica que opera com conceitos de domínio (MemoryChunk, MemoryType).

Backends concretos implementam este protocolo:
    - SQLiteMemoryRepository    → SQLite para Working/Episodic
    - ObsidianMemoryRepository  → Vault Obsidian para Semantic
    - VectorMemoryRepository    → Qdrant/Chroma para Semantic
    - RedisMemoryRepository     → Redis para Working
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from iaglobal.memory.cognitive.foundation import MemoryChunk, MemoryType


# ============================================================
# Contratos de repositório
# ============================================================


class MemoryReader(Protocol):
    """Contrato para leitura de memórias."""

    async def read(self, chunk_id: str) -> Optional[MemoryChunk]:
        """Lê uma memória por ID."""
        ...

    async def read_all(
        self, memory_type: Optional[MemoryType] = None
    ) -> List[MemoryChunk]:
        """Lê todas as memórias, opcionalmente filtradas por tipo."""
        ...

    async def read_by_context(self, context: Dict[str, Any]) -> List[MemoryChunk]:
        """Filtra memórias por campos do contexto."""
        ...


class MemoryWriter(Protocol):
    """Contrato para escrita de memórias."""

    async def write(self, chunk: MemoryChunk) -> str:
        """
        Escreve uma memória e retorna o ID atribuído.

        Returns:
            ID único da memória armazenada
        """
        ...

    async def write_batch(self, chunks: List[MemoryChunk]) -> List[str]:
        """Escreve múltiplas memórias em lote."""
        ...

    async def delete(self, chunk_id: str) -> bool:
        """Remove uma memória por ID."""
        ...


class MemorySearcher(Protocol):
    """Contrato para busca semântica ou fuzzy."""

    async def search(
        self,
        query: str,
        *,
        memory_type: Optional[MemoryType] = None,
        agent_id: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[MemoryChunk]:
        """
        Busca memórias relevantes para uma query.

        Args:
            query: Texto de busca
            memory_type: Filtro opcional por tipo cognitivo
            agent_id: Filtro opcional por agente
            limit: Máximo de resultados
            min_confidence: Confiança mínima (0.0 a 1.0)

        Returns:
            Lista de MemoryChunks ordenados por relevância
        """
        ...


class MemoryRepository(MemoryReader, MemoryWriter, MemorySearcher, Protocol):
    """
    Interface completa de repositório de memórias.

    Combina leitura, escrita e busca. Substitui MemoryBackend como
    abstração oficial para acesso a memórias.

    Backends concretos implementam esta interface:
        - SQLiteMemoryRepository    → SQLite (STM/LTM)
        - ObsidianMemoryRepository  → Vault Obsidian
        - VectorMemoryRepository    → Qdrant/Chroma (semantic search)
        - RedisMemoryRepository     → Redis (cache/working)

    Propriedades:
        repository_type: Nome do tipo de repositório
        is_read_only: True se não suporta escrita
        supported_types: Tipos de memória suportados
    """

    repository_type: str
    is_read_only: bool = False
    supported_types: List[MemoryType] = None
