# 🧬 Testes do módulo cache com barreira imunológica + apoptose
import time

import pytest

import iaglobal.memory.cache as cache_module
from iaglobal.memory import cache
from iaglobal.immunity.metabolic_immune_barrier import barrier


@pytest.fixture(autouse=True)
def _reset():
    cache._cache.clear()
    barrier.reset()
    # Desliga L2 para isolar L1 nos testes de roundtrip.
    original = cache_module.get_success_by_task
    cache_module.get_success_by_task = lambda prompt: None
    yield
    cache_module.get_success_by_task = original
    cache._cache.clear()
    barrier.reset()


def test_valid_roundtrip_preserves_tokens():
    cache.set("k1", "resposta valida e longa o suficiente", tokens=123)
    entry = cache.get_entry("k1")
    assert entry is not None
    assert entry["value"] == "resposta valida e longa o suficiente"
    assert entry["tokens"] == 123
    assert cache.get("k1") == "resposta valida e longa o suficiente"


def test_toxic_value_rejected_and_apoptosed():
    # Valor curto (abaixo de MIN_VALID_LEN) é tóxico -> não servido + evento.
    cache._cache[cache.hash_prompt("k2")] = {
        "value": "curto",
        "tokens": 0,
        "stored_at": time.monotonic(),
    }
    assert cache.get_entry("k2") is None
    assert cache.get("k2") is None
    assert barrier.counts()["cache_poison"] >= 1
    # Foi apoptosado do L1.
    assert cache.hash_prompt("k2") not in cache._cache


def test_expired_entry_apoptosed():
    cache.CACHE_TTL_SECONDS = 10
    cache._cache[cache.hash_prompt("k3")] = {
        "value": "x" * 50,
        "tokens": 5,
        "stored_at": time.monotonic() - 9999,
    }
    assert cache.get_entry("k3") is None
    assert barrier.counts()["stale_cache"] >= 1
    cache.CACHE_TTL_SECONDS = int(
        __import__("os").environ.get("IAGLOBAL_CACHE_TTL_SECONDS", "86400")
    )


def test_l2_toxic_evicted_and_not_served():
    toxic_l2 = {"codigo": "  ", "metadata": {"tokens": 0}}
    cache_module.get_success_by_task = lambda prompt: toxic_l2
    deletions = []
    original_store = cache_module.storage
    cache_module.storage.delete = lambda prompt: deletions.append(prompt)
    try:
        assert cache.get_entry("k4") is None
        assert barrier.counts()["cache_poison"] >= 1
        assert deletions, "entrada tóxica do L2 deveria ser apoptosada"
    finally:
        cache_module.storage = original_store


def test_l2_valid_loaded_with_tokens():
    valid_l2 = {"codigo": "x" * 40, "metadata": {"tokens": 77}}
    cache_module.get_success_by_task = lambda prompt: valid_l2
    entry = cache.get_entry("k5")
    assert entry is not None
    assert entry["tokens"] == 77
    # Populou L1 para próxima vez.
    assert cache.hash_prompt("k5") in cache._cache
