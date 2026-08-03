# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do spill-to-disk correto do ShortTermMemory.

Bug historico: o mecanismo de swap-on-disk media RAM do SISTEMA
(/proc/meminfo), escrevia .cbor2 orfaos que ninguem lia, e nunca liberava
a RAM (append incondicional). Resultado: 50k arquivos / 202MB orfaos.

Reimplementacao: mede o RSS do PROCESSO, drena o cache RAM quando o RSS
cruza o threshold (dados seguros no SQLite, gravados no add), re-le do
SQLite sob demanda, e NAO cria arquivos .cbor2.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from iaglobal.memory.term_short import ShortTermMemory, _process_rss_mb


@pytest.fixture
def stm_db(tests_temp_dir: Path):
    """Banco STM isolado por teste em tests_temp_dir."""
    db = tests_temp_dir / "stm_spill_test.db"
    if db.exists():
        db.unlink()
    db.parent.mkdir(parents=True, exist_ok=True)
    yield db


def test_process_rss_positive():
    """O RSS do processo deve ser um inteiro > 0 (mede o proprio processo)."""
    rss = _process_rss_mb()
    assert isinstance(rss, int)
    assert rss > 0


def test_add_persists_entries_to_sqlite(stm_db: Path):
    """add() grava no SQLite — e por isso drenar a RAM nao perde nada."""
    stm = ShortTermMemory(max_size=10, db_path=stm_db, spill_enabled=False)
    stm.add("primeiro", {"tipo": "teste"})
    stm.add("segundo")
    stm._spilled = True
    stm._buffer.clear()
    assert stm.get_recent(5) == ["primeiro", "segundo"]


def test_spill_drains_ram_when_rss_above_threshold(stm_db: Path, monkeypatch):
    """Quando RSS > threshold, o cache RAM e drenado; dados ficam no SQLite."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=True, spill_rss_threshold_mb=0
    )
    for i in range(5):
        stm.add(f"entrada-{i}")
    assert stm._spilled is True
    assert len(stm._buffer) == 0
    assert stm.count() == 0


def test_read_back_from_sqlite_when_spilled(stm_db: Path):
    """Ler com cache drenado retorna os dados vindos do SQLite, nao da RAM."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=True, spill_rss_threshold_mb=0
    )
    for i in range(4):
        stm.add(f"entrada-{i}")
    stm._spilled = True
    stm._buffer.clear()
    recent = stm.get_recent(4)
    assert recent == ["entrada-0", "entrada-1", "entrada-2", "entrada-3"]


def test_maybe_restore_after_pressure_subside(stm_db: Path, monkeypatch):
    """Quando o RSS volta abaixo do threshold, o cache RAM e re-hidratado."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=True, spill_rss_threshold_mb=0
    )
    for i in range(3):
        stm.add(f"e-{i}")
    assert stm._spilled is True
    stm._spill_threshold_mb = 10**9
    stm._maybe_restore()
    assert stm._spilled is False
    assert len(stm._buffer) == 3


def test_spill_no_cbor2_files_created(stm_db: Path, tests_temp_dir: Path):
    """O spill correto NAO cria arquivos .cbor2 no disco."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=True, spill_rss_threshold_mb=0
    )
    for i in range(6):
        stm.add(f"e-{i}")
    cbor_files = list(tests_temp_dir.glob("*.cbor2"))
    assert cbor_files == []


def test_spill_status_reports_state(stm_db: Path):
    """spill_status() expoe enabled/rss/threshold/spilled para o IVM."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=True, spill_rss_threshold_mb=0
    )
    stm.add("x")
    status = stm.spill_status()
    assert status["enabled"] is True
    assert status["spilled"] is True
    assert status["process_rss_mb"] > 0
    assert "threshold_mb" in status


def test_spill_disabled_when_flag_false(stm_db: Path):
    """Com STM_SPILL_ENABLED=0, nenhum dreno acontece."""
    stm = ShortTermMemory(
        max_size=10, db_path=stm_db, spill_enabled=False, spill_rss_threshold_mb=0
    )
    for i in range(4):
        stm.add(f"e-{i}")
    assert stm._spilled is False
    assert len(stm._buffer) == 4


def test_spill_env_fraction_parsed(stm_db: Path, monkeypatch):
    """STM_SPILL_RSS_FRACTION define o threshold default (fracao da RAM)."""
    monkeypatch.setenv("STM_SPILL_RSS_FRACTION", "0.7")
    with patch(
        "iaglobal.memory.term_short._total_ram_mb", return_value=16000
    ):
        stm = ShortTermMemory(db_path=stm_db, spill_enabled=False)
    assert stm._spill_threshold_mb == int(16000 * 0.7)
