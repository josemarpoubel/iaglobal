"""Testes de integracao do SemanticCache.

Testa:
1. set/get basico
2. Cache miss (query diferente)
3. Near-miss semantico (query similar)
4. Clear (RAM + SQLite)
5. Estatisticas (get_stats)
6. TTL/expiry
7. Persistencia L2 (re-criar instancia)
8. Penalizacao de queries longas (normalizacao)
"""
import os
import sys
import time
import json
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.memory.semantic_cache import SemanticCache


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_sem_cache.db")


@pytest.fixture
def cache(tmp_db: str) -> SemanticCache:
    c = SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=None)
    c.clear()
    return c


class TestSemanticCache:

    def test_set_and_get(self, cache: SemanticCache):
        cache.set("qual e a capital do brasil", "Brasilia")
        result = cache.get("qual e a capital do brasil")
        assert result == "Brasilia"

    def test_cache_miss(self, cache: SemanticCache):
        cache.set("qual e a capital do brasil", "Brasilia")
        result = cache.get("como fazer um bolo de chocolate")
        assert result is None

    def test_near_miss_different_phrasing(self, cache: SemanticCache):
        cache.set("capital do brasil", "Brasilia")
        result = cache.get("qual e a capital do brasil")
        assert result is not None, "near-miss semantico deveria retornar hit"

    def test_clear(self, cache: SemanticCache):
        cache.set("pergunta1", "resposta1")
        cache.set("pergunta2", "resposta2")
        assert cache.get("pergunta1") is not None
        cache.clear()
        assert cache.get("pergunta1") is None
        assert cache.get("pergunta2") is None
        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["ram_entries"] == 0

    def test_get_stats(self, cache: SemanticCache):
        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert "entries" in stats
        assert "ram_entries" in stats
        assert "threshold" in stats
        assert stats["entries"] == 0

        cache.set("teste", "resposta")
        stats = cache.get_stats()
        assert stats["entries"] == 1

    def test_ttl_expiry(self, tmp_db: str):
        cache = SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=1)
        cache.set("pergunta rapida", "resposta rapida")
        assert cache.get("pergunta rapida") is not None
        time.sleep(1.5)
        assert cache.get("pergunta rapida") is None
        cache.clear()

    def test_l2_persistence(self, tmp_db: str):
        c1 = SemanticCache(db_path=tmp_db, threshold=0.85)
        c1.set("persistir isso", "valor persistido")
        assert c1.get("persistir isso") == "valor persistido"
        del c1

        c2 = SemanticCache(db_path=tmp_db, threshold=0.85)
        result = c2.get("persistir isso")
        assert result == "valor persistido"
        c2.clear()

    def test_ram_and_l2_consistency(self, tmp_db: str):
        cache = SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=None)
        cache.set("qual e a formula da agua", "H2O")

        hit1 = cache.get("qual e a formula da agua")
        assert hit1 == "H2O"

        cache._ram.clear()
        cache._ram_embeddings.clear()

        hit2 = cache.get("qual e a formula da agua")
        assert hit2 == "H2O", "L2 fallback deveria retornar o mesmo valor"

        cache.clear()

    def test_normalized_scores_within_range(self, cache: SemanticCache):
        """Verifica que apos normalizacao os scores ficam entre -1 e 1."""
        cache.set("texto curto", "A")
        cache.set("texto muito maior para testar se a normalizacao funciona corretamente", "B")

        qvec = cache._embed("outro texto qualquer")
        assert all(-1.0 <= x <= 1.0 for x in qvec), "embedding normalizado deve ter valores entre -1 e 1"

        cache.clear()

    def test_cosine_similarity_short_vs_long(self, cache: SemanticCache):
        """Query curta vs longa similares devem produzir hits."""
        cache.set("python programming language", "versatil")

        hit_short = cache.get("python")
        hit_long = cache.get("python is a high level programming language")

        assert hit_short is not None, "query curta similar deve dar hit"
        assert hit_long is not None, "query longa similar deve dar hit"
        assert hit_short == hit_long, "ambas devem retornar o mesmo valor"
        cache.clear()

    def test_update_access_increments_count(self, tmp_db: str):
        import sqlite3
        cache = SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=None)
        cache.set("increment test", "value")
        cache.get("increment test")

        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT access_count FROM semantic_cache WHERE query_text = ?",
            ("increment test",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] >= 2, "access_count deve ser incrementado apos get()"
        cache.clear()

    def test_prune_old_embeddings(self, tmp_db: str):
        cache = SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=None)
        cache.set("keep me", "keep")
        cache.set("prune me", "prune")

        result = cache.prune_old_embeddings(max_age_days=0)
        assert isinstance(result, dict)
        cache.clear()


@pytest.fixture
def cache_with_helper(tmp_db: str) -> SemanticCache:
    return SemanticCache(db_path=tmp_db, threshold=0.85, ttl_seconds=None)
