# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do VaccineLedger — persistência de failure_patterns no vault Obsidian
e cruzamento com ImmuneMemoryExchange para vacinas entre agentes da mesma linhagem.

Cobertura:
  - registrar_falha persiste no Obsidian (05_Vaccines) e publica vacina.
  - vacinas() recupera o conjunto de padrões da linhagem.
  - aplicar_vacina pré-carrega _failure_patterns (gating por lineage_marker).
  - dedupe de padrões repetidos.
  - ImmuneMemoryExchange import_vaccine respeita o gating de linhagem.
"""
import asyncio
import logging

import pytest

from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.immunity.vaccine_ledger import vaccine_ledger
from iaglobal.immunity.immune_memory_exchange import immune_memory_exchange

logging.basicConfig(level=logging.ERROR)  # silencia ruído de OmniMind/chappie


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Garante registry evolutivo limpo entre testes (mesma linhagem)."""
    from iaglobal.agents.agent_base import _EVO_REGISTRY
    _EVO_REGISTRY.clear()
    yield
    _EVO_REGISTRY.clear()


class TestVaccineLedgerPersistence:
    """failure_patterns são persistidos no Obsidian por linhagem."""

    def test_registrar_e_recuperar(self):
        async def _t():
            # Limpa o ledger da linhagem antes do teste
            evo = await EvoAgent.genesis(task_hint="vaccine_test", name="evo-vac-1")
            marker = evo.lineage_marker
            # zera ledger
            await vaccine_ledger._vault.escrever_vacina(marker, vaccine_ledger._serialize([], marker))

            res = await evo.analyze_failure(RuntimeError("boom"), {"k": 1})
            await vaccine_ledger.aplicar_vacina(evo)  # força reload
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return res, vac
        res, vac = _run(_t())
        assert res["error_type"] == "RuntimeError"
        assert "RuntimeError" in vac

    def test_dedupe_padroes(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="vaccine_dedupe", name="evo-vac-2")
            marker = evo.lineage_marker
            await vaccine_ledger._vault.escrever_vacina(marker, vaccine_ledger._serialize([], marker))
            await evo.analyze_failure(ValueError("x"), {"a": 1})
            await evo.analyze_failure(ValueError("x"), {"a": 2})  # mesmo pattern
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return vac
        vac = _run(_t())
        # ValueError aparece apenas uma vez (dedupe por pattern)
        assert len([p for p in vac if p == "ValueError"]) == 1


class TestVaccineApplyGating:
    """A vacina só é aplicada ao próprio lineage_marker (sem autoimunidade)."""

    def test_aplicar_vacina_pre_carrega(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="vaccine_apply", name="evo-vac-3")
            marker = evo.lineage_marker
            await vaccine_ledger._vault.escrever_vacina(
                marker, vaccine_ledger._serialize(
                    [{"pattern": "TimeoutError", "agent": "ancestral", "context": {}}], marker)
            )
            # Filho por mitose — HERDA o mesmo lineage_marker (mesma família)
            evo2 = await evo.replicate(mutation_hint="vacina-test")
            # A vacina da linhagem deve ser herdada pelo filho
            n = await vaccine_ledger.aplicar_vacina(evo2)
            await evo.apoptose("t")
            await evo2.apoptose("t")
            return n, evo2._failure_patterns
        n, padroes = _run(_t())
        assert n >= 1
        assert "TimeoutError" in padroes

    def test_linhagem_distinta_nao_herda(self):
        async def _t():
            e1 = await EvoAgent.genesis(task_hint="vac_other_a", name="evo-vac-a")
            e2 = await EvoAgent.genesis(task_hint="vac_other_b", name="evo-vac-b")
            # injeta vacina apenas na linhagem de e1
            await vaccine_ledger._vault.escrever_vacina(
                e1.lineage_marker,
                vaccine_ledger._serialize(
                    [{"pattern": "ImportError", "agent": "a", "context": {}}], e1.lineage_marker)
            )
            n = await vaccine_ledger.aplicar_vacina(e2)  # e2 tem marker diferente
            await e1.apoptose("t")
            await e2.apoptose("t")
            return n, e2._failure_patterns
        n, padroes = _run(_t())
        assert n == 0  # gating: linhagem distinta não herda
        assert "ImportError" not in padroes


class TestImmuneMemoryExchangeLineage:
    """Import de vacina respeita o gating de linhagem (não-autoimunidade)."""

    def test_import_recusado_linhagem_estranha(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="ime_test", name="evo-ime-1")
            marker = evo.lineage_marker
            remote = {
                "lineage_marker": "zzzzzzzzzzzzzzzz",  # linhagem desconhecida
                "patterns": ["RuntimeError"],
                "node_id": "remote",
            }
            n = await immune_memory_exchange.import_vaccine(remote, "remote")
            await evo.apoptose("t")
            return n
        assert _run(_t()) == 0

    def test_import_aceito_mesma_linhagem(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="ime_test2", name="evo-ime-2")
            marker = evo.lineage_marker
            # zera ledger da linhagem
            await vaccine_ledger._vault.escrever_vacina(marker, vaccine_ledger._serialize([], marker))
            remote = {
                "lineage_marker": marker,  # mesmo marker → aceita
                "patterns": ["KeyError"],
                "node_id": "remote",
            }
            n = await immune_memory_exchange.import_vaccine(remote, "remote")
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return n, vac
        n, vac = _run(_t())
        assert n == 1
        assert "KeyError" in vac


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
