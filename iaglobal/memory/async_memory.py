# iaglobal/memory/async_memory.py
"""Async wrapper for memory operations - não bloqueia o event loop."""
import asyncio
from typing import Dict, Any, List, Optional
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.term_short import ShortTermMemory
from iaglobal.memory.memory_vector import MemoryVector
from iaglobal._paths import CORE_DB, MEMORY_SWAP_DIR
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Singletons
_ltm: Optional[LongTermMemory] = None
_stm: Optional[ShortTermMemory] = None
_memory_vector: Optional[MemoryVector] = None


def _get_ltm() -> LongTermMemory:
    global _ltm
    if _ltm is None:
        _ltm = LongTermMemory(db_path=CORE_DB)
    return _ltm


def _get_stm() -> ShortTermMemory:
    global _stm
    if _stm is None:
        _stm = ShortTermMemory(db_path=MEMORY_SWAP_DIR / "stm.db")
    return _stm


def _get_memory_vector() -> MemoryVector:
    global _memory_vector
    if _memory_vector is None:
        _memory_vector = MemoryVector()
    return _memory_vector


async def add_ltm(key: str, value: Dict[str, Any]) -> None:
    """Async wrapper para LongTermMemory.store."""
    try:
        ltm = _get_ltm()
        content = str(value.get("evaluations", []))
        metadata = {"key": key, "type": "evolution_committee"}
        await asyncio.to_thread(ltm.store, content, metadata)
        logger.info("[ASYNC_MEMORY] LTM salvo: %s", key)
    except Exception as e:
        logger.error("[ASYNC_MEMORY] Erro no LTM: %s", e)


async def add_stm(item: str, metadata: Optional[Dict] = None) -> None:
    """Async wrapper para ShortTermMemory.add."""
    try:
        stm = _get_stm()
        await asyncio.to_thread(stm.add, item, metadata)
        logger.info("[ASYNC_MEMORY] STM salvo: %s", item[:50])
    except Exception as e:
        logger.error("[ASYNC_MEMORY] Erro no STM: %s", e)


async def retrieve_ltm(query: str, top_k: int = 5) -> List[Dict]:
    """Async wrapper para LongTermMemory.retrieve."""
    try:
        ltm = _get_ltm()
        return await asyncio.to_thread(ltm.retrieve, query, top_k)
    except Exception as e:
        logger.error("[ASYNC_MEMORY] Erro retrieve LTM: %s", e)
        return []


async def get_ltm_stats() -> Dict[str, Any]:
    """Async wrapper para LongTermMemory.get_stats."""
    try:
        ltm = _get_ltm()
        return await asyncio.to_thread(ltm.get_stats)
    except Exception as e:
        logger.error("[ASYNC_MEMORY] Erro stats LTM: %s", e)
        return {}


async def add_memory_vector(text: str, mtype: str = "evolution") -> None:
    """Async wrapper para MemoryVector.add (STM implícito via embeddings)."""
    try:
        mv = _get_memory_vector()
        await asyncio.to_thread(mv.add, text, mtype)
        logger.info("[ASYNC_MEMORY] MemoryVector salvo: %s", text[:50])
    except Exception as e:
        logger.error("[ASYNC_MEMORY] Erro no MemoryVector: %s", e)