# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste de integracao da soberania do banco de staging.

Valida a propriedade arquitetural: produtores (async_memory,
CognitiveProxy, pipeline.engine) e consumidor (obsidian.consolidation.
_processar_staging_db) compartilham o MESMO banco (MEMORIES_DB).

Falhas dessa invariante causam o erro:
    sqlite3.OperationalError: no such table: stm_entries
no REM, deixando dados de STM/LTM orfaos (nunca chegam ao vault).

Bug historico: async_memory usava CORE_DB e MEMORY_SWAP_DIR/stm.db
enquanto o REM lia MEMORIES_DB. Fix: tudo converge para MEMORIES_DB.
"""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from iaglobal._paths import MEMORIES_DB
from iaglobal.memory.async_memory import add_ltm, add_stm


@pytest.fixture
def fresh_memories_db(tests_temp_dir, monkeypatch):
    """Aponta MEMORIES_DB para um arquivo limpo e isolado por teste."""
    import uuid

    target = tests_temp_dir / f"memories_test_{uuid.uuid4().hex}.db"
    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Resetar singletons ANTES do monkeypatch para garantir que
    # _get_ltm/_get_stm instanciem contra o path novo.
    import iaglobal.memory.async_memory as am

    monkeypatch.setattr(am, "_ltm", None)
    monkeypatch.setattr(am, "_stm", None)
    monkeypatch.setattr(am, "_memory_vector", None)
    monkeypatch.setattr("iaglobal._paths.MEMORIES_DB", target)
    monkeypatch.setattr("iaglobal.memory.async_memory.MEMORIES_DB", target)
    monkeypatch.setattr(
        "iaglobal.obsidian.consolidation.MEMORIES_DB", target
    )
    return target


def _read_staging(target: Path) -> dict:
    conn = sqlite3.connect(target)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        out = {"tables": tables}
        for t in ("stm_entries", "ltm_entries"):
            if t in tables:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE consolidated_at IS NULL"
                ).fetchone()[0]
                out[t] = n
        return out
    finally:
        conn.close()


def test_async_memory_writes_to_MEMORIES_DB(fresh_memories_db):
    """add_ltm/add_stm gravam em MEMORIES_DB - mesma tabela que o REM le."""

    async def write():
        await add_ltm("test_key", {"evaluations": ["a", "b"]})
        await add_stm("test_item", {"src": "test"})

    asyncio.run(write())

    staging = _read_staging(fresh_memories_db)
    assert "stm_entries" in staging["tables"], (
        "STM nao gravou em MEMORIES_DB - produtor e consumidor estao em "
        "bancos diferentes (bug de soberania)"
    )
    assert "ltm_entries" in staging["tables"], (
        "LTM nao gravou em MEMORIES_DB - produtor e consumidor estao em "
        "bancos diferentes (bug de soberania)"
    )
    assert staging["stm_entries"] == 1
    assert staging["ltm_entries"] == 1


def test_REM_staging_sees_what_async_memory_wrote(fresh_memories_db):
    """End-to-end: async_memory grava, REM staging le - mesmo banco."""

    async def write():
        await add_ltm("integration_key", {"evaluations": ["x"]})
        await add_stm("integration_item", {"src": "integration"})

    asyncio.run(write())

    # Simula o que _processar_staging_db faz: abre MEMORIES_DB e consulta
    # as tabelas de staging. Se a convergencia falhou, levara OperationalError.
    conn = sqlite3.connect(fresh_memories_db, timeout=30.0)
    try:
        for table in ("stm_entries", "ltm_entries"):
            cur = conn.execute(
                f"SELECT id FROM {table} WHERE consolidated_at IS NULL "
                f"ORDER BY created_at ASC LIMIT 10"
            )
            rows = cur.fetchall()
            assert len(rows) >= 1, (
                f"{table} deveria ter ao menos 1 entrada nao-consolidada "
                f"apos add_ltm/add_stm"
            )
    finally:
        conn.close()


def test_async_memory_singletons_share_db_with_rem(fresh_memories_db):
    """_get_ltm() e _get_stm() usam o mesmo db_path do REM."""

    import iaglobal.memory.async_memory as am

    ltm = am._get_ltm()
    stm = am._get_stm()
    # O fixture monkeypatch-ou iaglobal._paths.MEMORIES_DB; le do modulo
    # fresh para comparar contra o valor realmente usado pelas instancias.
    import iaglobal._paths as paths_module

    expected = paths_module.MEMORIES_DB
    assert ltm.db_path == expected
    assert stm.db_path == expected
    assert ltm.db_path == stm.db_path, (
        "LTM e STM devem apontar para o mesmo banco canonico (MEMORIES_DB)"
    )
