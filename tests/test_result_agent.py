"""Testes do ResultAgent — verifica registro de extractors,
dispatcher async/sync, contrato de saída e persistência.

Cobre:
1. Todos os extractors registrados sem duplicidade de agent_name
2. Extractors async detectados por iscoroutinefunction
3. Dispatcher executa sync e async corretamente
4. build_result produz contrato com campos esperados
5. _persist_contract salva JSON em RESULTS_DIR
6. Nó no_result_agent chama build_result com await
7. Conflitos: agente com múltiplos extractors
"""
import os
import sys
import json
import asyncio
import inspect
import pytest
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.agents.result_agent import ResultAgent


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def agent():
    return ResultAgent()


@pytest.fixture
def ctx():
    return {
        "execution_id": "test-123",
        "coder": {"output": "print('hello')", "language": "python", "tests_generated": True},
        "documentation": {"readme": "# Test"},
        "release": {"changelog": "v1.0.0"},
        "metrics": {"durations": {"step1": 1.5}, "quality_scores": {"code": 8}},
        "optimization": {"patterns": ["cpu_loop"]},
        "security_audit": {"vulnerabilities": []},
        "planner": {"output": "plan"},
        "search": {"output": "results"},
        "critic": {"output": "review"},
        "validator": {"output": "valid"},
        "multi_coder": {"output": "code", "language": "python"},
    }


# ═══════════════════════════════════════════════════════════════════
# 1. Registro de extractors — sem duplicidade
# ═══════════════════════════════════════════════════════════════════

class TestExtractorRegistration:

    def test_all_extractors_registered(self, agent):
        assert len(agent._summary_extractors) == 14

    def test_no_duplicate_agent_names(self, agent):
        assert len(set(agent._summary_extractors.keys())) == len(agent._summary_extractors)

    def test_expected_agents_present(self, agent):
        expected = {
            "documentation", "release", "metrics", "optimization",
            "coder", "security_audit", "planner", "search",
            "review", "multi_coder", "critic", "validator",
            "ast_validator", "security",
        }
        assert expected == set(agent._summary_extractors.keys())

    def test_security_and_security_audit_separate(self, agent):
        assert agent._summary_extractors["security"] is not agent._summary_extractors["security_audit"]
        assert agent._summary_extractors["security"].__func__ is agent._extract_security_summary.__func__


# ═══════════════════════════════════════════════════════════════════
# 2. Extractors async detectados
# ═══════════════════════════════════════════════════════════════════

class TestAsyncExtractors:

    ASYNC_EXTRACTORS = {
        "_extract_docs_summary",
        "_extract_release_summary",
        "_extract_metrics_summary",
        "_extract_optimization_summary",
        "_extract_code_summary",
        "_extract_security_summary",
    }

    SYNC_EXTRACTORS = {
        "_extract_generic_summary",
    }

    def test_six_extractors_are_coroutines(self, agent):
        for name in self.ASYNC_EXTRACTORS:
            func = getattr(agent, name)
            assert inspect.iscoroutinefunction(func), f"{name} should be async"

    def test_generic_is_sync(self, agent):
        for name in self.SYNC_EXTRACTORS:
            func = getattr(agent, name)
            assert not inspect.iscoroutinefunction(func), f"{name} should be sync"

    def test_registered_async_extractors_detected(self, agent):
        for agent_name, extractor in agent._summary_extractors.items():
            if extractor.__name__ in self.ASYNC_EXTRACTORS:
                assert inspect.iscoroutinefunction(extractor), f"{agent_name} registered async func not detected as coroutine"


# ═══════════════════════════════════════════════════════════════════
# 3. Dispatcher executa sync e async
# ═══════════════════════════════════════════════════════════════════

