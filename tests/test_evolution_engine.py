"""Testes dedicados do Evolution Engine:
- FastEvolutionStrategy / DeepEvolutionStrategy
- Strategy-aware engine (selector com pressure)
- _make_deterministic_run_fn
- 12 realocação de skills placeholder
- CLI cache refatorado
"""

import os
import sys
import asyncio
import inspect
import time
import pytest
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════
# 1. EvolutionStrategy — parâmetros corretos
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionStrategy:

    def test_fast_strategy_params(self):
        from iaglobal.evolution.evolutionruntime import FastEvolutionStrategy
        s = FastEvolutionStrategy()
        assert s.name == "fast"
        assert s.mutation_rate == 0.3
        assert s.crossover_rate == 0.5
        assert s.selection_pressure == 0.3
        assert s.interval == 30
        assert s.exploration_rate == 0.4

    def test_deep_strategy_params(self):
        from iaglobal.evolution.evolutionruntime import DeepEvolutionStrategy
        s = DeepEvolutionStrategy()
        assert s.name == "deep"
        assert s.mutation_rate == 0.05
        assert s.crossover_rate == 0.1
        assert s.selection_pressure == 0.7
        assert s.interval == 120
        assert s.exploration_rate == 0.05

    def test_fast_is_subclass(self):
        from iaglobal.evolution.evolutionruntime import EvolutionStrategy, FastEvolutionStrategy
        assert isinstance(FastEvolutionStrategy(), EvolutionStrategy)

    def test_deep_is_subclass(self):
        from iaglobal.evolution.evolutionruntime import EvolutionStrategy, DeepEvolutionStrategy
        assert isinstance(DeepEvolutionStrategy(), EvolutionStrategy)

    def test_strategy_to_dict(self):
        from iaglobal.evolution.evolutionruntime import FastEvolutionStrategy
        d = FastEvolutionStrategy().to_dict()
        assert d["name"] == "fast"
        assert d["mutation_rate"] == 0.3
        assert "description" in d

    def test_base_strategy_defaults(self):
        from iaglobal.evolution.evolutionruntime import EvolutionStrategy
        s = EvolutionStrategy()
        assert s.name == "base"
        assert s.mutation_rate == 0.1
        assert s.selection_pressure == 0.5
        assert s.interval == 60

    def test_strategies_different_intervals(self):
        from iaglobal.evolution.evolutionruntime import FastEvolutionStrategy, DeepEvolutionStrategy
        f = FastEvolutionStrategy()
        d = DeepEvolutionStrategy()
        assert f.interval < d.interval
        assert f.mutation_rate > d.mutation_rate
        assert f.selection_pressure < d.selection_pressure

    def test_fast_inhibits_deep_properties(self):
        from iaglobal.evolution.evolutionruntime import FastEvolutionStrategy, DeepEvolutionStrategy
        f = FastEvolutionStrategy()
        d = DeepEvolutionStrategy()
        assert f.exploration_rate > d.exploration_rate
        assert f.crossover_rate > d.crossover_rate


