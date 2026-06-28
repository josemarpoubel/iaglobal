"""Testes integrados do sistema metabólico: verifica que todos os ciclos
estão importáveis, consistentes e integrados na pipeline.

Cobre:
1. HomocysteinePool — adição, métricas, promoção, guardrail
2. MethylationCycle — threshold de promoção
3. TranssulfurationCycle — threshold de frequência
4. SAMe Engine — budget, spend, recharge
5. GlutathionePool — threat response
6. GlutathioneGuardrails — estrutura de defesa
7. MetaAgentDesigner — design_team por keyword
8. AcetylcholineBus — pub/sub
9. SkillQuarantine — isolamento de skills
10. GracefulShutdown — ciclo de vida
11. EvolutionEngine — API async evolve
12. Pipeline topology — nós de metabolismo registrados
13. Pipeline builder — RUN_NODE_NAMES includes nós
14. Pipeline registry — create_skill_node mapeado
15. Orchestrator — _run_metabolism_cycle existe
"""
import os
import sys
import time
import json
import asyncio
import inspect
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_skill(name, version="1.0.0", description=""):
    from iaglobal.evolution.skills.skill import Skill
    return Skill(name=name, version=version, description=description,
                 inputs=[], outputs=[], constraints=[])


def _make_candidate(skill_name, score=50.0, version="1.0.0"):
    from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill
    return CandidateSkill(skill=_make_skill(skill_name, version), score=score)


# ═══════════════════════════════════════════════════════════════════
# 1. HomocysteinePool — pool de skills candidatas
# ═══════════════════════════════════════════════════════════════════

class TestHomocysteinePool:

    @pytest.fixture
    def pool(self, tmp_path):
        from iaglobal.evolution.metabolism.homocysteine_pool import HomocysteinePool
        pool = HomocysteinePool(path=tmp_path / "hc_pool.json")
        yield pool

    def test_empty_pool(self, pool):
        assert pool.count() == 0
        assert pool.get_pending() == []
        assert pool.get_ready_for_methylation() == []

    def test_add_candidate(self, pool):
        c = _make_candidate("test_skill", score=90.0)
        pool.add(c)
        assert pool.count() == 1
        assert len(pool.get_pending()) == 1
        assert c in pool.get_pending()

    def test_get_ready_for_methylation_filters_by_score(self, pool):
        low = _make_candidate("low", score=30.0)
        high = _make_candidate("high", score=90.0)
        pool.add(low)
        pool.add(high)
        ready = pool.get_ready_for_methylation()
        assert len(ready) == 1
        assert ready[0].skill.name == "high"

    def test_get_candidates_for_methylation_same_as_ready(self, pool):
        c = _make_candidate("x", score=85.0)
        pool.add(c)
        assert pool.get_candidates_for_methylation() == pool.get_ready_for_methylation()

    def test_route_to_production(self, pool):
        c = _make_candidate("promoted", score=95.0)
        pool.add(c)
        assert pool.route_to_production(c) is True
        assert c.route == "production"

    def test_route_to_guardrail(self, pool):
        c = _make_candidate("guardrail_test", score=50.0)
        pool.add(c)
        assert pool.route_to_guardrail(c) is True
        assert c.route == "guardrail"

    def test_pending_excludes_routed(self, pool):
        c = _make_candidate("routed", score=80.0)
        pool.add(c)
        pool.route_to_production(c)
        assert c not in pool.get_pending()
        assert c not in pool.get_ready_for_methylation()

    def test_pool_persistence(self, tmp_path):
        from iaglobal.evolution.metabolism.homocysteine_pool import HomocysteinePool
        path = tmp_path / "persist.json"
        pool1 = HomocysteinePool(path=path)
        c = _make_candidate("persisted", score=88.0)
        pool1.add(c)
        del pool1
        pool2 = HomocysteinePool(path=path)
        assert pool2.count() == 1
        assert pool2.candidates[0].skill.name == "persisted"


