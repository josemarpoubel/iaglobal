# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do FailureAnalyzer — sistema de vigilância imunológica."""

import pytest
from iaglobal.interface.diagnostico import DiagnosticoFalha, RecoveryMetrics
from iaglobal.immunity.failure_analyzer import (
    parse_error,
    fingerprint_error,
    generate_correction_plan,
    _extract_error_type,
    _extract_error_message,
    _extract_line,
    _sanitize_paths,
    _fix_syntax_error,
    _fix_indentation,
    _fix_import_error,
    _fix_name_error,
    _fix_empty_output,
)


# ── DiagnosticoFalha Schema ──────────────────────────────────────────


def test_diagnostico_schema_defaults():
    d = DiagnosticoFalha()
    assert d.tipo_erro == "Unknown"
    assert d.mensagem == ""
    assert d.linha is None
    assert d.fingerprint == ""


def test_diagnostico_schema_full():
    d = DiagnosticoFalha(
        tipo_erro="SyntaxError",
        mensagem="invalid syntax",
        linha=10,
        fingerprint="abc123",
        codigo_original="x = 1 +",
    )
    assert d.tipo_erro == "SyntaxError"
    assert d.linha == 10
    assert d.model_dump()["tipo_erro"] == "SyntaxError"


def test_recovery_metrics_defaults():
    r = RecoveryMetrics()
    assert r.tentativas == 0
    assert r.delta_segundos == 0.0
    assert r.vacina_aplicada is False
    assert r.fingerprint_erro == ""


def test_recovery_metrics_full():
    r = RecoveryMetrics(tentativas=3, delta_segundos=12.5, vacina_aplicada=True, fingerprint_erro="xyz")
    assert r.tentativas == 3
    assert r.delta_segundos == 12.5
    assert r.vacina_aplicada is True


# ── Error Type Extraction ────────────────────────────────────────────


def test_extract_syntax_error():
    result = _extract_error_type('File "test.py", line 1\nSyntaxError: invalid syntax')
    assert result == "SyntaxError"


def test_extract_timeout():
    result = _extract_error_type("[Timeout] Execution exceeded 30s")
    assert result == "TimeoutError"


def test_extract_import_error():
    result = _extract_error_type('ModuleNotFoundError: No module named "requests"')
    assert result == "ImportError"


def test_extract_name_error():
    result = _extract_error_type("NameError: name 'x' is not defined")
    assert result == "NameError"


def test_extract_unknown():
    result = _extract_error_type("Something weird happened")
    assert result == "Unknown"


def test_extract_empty():
    result = _extract_error_type("")
    assert result == "EmptyOutput"


def test_extract_assertion():
    result = _extract_error_type("AssertionError: expected 5, got 3")
    assert result == "AssertionError"


def test_extract_zero_division():
    result = _extract_error_type("ZeroDivisionError: division by zero")
    assert result == "ZeroDivisionError"


# ── Error Message Extraction ─────────────────────────────────────────


def test_extract_message_with_error():
    msg = _extract_error_message('Traceback...\nValueError: invalid literal for int()')
    assert "invalid literal" in msg


def test_extract_message_fallback():
    msg = _extract_error_message("just a plain message here")
    assert "plain message" in msg


# ── Line Extraction ──────────────────────────────────────────────────


def test_extract_line():
    result = _extract_line('File "test.py", line 42, in foo')
    assert result == 42


def test_extract_line_none():
    result = _extract_line("No line information")
    assert result is None


# ── Path Sanitization ────────────────────────────────────────────────


def test_sanitize_paths():
    raw = 'File "/home/user/project/code.py", line 10'
    cleaned = _sanitize_paths(raw)
    assert "/home/user/project/" not in cleaned
    assert "/sanitized/path" in cleaned


# ── Fingerprint ──────────────────────────────────────────────────────