# ═══════════════════════════════════════════════════════════════════
# 2. EvolutionEngine — strategy-aware
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionEngineStrategy:

    def test_evolve_accepts_strategy(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        sig = inspect.signature(EvolutionEngine.evolve)
        assert "strategy" in sig.parameters

    def test_evolve_async_accepts_strategy(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        sig = inspect.signature(EvolutionEngine.evolve_async)
        assert "strategy" in sig.parameters

    def test_strategy_parameter_default_none(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        sig = inspect.signature(EvolutionEngine.evolve)
        param = sig.parameters["strategy"]
        assert param.default is None

    def test_select_survivors_accepts_pressure(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        sig = inspect.signature(EvolutionEngine._select_survivors)
        assert "pressure" in sig.parameters

    def test_select_survivors_pressure_default_none(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine
        sig = inspect.signature(EvolutionEngine._select_survivors)
        assert sig.parameters["pressure"].default is None


# ═══════════════════════════════════════════════════════════════════
# 3. _make_deterministic_run_fn
# ═══════════════════════════════════════════════════════════════════

class TestDeterministicRunFn:

    def test_creates_callable(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "hello {name}")
        assert callable(fn)
        assert asyncio.iscoroutinefunction(fn)

    @pytest.mark.asyncio
    async def test_basic_substitution(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "hello {name}")
        result = await fn({"name": "world"})
        assert result["success"]
        assert "world" in result["output"]

    @pytest.mark.asyncio
    async def test_missing_key(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "hello {name}")
        result = await fn({})
        assert result["success"]
        assert "{name}" in result["output"]

    @pytest.mark.asyncio
    async def test_empty_template(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "")
        result = await fn({"x": "y"})
        assert result["success"]
        assert result["strategy_used"] == "deterministic_empty"

    @pytest.mark.asyncio
    async def test_nested_context_key(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "val={input.x}")
        result = await fn({"input": {"x": "42"}})
        assert result["success"]
        assert "42" in result["output"]

    @pytest.mark.asyncio
    async def test_strategy_label(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "data")
        result = await fn({"x": "y"})
        assert result["strategy_used"] == "deterministic"

    def test_returns_async_function(self):
        from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn
        fn = _make_deterministic_run_fn("test", "plain")
        assert asyncio.iscoroutinefunction(fn)


# ═══════════════════════════════════════════════════════════════════
# 4. Skills placeholder — implementações reais
# ═══════════════════════════════════════════════════════════════════

class TestSkillsReplacement:

    def _get_skill_run_fn(self, skill_name: str):
        from iaglobal.evolution.skills.skill import _BUILTIN_SKILLS
        for s in _BUILTIN_SKILLS:
            if s.name == skill_name:
                return s.run_fn
        return None

    def test_architecture_validator_has_real_fn(self):
        fn = self._get_skill_run_fn("architecture_validator")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_frontend_builder_has_real_fn(self):
        fn = self._get_skill_run_fn("frontend_builder")
        assert fn is not None
        assert callable(fn)

    def test_backend_builder_has_real_fn(self):
        fn = self._get_skill_run_fn("backend_builder")
        assert fn is not None
        assert callable(fn)

    def test_api_builder_has_real_fn(self):
        fn = self._get_skill_run_fn("api_builder")
        assert fn is not None
        assert callable(fn)

    def test_release_has_real_fn(self):
        fn = self._get_skill_run_fn("release")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_test_generator_has_real_fn(self):
        fn = self._get_skill_run_fn("test_generator")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_validator_has_real_fn(self):
        fn = self._get_skill_run_fn("validator")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_fix_validator_has_real_fn(self):
        fn = self._get_skill_run_fn("fix_validator")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_security_design_has_real_fn(self):
        fn = self._get_skill_run_fn("security_design")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_deployment_plan_has_real_fn(self):
        fn = self._get_skill_run_fn("deployment_plan")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_performance_design_has_real_fn(self):
        fn = self._get_skill_run_fn("performance_design")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)

    def test_retrospective_has_real_fn(self):
        fn = self._get_skill_run_fn("retrospective")
        assert fn is not None
        assert asyncio.iscoroutinefunction(fn)


    def test_no_placeholder_references_in_skills(self):
        from iaglobal.evolution.skills.skill import _BUILTIN_SKILLS
        for s in _BUILTIN_SKILLS:
            if s.run_fn is not None:
                fn_name = getattr(s.run_fn, "__name__", str(s.run_fn))
                assert "_placeholder_run" not in fn_name, \
                    f"Skill '{s.name}' ainda usa _placeholder_run"


    @pytest.mark.asyncio
    async def test_architecture_validator_execution(self):
        from iaglobal.evolution.skills.skill import _run_architecture_validator
        result = await _run_architecture_validator({"technology_selection": "Django + PostgreSQL"})
        assert result["success"]
        assert "architecture_validation" in result
        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    async def test_release_execution(self):
        from iaglobal.evolution.skills.skill import _run_release
        result = await _run_release({"code": "print('hello')", "documentation": "README"})
        assert result["success"]
        assert "changelog" in result
        assert result["version"].startswith("1.0.")

    @pytest.mark.asyncio
    async def test_test_generator_execution(self):
        from iaglobal.evolution.skills.skill import _run_test_generator
        result = await _run_test_generator({"backend_code": "def foo(): pass"})
        assert result["success"]
        assert "Test" in result["output"]

    @pytest.mark.asyncio
    async def test_validator_execution(self):
        from iaglobal.evolution.skills.skill import _run_validator
        result = await _run_validator({"code": "x = 1\n"})
        assert result["success"]
        assert "issues" in result

    @pytest.mark.asyncio
    async def test_security_design_execution(self):
        from iaglobal.evolution.skills.skill import _run_security_design
        result = await _run_security_design({"task": "Build a web app"})
        assert result["success"]
        assert "security_design_report" in result

    @pytest.mark.asyncio
    async def test_deployment_plan_execution(self):
        from iaglobal.evolution.skills.skill import _run_deployment_plan
        result = await _run_deployment_plan({"code": "print('hi')"})
        assert result["success"]
        assert "deployment_plan" in result

    @pytest.mark.asyncio
    async def test_performance_design_execution(self):
        from iaglobal.evolution.skills.skill import _run_performance_design
        result = await _run_performance_design({"architecture": "microservices"})
        assert result["success"]
        assert "performance_design_report" in result

    @pytest.mark.asyncio
    async def test_retrospective_execution(self):
        from iaglobal.evolution.skills.skill import _run_retrospective
        result = await _run_retrospective({"metrics_report": "all good"})
        assert result["success"]
        assert "lessons_learned" in result

    @pytest.mark.asyncio
    async def test_frontend_builder_execution(self):
        from iaglobal.evolution.skills.skill import _run_code_builder
        result = await _run_code_builder("frontend", {"execution_plan": "Build UI"})
        assert result["success"]
        assert "frontend_code" in result

    @pytest.mark.asyncio
    async def test_backend_builder_execution(self):
        from iaglobal.evolution.skills.skill import _run_code_builder
        result = await _run_code_builder("backend", {"execution_plan": "Build API"})
        assert result["success"]
        assert "backend_code" in result

    @pytest.mark.asyncio
    async def test_fix_validator_execution(self):
        from iaglobal.evolution.skills.skill import _run_fix_validator
        result = await _run_fix_validator({"code": "fixed = True"})
        assert result["success"]
        assert "fix_validation_report" in result


# ═══════════════════════════════════════════════════════════════════
# 5. Runtime set_strategy — altera intervalo
# ═══════════════════════════════════════════════════════════════════

class TestRuntimeStrategy:

    def test_set_strategy_changes_interval(self):
        from iaglobal.evolution.evolutionruntime import EvolutionRuntime, FastEvolutionStrategy, DeepEvolutionStrategy
        rt = EvolutionRuntime.__new__(EvolutionRuntime)
        rt._initialized = False
        rt.__init__(interval=60)
        old_interval = rt.interval
        rt.set_strategy(DeepEvolutionStrategy())
        assert rt.interval == 120
        assert rt.interval != old_interval
        rt.set_strategy(FastEvolutionStrategy())
        assert rt.interval == 30

    def test_set_strategy_updates_name(self):
        from iaglobal.evolution.evolutionruntime import EvolutionRuntime, FastEvolutionStrategy, DeepEvolutionStrategy
        rt = EvolutionRuntime.__new__(EvolutionRuntime)
        rt._initialized = False
        rt.__init__()
        rt.set_strategy(DeepEvolutionStrategy())
        assert rt.current_strategy.name == "deep"

    def test_status_includes_strategy_name(self):
        from iaglobal.evolution.evolutionruntime import EvolutionRuntime, FastEvolutionStrategy
        rt = EvolutionRuntime.__new__(EvolutionRuntime)
        rt._initialized = False
        rt.__init__()
        status = rt.status()
        assert "strategy" in status
        assert status["strategy"] == "FastEvolutionStrategy"


# ═══════════════════════════════════════════════════════════════════
# 6. CLI Cache — module-level globals existem (refatoração mantém API)
# ═══════════════════════════════════════════════════════════════════

class TestCliCache:

    def test_cache_class_exists(self):
        from iaglobal.cli import evolution_lab as cli
        assert hasattr(cli, "_EvolutionLabCache")
        assert hasattr(cli, "_LAB_CACHE")

    def test_store_and_load(self):
        from iaglobal.cli import evolution_lab as cli
        import argparse
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.evolution.evolutionengine import EvolutionEngine

        g = ExecutionGraph()
        e = EvolutionEngine(g)
        cli._store_engine(g, e)
        loaded_g, loaded_e = cli._load_or_init(argparse.Namespace(pipeline=False, mutation_rate=0.3))
        assert loaded_g is g
        assert loaded_e is e