# ═══════════════════════════════════════════════════════════════════
# 2. MethylationCycle — promoção para production
# ═══════════════════════════════════════════════════════════════════

class TestMethylationCycle:

    def test_promotes_above_threshold(self, tmp_path):
        from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
        from iaglobal.evolution.metabolism.homocysteine_pool import HomocysteinePool
        pool = HomocysteinePool(path=tmp_path / "methyl_test.json")
        c = _make_candidate("good", score=0.8)
        pool.add(c)
        cycle = MethylationCycle(threshold=0.6)
        assert cycle.run(c) is True

    def test_rejects_below_threshold(self, tmp_path):
        from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
        from iaglobal.evolution.metabolism.homocysteine_pool import HomocysteinePool
        pool = HomocysteinePool(path=tmp_path / "methyl_reject.json")
        c = _make_candidate("bad", score=0.3)
        pool.add(c)
        cycle = MethylationCycle(threshold=0.6)
        assert cycle.run(c) is False

    def test_importable(self):
        from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
        assert MethylationCycle is not None


# ═══════════════════════════════════════════════════════════════════
# 3. TranssulfurationCycle — conversão para guardrail
# ═══════════════════════════════════════════════════════════════════

class TestTranssulfurationCycle:

    def test_importable(self):
        from iaglobal.evolution.metabolism.transsulfuration_cycle import TranssulfurationCycle
        assert TranssulfurationCycle is not None

    def test_instantiate(self):
        from iaglobal.evolution.metabolism.transsulfuration_cycle import TranssulfurationCycle
        cycle = TranssulfurationCycle()
        assert cycle.frequency_threshold == 3


# ═══════════════════════════════════════════════════════════════════
# 4. SAMe Engine — budget metabólico
# ═══════════════════════════════════════════════════════════════════

class TestSAMeEngine:

    def test_same_pool_balance(self):
        from iaglobal.evolution.same_engine import same_pool
        balance = same_pool.balance("test_agent")
        assert isinstance(balance, (int, float))

    def test_same_inhibitor_can_mutate(self):
        from iaglobal.evolution.same_engine import same_inhibitor
        result = same_inhibitor.can_mutate("test", 1, critical=False)
        assert isinstance(result, bool)

    def test_spend_and_recharge(self):
        from iaglobal.evolution.same_engine import same_pool, COST_CREATE_SKILL
        before = same_pool.balance("test_agent")
        same_pool.spend("test_agent", COST_CREATE_SKILL)
        after = same_pool.balance("test_agent")
        assert after <= before

    def test_importable(self):
        from iaglobal.evolution.same_engine import SAMePool, MethylationInhibitor
        assert SAMePool is not None
        assert MethylationInhibitor is not None


# ═══════════════════════════════════════════════════════════════════
# 5. GlutathionePool — resposta imune
# ═══════════════════════════════════════════════════════════════════

class TestGlutathionePool:

    def test_respond_returns_dict(self):
        from iaglobal.immunity.glutathione_pool import GlutathionePool
        pool = GlutathionePool()
        result = pool.respond("test_threat", {"source": "pytest"})
        assert isinstance(result, dict)

    def test_importable(self):
        from iaglobal.immunity.glutathione_pool import GlutathionePool
        assert GlutathionePool is not None


# ═══════════════════════════════════════════════════════════════════
# 6. GlutathioneGuardrails — defesa estrutural
# ═══════════════════════════════════════════════════════════════════

class TestGlutathioneGuardrails:

    def test_defend_and_correct_exists(self):
        from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
        assert hasattr(GlutathioneGuardrails, "defend_and_correct")

    def test_register_guardrail_exists(self):
        from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
        assert hasattr(GlutathioneGuardrails, "register_guardrail")

    def test_importable(self):
        from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
        assert GlutathioneGuardrails is not None


# ═══════════════════════════════════════════════════════════════════
# 7. MetaAgentDesigner — design_team por keyword
# ═══════════════════════════════════════════════════════════════════

