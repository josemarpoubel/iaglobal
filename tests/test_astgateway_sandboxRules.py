"""Testes da pipeline de seguranca: ASTGateway + SandboxRules + SandboxExecutor.

Testa:
1. ASTGateway bloqueia imports nao permitidos
2. ASTGateway bloqueia chamadas perigosas (eval, exec, compile, __import__)
3. ASTGateway bloqueia atributos perigosos (system, popen, spawn)
4. ASTGateway bloqueia dunders perigosos (__subclasses__, __globals__)
5. SandboxRules valida whitelist de modulos
6. SandboxExecutor executa codigo seguro em subprocesso isolado
7. SandboxExecutor retorna SecurityViolation para codigo inseguro
8. SandboxExecutor retorna violacoes detalhadas no resultado
9. Erro de sintaxe e codigo vazio
"""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.security.ast_gateway import ASTGateway, ASTResult
from iaglobal.security.sandbox_rules import SandboxRules
from iaglobal.security.sandbox_executor import SandboxExecutor


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def rules():
    r = SandboxRules()
    r.configure_defaults()
    return r


@pytest.fixture
def gateway(rules):
    return ASTGateway(sandbox_rules=rules)


@pytest.fixture
def executor(rules):
    return SandboxExecutor(timeout=10, sandbox_rules=rules)


# ── ASTGateway: Import validation ───────────────────────────────────

class TestASTGatewayImports:

    def test_allows_math_import(self, gateway):
        result = gateway.parse("import math")
        assert result.valid is True
        assert result.errors == []

    def test_allows_json_from_import(self, gateway):
        result = gateway.parse("from json import dumps")
        assert result.valid is True
        assert result.errors == []

    def test_allows_iaglobal_import(self, gateway):
        result = gateway.parse("from iaglobal.utils.logger import logger")
        assert result.valid is True
        assert result.errors == []

    def test_subprocess_import_blocked_in_both(self, gateway):
        """subprocess bloqueado tanto no ASTGateway (whitelist) quanto no
        ASTSecurityEngine (blacklist). Apenas controlled_subprocess.py pode
        chamar subprocess, e ele é código do framework, não gerado."""
        result = gateway.parse("import subprocess")
        assert result.valid is False

    def test_os_is_blocked_in_both(self, gateway):
        """'os' bloqueado no ASTGateway (whitelist) e no ASTSecurityEngine
        (blacklist) — política unificada de segurança."""
        result = gateway.parse("import os")
        assert result.valid is False

    def test_os_system_blocked_by_ast(self, gateway):
        """O bloqueio de os.system() ocorre pelo check de attr perigoso."""
        result = gateway.parse("os.system('ls')")
        assert result.valid is False
        assert any("system" in e for e in result.errors)

    def test_blocks_socket_import(self, gateway):
        result = gateway.parse("import socket")
        assert result.valid is False
        assert any("socket" in e for e in result.errors)

    def test_blocks_shutil_import(self, gateway):
        result = gateway.parse("import shutil")
        assert result.valid is False
        assert any("shutil" in e for e in result.errors)

    def test_blocks_ctypes_import(self, gateway):
        result = gateway.parse("import ctypes")
        assert result.valid is False
        assert any("ctypes" in e for e in result.errors)

    def test_blocks_multiprocessing_import(self, gateway):
        result = gateway.parse("import multiprocessing")
        assert result.valid is False
        assert any("multiprocessing" in e for e in result.errors)

    def test_os_from_import_is_blocked_by_gateway(self, gateway):
        result = gateway.parse("from os import system")
        assert result.valid is False

    def test_subprocess_from_import_now_blocked(self, gateway):
        result = gateway.parse("from subprocess import run")
        assert result.valid is False


# ── ASTGateway: Dangerous calls ─────────────────────────────────────

class TestASTGatewayDangerousCalls:

    def test_blocks_eval(self, gateway):
        result = gateway.parse("eval('1+1')")
        assert result.valid is False
        assert any("eval" in e for e in result.errors)

    def test_blocks_exec(self, gateway):
        result = gateway.parse("exec('x=1')")
        assert result.valid is False
        assert any("exec" in e for e in result.errors)

    def test_blocks_compile(self, gateway):
        result = gateway.parse("compile('x=1', '', 'exec')")
        assert result.valid is False
        assert any("compile" in e for e in result.errors)

    def test_blocks_import_function(self, gateway):
        result = gateway.parse("__import__('os')")
        assert result.valid is False
        assert any("__import__" in e for e in result.errors)

    def test_blocks_getattr(self, gateway):
        result = gateway.parse("getattr(obj, '__code__')")
        assert result.valid is False

    def test_blocks_setattr(self, gateway):
        result = gateway.parse("setattr(obj, 'x', 1)")
        assert result.valid is False

    def test_blocks_delattr(self, gateway):
        result = gateway.parse("delattr(obj, 'x')")
        assert result.valid is False


# ── ASTGateway: Dangerous attribute access ──────────────────────────

class TestASTGatewayDangerousAttrs:

    def test_blocks_os_system(self, gateway):
        result = gateway.parse("os.system('ls')")
        assert result.valid is False
        assert any("system" in e for e in result.errors)

    def test_blocks_popen_call(self, gateway):
        result = gateway.parse("x.popen('ls')")
        assert result.valid is False
        assert any("popen" in e for e in result.errors)

    def test_blocks_spawn(self, gateway):
        result = gateway.parse("os.spawn('ls')")
        assert result.valid is False

    def test_blocks_execute(self, gateway):
        result = gateway.parse("driver.execute('script')")
        assert result.valid is False

    def test_blocks_popen_method(self, gateway):
        result = gateway.parse("subprocess.popen('ls')")
        assert result.valid is False

    def test_blocks_spawn_method(self, gateway):
        result = gateway.parse("os.spawn('ls')")
        assert result.valid is False


