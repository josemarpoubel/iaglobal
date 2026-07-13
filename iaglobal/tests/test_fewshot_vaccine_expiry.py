# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes de expiry de vacinas e monitoramento do FewShotProvider."""

import json
import pytest
import time
from datetime import datetime, timezone

from iaglobal.core.few_shot_provider import (
    FewShotProvider,
    FewShotExample,
    MAX_VACCINES,
    ESTIMATED_TOKENS_PER_EXAMPLE,
)


@pytest.fixture
def provider_with_vaccines(tmp_path):
    """Cria FewShotProvider com vacinas seed."""
    provider = FewShotProvider(preload=False)
    provider._example_cache.clear()
    provider._negative_examples.clear()

    # Seed 5 vacinas recentes
    for i in range(5):
        key = f"dlq:test_{i}"
        ex = FewShotExample(
            source=f"dlq:test_{i}",
            query=f"test {i}",
            answer=f"error {i}",
            score=0.15,
        )
        provider._example_cache[key] = ([ex], time.monotonic())
        provider._negative_examples.append(ex)

    yield provider


async def test_vaccine_expiry_by_age(provider_with_vaccines, monkeypatch):
    """Vacinas com idade >30 dias são removidas."""
    # Avança tempo artificialmente para simular 31 dias
    old_timestamp = time.monotonic() - (31 * 86400)
    provider_with_vaccines._example_cache["dlq:test_0"] = (
        provider_with_vaccines._example_cache["dlq:test_0"][0],
        old_timestamp,
    )

    expiry_stats = provider_with_vaccines._expire_old_vaccines()

    assert expiry_stats["expired_by_age"] == 1
    assert expiry_stats["remaining"] == 4
    assert "dlq:test_0" not in provider_with_vaccines._example_cache


async def test_vaccine_expiry_by_cap(provider_with_vaccines):
    """Vacinas excedentes (>100) são removidas (mais antigas primeiro)."""
    # Adiciona 100 vacinas extras
    for i in range(100):
        key = f"dlq:extra_{i}"
        ex = FewShotExample(
            source=f"dlq:extra_{i}",
            query=f"extra {i}",
            answer=f"error {i}",
            score=0.15,
        )
        # Timestamp decrescente (mais antigo primeiro)
        provider_with_vaccines._example_cache[key] = (
            [ex],
            time.monotonic() - (i * 100),
        )
        provider_with_vaccines._negative_examples.append(ex)

    expiry_stats = provider_with_vaccines._expire_old_vaccines()

    assert expiry_stats["expired_by_cap"] > 0
    assert len(provider_with_vaccines._example_cache) <= MAX_VACCINES


async def test_vaccine_expiry_syncs_negative_examples(provider_with_vaccines):
    """Expiry sincroniza _example_cache e _negative_examples."""
    # Adiciona vacina antiga
    old_timestamp = time.monotonic() - (31 * 86400)
    ex = FewShotExample(
        source="dlq:old_test",
        query="old test",
        answer="old error",
        score=0.15,
    )
    provider_with_vaccines._example_cache["dlq:old_test"] = ([ex], old_timestamp)
    provider_with_vaccines._negative_examples.append(ex)

    initial_count = len(provider_with_vaccines._negative_examples)
    expiry_stats = provider_with_vaccines._expire_old_vaccines()

    assert expiry_stats["expired_by_age"] == 1
    assert len(provider_with_vaccines._negative_examples) == initial_count - 1


def test_estimated_token_overhead_constant():
    """Constante ESTIMATED_TOKENS_PER_EXAMPLE é razoável (200-500 tokens)."""
    assert 200 <= ESTIMATED_TOKENS_PER_EXAMPLE <= 500
    assert ESTIMATED_TOKENS_PER_EXAMPLE == 300  # Valor padrão


async def test_ingest_dlq_calls_expiry(provider_with_vaccines, tmp_path, monkeypatch):
    """ingest_dlq_examples() chama _expire_old_vaccines() antes de injetar."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Seed 1 arquivo DLQ
    fpath = quarantine_dir / "cache_poison_test.json"
    fpath.write_text(
        json.dumps(
            {
                "prompt_snippet": "test prompt",
                "response_snippet": "error",
                "reason": "test_reason",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    # Mock _expire_old_vaccines para verificar chamada
    expiry_called = False
    original_expiry = provider_with_vaccines._expire_old_vaccines

    def mock_expiry():
        nonlocal expiry_called
        expiry_called = True
        return original_expiry()

    monkeypatch.setattr(provider_with_vaccines, "_expire_old_vaccines", mock_expiry)

    await provider_with_vaccines.ingest_dlq_examples(quarantine_dir)

    assert expiry_called, "_expire_old_vaccines() não foi chamado"