class TestMetaAgentDesigner:

    def test_design_team_security(self, dummy_graph):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(dummy_graph)
        result = designer.design_team("implement login with JWT and OAuth")
        assert isinstance(result, dict)
        assert "strategies" in result
        assert "security" in result["strategies"]

    def test_design_team_general(self, dummy_graph):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(dummy_graph)
        result = designer.design_team("hello world")
        assert isinstance(result, dict)
        assert "general" in result["strategies"]

    def test_design_team_lacunas(self, dummy_graph):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(dummy_graph)
        result = designer.design_team("CREATE TABLE users")
        assert isinstance(result, dict)
        assert "lacunas_detectadas" in result
        assert len(result["lacunas_detectadas"]) > 0

    def test_design_team_multiple_specializations(self, dummy_graph):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(dummy_graph)
        result = designer.design_team("create a REST API with SQL database and documentation")
        assert "api_design" in result["strategies"]
        assert "database" in result["strategies"]
        assert "documentation" in result["strategies"]

    @pytest.fixture
    def dummy_graph(self):
        class DummyGraph:
            nodes = {}
        return DummyGraph()


# ═══════════════════════════════════════════════════════════════════
# 8. AcetylcholineBus — sinalização assíncrona
# ═══════════════════════════════════════════════════════════════════

class TestAcetylcholineBus:

    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
        bus = AcetylcholineBus()
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("tester", handler)
        msg = AgentMessage(sender="pytest", receiver="tester", type="test",
                           payload={"key": "value"})
        await bus.publish(msg)
        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0].sender == "pytest"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
        bus = AcetylcholineBus()
        msg = AgentMessage(sender="pytest", receiver="any", type="test",
                           payload={}, ttl=0)
        await bus.publish(msg)
        await bus.purge_expired()
        count = await bus.pending_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_pending_count(self):
        from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
        bus = AcetylcholineBus()
        msg = AgentMessage(sender="pytest", receiver="any", type="test",
                           payload={}, ttl=60)
        await bus.publish(msg)
        count = await bus.pending_count()
        assert count == 1

    def test_importable(self):
        from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus
        assert AcetylcholineBus is not None


# ═══════════════════════════════════════════════════════════════════
# 9. SkillQuarantine — isolamento de skills
# ═══════════════════════════════════════════════════════════════════

class TestSkillQuarantine:

    def test_is_quarantined_returns_bool(self):
        from iaglobal.evolution.skill_quarantine import quarantine
        result = quarantine.is_quarantined("nonexistent_skill")
        assert isinstance(result, bool)

    def test_importable(self):
        from iaglobal.evolution.skill_quarantine import SkillQuarantine
        assert SkillQuarantine is not None


# ═══════════════════════════════════════════════════════════════════
# 10. GracefulShutdown — ciclo de vida
# ═══════════════════════════════════════════════════════════════════

class TestGracefulShutdown:

    def test_add_callback(self):
        from iaglobal.core.graceful_shutdown import graceful_shutdown
        called = False

        def cb():
            nonlocal called
            called = True

        graceful_shutdown.add_callback(cb)
        assert cb in graceful_shutdown._sync_callbacks

    def test_sync_cleanup_executes_callbacks(self):
        from iaglobal.core.graceful_shutdown import graceful_shutdown
        executed = []

        def cb():
            executed.append("ok")

        graceful_shutdown.add_callback(cb)
        graceful_shutdown.sync_cleanup()
        assert len(executed) >= 1

    def test_importable(self):
        from iaglobal.core.graceful_shutdown import graceful_shutdown
        assert graceful_shutdown is not None


