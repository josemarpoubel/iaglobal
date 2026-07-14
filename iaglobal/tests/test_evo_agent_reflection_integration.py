# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de integração EvoAgent ↔ AgentBase.

Cobertura:
  - EvoAgent consome os 4 módulos de reflexão (SelfCritique, ReflexionEngine,
    FailureAnalyzer, LearningLoop).
  - AgentBase delega para o EvoAgent de sua linhagem.
  - Registry evolutivo compartilha um EvoAgent por agent_name (mitose).
  - Auto-integração em _call_llm (auto-crítica pós-LLM + análise de falha).
"""

import asyncio
import logging

import pytest

from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.agents.agent_base import AgentBase, get_evo_registry

logging.basicConfig(level=logging.ERROR)  # silencia ruído de OmniMind/chappie


class _DummyAgent(AgentBase):
    """Agente mínimo para exercitar a integração sem dependências pesadas."""

    def __init__(self):
        super().__init__(agent_name="dummy_evo_test")


def _run(coro):
    return asyncio.run(coro)


class TestEvoAgentFourModules:
    """EvoAgent usa os 4 módulos de reflexão nativos do iaglobal."""

    def test_self_critique(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-t-sc")
            res = await evo.self_critique("def f():\n    return 1\n")
            await evo.apoptose("t")
            return res

        res = _run(_t())
        assert isinstance(res, dict)
        assert "score" in res

    def test_analyze_failure(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-t-af")
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
            evo = await EvoAgent.genesis(task_hint="t", name="evo-t-li")
            res = await evo.learning_iterate(lambda t: "r", "task", lambda r: 1.0)
            await evo.apoptose("t")
            return res

        res = _run(_t())
        assert res["iteration"] >= 1
        assert res["score"] == 1.0

    def test_reflexion_fix_returns_str(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-t-rf")
            res = await evo.reflexion_fix("def f(): return 1")
            created = evo._reflexion_engine is not None
            await evo.apoptose("t")
            return res, created

        res, created = _run(_t())
        assert isinstance(res, str)
        assert created is True  # ReflexionEngine foi instanciado sob demanda

    def test_handle_activates_self_critique(self):
        async def _t():
            evo = await EvoAgent.genesis(task_hint="t", name="evo-t-h")
            expr = await evo.handle("tarefa normal de análise")
            await evo.apoptose("t")
            return expr

        expr = _run(_t())
        assert expr.cycles_activated["self_critique"] is True
        assert "evo-t-h" in expr.agent_name


class TestAgentBaseDelegation:
    """Qualquer agente que herda de AgentBase ganha a capacidade evolutiva."""

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

        res = _run(_t())
        assert res["error_type"] == "ValueError"

    def test_evo_reflexion_fix_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_reflexion_fix("def f(): return 1")
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res

        res = _run(_t())
        assert isinstance(res, str)

    def test_evo_learning_iterate_delegates(self):
        async def _t():
            a = _DummyAgent()
            res = await a.evo_learning_iterate(lambda t: "r", "task", lambda r: 0.5)
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return res

        res = _run(_t())
        assert res["score"] == 0.5


class TestEvoRegistry:
    """Registry evolutivo: uma linhagem (mesmo agent_name) = um EvoAgent."""

    def test_shared_lineage(self):
        async def _t():
            a1 = _DummyAgent()
            a2 = _DummyAgent()
            e1 = await a1.get_evo_agent()
            e2 = await a2.get_evo_agent()
            await e1.apoptose("t")
            return e1, e2

        e1, e2 = _run(_t())
        assert e1 is e2  # mesma instância → mesma família evolutiva
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


class TestCallLlmAutoCritique:
    """Auto-integração: _call_llm roda auto-crítica e análise de falha."""

    @pytest.mark.skip(
        reason="Teste travando em asyncio Future - precisa de refatoração"
    )
    def test_self_critique_after_llm(self):
        async def _t():
            a = _DummyAgent()
            # Stub do provider para não depender de LLM real
            a.bandit.generate = lambda **kw: asyncio.Future()
            fut = a.bandit.generate()
            fut.set_result("def f():\n    return 1\n")

            out = await a._call_llm(prompt="faça uma função", task_type="code")
            await a.get_evo_agent()  # garante EvoAgent criado p/ análise
            evo = await a.get_evo_agent()
            await evo.apoptose("t")
            return out, a._last_evo_critique

        out, critique = _run(_t())
        # _call_llm pode retornar resposta da memória de longo prazo (MemoryFirstRouter)
        # ou do provider; o ponto é que a auto-crítica evolutiva foi acionada.
        assert isinstance(out, str) and out
        assert isinstance(critique, dict)
        assert "score" in critique

    @pytest.mark.skip(
        reason="Teste travando em asyncio Future - precisa de refatoração"
    )
    def test_failure_analysis_on_exception(self):
        async def _t():
            a = _DummyAgent()
            a.bandit.generate = lambda **kw: (_ for _ in ()).throw(
                RuntimeError("provider down")
            )
            try:
                await a._call_llm(prompt="x", task_type="code")
            except RuntimeError:
                pass
            evo = await a.get_evo_agent()
            n = len(evo._failure_patterns)
            await evo.apoptose("t")
            return n

        # Ao menos 1 padrão de falha registrado na memória imunológica
        assert _run(_t()) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
