# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do SearchMemory — Fase 5 do RAG Autônomo.

Cobertura:
  - save_search() persiste no Obsidian
  - search_memory() retorna cache ou None
  - cleanup_old_searches() remove antigos
  - get_search_history() retorna histórico
  - Stats são atualizados
"""

import pytest
import asyncio
import json
import time

from iaglobal.search.search_memory import (
    SearchMemory,
    SearchRecord,
    get_memory_stats,
)


class TestSearchRecord:
    """Testes da dataclass SearchRecord."""

    def test_search_record_creation(self):
        """SearchRecord deve criar com campos obrigatórios."""
        record = SearchRecord(
            query="test query",
            query_hash="abc123",
            results=[{"url": "url1", "snippet": "content"}],
            success=True,
            timestamp=time.time(),
        )
        assert record.query == "test query"
        assert record.success is True
        assert record.usage_count == 0

    def test_search_record_to_dict(self):
        """to_dict deve serializar corretamente."""
        record = SearchRecord(
            query="test",
            query_hash="hash",
            results=[],
            success=False,
            timestamp=1234567890.0,
            agent_id="coder",
        )
        data = record.to_dict()
        assert data["query"] == "test"
        assert data["agent_id"] == "coder"
        assert data["success"] is False

    def test_search_record_from_dict(self):
        """from_dict deve desserializar corretamente."""
        data = {
            "query": "test",
            "query_hash": "hash",
            "results": [],
            "success": True,
            "timestamp": 1234567890.0,
            "agent_id": None,
            "task_hash": None,
            "usage_count": 0,
            "last_used": None,
        }
        record = SearchRecord.from_dict(data)
        assert record.query == "test"
        assert record.success is True


class TestSearchMemory:
    """Testes do SearchMemory."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reseta singleton, cache e stats da classe entre testes."""
        from iaglobal.search import search_memory

        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }
        yield
        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        """Cria diretório Obsidian temporário."""
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "search_memory"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.fixture
    def memory(self, temp_obsidian):
        """Cria SearchMemory com path temporário."""
        return SearchMemory(obsidian_path=temp_obsidian)

    @pytest.fixture
    def sample_results(self):
        """Resultados de exemplo."""
        return [
            {
                "url": "https://arxiv.org/abs/123",
                "title": "Paper Title",
                "snippet": "Abstract content",
                "_source_score": 0.92,
            },
            {
                "url": "https://github.com/user/repo",
                "title": "GitHub Repo",
                "snippet": "Code implementation",
                "_source_score": 0.85,
            },
        ]

    # ── Testes de save_search ───────────────────────────────

    @pytest.mark.asyncio
    async def test_save_search_basic(self, memory, sample_results):
        """save_search deve salvar busca com sucesso."""
        result = await memory.save_search(
            query="test query",
            results=sample_results,
            success=True,
            agent_id="coder",
        )

        assert result is True
        assert len(memory._cache) == 1

        # Verificar cache
        query_hash = memory._query_hash("test query")
        assert query_hash in memory._cache

        record = memory._cache[query_hash]
        assert record.query == "test query"
        assert record.success is True
        assert len(record.results) == 2

    @pytest.mark.asyncio
    async def test_save_search_empty_results(self, memory):
        """save_search deve retornar False se results vazios."""
        result = await memory.save_search(
            query="test",
            results=[],
            success=True,
        )

        assert result is False
        assert len(memory._cache) == 0

    @pytest.mark.asyncio
    async def test_save_search_persists_to_disk(
        self, memory, temp_obsidian, sample_results
    ):
        """save_search deve persistir no disco."""
        await memory.save_search(
            query="persistent query",
            results=sample_results,
            success=True,
        )

        # Verificar arquivo de índice
        assert memory.INDEX_FILE.exists()

        with open(memory.INDEX_FILE, "r") as f:
            index = json.load(f)

        assert len(index) == 1
        query_hash = memory._query_hash("persistent query")
        assert query_hash in index

    @pytest.mark.asyncio
    async def test_save_search_creates_md_file(
        self, memory, temp_obsidian, sample_results
    ):
        """save_search deve criar arquivo .md individual."""
        await memory.save_search(
            query="markdown query",
            results=sample_results,
            success=True,
        )

        query_hash = memory._query_hash("markdown query")
        md_file = temp_obsidian / f"{query_hash}.md"

        assert md_file.exists()

        content = md_file.read_text()
        assert "# Search: markdown query" in content
        assert "arxiv.org" in content
        assert "github.com" in content

    # ── Testes de search_memory ─────────────────────────────

    @pytest.mark.asyncio
    async def test_search_memory_hit(self, memory, sample_results):
        """search_memory deve retornar resultados se hit."""
        # Salvar primeiro
        await memory.save_search(
            query="cached query",
            results=sample_results,
            success=True,
        )

        # Buscar
        results = await memory.search_memory("cached query")

        assert results is not None
        assert len(results) == 2
        assert results[0]["url"] == "https://arxiv.org/abs/123"

    @pytest.mark.asyncio
    async def test_search_memory_miss(self, memory):
        """search_memory deve retornar None se miss."""
        results = await memory.search_memory("uncached query")

        assert results is None

    @pytest.mark.asyncio
    async def test_search_memory_updates_usage(self, memory, sample_results):
        """search_memory deve atualizar usage_count."""
        await memory.save_search(
            query="reuse query",
            results=sample_results,
            success=True,
        )

        # Buscar 3 vezes
        for _ in range(3):
            await memory.search_memory("reuse query")

        query_hash = memory._query_hash("reuse query")
        record = memory._cache[query_hash]

        assert record.usage_count == 3
        assert record.last_used is not None

    # ── Testes de get_search_history ─────────────────────────

    @pytest.mark.asyncio
    async def test_get_search_history_basic(self, memory, sample_results):
        """get_search_history deve retornar histórico."""
        # Salvar 3 buscas
        for i in range(3):
            await memory.save_search(
                query=f"query {i}",
                results=sample_results,
                success=True,
            )

        history = await memory.get_search_history()

        assert len(history) == 3
        assert all(isinstance(r, SearchRecord) for r in history)

    @pytest.mark.asyncio
    async def test_get_search_history_limit(self, memory, sample_results):
        """get_search_history deve respeitar limit."""
        # Salvar 10 buscas
        for i in range(10):
            await memory.save_search(
                query=f"query {i}",
                results=sample_results,
                success=True,
            )

        history = await memory.get_search_history(limit=5)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_search_history_sorted_by_timestamp(self, memory, sample_results):
        """get_search_history deve ordenar por timestamp (recente primeiro)."""
        # Salvar com delay
        for i in range(3):
            await memory.save_search(
                query=f"query {i}",
                results=sample_results,
                success=True,
            )
            await asyncio.sleep(0.01)  # Pequeno delay

        history = await memory.get_search_history()

        # Verificar ordem (mais recente primeiro)
        assert history[0].timestamp >= history[1].timestamp >= history[2].timestamp

    # ── Testes de cleanup_old_searches ──────────────────────

    @pytest.mark.asyncio
    async def test_cleanup_old_searches_removes_old(self, memory, sample_results):
        """cleanup_old_searches deve remover registros antigos."""
        # Salvar busca antiga (mock de timestamp)
        await memory.save_search(
            query="old query",
            results=sample_results,
            success=True,
        )

        # Modificar timestamp para 31 dias atrás
        query_hash = memory._query_hash("old query")
        memory._cache[query_hash].timestamp = time.time() - (31 * 86400)

        # Limpar (default 30 dias)
        removed = await memory.cleanup_old_searches()

        assert removed == 1
        assert query_hash not in memory._cache

    @pytest.mark.asyncio
    async def test_cleanup_old_searches_keeps_recent(self, memory, sample_results):
        """cleanup_old_searches deve manter registros recentes."""
        await memory.save_search(
            query="recent query",
            results=sample_results,
            success=True,
        )

        # Limpar (default 30 dias)
        removed = await memory.cleanup_old_searches()

        assert removed == 0
        assert len(memory._cache) == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_searches_removes_md_file(
        self, memory, temp_obsidian, sample_results
    ):
        """cleanup_old_searches deve remover arquivo .md."""
        await memory.save_search(
            query="file query",
            results=sample_results,
            success=True,
        )

        query_hash = memory._query_hash("file query")
        md_file = temp_obsidian / f"{query_hash}.md"

        assert md_file.exists()

        # Envelhecer
        memory._cache[query_hash].timestamp = time.time() - (31 * 86400)

        # Limpar
        await memory.cleanup_old_searches()

        assert not md_file.exists()

    # ── Testes de stats ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, memory):
        """Stats iniciais devem ter valores padrão."""
        stats = memory.get_stats()

        assert stats["saved"] == 0
        assert stats["loaded"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_updated(self, memory, sample_results):
        """Stats devem atualizar após operações."""
        await memory.save_search("query", sample_results, True)
        await memory.search_memory("query")  # Hit
        await memory.search_memory("other")  # Miss

        stats = memory.get_stats()

        assert stats["saved"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_clear_cache(self, memory, sample_results):
        """clear_cache deve limpar cache em memória."""
        # Salvar
        import asyncio

        asyncio.run(memory.save_search("query", sample_results, True))

        assert len(memory._cache) == 1

        # Limpar
        memory.clear_cache()

        assert len(memory._cache) == 0


class TestSearchMemoryIntegration:
    """Testes de integração."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reseta singleton, cache e stats da classe entre testes."""
        from iaglobal.search import search_memory

        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }
        yield
        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        """Cria diretório Obsidian temporário."""
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "search_memory"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.fixture
    def sample_results(self):
        """Resultados de exemplo."""
        return [
            {
                "url": "https://arxiv.org/abs/123",
                "title": "Paper Title",
                "snippet": "Abstract content",
                "_source_score": 0.92,
            },
            {
                "url": "https://github.com/user/repo",
                "title": "GitHub Repo",
                "snippet": "Code implementation",
                "_source_score": 0.85,
            },
        ]

    @pytest.mark.asyncio
    async def test_save_search_wrapper(self, temp_obsidian, sample_results):
        """save_search wrapper deve funcionar."""
        # Criar memória temporária
        mem = SearchMemory(obsidian_path=temp_obsidian)

        result = await mem.save_search(
            query="wrapper query",
            results=sample_results,
            success=True,
            agent_id="tester",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_search_memory_wrapper(self, temp_obsidian, sample_results):
        """search_memory wrapper deve funcionar."""
        mem = SearchMemory(obsidian_path=temp_obsidian)

        await mem.save_search("cached", sample_results, True)
        results = await mem.search_memory("cached")

        assert results is not None
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_memory_stats_wrapper(self):
        """get_memory_stats wrapper deve funcionar."""
        stats = get_memory_stats()

        assert "saved" in stats
        assert "hits" in stats


class TestSearchMemoryE2E:
    """Testes end-to-end."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reseta singleton, cache e stats da classe entre testes."""
        from iaglobal.search import search_memory

        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }
        yield
        search_memory._memory = None
        search_memory.SearchMemory._cache = {}
        search_memory.SearchMemory._index = {}
        search_memory.SearchMemory._stats = {
            "saved": 0,
            "loaded": 0,
            "hits": 0,
            "misses": 0,
            "cleaned": 0,
        }

    @pytest.fixture
    def temp_obsidian(self, tmp_path):
        """Cria diretório Obsidian temporário."""
        obsidian_path = tmp_path / "obsidian" / "04_Synapses" / "search_memory"
        obsidian_path.mkdir(parents=True, exist_ok=True)
        return obsidian_path

    @pytest.fixture
    def sample_results(self):
        """Resultados de exemplo."""
        return [
            {
                "url": "https://arxiv.org/abs/123",
                "title": "Paper Title",
                "snippet": "Abstract content",
                "_source_score": 0.92,
            },
            {
                "url": "https://github.com/user/repo",
                "title": "GitHub Repo",
                "snippet": "Code implementation",
                "_source_score": 0.85,
            },
        ]

    @pytest.mark.asyncio
    async def test_full_search_lifecycle(self, temp_obsidian):
        """Ciclo completo: save → search → cleanup."""
        memory = SearchMemory(obsidian_path=temp_obsidian)

        results = [
            {"url": "url1", "snippet": "content 1", "_source_score": 0.9},
            {"url": "url2", "snippet": "content 2", "_source_score": 0.8},
        ]

        # 1. Salvar busca
        await memory.save_search(
            query="lifecycle query",
            results=results,
            success=True,
            agent_id="coder",
            task_hash="task123",
        )

        # 2. Buscar (hit)
        found = await memory.search_memory("lifecycle query")
        assert found is not None
        assert len(found) == 2

        # 3. Verificar histórico
        history = await memory.get_search_history()
        assert len(history) == 1
        assert history[0].query == "lifecycle query"
        assert history[0].usage_count == 1

        # 4. Verificar stats
        stats = memory.get_stats()
        assert stats["saved"] == 1
        assert stats["hits"] == 1

        # 5. Cleanup (não deve remover, é recente)
        removed = await memory.cleanup_old_searches()
        assert removed == 0
        assert len(memory._cache) == 1

    @pytest.mark.asyncio
    async def test_multiple_queries_and_reuse(self, temp_obsidian):
        """Múltiplas queries e reutilização."""
        memory = SearchMemory(obsidian_path=temp_obsidian)

        results = [
            {"url": "url1", "snippet": "content"},
        ]

        # Salvar 5 queries diferentes
        for i in range(5):
            await memory.save_search(
                query=f"query {i}",
                results=results,
                success=True,
            )

        # Reutilizar query 2 três vezes
        for _ in range(3):
            await memory.search_memory("query 2")

        # Verificar usage_count
        query_hash = memory._query_hash("query 2")
        record = memory._cache[query_hash]
        assert record.usage_count == 3

        # Verificar histórico (ordenado)
        history = await memory.get_search_history(limit=3)
        assert len(history) == 3
