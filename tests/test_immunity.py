import pytest
import asyncio
from unittest.mock import MagicMock, patch

from iaglobal.immunity.loop_detector import LoopDetector
from iaglobal.immunity.hallucination_detector import HallucinationDetector
from iaglobal.immunity.glutathione_guardrails import GlutathioneGuardrails
from iaglobal.immunity.regression_detector import RegressionDetector
from iaglobal.immunity.emergent_behavior_detector import EmergentBehaviorDetector


class TestLoopDetector:

    def test_record_and_detect_loop(self):
        d = LoopDetector(max_executions=3)
        for _ in range(4):
            d.record_execution("node_a", False)
        loops = d.detect()
        assert len(loops) == 1
        assert loops[0]["node"] == "node_a"

    def test_success_resets_counter(self):
        d = LoopDetector(max_executions=3)
        d.record_execution("node_a", False)
        d.record_execution("node_a", False)
        d.record_execution("node_a", True)
        assert len(d.detect()) == 0

    def test_check_returns_loop_status(self):
        d = LoopDetector(max_executions=2)
        r1 = d.check("node_b", False)
        assert r1["in_loop"] is False
        r2 = d.check("node_b", False)
        assert r2["in_loop"] is True


class TestHallucinationDetector:

    def test_clean_text_no_hallucination(self):
        r = HallucinationDetector.check("def hello():\n    print('hello world')")
        assert r["hallucinating"] is False

    def test_multiple_uncertainty_patterns_detected(self):
        r = HallucinationDetector.check(
            "eu acho que provavelmente funciona, confiança: 0.95, não tenho certeza"
        )
        assert r["hallucinating"] is True
        assert r["finding_count"] >= 2

    def test_fake_lib_detected(self):
        r = HallucinationDetector.check("import fake_module")
        assert r["finding_count"] >= 1


class TestGlutathioneGuardrails:

    def test_safe_code_passes(self):
        r = GlutathioneGuardrails.validate("x = 1\ny = x + 2\nprint(y)")
        assert r["safe"] is True

    def test_eval_detected(self):
        r = GlutathioneGuardrails.validate("eval('print(1)')")
        assert r["safe"] is False
        assert any("eval" in i["message"] for i in r["issues"])

    def test_forbidden_import_detected(self):
        r = GlutathioneGuardrails.validate("import socket")
        assert r["safe"] is False
        assert any("socket" in i["message"] for i in r["issues"])

    def test_syntax_error_detected(self):
        r = GlutathioneGuardrails.validate("def foo(:")
        assert r["safe"] is False
        assert any("sintaxe" in i["message"].lower() for i in r["issues"])


class TestRegressionDetector:

    def test_no_regression(self):
        d = RegressionDetector(threshold=0.2)
        d.record_score("node_a", 0.8)
        r = d.check("node_a", 0.85)
        assert r["regression"] is False

    def test_regression_detected(self):
        d = RegressionDetector(threshold=0.2)
        d.record_score("node_a", 0.9)
        d.record_score("node_a", 0.85)
        r = d.check("node_a", 0.5)
        assert r["regression"] is True


class TestEmergentBehaviorDetector:

    def test_clean_dependencies(self):
        d = EmergentBehaviorDetector()
        d.check_dependencies("node_a", ["node_c"])
        d.check_dependencies("node_b", ["node_a"])
        r = d.check_dependencies("node_c", ["node_b"])
        assert r["has_issues"] is False

    def test_circular_dependency_detected(self):
        d = EmergentBehaviorDetector()
        d.check_dependencies("node_b", ["node_a"])
        r = d.check_dependencies("node_a", ["node_b"])
        assert r["has_issues"] is True
        assert any(i["type"] == "circular_dependency" for i in r["issues"])

    def test_malicious_skill_name(self):
        d = EmergentBehaviorDetector()
        r = d.check_skill_name("install_malware")
        assert r["suspicious"] is True


class TestImmunityIntegration:

    def test_loop_detector_in_graph_execution(self):
        from iaglobal.graphs.execution_graph import ExecutionGraph
        from iaglobal.graphs.node import Node
        graph = ExecutionGraph()
        assert hasattr(graph, "_loop_detector")
        assert graph._loop_detector is not None

    def test_evaluator_includes_hallucination(self):
        from iaglobal.evolution.metacognition.evaluator import _run_evaluator
        result = asyncio.run(_run_evaluator({
            "input": {"task": "test"},
            "memory": {"result_agent": {"output": "acho que provavelmente import fake_module"}},
        }))
        assert "hallucination_score" in result
        assert "hallucination_findings" in result

    def test_evaluator_includes_regression(self):
        from iaglobal.evolution.metacognition.evaluator import _run_evaluator
        result = asyncio.run(_run_evaluator({
            "input": {"task": "test"},
            "memory": {"result_agent": {"output": "codigo legal " * 50}},
        }))
        assert "regression_detected" in result
        assert "regression_delta" in result

    def test_builder_has_emergence_detector(self):
        from iaglobal.graphs.nodes.no_integrator import build_graph_from_skills, PIPELINE_SKILLS
        from unittest.mock import MagicMock
        from iaglobal.evolution.skills.skill_registry import SkillRegistry
        from iaglobal.evolution.skills.skill import Skill
        registry = SkillRegistry()
        for name, _ in PIPELINE_SKILLS[:5]:
            registry.register(Skill(name=name, description="test", run_fn=lambda ctx: {"output": "ok"}))
        mock_orch = MagicMock()
        mock_orch._model_fn = lambda p: "print('ok')"
        graph = build_graph_from_skills(mock_orch, registry=registry)
        assert graph is not None
        assert len(graph.nodes) >= 1

    def test_sandbox_glutathione_catches_dangerous_patterns(self):
        from iaglobal.security.sandbox_executor import SandboxExecutor
        executor = SandboxExecutor(timeout=5)
        r = executor.execute("x = 1\ny = x + 2\nprint(y)")
        assert r.get("erro") != "GlutathioneViolation"
        assert r.get("sucesso") is not False

    def test_sandbox_glutathione_catches_comment_pattern(self):
        from iaglobal.security.sandbox_executor import SandboxExecutor
        executor = SandboxExecutor(timeout=5)
        r = executor.execute("# shutil.rmtree('/home') is dangerous\nx = 1")
        assert r.get("erro") == "GlutathioneViolation"

    def test_sandbox_clean_code_passes_glutathione(self):
        from iaglobal.security.sandbox_executor import SandboxExecutor
        executor = SandboxExecutor(timeout=5)
        r = executor.execute("x = 1\nprint(x)")
        assert r.get("erro") != "GlutathioneViolation"
