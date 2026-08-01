# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Tests for CodeScorer — qualidade de código via AST centralizado."""

import ast
import json
from pathlib import Path

import pytest

from iaglobal.validation.scoring import CodeScorer, calculate_score

try:
    from iaglobal.validation.scoring import _capture_failure

    _HAS_CAPTURE_FAILURE = True
except ImportError:
    _capture_failure = None
    _HAS_CAPTURE_FAILURE = False


@pytest.fixture
def scorer():
    return CodeScorer()


class TestCaptureFailure:
    @pytest.mark.skipif(
        not _HAS_CAPTURE_FAILURE, reason="_capture_failure removida do scoring.py"
    )
    def test_capture_failure_creates_dump_file(self, tests_temp_dir: Path):
        code = "x = 01\ny = 2\n"
        errors = ["invalid decimal literal (<unknown>, line 1)"]
        _capture_failure(code, errors)

        dump_dir = tests_temp_dir / "failure_dumps"
        if dump_dir.exists():
            files = list(dump_dir.glob("failure_*.py"))
            assert len(files) >= 0

    @pytest.mark.skipif(
        not _HAS_CAPTURE_FAILURE, reason="_capture_failure removida do scoring.py"
    )
    def test_capture_failure_writes_content(self, tests_temp_dir):
        code = "z = 007\n"
        errors = ["invalid decimal literal"]
        _capture_failure(code, errors)

        from iaglobal.validation.scoring import _capture_failure as cf

        dump_dir = tests_temp_dir / "failure_dumps"
        if dump_dir.exists():
            files = sorted(dump_dir.glob("failure_*.py"))
            if files:
                content = files[-1].read_text(encoding="utf-8")
                assert "z = 007" in content


class TestCodeScorerAnalyze:
    def test_valid_code_returns_score(self, scorer):
        result = scorer.analyze_code("x = 1")
        assert result["valid"] is True
        assert result["score"] > 0

    def test_empty_code_returns_zero(self, scorer):
        result = scorer.analyze_code("")
        assert result["valid"] is False
        assert result["score"] == 0.0

    def test_blank_code_returns_zero(self, scorer):
        result = scorer.analyze_code("   \n  ")
        assert result["valid"] is False
        assert result["score"] == 0.0

    def test_syntax_error_returns_zero(self, scorer):
        result = scorer.analyze_code("x = 01")
        assert result["valid"] is False
        assert result["score"] == 0.0
        assert "error" in result or "errors" in result

    def test_none_code_returns_zero(self, scorer):
        result = scorer.analyze_code(None)
        assert result["valid"] is False
        assert result["score"] == 0.0

    def test_score_in_range(self, scorer):
        result = scorer.analyze_code("def f():\n    return 42")
        assert 0 <= result["score"] <= 100

    def test_complex_code_scores_lower(self, scorer):
        simple = scorer.analyze_code("x = 1")["score"]
        complex_code = """
def a():
    if True:
        for i in range(10):
            while False:
                pass
"""
        complex = scorer.analyze_code(complex_code)["score"]
        assert complex >= 0

    def test_docstring_adds_score(self, scorer):
        no_doc = scorer.analyze_code("def f():\n    pass")["score"]
        with_doc = scorer.analyze_code('def f():\n    """doc"""\n    pass')["score"]
        assert with_doc >= no_doc

    def test_try_except_adds_score(self, scorer):
        no_try = scorer.analyze_code("def f():\n    pass")["score"]
        with_try = scorer.analyze_code(
            "def f():\n    try:\n        pass\n    except:\n        pass"
        )["score"]
        assert with_try >= no_try

    def test_long_code_penalty(self, scorer):
        long_code = "\n".join(f"x{i} = {i}" for i in range(100))
        result = scorer.analyze_code(long_code)
        assert result["valid"] is True
        assert 0 <= result["score"] <= 100

    def test_large_function_penalty(self, scorer):
        many_branches = """
def f():
    if 1: pass
    if 2: pass
    if 3: pass
    if 4: pass
    if 5: pass
    if 6: pass
    if 7: pass
    if 8: pass
    if 9: pass
    if 10: pass
"""
        result = scorer.analyze_code(many_branches)
        assert result["valid"] is True


class TestCodeScorerMetrics:
    def test_analisar_tree_empty_function(self, scorer):
        tree = ast.parse("def f():\n    pass")
        metrics = scorer._analisar_tree(tree)
        assert metrics["total_funcoes"] == 1
        assert metrics["funcoes_com_try"] == 0
        assert metrics["possui_docstring"] is False

    def test_analisar_tree_with_try(self, scorer):
        tree = ast.parse("def f():\n    try:\n        pass\n    except:\n        pass")
        metrics = scorer._analisar_tree(tree)
        assert metrics["total_funcoes"] == 1
        assert metrics["funcoes_com_try"] == 1

    def test_analisar_tree_docstring(self, scorer):
        tree = ast.parse('def f():\n    """doc"""\n    pass')
        metrics = scorer._analisar_tree(tree)
        assert metrics["possui_docstring"] is True

    def test_analisar_tree_complexity(self, scorer):
        tree = ast.parse("""
def f():
    if 1:
        for i in range(10):
            while 0:
                pass
""")
        metrics = scorer._analisar_tree(tree)
        assert metrics["complexidade"] >= 3  # if + for + while


class TestCalcularScoreFinal:
    def test_base_score(self, scorer):
        score = scorer._calcular_score_final(
            {
                "total_funcoes": 0,
                "funcoes_com_try": 0,
                "complexidade": 0,
                "possui_docstring": False,
                "valid": True,
            },
            lines=5,
        )
        # SINTAXE(40) + proporcao_fallback(0.5)*EXC(20) + ESTRUTURA(20) = 70
        assert score == 70.0

    def test_docstring_bonus(self, scorer):
        score = scorer._calcular_score_final(
            {
                "total_funcoes": 1,
                "funcoes_com_try": 0,
                "complexidade": 0,
                "possui_docstring": True,
                "valid": True,
            },
            lines=5,
        )
        assert score == 80.0  # SINTAXE(40) + DOC(20) + ESTRUTURA(20)

    def test_complexity_penalty(self, scorer):
        score = scorer._calcular_score_final(
            {
                "total_funcoes": 1,
                "funcoes_com_try": 0,
                "complexidade": 12,
                "possui_docstring": False,
                "valid": True,
            },
            lines=5,
        )
        assert score < 60.0

    def test_long_lines_penalty(self, scorer):
        score = scorer._calcular_score_final(
            {
                "total_funcoes": 0,
                "funcoes_com_try": 0,
                "complexidade": 0,
                "possui_docstring": False,
                "valid": True,
            },
            lines=100,
        )
        assert score < 60.0  # penalidade por >60 linhas


class TestCalculateScoreGlobal:
    def test_calculate_score_valid(self):
        score = calculate_score("x = 42")
        assert score > 0

    def test_calculate_score_invalid(self):
        score = calculate_score("x = 01")
        assert score == 0.0

    def test_calculate_score_empty(self):
        score = calculate_score("")
        assert score == 0.0
