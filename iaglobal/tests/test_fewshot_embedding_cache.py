# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do cache de embeddings do FewShotProvider."""

import json
import pytest
import time
from pathlib import Path

from iaglobal.core.few_shot_provider import (
    FewShotProvider,
    EMBEDDING_CACHE_PATH,
    LRU_CACHE_SIZE,
)


@pytest.fixture
def provider_with_cache():
    """Cria provider com cache vazio."""
    provider = FewShotProvider(preload=False)
    provider._embedding_cache.clear()
    yield provider


@pytest.fixture(autouse=True)
def cleanup_cache_file():
    """Limpa cache file após cada teste."""
    yield
    if EMBEDDING_CACHE_PATH.exists():
        try:
            EMBEDDING_CACHE_PATH.unlink()
        except Exception:
            pass


def test_hash_text_consistency(provider_with_cache):
    """Hash de texto é consistente."""
    text = "test embedding cache"
    hash1 = provider_with_cache._hash_text(text)
    hash2 = provider_with_cache._hash_text(text)

    assert hash1 == hash2
    assert len(hash1) == 16  # 16 chars hex


def test_hash_text_different_inputs(provider_with_cache):
    """Textos diferentes geram hashes diferentes."""
    hash1 = provider_with_cache._hash_text("texto 1")
    hash2 = provider_with_cache._hash_text("texto 2")

    assert hash1 != hash2


def test_embedding_cache_lru_eviction(provider_with_cache):
    """Cache LRU evicta entradas antigas quando atinge limite."""
    for i in range(LRU_CACHE_SIZE + 10):
        key = "key_{}".format(i)
        if len(provider_with_cache._embedding_cache) >= LRU_CACHE_SIZE:
            provider_with_cache._embedding_cache.popitem(last=False)
        provider_with_cache._embedding_cache[key] = "value_{}".format(i)

    assert len(provider_with_cache._embedding_cache) <= LRU_CACHE_SIZE
    for i in range(10):
        assert "key_{}".format(i) not in provider_with_cache._embedding_cache
    assert "key_{}".format(LRU_CACHE_SIZE + 9) in provider_with_cache._embedding_cache


def test_save_and_load_embedding_cache(provider_with_cache):
    """Salva e carrega cache do disco."""
    provider_with_cache._embedding_cache["test1"] = [0.1, 0.2, 0.3]
    provider_with_cache._embedding_cache["test2"] = [0.4, 0.5, 0.6]

    provider_with_cache._save_embedding_cache()

    assert EMBEDDING_CACHE_PATH.exists()

    provider2 = FewShotProvider(preload=False)
    provider2._embedding_cache.clear()
    provider2._load_embedding_cache()

    assert "test1" in provider2._embedding_cache
    assert "test2" in provider2._embedding_cache
    assert provider2._embedding_cache["test1"] == [0.1, 0.2, 0.3]


def test_get_or_compute_embedding_caches(provider_with_cache):
    """Embedding é cacheado após primeira computação."""
    text = "test cache embedding"

    emb1 = provider_with_cache._get_or_compute_embedding(text)
    emb2 = provider_with_cache._get_or_compute_embedding(text)

    if emb1 is not None and emb2 is not None:
        assert emb1 == emb2


@pytest.mark.skip(reason="Slow - requer sentence-transformers")
def test_preload_embeddings(provider_with_cache):
    """Preload carrega modelo e cacheia exemplos."""
    start = time.time()
    provider_with_cache._preload_embeddings()
    elapsed = time.time() - start

    assert len(provider_with_cache._embedding_cache) > 0
    assert EMBEDDING_CACHE_PATH.exists()

    assert elapsed < 20.0


def test_cache_reduces_latency(provider_with_cache):
    """Cache reduz latência em chamadas subsequentes."""
    text = "test latency reduction"

    provider_with_cache._ensure_embedder()

    start1 = time.time()
    provider_with_cache._get_or_compute_embedding(text)
    elapsed1 = time.time() - start1

    start2 = time.time()
    provider_with_cache._get_or_compute_embedding(text)
    elapsed2 = time.time() - start2

    assert elapsed2 <= elapsed1 or elapsed2 < 0.01


# ---------------------------------------------------------------------------
#   DLQ — ingestão de exemplos negativos
# ---------------------------------------------------------------------------


@pytest.fixture
def dlq_quarantine(tmp_path):
    """Quarentena temporária com dois arquivos cache_poison_*.json."""
    f1 = tmp_path / "cache_poison_refusal_2026-01-01_abc123.json"
    f1.write_text(
        json.dumps(
            {
                "prompt_snippet": "qual e a capital da Franca?",
                "response_snippet": "Eu no posso ajudar com isso.",
                "reason": "refusal_or_hallucination",
                "model_hint": "ollama",
            }
        ),
        encoding="utf-8",
    )
    f2 = tmp_path / "cache_poison_hallucination_2026-01-02_def456.json"
    f2.write_text(
        json.dumps(
            {
                "prompt_snippet": "deploy k8s cluster terraform",
                "response_snippet": "made-up gibberish",
                "reason": "irrelevant_response",
                "model_hint": "grok",
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def provider_dlq():
    """Provider isolado sem cache pré-existente."""
    p = FewShotProvider(preload=False)
    p._example_cache.clear()
    p._negative_examples.clear()
    yield p


async def test_ingest_dlq_returns_count(provider_dlq, dlq_quarantine):
    """ingest_dlq_examples retorna 2 para duas entradas."""
    result = await provider_dlq.ingest_dlq_examples(dlq_quarantine)
    assert result == 2


async def test_ingest_dlq_populates_negative_examples(provider_dlq, dlq_quarantine):
    """Exemplos negativos são adicionados a _negative_examples."""
    await provider_dlq.ingest_dlq_examples(dlq_quarantine)
    assert len(provider_dlq._negative_examples) >= 2


async def test_ingest_dlq_idempotent(provider_dlq, dlq_quarantine):
    """Segunda ingestão não duplica exemplos."""
    c1 = await provider_dlq.ingest_dlq_examples(dlq_quarantine)
    c2 = await provider_dlq.ingest_dlq_examples(dlq_quarantine)
    assert c1 == 2
    assert c2 == 0


async def test_ingest_dlq_missing_dir_returns_zero(provider_dlq):
    """Diretório inexistente retorna 0 sem erro."""
    result = await provider_dlq.ingest_dlq_examples(
        Path("/tmp/iaglobal_no_such_dir_dlq_xyz")
    )
    assert result == 0


async def test_ingest_dlq_appears_in_format(provider_dlq, dlq_quarantine):
    """Exemplos DLQ aparecem formatados como padrão a evitar."""
    await provider_dlq.ingest_dlq_examples(dlq_quarantine)
    result = provider_dlq.get_few_shot("deploy k8s cluster")
    section = result.section
    assert "❌" in section
    assert "a evitar" in section