def test_fingerprint_consistency():
    fp1 = fingerprint_error('File "/home/user/x.py", line 42\nSyntaxError: bad')
    fp2 = fingerprint_error('File "/home/other/x.py", line 42\nSyntaxError: bad')
    assert fp1 == fp2, "Fingerprints devem ser iguais mesmo com paths diferentes"


def test_fingerprint_different_errors():
    fp1 = fingerprint_error("SyntaxError: invalid syntax")
    fp2 = fingerprint_error("ValueError: invalid value")
    assert fp1 != fp2, "Fingerprints devem diferir para erros diferentes"


# ── parse_error ──────────────────────────────────────────────────────


def test_parse_error_syntax():
    output = 'File "test.py", line 5\nSyntaxError: invalid syntax'
    d = parse_error(output, "x = 1 +")
    assert d.tipo_erro == "SyntaxError"
    assert d.linha == 5
    assert d.fingerprint


def test_parse_error_code_executor_format():
    output = """hello
[stderr] Traceback (most recent call last):
  File "/tmp/code.py", line 3, in <module>
    result = 1 / 0
ZeroDivisionError: division by zero"""
    d = parse_error(output, "x = 1\nprint(x)\n1/0")
    assert d.tipo_erro == "ZeroDivisionError"
    assert d.linha == 3


def test_parse_error_empty():
    d = parse_error("")
    assert d.tipo_erro == "EmptyOutput"


def test_parse_error_timeout():
    d = parse_error("[Timeout] Execution exceeded 30s")
    assert d.tipo_erro == "TimeoutError"


# ── Correction Plans (deterministic) ────────────────────────────────


def test_fix_syntax_missing_paren():
    result = _fix_syntax_error("x = (1 + 2", 1)
    assert result == "x = (1 + 2)"


def test_fix_syntax_missing_bracket():
    result = _fix_syntax_error("items = [1, 2, 3", 1)
    assert result == "items = [1, 2, 3]"


def test_fix_syntax_missing_brace():
    result = _fix_syntax_error("d = {'a': 1", 1)
    assert result == "d = {'a': 1}"


def test_fix_syntax_unclosed_string():
    result = _fix_syntax_error("msg = 'hello", 1)
    assert result == "msg = 'hello'"


def test_fix_indentation_tabs():
    code = "\tif True:\n\t\tpass"
    result = _fix_indentation(code)
    assert "\t" not in result
    assert "    " in result


def test_fix_import_error():
    code = "import nonexistent_module\nprint('ok')"
    result = _fix_import_error(code, "No module named 'nonexistent_module'")
    assert "try:" in result
    assert "except ImportError:" in result


def test_fix_name_error():
    code = "print(x)"
    result = _fix_name_error(code, "name 'x' is not defined")
    assert "x = None" in result


def test_fix_empty_output():
    code = "42"
    result = _fix_empty_output(code)
    assert "print(42)" in result


def test_fix_empty_output_already_has_print():
    code = "print('hello')"
    result = _fix_empty_output(code)
    assert result == code  # unchanged


def test_generate_correction_plan_syntax():
    d = DiagnosticoFalha(tipo_erro="SyntaxError", linha=1)
    plan = generate_correction_plan(d, "x = (1")
    assert plan is not None and len(plan) > 0


def test_generate_correction_plan_unknown():
    d = DiagnosticoFalha(tipo_erro="RuntimeError", mensagem="something broke")
    plan = generate_correction_plan(d, "print('hi')")
    assert plan == ""  # no deterministic fix for unknown


def test_generate_correction_plan_timeout():
    code = "for i in range(1000000):\n    pass"
    d = DiagnosticoFalha(tipo_erro="TimeoutError")
    plan = generate_correction_plan(d, code)
    assert "OPTIMIZED" in plan


# ── Import sanity ────────────────────────────────────────────────────


def test_import_diagnostico_modulo():
    from iaglobal.interface import chat_agent
    fields = chat_agent.IntencaoBiologica.model_fields
    assert "diagnostico" in fields
    assert "plano_correcao" in fields
    assert "recovery" in fields
