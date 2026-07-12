# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do processamento de DLQ pelo REMSleepEngine."""
import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from iaglobal.obsidian.consolidation import REMSleepEngine
from iaglobal._paths import PACKAGE_DIR


@pytest.fixture
def rem_sleep_with_dlq(tmp_path):
    """Cria REMSleepEngine com quarantine_dir temporário."""
    engine = REMSleepEngine(vault_path=tmp_path)
    yield engine


@pytest.fixture
def dlq_seed_files(tmp_path):
    """Seed de arquivos DLQ para testes."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed 5 arquivos com reason="refusal", domain="api"
    for i in range(5):
        fpath = quarantine_dir / f"cache_poison_refusal_2026-01-0{i}_test{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"crie uma API endpoint {i}",
            "response_snippet": "Eu não posso ajudar com isso.",
            "reason": "refusal_or_hallucination",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    # Seed 2 arquivos com reason="hallucination", domain="database"
    for i in range(2):
        fpath = quarantine_dir / f"cache_poison_hallucination_2026-01-0{i}_test{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"query SQL para tabela {i}",
            "response_snippet": "SELECT * FROM fake_table",
            "reason": "irrelevant_response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    return quarantine_dir


async def test_dlq_scan_aggregates_patterns(rem_sleep_with_dlq, dlq_seed_files):
    """Varredura agrega múltiplos arquivos por (reason, domain)."""
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    
    assert result["total_files_scanned"] == 7  # 5 + 2
    assert result["significant_patterns"] == 1  # Apenas refusal atinge threshold=3
    assert result["vaccines_injected"] == 7     # Todos injetados


async def test_dlq_scan_respects_threshold(rem_sleep_with_dlq, tmp_path):
    """Padrões abaixo do threshold não são considerados significativos."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed apenas 2 arquivos (abaixo de threshold=3)
    for i in range(2):
        fpath = quarantine_dir / f"cache_poison_test_{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"test {i}",
            "response_snippet": "error",
            "reason": "test_reason",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    assert result["significant_patterns"] == 0


async def test_dlq_scan_async_io_non_blocking(rem_sleep_with_dlq, tmp_path):
    """I/O de disco não bloqueia event loop (thread pool)."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed 100 arquivos
    for i in range(100):
        fpath = quarantine_dir / f"cache_poison_batch_{i:03d}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"batch test {i}",
            "response_snippet": "error",
            "reason": "batch_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    start = asyncio.get_event_loop().time()
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert result["total_files_scanned"] == 100
    assert elapsed < 2.0  # 100 arquivos em <2s (thread pool)


async def test_dlq_scan_missing_dir_returns_zero(rem_sleep_with_dlq):
    """Diretório inexistente retorna 0 sem erro."""
    # Remove quarantine_dir se existir
    if rem_sleep_with_dlq.quarantine_dir.exists():
        rem_sleep_with_dlq.quarantine_dir.rmdir()
    
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    assert result["total_files_scanned"] == 0
    assert result["vaccines_injected"] == 0


async def test_dlq_scan_idempotent(rem_sleep_with_dlq, dlq_seed_files):
    """Segunda varredura não duplica vacinas (idempotência do FewShot)."""
    # Limpa estado pré-existente do FewShotProvider
    from iaglobal.core.few_shot_provider import few_shot_provider
    few_shot_provider._example_cache.clear()
    few_shot_provider._negative_examples.clear()
    
    result1 = await rem_sleep_with_dlq._process_quarantine_dlq()
    initial_vaccine_count = len(few_shot_provider._negative_examples)
    
    result2 = await rem_sleep_with_dlq._process_quarantine_dlq()
    
    # Segunda varredura não injeta vacinas duplicadas (arquivos já processados)
    assert result2["vaccines_injected"] == 0, "Segunda injeção deve ser 0 (idempotência)"
    # Vacinas permanecem estáveis (sem duplicação)
    assert len(few_shot_provider._negative_examples) == initial_vaccine_count


def test_extract_domain_heuristics():
    """Heurística de domínio classifica corretamente."""
    test_cases = [
        ("crie uma API endpoint", "api"),
        ("query SQL para tabela", "database"),
        ("component React JSX", "frontend"),
        ("token de autenticação", "security"),
        ("teste com pytest mock", "testing"),
        ("async await coroutine", "async"),
        ("texto genérico sem keywords", "general"),
        ("", "general"),  # empty string
        (None, "general"),  # None
    ]
    
    for snippet, expected in test_cases:
        result = REMSleepEngine._extract_domain(snippet)
        assert result == expected, f"Failed for {snippet!r}: expected {expected}, got {result}"