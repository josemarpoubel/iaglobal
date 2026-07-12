# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
TESTE DE REFERÊNCIA — Integrações Evolutivas Recentes do iaglobal

Este arquivo é a âncora de regressão de TODAS as mutações recentes do ecossistema
evolutivo. Ele exercita ponta a ponta:

  1. EvoAgent consome os 4 módulos de reflexão nativos
     (SelfCritique, ReflexionEngine, FailureAnalyzer, LearningLoop).
  2. AgentBase delega para o EvoAgent de sua linhagem + auto-hooks em _call_llm
     (auto-crítica pós-LLM + análise de falha em exceção).
  3. Registry evolutivo: 1 EvoAgent por agent_name (mesma família / mitose).
  4. VaccineLedger: persistência de failure_patterns no Obsidian (05_Vaccines),
     dedupe, e aplicação de vacina por linhagem (gating evolutivo).
  5. ImmuneMemoryExchange: transporte de vacinas com gating de mesma linhagem
     (recusa de linhagem estranha = sem autoimunidade arquitetural).

Execute:
    python -m pytest tests/test_evo_integration_recent.py -q
"""
import asyncio
import logging
from dataclasses import dataclass

import pytest

from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.agents.agent_base import AgentBase, get_evo_registry
from iaglobal.immunity.vaccine_ledger import vaccine_ledger
from iaglobal.immunity.immune_memory_exchange import immune_memory_exchange

logging.basicConfig(level=logging.ERROR)  # silencia ruído de OmniMind/chappie


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Garante registry evolutivo e known-markers limpos entre testes."""
    from iaglobal.agents.agent_base import _EVO_REGISTRY
    _EVO_REGISTRY.clear()
    vaccine_ledger._known_markers.clear()
    yield
    _EVO_REGISTRY.clear()
    vaccine_ledger._known_markers.clear()


class _DummyAgent(AgentBase):
    """Agente mínimo para exercitar a integração sem dependências pesadas."""

    def __init__(self, name: str = "dummy_recent_test"):
        super().__init__(agent_name=name)


async def _fresh_ledger(marker: str) -> None:
    """Zera o ledger Obsidian da linhagem para testes determinísticos."""
    await vaccine_ledger._vault.escrever_vacina(
        marker, vaccine_ledger._serialize([], marker)
    )


class _StubMemoryRouter:
    """
    Router que SEMPRE dá cache-miss — força o path do provider (bandit.generate)
    para que os testes exercitem de forma determinística o hook de falha de
    `_call_llm` (sem interferência do MemoryFirstRouter persistente, que lê um
    cache/ Obsidian real e pode "achar" a resposta antes de chegar ao provider).
    """

    @dataclass
    class _Miss:
        found: bool = False
        content: str = ""
        source: str = ""
        confidence: float = 0.0
        latency_ms: float = 0.0

    async def route(self, task, task_type, tags=None, min_chars=50):
        return self._Miss()

    async def store_result(self, *args, **kwargs):
        return None


def _patch_memory_router(monkeypatch) -> None:
    """Substitui o MemoryFirstRouter global por um stub determinístico."""
    import iaglobal.agents.agent_base as _ab
    monkeypatch.setattr(_ab, "_get_memory_router", lambda: _StubMemoryRouter())


# ─────────────────────────────────────────────────────────────────────────────
# 1. EvoAgent — 4 módulos de reflexão
# ─────────────────────────────────────────────────────────────────────────────

