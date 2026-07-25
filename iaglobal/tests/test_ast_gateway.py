# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for ASTGateway — único ponto de entrada para parsing AST."""

import ast
import pytest

from iaglobal.security.ast_gateway import ASTGateway, ASTResult
from iaglobal.security.sandbox_rules import SandboxRules


def _gateway() -> ASTGateway:
    rules = SandboxRules()
    rules.allowed_modules = {"math", "json", "os", "sys"}
    rules.blocked_modules = {"subprocess"}
    return ASTGateway(sandbox_rules=rules)


class TestASTResult:
    def test_dataclass_defaults(self):
        r = ASTResult(valid=True, tree=None, errors=[])
        assert r.valid is True
        assert r.errors == []
        assert r.metadata == []
        assert r.error_type is None
        assert r.error_line is None

    def test_dataclass_full(self):
        r = ASTResult(
            valid=False,
            tree=None,
            errors=["bad syntax"],
            metadata=[{"type": "ERROR"}],
            error_type="SyntaxError",
            error_line=10,
            error_snippet="x = 01",
            fix_hint="remove leading zero",
        )
        assert r.valid is False
        assert r.fix_hint == "remove leading zero"


class TestASTGatewayParse:
    def test_valid_code(self):
        gw = _gateway()
        result = gw.parse("x = 1")
        assert result.valid is True
        assert result.tree is not None
        assert result.errors == []

    def test_empty_code(self):
        gw = _gateway()
        result = gw.parse("")
        assert result.valid is False
        assert result.tree is None
        assert "Empty code" in result.errors

    def test_blank_code(self):
        gw = _gateway()
        result = gw.parse("   \n  \n")
        assert result.valid is False
        assert result.error_type == "EmptyCode"

    def test_syntax_error_leading_zeros(self):
        gw = _gateway()
        result = gw.parse("x = 01")
        assert result.valid is False
        assert result.tree is None
        assert any("leading zeros" in e for e in result.errors)
        assert result.error_type == "SyntaxError"
        assert result.error_line is not None

    def test_syntax_error_multi_zero(self):
        gw = _gateway()
        result = gw.parse("y = 007")
        assert result.valid is False
        assert "leading zeros" in result.errors[0]

    def test_syntax_fix_hint_invalid_decimal(self):
        hint = ASTGateway._syntax_fix_hint(
            SyntaxError("invalid decimal literal", ("<unknown>", 1, 1, "x = 01"))
        )
        assert "zero" in hint.lower()

    def test_syntax_fix_hint_generic(self):
        hint = ASTGateway._syntax_fix_hint(
            SyntaxError("invalid syntax", ("<unknown>", 1, 1, "x = "))
        )
        assert "parênteses" in hint

    def test_syntax_fix_hint_indentation(self):
        hint = ASTGateway._syntax_fix_hint(
            SyntaxError("unexpected indent", ("<unknown>", 2, 1, "    pass"))
        )
        assert "indentação" in hint

    def test_syntax_fix_hint_indented_block(self):
        hint = ASTGateway._syntax_fix_hint(
            SyntaxError("expected an indented block", ("<unknown>", 2, 1, ""))
        )
        assert "bloco indentado" in hint

    def test_syntax_fix_hint_fallback(self):
        hint = ASTGateway._syntax_fix_hint(
            SyntaxError("unknown error here", ("<unknown>", 1, 1, ""))
        )
        assert "Erro de sintaxe" in hint


class TestASTGatewaySecurity:
    def test_blocked_import(self):
        gw = _gateway()
        result = gw.parse("import subprocess")
        assert result.valid is False
        assert any("BANNED_MODULE" in m.get("type", "") for m in result.metadata)
        assert any("subprocess" in e for e in result.errors)

    def test_blocked_import_from(self):
        gw = _gateway()
        result = gw.parse("from subprocess import run")
        assert result.valid is False
        assert any("BANNED_MODULE" in m.get("type", "") for m in result.metadata)

    def test_allowed_import_passes(self):
        gw = _gateway()
        result = gw.parse("import math")
        assert result.valid is True

    def test_blocked_exec_node(self):
        gw = _gateway()
        result = gw.parse("exec('x = 1')")
        assert result.valid is False

    def test_blocked_eval_call(self):
        gw = _gateway()
        result = gw.parse("eval('1+1')")
        assert result.valid is False
        assert any("UNSAFE_CALL" in m.get("type", "") for m in result.metadata)

    def test_blocked_dunder_access(self):
        gw = _gateway()
        result = gw.parse("obj.__subclasses__()")
        assert result.valid is False
        assert any("FORBIDDEN_DUNDER" in m.get("type", "") for m in result.metadata)

    def test_validate_alias(self):
        gw = _gateway()
        result = gw.validate("x = 42")
        assert result.valid is True


class TestASTGatewayEdgeCases:
    def test_large_code(self):
        gw = _gateway()
        code = "\n".join(f"x{i} = {i}" for i in range(500))
        result = gw.parse(code)
        assert result.valid is True

    def test_function_with_docstring(self):
        gw = _gateway()
        code = 'def foo():\n    """doc"""\n    pass'
        result = gw.parse(code)
        assert result.valid is True
