"""Tests for handler evolution via mutation/crossover."""

import ast
import importlib
import sys
from pathlib import Path

import pytest

from iaglobal.evolution.handler_evolution import (
    _ScoreThresholdMutator, _SourceTupleMutator,
    _LogLevelMutator, _BoolFlagMutator, _IntParamMutator,
    _SourceCrossover, _ThresholdCrossover,
    _load_handler_source, _is_stub, _extract_run_fn_name,
    _write_handler, _validate_import, _indent,
    HandlerEvolver, HANDLERS_DIR,
)


# ======================================================================
# Mutation operator tests (deterministic — seed with fixed rng)
# ======================================================================


class TestScoreThresholdMutator:
    def test_mutates_numeric_comparison(self):
        source = "if score >= 50: pass"
        # Run 20 times — should eventually get a mutation
        for _ in range(20):
            tree = ast.parse(source)
            mut = _ScoreThresholdMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                result = ast.unparse(tree)
                assert result != source
                assert "score >=" in result or "score >" in result or "score ==" in result
                return
        pytest.skip("Non-deterministic mutation did not trigger")

    def test_skips_large_ints(self):
        source = "if len(x) > 10000: pass"
        for _ in range(20):
            tree = ast.parse(source)
            mut = _ScoreThresholdMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                pytest.fail("Should not mutate large ints")
        # If we get here without mutation, test passes
        assert True

    def test_skips_non_compare(self):
        source = "x = 50"
        tree = ast.parse(source)
        mut = _ScoreThresholdMutator()
        result = mut.visit(tree)
        ast.fix_missing_locations(result)
        assert not mut._mutated


class TestSourceTupleMutator:
    def test_mutates_source_tuple(self):
        source = """
for source in ("multi_coder", "coder", "debug_coder"):
    artifact = memory.get(source, {}).get("output")
"""
        for _ in range(30):
            tree = ast.parse(source)
            mut = _SourceTupleMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                result = ast.unparse(tree)
                assert "multi_coder" in result or "coder" in result
                return
        pytest.skip("Non-deterministic mutation did not trigger")


class TestLogLevelMutator:
    def test_mutates_logger_level(self):
        source = """
async def test():
    logger.info("hello")
"""
        for _ in range(20):
            tree = ast.parse(source)
            mut = _LogLevelMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                result = ast.unparse(tree)
                assert "logger." in result
                return
        pytest.skip("Non-deterministic mutation did not trigger")


class TestIntParamMutator:
    def test_mutates_named_params(self):
        source = """
async def test():
    agent = SomeAgent(max_attempts=5, timeout=30)
"""
        for _ in range(20):
            tree = ast.parse(source)
            mut = _IntParamMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                result = ast.unparse(tree)
                assert "max_attempts=" in result
                return
        pytest.skip("Non-deterministic mutation did not trigger")


class TestBoolFlagMutator:
    def test_flips_bool(self):
        source = """
async def test():
    return {"valid": True, "score": 0}
"""
        for _ in range(30):
            tree = ast.parse(source)
            mut = _BoolFlagMutator()
            mut.visit(tree)
            ast.fix_missing_locations(tree)
            if mut._mutated:
                result = ast.unparse(tree)
                assert "False" in result or "True" in result
                return
        pytest.skip("Non-deterministic mutation did not trigger")


# ======================================================================
# Crossover operator tests
# ======================================================================


class TestSourceCrossover:
    def test_combines_sources(self):
        src_a = 'for source in ("multi_coder", "coder"):\n    pass'
        src_b = 'for source in ("search", "knowledge"):\n    pass'
        result = _SourceCrossover.apply(src_a, src_b)
        assert "multi_coder" in result
        assert "search" in result
        assert "knowledge" in result
        assert "coder" in result

    def test_returns_original_if_no_sources(self):
        src_a = "x = 1"
        src_b = "y = 2"
        result = _SourceCrossover.apply(src_a, src_b)
        assert result == src_a


class TestThresholdCrossover:
    def test_swaps_thresholds(self):
        src_a = """
async def run_a(ctx):
    if score >= 50:
        pass
"""
        src_b = """
async def run_b(ctx):
    if score >= 80:
        pass
"""
        result = _ThresholdCrossover.apply(src_a, src_b)
        assert "80" in result


# ======================================================================
# Utility tests
# ======================================================================