# ═══════════════════════════════════════════════════════════════════
# 11. EvolutionEngine — API assíncrona
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionEngine:

    def test_has_evolve_async(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        assert hasattr(EvolutionEngine, "evolve_async")

    def test_has_evolve_alias(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        assert hasattr(EvolutionEngine, "evolve")

    def test_evolve_is_coroutine(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        assert inspect.iscoroutinefunction(EvolutionEngine.evolve)

    def test_evolve_async_is_coroutine(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        assert inspect.iscoroutinefunction(EvolutionEngine.evolve_async)

    def test_has_set_task_async(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        assert hasattr(EvolutionEngine, "set_task_async")


# ═══════════════════════════════════════════════════════════════════
# 12. Pipeline topology — nós de metabolismo registrados
# ═══════════════════════════════════════════════════════════════════

class TestPipelineTopology:

    def test_evolution_nodes_in_topology(self):
        from iaglobal.graphs.topology import NODE_DEPENDENCIES
        required = {
            "evolution_homocysteine",
            "evolution_methylation",
            "evolution_knowledge",
            "evolution_trigger",
            "evolution_committee",
        }
        present = set(NODE_DEPENDENCIES.keys())
        missing = required - present
        assert not missing, f"Nós faltando em topology.py: {missing}"

    def test_evolution_dependencies_correct(self):
        from iaglobal.graphs.topology import NODE_DEPENDENCIES
        assert "skill_generator" in NODE_DEPENDENCIES.get("evolution_homocysteine", [])
        assert "evolution_homocysteine" in NODE_DEPENDENCIES.get("evolution_methylation", [])
        assert "knowledge_analyzer" in NODE_DEPENDENCIES.get("evolution_knowledge", [])
        assert "pipeline_updater" in NODE_DEPENDENCIES.get("evolution_trigger", [])


# ═══════════════════════════════════════════════════════════════════
# 13. Pipeline builder — RUN_NODE_NAMES includes nós
# ═══════════════════════════════════════════════════════════════════

class TestPipelineBuilder:

    def test_evolution_nodes_in_run_order(self):
        from iaglobal.graphs.builder import RUN_NODE_NAMES
        required = {
            "evolution_homocysteine",
            "evolution_methylation",
            "evolution_knowledge",
            "evolution_trigger",
            "evolution_committee",
        }
        present = set(RUN_NODE_NAMES)
        missing = required - present
        assert not missing, f"Nós faltando em builder.RUN_NODE_NAMES: {missing}"


# ═══════════════════════════════════════════════════════════════════
# 14. Pipeline registry — nós carregados dinamicamente
# ═══════════════════════════════════════════════════════════════════

class TestPipelineRegistry:

    def test_registry_has_evolution_trigger(self):
        from iaglobal.graphs.registry import NODE_REGISTRY
        assert "evolution_trigger" in NODE_REGISTRY

    def test_registry_has_evolution_committee(self):
        from iaglobal.graphs.registry import NODE_REGISTRY
        assert "evolution_committee" in NODE_REGISTRY

    def test_dynamic_nodes_loaded_by_nodes_py(self):
        """evolution_homocysteine e evolution_methylation são carregados
        dinamicamente por Nodes._load_dynamic_nodes(), não via registry."""
        from iaglobal.graphs.nodes import Nodes
        nodes = Nodes()
        assert hasattr(nodes, "run_evolution_homocysteine")
        assert hasattr(nodes, "run_evolution_methylation")
        assert hasattr(nodes, "run_evolution_knowledge")


# ═══════════════════════════════════════════════════════════════════
# 15. Orchestrator — _run_metabolism_cycle
# ═══════════════════════════════════════════════════════════════════

class TestOrchestratorMetabolism:

    def test_orchestrator_has_metabolism_method(self):
        from iaglobal.core.orchestrator import Orchestrator
        assert hasattr(Orchestrator, "_run_metabolism_cycle")

    def test_metabolism_method_is_coroutine(self):
        from iaglobal.core.orchestrator import Orchestrator
        assert inspect.iscoroutinefunction(Orchestrator._run_metabolism_cycle)

    def test_orchestrator_imports_metabolism_modules(self):
        import ast
        import inspect
        from iaglobal.core.orchestrator import Orchestrator
        src = inspect.getsource(Orchestrator._run_metabolism_cycle)
        assert "MethylationCycle" in src
        assert "TranssulfurationCycle" in src
        assert "homocysteine_pool" in src
