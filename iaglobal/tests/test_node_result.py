# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for NodeResult contract and normalize_node_result boundary."""

from iaglobal.core.node_result import NodeResult, normalize_node_result


class TestNodeResultContract:
    def test_success_field_mandatory(self):
        r = NodeResult(success=True)
        assert r.success is True

    def test_defaults(self):
        r = NodeResult(success=False)
        assert r.output is None
        assert r.artifacts == []
        assert r.warnings == []
        assert r.errors == []
        assert r.metrics == {}
        assert r.metadata == {}

    def test_to_dict_roundtrip(self):
        nr = NodeResult(success=True, output="hello", warnings=["note"])
        d = nr.to_dict()
        assert d["success"] is True
        assert d["output"] == "hello"
        assert d["warnings"] == ["note"]


class TestNormalizeNodeResult:
    def test_passthrough_node_result(self):
        nr = NodeResult(success=True)
        assert normalize_node_result(nr) is nr

    def test_dict_success(self):
        r = normalize_node_result({"success": True, "output": "ok"})
        assert isinstance(r, NodeResult)
        assert r.success is True
        assert r.output == "ok"

    def test_dict_missing_success_defaults_false(self):
        r = normalize_node_result({})
        assert r.success is False

    def test_bool_coercion_string_false(self):
        r = normalize_node_result({"success": "false"})
        assert r.success is False

    def test_bool_coercion_string_true(self):
        r = normalize_node_result({"success": "true"})
        assert r.success is True

    def test_bool_coercion_none(self):
        r = normalize_node_result({"success": None})
        assert r.success is False

    def test_execution_metrics_fallback(self):
        r = normalize_node_result(
            {"success": True, "execution_metrics": {"latency": 1.5}}
        )
        assert r.metrics["latency"] == 1.5

    def test_singular_error_fallback(self):
        r = normalize_node_result({"success": False, "error": "fail"})
        assert "fail" in r.errors

    def test_rejects_non_dict(self):
        try:
            normalize_node_result("bad")
            assert False
        except TypeError:
            pass

    def test_artifact_empty_content_warning(self):
        r = normalize_node_result({"success": True, "artifacts": [{"content": ""}]})
        assert any("sem conteúdo" in w for w in r.warnings)


def test_all_results_write_go_through_normalize():
    """Garantia Fase 2: toda escrita em self.results[] passa por normalize_node_result.
    Varredura estática do source do execution_graph."""
    import ast
    import inspect
    from iaglobal.graphs.execution_graph import ExecutionGraph

    source = inspect.getsource(ExecutionGraph)
    tree = ast.parse(source)

    assignments: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(
                    target.value, ast.Attribute
                ):
                    if (
                        isinstance(target.value.value, ast.Name)
                        and target.value.value.id == "self"
                        and target.value.attr == "results"
                    ):
                        assignments.append(node.lineno)

    for lineno in assignments:
        line = source.split("\n")[lineno - 1].strip()
        assert "normalize_node_result" in line or "NodeResult" in line, (
            f"Linha {lineno}: self.results[] deve passar por normalize_node_result\n  {line}"
        )