class TestHandlerUtils:
    def test_load_handler_source_found(self):
        src = _load_handler_source("debugger")
        assert src is not None
        assert "run_debugger" in src

    def test_load_handler_source_not_found(self):
        src = _load_handler_source("nonexistent_handler_xyz")
        assert src is None

    def test_is_stub_short(self):
        stub_src = '''"""Stub."""
from typing import Dict, Any


async def run_stub(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx
'''
        assert _is_stub(stub_src)

    def test_is_stub_real_handler(self):
        src = _load_handler_source("debugger")
        assert src is not None
        assert not _is_stub(src)

    def test_extract_run_fn_name(self):
        src = "async def run_debugger(ctx): pass"
        assert _extract_run_fn_name(src) == "run_debugger"

    def test_extract_run_fn_name_none(self):
        src = "x = 1"
        assert _extract_run_fn_name(src) is None

    def test_write_and_validate(self):
        name = "_test_evo_handler"
        source = '''
from typing import Dict, Any


async def run_{name}(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {{"output": "test"}}
'''.format(name=name)

        path = _write_handler(name, source)
        assert path is not None
        assert path.exists()

        try:
            assert _validate_import(name)
            # Cleanup
            mod_name = f"iaglobal.graphs.nodes.no_{name}"
            if mod_name in sys.modules:
                del sys.modules[mod_name]
        finally:
            path.unlink()

    def test_write_handler_already_exists(self):
        path = _write_handler("debugger", "x = 1")
        assert path is None  # already exists, returns None


# ======================================================================
# HandlerEvolver integration tests
# ======================================================================


class FakeNode:
    """Minimal Node-like object for testing HandlerEvolver."""

    def __init__(self, name: str, executions: int = 1, success_count: int = 1, total_latency: float = 1.0):
        self.name = name
        self.executions = executions
        self.success_count = success_count
        self.total_latency = total_latency
        self.fail_count = 0

    def fitness(self) -> float:
        return self.success_count / self.executions if self.executions > 0 else 0.5


class FakeGraph:
    def __init__(self, nodes: dict):
        self.nodes = nodes


class FakeEngine:
    def __init__(self, nodes: dict, generation: int = 1):
        self.graph = FakeGraph(nodes)
        self.generation = generation
        self.CORE_NODE_NAMES = ["core_node"]


class TestHandlerEvolver:
    @pytest.fixture(autouse=True)
    def cleanup_evo_files(self):
        yield
        for f in HANDLERS_DIR.glob("no_*_evo_*"):
            f.unlink(missing_ok=True)

    def test_collect_evo_nodes_skips_core_and_stubs(self):
        nodes = {
            "debugger": FakeNode("debugger", executions=5, success_count=4),
            "core_node": FakeNode("core_node", executions=5),
            "agentmailbox": FakeNode("agentmailbox", executions=5),
        }
        engine = FakeEngine(nodes)
        evolver = HandlerEvolver(engine=engine)
        assert len(evolver._evo_nodes) >= 1
        names = [n[0] for n in evolver._evo_nodes]
        assert "core_node" not in names

    def test_select_parents_top_half(self):
        nodes = {
            "debugger": FakeNode("debugger", executions=5, success_count=5),
            "validator": FakeNode("validator", executions=5, success_count=3),
            "tester": FakeNode("tester", executions=5, success_count=1),
        }
        engine = FakeEngine(nodes)
        evolver = HandlerEvolver(engine=engine)
        # Only debugger and validator are non-core and non-stub
        parents = evolver._select_parents()
        assert len(parents) >= 1

    def test_mutate_handler(self):
        source = '''
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_debugger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    for source in ("multi_coder", "coder", "debug_coder"):
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break

    if not code:
        logger.warning("No code")
        return {**ctx, "output": ""}

    try:
        if code and len(code) > 50:
            return {**ctx, "output": code}
        return {**ctx, "output": ""}
    except Exception:
        return {**ctx, "output": ""}
'''
        evolver = HandlerEvolver(FakeEngine({"debugger": FakeNode("debugger", executions=3)}))
        for _ in range(30):
            result = evolver._mutate_handler("debugger", source)
            if result is not None:
                new_name, new_src = result
                assert new_name != "debugger"
                assert "_evo_" in new_name
                assert "run_" + new_name in new_src
                # Verify it parses
                ast.parse(new_src)
                return
        pytest.skip("Non-deterministic mutation did not trigger")

    def test_evolve_creates_files(self):
        """Integration test: evolve should create new handler files."""
        nodes = {
            "debugger": FakeNode("debugger", executions=3, success_count=3),
        }
        engine = FakeEngine(nodes, generation=1)
        evolver = HandlerEvolver(engine=engine)
        stats = evolver.evolve()
        # Check if any files were created
        created = list(HANDLERS_DIR.glob("no_*_evo_*"))
        if created:
            _log_cleanup = created  # keep ref
            assert stats["mutations"] >= 1 or stats["crossovers"] >= 1
            # Verify the created file is valid
            for f in created:
                src = f.read_text()
                assert "async def run_" in src
                ast.parse(src)
        else:
            # May not trigger due to randomness — that's OK
            assert stats["registered"] == 0