class TestEvoAgentReflectionModules:
    def test_self_critique(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-r-self")
            res = await evo.self_critique("def f():\n    return 1\n")
            await evo.apoptose("t")
            return res
        res = _run(_t())
        assert isinstance(res, dict) and "score" in res

    def test_analyze_failure(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-r-af")
            before = len(evo._failure_patterns)
            res = await evo.analyze_failure(RuntimeError("boom"), {"k": 1})
            after = len(evo._failure_patterns)
            await evo.apoptose("t")
            return res, before, after
        res, before, after = _run(_t())
        assert res["error_type"] == "RuntimeError"
        assert after == before + 1

    def test_learning_iterate(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-r-li")
            res = await evo.learning_iterate(lambda t: "r", "task", lambda r: 1.0)
            await evo.apoptose("t")
            return res
        res = _run(_t())
        assert res["iteration"] >= 1 and res["score"] == 1.0

    def test_reflexion_fix_returns_str(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-r-rf")
            res = await evo.reflexion_fix("def f(): return 1")
            created = evo._reflexion_engine is not None
            await evo.apoptose("t")
            return res, created
        res, created = _run(_t())
        assert isinstance(res, str) and created is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. AgentBase — delegação + auto-hooks
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentBaseEvolutionDelegation:
    def test_evo_self_critique_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_self_critique("x = 1")
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res, evo
        res, evo = _run(_t())
        assert isinstance(res, dict)
        assert hasattr(evo, "lineage_id")

    def test_evo_analyze_failure_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_analyze_failure(ValueError("x"), {"agent": a.agent_name})
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res
        assert _run(_t())["error_type"] == "ValueError"

    def test_evo_reflexion_fix_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_reflexion_fix("def f(): return 1")
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res
        assert isinstance(_run(_t()), str)

    def test_evo_learning_iterate_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_learning_iterate(lambda t: "r", "task", lambda r: 0.5)
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res
        assert _run(_t())["score"] == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 3. Registry evolutivo — uma linhagem = um EvoAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestEvoRegistryLineage:
    def test_shared_lineage(self):
        async def _t():
            a1, a2 = _DummyAgent(), _DummyAgent()
            e1, e2 = await a1.get_evo_agent(), await a2.get_evo_agent()
            await e1.apoptose("t")
            return e1, e2
        e1, e2 = _run(_t())
        assert e1 is e2
        assert e1.lineage_marker == e2.lineage_marker

    def test_registry_exposes_instances(self):
        async def _t():
            a = _DummyAgent()
            evo = await a.get_evo_agent()
            reg = get_evo_registry()
            await evo.apoptose("t")
            return evo, reg
        evo, reg = _run(_t())
        assert evo.lineage_marker in {e.lineage_marker for e in reg.values()}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Auto-evolução em _call_llm
# ─────────────────────────────────────────────────────────────────────────────

class TestCallLlmAutoEvolution:
    def test_self_critique_after_llm(self, monkeypatch):
        _patch_memory_router(monkeypatch)
        async def _t():
            a = _DummyAgent()
            fut = asyncio.Future()
            a.bandit.generate = lambda **kw: fut
            fut.set_result("def f():\n    return 1\n")
            out = await a._call_llm(prompt="faça uma função", task_type="code")
            evo = await a.get_evo_agent()
            crit = a._last_evo_critique
            await evo.apoptose("t")
            return out, crit
        out, crit = _run(_t())
        assert isinstance(out, str) and out
        assert isinstance(crit, dict) and "score" in crit

    def test_failure_analysis_on_exception(self, monkeypatch):
        _patch_memory_router(monkeypatch)
        async def _t():
            a = _DummyAgent()
            a.bandit.generate = lambda **kw: (_ for _ in ()).throw(RuntimeError("down"))
            try:
                await a._call_llm(prompt="x", task_type="code")
            except RuntimeError:
                pass
            evo = await a.get_evo_agent()
            n = len(evo._failure_patterns)
            await evo.apoptose("t")
            return n
        assert _run(_t()) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. VaccineLedger — persistência + gating por linhagem
# ─────────────────────────────────────────────────────────────────────────────

class TestVaccineLedgerLineage:
    def test_registrar_e_recuperar(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="vac_ref", name="evo-vac-ref")
            marker = evo.lineage_marker
            await _fresh_ledger(marker)
            res = await evo.analyze_failure(RuntimeError("boom"), {"k": 1})
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return res, vac
        res, vac = _run(_t())
        assert res["error_type"] == "RuntimeError"
        assert "RuntimeError" in vac

    def test_dedupe_padroes(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="vac_dup", name="evo-vac-dup")
            marker = evo.lineage_marker
            await _fresh_ledger(marker)
            await evo.analyze_failure(ValueError("x"), {"a": 1})
            await evo.analyze_failure(ValueError("x"), {"a": 2})
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return vac
        vac = _run(_t())
        assert len([p for p in vac if p == "ValueError"]) == 1

    def test_aplicar_vacina_por_mitose(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="vac_ap", name="evo-vac-ap")
            marker = evo.lineage_marker
            await _fresh_ledger(marker)
            await vaccine_ledger._vault.escrever_vacina(
                marker,
                vaccine_ledger._serialize(
                    [{"pattern": "TimeoutError", "agent": "ancestral", "context": {}}],
                    marker,
                ),
            )
            child = await evo.replicate(mutation_hint="vac-test")
            n = await vaccine_ledger.aplicar_vacina(child)
            await evo.apoptose("t")
            await child.apoptose("t")
            return n, child._failure_patterns
        n, padroes = _run(_t())
        assert n >= 1 and "TimeoutError" in padroes

    def test_linhagem_distinta_nao_herda(self):
        async def _t():
            e1 = await EvoAgent.genesis(task_hint="vac_o_a", name="evo-vac-oa")
            e2 = await EvoAgent.genesis(task_hint="vac_o_b", name="evo-vac-ob")
            await vaccine_ledger._vault.escrever_vacina(
                e1.lineage_marker,
                vaccine_ledger._serialize(
                    [{"pattern": "ImportError", "agent": "a", "context": {}}],
                    e1.lineage_marker,
                ),
            )
            n = await vaccine_ledger.aplicar_vacina(e2)
            await e1.apoptose("t")
            await e2.apoptose("t")
            return n, e2._failure_patterns
        n, padroes = _run(_t())
        assert n == 0 and "ImportError" not in padroes


# ─────────────────────────────────────────────────────────────────────────────
# 6. ImmuneMemoryExchange — gating de vacina por linhagem
# ─────────────────────────────────────────────────────────────────────────────

class TestImmuneMemoryExchangeVaccine:
    def test_import_recusado_linhagem_estranha(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="ime_r", name="evo-ime-r")
            remote = {
                "lineage_marker": "zzzzzzzzzzzzzzzz",
                "patterns": ["RuntimeError"],
                "node_id": "remote",
            }
            n = await immune_memory_exchange.import_vaccine(remote, "remote")
            await evo.apoptose("t")
            return n
        assert _run(_t()) == 0

    def test_import_aceito_mesma_linhagem(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="ime_a", name="evo-ime-a")
            marker = evo.lineage_marker
            await _fresh_ledger(marker)
            remote = {
                "lineage_marker": marker,
                "patterns": ["KeyError"],
                "node_id": "remote",
            }
            n = await immune_memory_exchange.import_vaccine(remote, "remote")
            vac = await vaccine_ledger.vacinas(marker)
            await evo.apoptose("t")
            return n, vac
        n, vac = _run(_t())
        assert n == 1 and "KeyError" in vac


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cenário end-to-end (referência viva das integrações)
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegrationEndToEnd:
    def test_agente_completo_evolui_e_vacina(self, monkeypatch):
        """Um agente real (via AgentBase) critica, falha, vacina e herda lição."""
        _patch_memory_router(monkeypatch)
        async def _t():
            a = _DummyAgent(name="evo_e2e_agent")

            # 1) Sucesso → auto-crítica evolutiva
            fut = asyncio.Future()
            a.bandit.generate = lambda **kw: fut
            fut.set_result("def f():\n    return 1\n")
            out = await a._call_llm(prompt="gere função", task_type="code")
            crit = a._last_evo_critique

            # 2) Falha → análise de falha + vacina persistida no Obsidian
            a.bandit.generate = lambda **kw: (_ for _ in ()).throw(RuntimeError("db down"))
            try:
                await a._call_llm(prompt="x", task_type="code")
            except RuntimeError:
                pass

            evo = await a.get_evo_agent()
            marker = evo.lineage_marker
            vac = await vaccine_ledger.vacinas(marker)

            # 3) Filho por mitose herda a vacina da família
            child = await evo.replicate(mutation_hint="e2e")
            n_herdadas = await vaccine_ledger.aplicar_vacina(child)

            await evo.apoptose("t")
            await child.apoptose("t")
            return out, crit, vac, n_herdadas
        out, crit, vac, n_herdadas = _run(_t())
        assert out and isinstance(crit, dict) and "score" in crit
        assert "RuntimeError" in vac               # vacina persistida
        assert n_herdadas >= 1                       # filho herdou a lição


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
