# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SearchMemory — Persiste buscas bem-sucedidas no Obsidian.

Funcionalidades:
1. save_search(query, results, success) → Salva busca no Obsidian
2. search_memory(query) → Busca no Obsidian antes de buscar na web
3. get_search_history() → Histórico de buscas
4. cleanup_old_searches(max_age_days) → Limpeza de buscas antigas

Integra com:
- SearchMiddleware (cache persistente entre sessões)
- ObsidianVault (escrita em 04_Synapses/)
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.search_memory")


@dataclass
class SearchRecord:
    """Registro de uma busca persistida."""
    query: str
    query_hash: str
    results: List[dict]  # Snippets salvos
    success: bool  # Se a busca ajudou
    timestamp: float
    agent_id: Optional[str] = None
    task_hash: Optional[str] = None
    usage_count: int = 0  # Quantas vezes foi reutilizada
    last_used: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SearchRecord":
        return cls(**data)


class SearchMemory:
    """Persiste buscas bem-sucedidas no Obsidian."""

    # Path do Obsidian
    OBSIDIAN_PATH = Path("obsidian/04_Synapses/search_memory")
    
    # Arquivo de índice (JSON)
    INDEX_FILE = OBSIDIAN_PATH / "search_index.json"
    
    # TTL padrão (30 dias)
    DEFAULT_TTL_DAYS = 30
    
    # Cache em memória
    _cache: Dict[str, SearchRecord] = {}
    _index: Dict[str, dict] = {}
    
    # Stats
    _stats = {
        "saved": 0,
        "loaded": 0,
        "hits": 0,
        "misses": 0,
        "cleaned": 0,
    }

    def __init__(self, obsidian_path: Optional[Path] = None):
        self.obsidian_path = obsidian_path or self.OBSIDIAN_PATH
        self.INDEX_FILE = self.obsidian_path / "search_index.json"  # Path da instância
        self._ensure_directory()
        self._load_index()

    def _ensure_directory(self):
        """Garante que diretório existe."""
        self.obsidian_path.mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """Carrega índice do disco."""
        if not self.INDEX_FILE.exists():
            logger.debug("[SEARCH_MEMORY] Índice não existe, criando vazio")
            self._save_index()
            return

        try:
            with open(self.INDEX_FILE, "r", encoding="utf-8") as f:
                self._index = json.load(f)
            
            # Carregar cache em memória
            self._cache.clear()
            for query_hash, record_data in self._index.items():
                self._cache[query_hash] = SearchRecord.from_dict(record_data)
            
            logger.info("[SEARCH_MEMORY] Carregadas %d buscas do Obsidian", len(self._cache))
            self._stats["loaded"] = len(self._cache)
            
        except Exception as e:
            logger.error("[SEARCH_MEMORY] Erro ao carregar índice: %s", e)
            self._index = {}
            self._cache = {}

    def _save_index(self):
        """Salva índice no disco."""
        try:
            # Atualizar índice do cache
            self._index = {
                query_hash: record.to_dict()
                for query_hash, record in self._cache.items()
            }
            
            # Salvar JSON (usar path absoluto)
            with open(str(self.INDEX_FILE), "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2, ensure_ascii=False)
            
            logger.debug("[SEARCH_MEMORY] Índice salvo (%d registros)", len(self._cache))
            
        except Exception as e:
            logger.error("[SEARCH_MEMORY] Erro ao salvar índice: %s", e)

    def _query_hash(self, query: str) -> str:
        """Gera hash único para query."""
        return hashlib.sha3_512(query.encode()).hexdigest()[:32]

    async def save_search(
        self,
        query: str,
        results: List[dict],
        success: bool,
        agent_id: Optional[str] = None,
        task_hash: Optional[str] = None,
    ) -> bool:
        """
        Salva busca no Obsidian.

        Args:
            query: Query original
            results: Snippets retornados
            success: Se a busca ajudou (feedback)
            agent_id: Agente que fez a busca
            task_hash: Hash da tarefa

        Returns:
            True se salvou com sucesso
        """
        if not results:
            return False  # Não salvar buscas vazias

        query_hash = self._query_hash(query)
        
        # Criar registro
        record = SearchRecord(
            query=query,
            query_hash=query_hash,
            results=results,
            success=success,
            timestamp=time.time(),
            agent_id=agent_id,
            task_hash=task_hash,
            usage_count=0,
            last_used=None,
        )

        # Salvar no cache
        self._cache[query_hash] = record
        
        # Salvar no disco (async)
        await asyncio.to_thread(self._save_index)
        
        # Salvar arquivo individual (opcional, para debugging)
        await self._save_individual_record(record)

        self._stats["saved"] += 1
        
        logger.info(
            "[SEARCH_MEMORY] Salvou: %s (success=%s, results=%d)",
            query[:50], success, len(results)
        )

        return True

    async def _save_individual_record(self, record: SearchRecord):
        """Salva registro individual em arquivo MD."""
        try:
            filename = f"{record.query_hash}.md"
            filepath = self.obsidian_path / filename
            
            content = self._format_record_md(record)
            
            await asyncio.to_thread(self._write_file, filepath, content)
            
        except Exception as e:
            logger.debug("[SEARCH_MEMORY] Erro ao salvar arquivo individual: %s", e)

    def _write_file(self, filepath: Path, content: str):
        """Escreve arquivo (thread-safe)."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def _format_record_md(self, record: SearchRecord) -> str:
        """Formata registro como Markdown."""
        lines = [
            f"# Search: {record.query}",
            "",
            f"**Hash:** `{record.query_hash}`",
            f"**Data:** {datetime.fromtimestamp(record.timestamp, tz=timezone.utc).isoformat()}",
            f"**Sucesso:** {'Sim' if record.success else 'Não'}",
            f"**Agente:** {record.agent_id or 'N/A'}",
            f"**Reutilizações:** {record.usage_count}",
            "",
            "## Resultados",
            "",
        ]
        
        for i, result in enumerate(record.results, 1):
            url = result.get("url", "N/A")
            title = result.get("title", "Sem título")
            snippet = result.get("snippet", "Sem conteúdo")
            score = result.get("_source_score", result.get("score"))
            
            score_str = f" (score={score:.2f})" if score else ""
            lines.append(f"### {i}. {title}{score_str}")
            lines.append(f"**URL:** {url}")
            lines.append(f"**Conteúdo:** {snippet}")
            lines.append("")
        
        lines.append("---")
        lines.append(f"*Persistido por iaglobal.SearchMemory*")
        
        return "\n".join(lines)

    async def search_memory(self, query: str) -> Optional[List[dict]]:
        """
        Busca no Obsidian antes de buscar na web.

        Args:
            query: Query original

        Returns:
            Lista de snippets se encontrado, None se miss
        """
        query_hash = self._query_hash(query)
        
        # Check cache
        if query_hash in self._cache:
            record = self._cache[query_hash]
            
            # Atualizar uso
            record.usage_count += 1
            record.last_used = time.time()
            
            # Salvar atualização
            await asyncio.to_thread(self._save_index)
            
            self._stats["hits"] += 1
            
            logger.debug(
                "[SEARCH_MEMORY] Hit: %s (usage_count=%d)",
                query[:50], record.usage_count
            )
            
            return record.results
        
        self._stats["misses"] += 1
        return None

    async def get_search_history(self, limit: int = 50) -> List[SearchRecord]:
        """
        Retorna histórico de buscas.

        Args:
            limit: Máximo de registros

        Returns:
            Lista de SearchRecord (ordenados por timestamp, mais recente primeiro)
        """
        records = sorted(
            self._cache.values(),
            key=lambda r: r.timestamp,
            reverse=True,
        )
        return records[:limit]

    async def cleanup_old_searches(self, max_age_days: Optional[int] = None) -> int:
        """
        Limpa buscas antigas.

        Args:
            max_age_days: Idade máxima em dias (default: 30)

        Returns:
            Número de registros removidos
        """
        max_age = max_age_days or self.DEFAULT_TTL_DAYS
        cutoff = time.time() - (max_age * 86400)  # segundos
        
        to_remove = []
        for query_hash, record in self._cache.items():
            if record.timestamp < cutoff:
                to_remove.append(query_hash)

        # Remover
        for query_hash in to_remove:
            del self._cache[query_hash]
            
            # Remover arquivo individual
            try:
                filepath = self.obsidian_path / f"{query_hash}.md"
                if filepath.exists():
                    filepath.unlink()
            except Exception:
                pass

        # Salvar índice atualizado
        await asyncio.to_thread(self._save_index)

        removed = len(to_remove)
        self._stats["cleaned"] += removed
        
        logger.info(
            "[SEARCH_MEMORY] Limpeza: %d registros removidos (> %d dias)",
            removed, max_age
        )

        return removed

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso."""
        return self._stats.copy()
    
    def clear_cache(self):
        """Limpa cache em memória (não remove do disco)."""
        self._cache.clear()
        logger.debug("[SEARCH_MEMORY] Cache em memória limpo")


# Singleton global
_memory: Optional[SearchMemory] = None


def get_search_memory(obsidian_path: Optional[Path] = None) -> SearchMemory:
    """Retorna singleton do SearchMemory."""
    global _memory
    if _memory is None:
        _memory = SearchMemory(obsidian_path=obsidian_path)
    return _memory


# Funções utilitárias
async def save_search(
    query: str,
    results: List[dict],
    success: bool,
    agent_id: Optional[str] = None,
    task_hash: Optional[str] = None,
) -> bool:
    """Wrapper para SearchMemory.save_search()."""
    return await get_search_memory().save_search(
        query, results, success, agent_id, task_hash
    )


async def search_memory(query: str) -> Optional[List[dict]]:
    """Wrapper para SearchMemory.search_memory()."""
    return await get_search_memory().search_memory(query)


async def get_search_history(limit: int = 50) -> List[SearchRecord]:
    """Wrapper para SearchMemory.get_search_history()."""
    return await get_search_memory().get_search_history(limit)


async def cleanup_old_searches(max_age_days: Optional[int] = None) -> int:
    """Wrapper para SearchMemory.cleanup_old_searches()."""
    return await get_search_memory().cleanup_old_searches(max_age_days)


def get_memory_stats() -> dict:
    """Wrapper para SearchMemory.get_stats()."""
    return get_search_memory().get_stats()