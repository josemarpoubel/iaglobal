# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testa a unificação do IVMAxiom canônico (fim do split-brain metabólico).

Antes da correção, os Agentes (escritores) usavam get_ivm_axiom() — singleton em
memória — enquanto os Observadores (no_system_analysis, ivm_compliance) liam
_get_chappie()["ivm"] — instância persistida em memory_swap/ivm.db. Os pools eram
distintos: a telemetria IVM era cega (ranking sempre vazio em runtime).

Este teste garante que escritor e leitor compartilham o MESMO objeto/pool.
"""

import asyncio
from pathlib import Path

import pytest

from iaglobal.chappie.ivm_axiom import (
    IVMAxiom,
    get_ivm_axiom,
    init_ivm_axiom_com_persistencia,
)
from iaglobal.chappie import _set_chappie, _get_chappie


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Isola o singleton entre testes para evitar contaminação de módulo."""
    import iaglobal.chappie.ivm_axiom as mod

    prev = mod.ivm_axiom
    mod.ivm_axiom = None
    _set_chappie()  # limpa registry
    yield
    mod.ivm_axiom = prev
    _set_chappie()


def test_init_persistencia_registra_chappie(tests_temp_dir: Path):
    """init_ivm_axiom_com_persistencia deve registrar a instância no Chappie."""
    db = tests_temp_dir / "ivm_test.db"
    ivm = init_ivm_axiom_com_persistencia(db_path=db)
    assert _get_chappie().get("ivm") is ivm
    assert isinstance(ivm, IVMAxiom)


def test_get_ivm_axiom_prefere_registrado(tests_temp_dir: Path):
    """get_ivm_axiom() deve reaproveitar a instância canônica registrada."""
    db = tests_temp_dir / "ivm_test.db"
    canon = init_ivm_axiom_com_persistencia(db_path=db)
    assert get_ivm_axiom() is canon


def test_escritor_e_leitor_compartilham_pool(tests_temp_dir: Path):
    """Agente escreve via _get_chappie()['ivm']; observador lê o mesmo objeto."""
    db = tests_temp_dir / "ivm_test.db"
    init_ivm_axiom_com_persistencia(db_path=db)


def test_agente_via_get_ivm_axiom_popula_pool_observavel(tests_temp_dir: Path):
    """Fluxo real: agente usa get_ivm_axiom() (como agent_base) e observador vê."""
    db = tests_temp_dir / "ivm_test.db"
    init_ivm_axiom_com_persistencia(db_path=db)

    # Escritor (simula agent_base._get_ivm)
    from iaglobal.chappie import _get_chappie as gc

    writer = gc().get("ivm")

    # Observador (simula no_system_analysis)
    reader = gc().get("ivm")

    assert writer is reader  # mesmo objeto

    async def _run():
        await writer.atualizar_metricas(
            "coder",
            tasks_completed=1,
            total_latency_ms=500.0,
            skills_exchanged=0,
            mhc_validation_score=0.9,
        )
        return reader.get_ranking()

    ranking = asyncio.run(_run())
    assert len(ranking) == 1
    assert ranking[0]["agent_name"] == "coder"
    assert ranking[0]["current_ivm"] > 0


def test_agente_via_get_ivm_axiom_popula_pool_observavel(tests_temp_dir: Path):
    """Fluxo real: agente usa get_ivm_axiom() (como agent_base) e observador vê."""
    db = tests_temp_dir / "ivm_test.db"
    init_ivm_axiom_com_persistencia(db_path=db)

    async def _run():
        # agent_base escreve via get_ivm_axiom() (após o patch, prefere registrado)
        ivm_writer = get_ivm_axiom()
        await ivm_writer.atualizar_metricas(
            "system-analysis-evo",
            tasks_completed=1,
            total_latency_ms=1200.0,
            skills_exchanged=1,
            mhc_validation_score=0.9,
        )
        # observador lê via _get_chappie()
        return _get_chappie().get("ivm").get_ranking()

    ranking = asyncio.run(_run())
    assert any(r["agent_name"] == "system-analysis-evo" for r in ranking)