class TestDispatcher:

    @pytest.mark.asyncio
    async def test_dispatch_async_extractor(self, agent):
        result = await agent._call_summary_extractor("documentation", {"readme": "# doc"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert "documentation" in result[0].lower()

    @pytest.mark.asyncio
    async def test_dispatch_sync_extractor(self, agent):
        result = await agent._call_summary_extractor("planner", {"output": "plan"})
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dispatch_unknown_agent_falls_to_generic(self, agent):
        result = await agent._call_summary_extractor("unknown_agent", {"output": "data"})
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_dispatch_coder_with_tests(self, agent):
        result = await agent._call_summary_extractor("coder", {"language": "python", "tests_generated": True})
        assert "Code" in result[0]
        assert result[1] == []

    @pytest.mark.asyncio
    async def test_dispatch_coder_without_tests(self, agent):
        result = await agent._call_summary_extractor("coder", {"language": "python", "tests_generated": False})
        assert "Code" in result[0]
        assert "Generate unit tests" in result[1]

    @pytest.mark.asyncio
    async def test_dispatch_security_with_critical(self, agent):
        result = await agent._call_summary_extractor("security_audit", {
            "vulnerabilities": [{"severity": "critical"}, {"severity": "low"}]
        })
        assert "critical" in result[0].lower()
        assert "Immediate security remediation" in result[1]

    @pytest.mark.asyncio
    async def test_dispatch_security_clean(self, agent):
        result = await agent._call_summary_extractor("security_audit", {
            "vulnerabilities": [{"severity": "low"}]
        })
        assert "passed" in result[0].lower()


# ═══════════════════════════════════════════════════════════════════
# 4. build_result produz contrato completo
# ═══════════════════════════════════════════════════════════════════

class TestBuildResult:

    @pytest.mark.asyncio
    async def test_contract_has_expected_keys(self, agent, ctx):
        contract = await agent.build_result(ctx)
        assert isinstance(contract, dict)
        assert "version" in contract
        assert "timestamp" in contract
        assert "execution_id" in contract
        assert contract["execution_id"] == "test-123"
        assert "final_result" in contract
        assert "summary" in contract
        assert "next_steps" in contract
        assert "health" in contract

    @pytest.mark.asyncio
    async def test_contract_version(self, agent, ctx):
        contract = await agent.build_result(ctx)
        assert contract["version"] == "3.0.0"

    @pytest.mark.asyncio
    async def test_contract_health_structure(self, agent, ctx):
        contract = await agent.build_result(ctx)
        health = contract["health"]
        assert "total_agents" in health
        assert "successful_agents" in health
        assert "failed_agents" in health
        assert "success_rate" in health
        assert 0 <= health["success_rate"] <= 100

    @pytest.mark.asyncio
    async def test_contract_final_result_has_checksum(self, agent, ctx):
        contract = await agent.build_result(ctx)
        fr = contract["final_result"]
        assert fr["status"] == "completed"
        assert isinstance(fr["checksum"], str)
        assert len(fr["checksum"]) == 64

    @pytest.mark.asyncio
    async def test_contract_summary_not_empty(self, agent, ctx):
        contract = await agent.build_result(ctx)
        assert len(contract["summary"]) > 0
        assert "Code" in contract["summary"]

    @pytest.mark.asyncio
    async def test_contract_payload_not_empty(self, agent, ctx):
        contract = await agent.build_result(ctx)
        payload = contract["final_result"]["payload"]
        assert payload, f"payload should contain output string, got: {payload!r}"
        assert isinstance(payload, str)
        assert len(payload) > 0

    @pytest.mark.asyncio
    async def test_contract_with_empty_ctx(self, agent):
        contract = await agent.build_result({})
        assert contract["health"]["success_rate"] == 0.0
        assert contract["health"]["successful_agents"] == 0
        assert contract["summary"] == "Pipeline completed successfully."

    @pytest.mark.asyncio
    async def test_auto_healing_next_steps(self, agent):
        contract = await agent.build_result({})
        assert len(contract["next_steps"]) >= 3


# ═══════════════════════════════════════════════════════════════════
# 5. Persistência do contrato em RESULTS_DIR
# ═══════════════════════════════════════════════════════════════════

class TestPersistence:

    @pytest.mark.asyncio
    async def test_persist_contract_creates_file(self, agent, ctx, tmp_path):
        from iaglobal._paths import RESULTS_DIR
        original = RESULTS_DIR
        try:
            import iaglobal._paths as p
            test_dir = tmp_path / "result"
            test_dir.mkdir(parents=True, exist_ok=True)
            p.RESULTS_DIR = test_dir

            contract = await agent.build_result(ctx)
            files = list(test_dir.glob("contract_*.json"))
            assert len(files) >= 1

            saved = json.loads(files[0].read_text(encoding="utf-8"))
            assert saved["execution_id"] == "test-123"
            assert saved["version"] == "3.0.0"
        finally:
            p.RESULTS_DIR = original

    @pytest.mark.asyncio
    async def test_persist_contract_json_valid(self, agent, ctx, tmp_path):
        from iaglobal._paths import RESULTS_DIR
        original = RESULTS_DIR
        try:
            import iaglobal._paths as p
            p.RESULTS_DIR = tmp_path / "result2"
            p.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

            contract = await agent.build_result(ctx)
            files = list(p.RESULTS_DIR.glob("contract_*.json"))
            assert len(files) == 1
            data = json.loads(files[0].read_text())
            assert data == contract
        finally:
            p.RESULTS_DIR = original


# ═══════════════════════════════════════════════════════════════════
# 6. Nó no_result_agent chama build_result com await
# ═══════════════════════════════════════════════════════════════════

class TestNodeIntegration:

    def test_node_calls_build_result_with_await(self):
        import ast
        node_path = Path(__file__).resolve().parent.parent / "iaglobal" / "graphs" / "nodes" / "no_result_agent.py"
        source = node_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        found_await = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == "build_result":
                            found_await = True
        assert found_await, "no_result_agent.py must call await agent.build_result()"

    def test_node_imports_ResultAgent(self):
        node_path = Path(__file__).resolve().parent.parent / "iaglobal" / "graphs" / "nodes" / "no_result_agent.py"
        source = node_path.read_text(encoding="utf-8")
        assert "from iaglobal.agents.result_agent import ResultAgent" in source


# ═══════════════════════════════════════════════════════════════════
# 7. Conflitos e duplicidade
# ═══════════════════════════════════════════════════════════════════

class TestConflicts:

    def test_re_registration_overwrites_cleanly(self, agent):
        old = agent._summary_extractors["coder"]
        agent._summary_extractors["coder"] = agent._extract_generic_summary
        assert agent._summary_extractors["coder"].__func__ is agent._extract_generic_summary.__func__
        agent._summary_extractors["coder"] = old

    def test_no_agent_name_duplicated_in_register(self, agent):
        names = list(agent._summary_extractors.keys())
        assert len(names) == len(set(names))

    @pytest.mark.asyncio
    async def test_async_extractor_returns_coroutine(self, agent):
        coro = agent._extract_code_summary({"language": "python", "tests_generated": True})
        assert inspect.iscoroutine(coro)
        await coro

    @pytest.mark.asyncio
    async def test_async_extractor_awaited(self, agent):
        result = await agent._extract_code_summary({"language": "python", "tests_generated": True})
        assert result[0] == "Code artifact generated [python]"