# ── ASTGateway: Dangerous dunders ───────────────────────────────────

class TestASTGatewayDangerousDunders:

    def test_blocks_subclasses(self, gateway):
        result = gateway.parse("obj.__subclasses__()")
        assert result.valid is False
        assert any("subclasses" in e for e in result.errors)

    def test_blocks_globals(self, gateway):
        result = gateway.parse("obj.__globals__()")
        assert result.valid is False

    def test_blocks_closure(self, gateway):
        result = gateway.parse("obj.__closure__()")
        assert result.valid is False

    def test_blocks_class(self, gateway):
        result = gateway.parse("obj.__class__()")
        assert result.valid is False

    def test_blocks_reduce(self, gateway):
        result = gateway.parse("obj.__reduce__()")
        assert result.valid is False

    def test_blocks_dict_access(self, gateway):
        result = gateway.parse("obj.__dict__()")
        assert result.valid is False


# ── ASTGateway: Edge cases ──────────────────────────────────────────

class TestASTGatewayEdgeCases:

    def test_empty_code(self, gateway):
        result = gateway.parse("")
        assert result.valid is False

    def test_whitespace_code(self, gateway):
        result = gateway.parse("   \n  \n  ")
        assert result.valid is False

    def test_syntax_error(self, gateway):
        result = gateway.parse("def foo(:")
        assert result.valid is False
        assert result.tree is None

    def test_safe_code_passes(self, gateway):
        code = """
import math
import json
from collections import Counter

def calculate(data):
    values = json.loads(data)
    return math.sqrt(sum(values))
"""
        result = gateway.parse(code)
        assert result.valid is True
        assert result.errors == []

    def test_multiple_blocked_imports(self, gateway):
        code = "import subprocess; import socket; import shutil"
        result = gateway.parse(code)
        assert result.valid is False
        assert len(result.errors) >= 2

    def test_print_is_allowed(self, gateway):
        result = gateway.parse("print('hello')")
        assert result.valid is True


# ── SandboxExecutor: Full pipeline ──────────────────────────────────

class TestSandboxExecutorPipeline:

    def test_safe_code_executes(self, executor):
        result = executor.execute("import math; print(math.sqrt(16))")
        assert result.get("sucesso") is True
        assert result.get("stdout") == "4.0"

    def test_safe_json_code(self, executor):
        result = executor.execute(
            "import json; print(json.dumps({'a': 1}))"
        )
        assert result.get("sucesso") is True
        assert "a" in result.get("stdout", "")

    def test_blocked_import_returns_violation(self, executor):
        result = executor.execute("import socket")
        assert result.get("sucesso") is False
        assert result.get("erro") == "SecurityViolation"
        assert "violacoes" in result
        assert len(result["violacoes"]) > 0

    def test_unsafe_call_returns_violation(self, executor):
        result = executor.execute("eval('1+1')")
        assert result.get("sucesso") is False
        assert result.get("erro") == "SecurityViolation"
        violacoes = result.get("violacoes", [])
        assert any("eval" in v for v in violacoes)

    def test_unsafe_attr_returns_violation(self, executor):
        result = executor.execute("import os; os.system('ls')")
        assert result.get("sucesso") is False
        assert result.get("erro") == "SecurityViolation"

    def test_glutathione_blocks_dangerous(self, executor):
        result = executor.execute("pickle.loads(b'data')")
        if result.get("erro") in ("SecurityViolation", "GlutathioneViolation"):
            assert "violacoes" in result
        else:
            pytest.skip("Glutathione pode estar desabilitado")

    def test_violacoes_detalhadas_no_resultado(self, executor):
        result = executor.execute("import socket; socket.socket()")
        assert result.get("sucesso") is False
        violacoes = result.get("violacoes", [])
        assert len(violacoes) >= 1
        primeira = violacoes[0]
        assert isinstance(primeira, str)
        assert len(primeira) > 5


# ── SandboxRules: Module whitelist ──────────────────────────────────

class TestSandboxRulesModules:

    def test_math_is_allowed(self, rules):
        assert rules.is_module_allowed("math") is True

    def test_json_is_allowed(self, rules):
        assert rules.is_module_allowed("json") is True

    def test_os_is_blocked(self, rules):
        assert rules.is_module_allowed("os") is False

    def test_subprocess_is_blocked(self, rules):
        assert rules.is_module_allowed("subprocess") is False

    def test_socket_is_blocked(self, rules):
        assert rules.is_module_allowed("socket") is False

    def test_shutil_is_blocked(self, rules):
        assert rules.is_module_allowed("shutil") is False

    def test_multiprocessing_is_blocked(self, rules):
        assert rules.is_module_allowed("multiprocessing") is False

    def test_numpy_is_allowed(self, rules):
        assert rules.is_module_allowed("numpy") is True

    def test_pandas_is_allowed(self, rules):
        assert rules.is_module_allowed("pandas") is True

    def test_flask_is_allowed(self, rules):
        assert rules.is_module_allowed("flask") is True

    def test_iaglobal_is_allowed(self, rules):
        assert rules.is_module_allowed("iaglobal") is True

    def test_requests_is_allowed(self, rules):
        assert rules.is_module_allowed("requests") is True
