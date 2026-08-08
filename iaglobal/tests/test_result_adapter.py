# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for result_adapter — dict | NodeResult compatibility layer."""

from iaglobal.core.node_result import NodeResult
from iaglobal.core.artifact import GeneratedArtifact, ArtifactKind
from iaglobal.core.result_adapter import (
    extract_output,
    extract_artifact,
    extract_metadata,
    extract_errors,
    is_successful,
    extract_metric,
    is_skipped,
    extract_one,
    extract_field,
)


class TestExtractOutput:
    def test_node_result(self):
        r = NodeResult(success=True, output="print('ok')")
        assert extract_output(r) == "print('ok')"

    def test_node_result_no_output(self):
        r = NodeResult(success=True)
        assert extract_output(r) == ""

    def test_dict_legacy(self):
        assert extract_output({"output": "x"}) == "x"

    def test_dict_no_output(self):
        assert extract_output({}) == ""

    def test_string(self):
        assert extract_output("code") == "code"

    def test_none(self):
        assert extract_output(None) == ""


class TestExtractArtifact:
    def test_node_result_with_explicit_artifact(self):
        a = GeneratedArtifact(content="<h1>oi</h1>", kind=ArtifactKind.HTML)
        r = NodeResult(success=True, artifacts=[a])
        assert extract_artifact(r) is a

    def test_node_result_output_fallback(self):
        r = NodeResult(success=True, output="<h1>oi</h1>")
        art = extract_artifact(r)
        assert art is not None
        assert art.kind == ArtifactKind.HTML

    def test_dict_with_artifact(self):
        a = GeneratedArtifact(content="x", kind=ArtifactKind.CODE)
        assert extract_artifact({"artifact": a}) is a

    def test_dict_output_fallback(self):
        art = extract_artifact({"output": "import os"})
        assert art is not None
        assert art.kind == ArtifactKind.CODE

    def test_string(self):
        art = extract_artifact("<h1>x</h1>")
        assert art is not None
        assert art.kind == ArtifactKind.HTML

    def test_none(self):
        assert extract_artifact(None) is None


class TestExtractMetadata:
    def test_node_result(self):
        r = NodeResult(success=True, metadata={"qa_decision": "approved"})
        assert extract_metadata(r) == {"qa_decision": "approved"}

    def test_node_result_empty(self):
        r = NodeResult(success=True)
        assert extract_metadata(r) == {}

    def test_dict(self):
        assert extract_metadata({"metadata": {"a": 1}}) == {"a": 1}

    def test_dict_no_metadata(self):
        assert extract_metadata({"output": "x"}) == {}

    def test_non_dict(self):
        assert extract_metadata("xyz") == {}


class TestExtractErrors:
    def test_node_result(self):
        r = NodeResult(success=False, errors=["fail", "x"])
        assert extract_errors(r) == ["fail", "x"]

    def test_dict_errors_list(self):
        assert extract_errors({"errors": ["a"]}) == ["a"]

    def test_dict_singular_error(self):
        assert extract_errors({"error": "boom"}) == ["boom"]

    def test_dict_no_errors(self):
        assert extract_errors({}) == []


class TestIsSuccessful:
    def test_node_result_true(self):
        assert is_successful(NodeResult(success=True)) is True

    def test_node_result_false(self):
        assert is_successful(NodeResult(success=False)) is False

    def test_dict_true(self):
        assert is_successful({"success": True}) is True

    def test_dict_false_default(self):
        assert is_successful({}) is False


class TestExtractMetric:
    def test_node_result(self):
        r = NodeResult(success=True, metrics={"latency": 1.5})
        assert extract_metric(r, "latency") == 1.5

    def test_node_result_default(self):
        r = NodeResult(success=True)
        assert extract_metric(r, "latency", 0.0) == 0.0

    def test_dict_execution_metrics(self):
        assert extract_metric({"execution_metrics": {"latency": 1.0}}, "latency") == 1.0

    def test_dict_metrics(self):
        assert extract_metric({"metrics": {"latency": 1.0}}, "latency") == 1.0


class TestIsSkipped:
    def test_node_result(self):
        r = NodeResult(success=True, metadata={"skipped": True})
        assert is_skipped(r) is True

    def test_dict_true(self):
        assert is_skipped({"skipped": True}) is True

    def test_dict_false(self):
        assert is_skipped({"skipped": False}) is False

    def test_null_default_false(self):
        assert is_skipped({}) is False


class TestExtractField:
    def test_node_result_attribute(self):
        nr = NodeResult(success=True, output="code")
        assert extract_field(nr, "success") is True
        assert extract_field(nr, "output") == "code"

    def test_node_result_metadata_fallback(self):
        nr = NodeResult(success=True, metadata={"detected_domain": "web"})
        assert extract_field(nr, "detected_domain") == "web"

    def test_node_result_metrics_fallback(self):
        nr = NodeResult(success=True, metrics={"latency": 1.5})
        assert extract_field(nr, "latency") == 1.5

    def test_node_result_default_when_absent(self):
        nr = NodeResult(success=True)
        assert extract_field(nr, "code", "fallback") == "fallback"

    def test_dict_legacy(self):
        d = {"success": True, "output": "x", "custom": "y"}
        assert extract_field(d, "success") is True
        assert extract_field(d, "output") == "x"
        assert extract_field(d, "custom") == "y"
        assert extract_field(d, "missing", 42) == 42


class TestExtractOne:
    def test_present(self):
        nr = NodeResult(success=True, output="x")
        assert extract_one({"coder": nr}, "coder") is nr

    def test_missing_returns_default(self):
        assert extract_one({"x": 1}, "y", "default") == "default"

    def test_non_dict_memory(self):
        assert extract_one(None, "x", "default") == "default"


class TestGoldenPathContract:
    """Verifica que NodeResult e dict legado produzem o mesmo resultado."""

    def test_generate_code_node_result(self):
        nr = NodeResult(success=True, output="print('hello')")
        assert extract_output(nr) == "print('hello')"
        assert is_successful(nr) is True
        assert extract_artifact(nr).kind == ArtifactKind.CODE

    def test_generate_code_dict(self):
        d = {"success": True, "output": "print('hello')"}
        assert extract_output(d) == "print('hello')"
        assert is_successful(d) is True
        assert extract_artifact(d).kind == ArtifactKind.CODE
