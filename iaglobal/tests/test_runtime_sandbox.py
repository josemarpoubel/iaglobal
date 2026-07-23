# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Runtime Sandbox — valida os 5 gaps do Fuzzer que a AST não detecta.

Cobertura:
  1. String concatenação (__import__ via f-string)
  2. Dict access dinâmico (builtins['exec'])
  3. getattr(__builtins__, 'exec')
  4. globals() / vars() introspection
  5. setattr em dunder methods
"""

import pytest

from iaglobal.security.runtime_sandbox import (
    create_sandboxed_exec,
    SecurityViolation,
    BLOCKED_BUILTINS,
    AuditLogger,
)


@pytest.fixture
def sandbox():
    al = AuditLogger()
    safe, _ = create_sandboxed_exec(agent_id="test-agent-1", audit_logger=al)
    safe["print"] = print
    safe["len"] = len
    safe["str"] = str
    safe["int"] = int
    safe["range"] = range
    safe["sum"] = sum
    safe["list"] = list
    safe["dict"] = dict
    safe["set"] = set
    safe["tuple"] = tuple
    safe["bool"] = bool
    safe["float"] = float
    safe["isinstance"] = isinstance
    safe["hasattr"] = hasattr
    safe["type"] = type
    safe["object"] = object
    return safe, al


def exec_sandboxed(code: str, safe: dict, local_vars: dict | None = None) -> None:
    """Helper: executa código no sandbox."""
    if local_vars is not None:
        exec(code, safe, local_vars)
    else:
        exec(code, safe)


# ══════════════════════════════════════════════════════════════════════════════
# Testes dos 5 Gaps do Fuzzer
# ══════════════════════════════════════════════════════════════════════════════


class TestFuzzerGaps:
    """Testa os 5 gaps que a análise estática não detecta."""

    def test_gap_1_string_concat_import(self, sandbox):
        """Gap 1: __import__ via concatenação de string."""
        safe, _ = sandbox
        code = """
module_name = "os"
__import__(module_name)
"""
        with pytest.raises(SecurityViolation, match="import bloqueado"):
            exec_sandboxed(code, safe)

    def test_gap_2_dict_access_exec(self, sandbox):
        """Gap 2: Acesso via dict a builtin perigoso."""
        safe, _ = sandbox
        code = """
builtins_dict = __builtins__
exec(builtins_dict['exec'], "print(1)")
"""
        with pytest.raises(SecurityViolation, match="bloqueado"):
            exec_sandboxed(code, safe)

    def test_gap_3_getattr_builtins(self, sandbox):
        """Gap 3: getattr em __builtins__ para acessar builtins perigosos."""
        safe, _ = sandbox
        code = """
getattr(__builtins__, 'exec')("print(1)")
"""
        with pytest.raises(SecurityViolation, match="getattr bloqueado"):
            exec_sandboxed(code, safe)

    def test_gap_4_globals_introspection(self, sandbox):
        """Gap 4: globals() não permite acesso a builtins perigosos."""
        safe, _ = sandbox
        code = """
all_globals = globals()
exec_in_globals = all_globals.get('exec')
"""
        local_vars = {}
        exec(code, safe, local_vars)
        # globals() filtrado não deve retornar 'exec' como nome
        assert local_vars.get("exec_in_globals") is None

    def test_gap_5_setattr_dunder(self, sandbox):
        """Gap 5: setattr em dunder methods é bloqueado."""
        safe, _ = sandbox
        code = """
class MyClass:
    pass

obj = MyClass()
setattr(obj, '__class__', str)
"""
        with pytest.raises(SecurityViolation, match="setattr bloqueado"):
            exec_sandboxed(code, safe)


# ══════════════════════════════════════════════════════════════════════════════
# Testes de Bloqueio Total
# ══════════════════════════════════════════════════════════════════════════════


class TestBloqueioTotal:
    """Builtins perigosos bloqueados diretamente."""

    @pytest.mark.parametrize("builtin", list(BLOCKED_BUILTINS))
    def test_builtin_bloqueado(self, sandbox, builtin):
        safe, _ = sandbox
        code = f"{builtin}('malicious_code')"
        with pytest.raises(SecurityViolation, match="bloqueado"):
            exec_sandboxed(code, safe)


# ══════════════════════════════════════════════════════════════════════════════
# Testes de Import Restrito
# ══════════════════════════════════════════════════════════════════════════════


class TestImportRestrito:
    """__import__ com whitelist/blacklist de módulos."""

    def test_import_modulo_permitido(self, sandbox):
        safe, _ = sandbox
        code = "import math\nr = math.sqrt(16)"
        local_vars = {}
        exec_sandboxed(code, safe)
        assert safe.get("r") == 4.0

    def test_import_modulo_blacklist(self, sandbox):
        safe, _ = sandbox
        code = "import os"
        with pytest.raises(SecurityViolation, match="import bloqueado"):
            exec_sandboxed(code, safe)

    def test_import_dinamico_via_variavel(self, sandbox):
        safe, _ = sandbox
        code = """
mod = "subprocess"
__import__(mod)
"""
        with pytest.raises(SecurityViolation, match="import bloqueado"):
            exec_sandboxed(code, safe)


# ══════════════════════════════════════════════════════════════════════════════
# Testes de Attribute Access
# ══════════════════════════════════════════════════════════════════════════════


class TestAttributeAccess:
    """getattr, setattr, delattr com verificação contextual."""

    def test_getattr_objeto_normal(self, sandbox):
        safe, _ = sandbox
        code = """
class MyClass:
    value = 42

obj = MyClass()
val = getattr(obj, 'value')
"""
        local_vars = {}
        exec_sandboxed(code, safe, local_vars)
        assert local_vars["val"] == 42

    def test_getattr_builtins_bloqueado(self, sandbox):
        safe, _ = sandbox
        code = "getattr(__builtins__, 'exec')"
        with pytest.raises(SecurityViolation, match="getattr bloqueado"):
            exec_sandboxed(code, safe)

    def test_setattr_dunder_bloqueado(self, sandbox):
        safe, _ = sandbox
        code = """
class MyClass:
    pass
obj = MyClass()
setattr(obj, '__class__', str)
"""
        with pytest.raises(SecurityViolation, match="setattr bloqueado"):
            exec_sandboxed(code, safe)

    def test_setattr_normal_permitido(self, sandbox):
        safe, _ = sandbox
        code = """
class MyClass:
    pass
obj = MyClass()
setattr(obj, 'value', 42)
"""
        local_vars = {}
        exec_sandboxed(code, safe, local_vars)
        assert getattr(local_vars["obj"], "value") == 42


# ══════════════════════════════════════════════════════════════════════════════
# Testes de Introspection
# ══════════════════════════════════════════════════════════════════════════════


class TestIntrospection:
    """globals(), vars(), dir() com filtragem."""

    def test_globals_filtrado(self, sandbox):
        safe, _ = sandbox
        code = """
x = 42
g = globals()
"""
        exec_sandboxed(code, safe)
        g = safe["g"]
        assert "x" in g
        assert "eval" not in g

    def test_vars_filtrado(self, sandbox):
        safe, _ = sandbox
        code = """
x = 1
y = 2
v = vars()
"""
        local_vars = {}
        exec_sandboxed(code, safe, local_vars)
        v = local_vars["v"]
        assert "x" in v and "y" in v

    def test_dir_filtrado(self, sandbox):
        safe, _ = sandbox
        code = """
class MyClass:
    public = 1
    __private = 2
d = dir(MyClass())
"""
        local_vars = {}
        exec_sandboxed(code, safe, local_vars)
        d = local_vars["d"]
        assert "public" in d
        assert "__private" not in d


# ══════════════════════════════════════════════════════════════════════════════
# Testes de Integração
# ══════════════════════════════════════════════════════════════════════════════


class TestIntegracao:
    """Fluxo completo: código seguro passa, código malicioso é bloqueado."""

    def test_codigo_seguro_executa(self, sandbox):
        safe, _ = sandbox
        code = """
import math
result = math.sqrt(25) + math.pow(2, 3)
"""
        local_vars = {}
        exec_sandboxed(code, safe, local_vars)
        assert local_vars["result"] == 13.0

    def test_codigo_malicioso_eval_bloqueado(self, sandbox):
        safe, _ = sandbox
        code = 'eval(\'__import__("os").system("ls")\')'
        with pytest.raises(SecurityViolation):
            exec_sandboxed(code, safe)

    def test_codigo_malicioso_import_os_bloqueado(self, sandbox):
        safe, _ = sandbox
        code = "import os; os.system('ls')"
        with pytest.raises(SecurityViolation):
            exec_sandboxed(code, safe)

    def test_getattr_dunder_exec_bloqueado(self, sandbox):
        safe, _ = sandbox
        code = "getattr(__builtins__, 'exec')('import os')"
        with pytest.raises(SecurityViolation, match="getattr bloqueado"):
            exec_sandboxed(code, safe)


class TestPerformance:
    """Overhead (sync, sem async)."""

    def test_setup_time_100_iter(self):
        import time

        start = time.time()
        for _ in range(100):
            create_sandboxed_exec("perf")
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_exec_overhead(self):
        import time

        code = "result = sum(range(1000))"
        safe, _ = create_sandboxed_exec("perf")

        start = time.time()
        for _ in range(50):
            exec(code, safe)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_safe_globals_assignment_blocked(self):
        safe, _ = create_sandboxed_exec("agent-1")
        with pytest.raises(SecurityViolation):
            safe["eval"] = lambda x: x

    def test_safe_globals_allows_safe_funcs(self):
        safe, _ = create_sandboxed_exec("agent-1")
        safe["my_func"] = lambda: 42
        local_vars = {}
        exec("r = my_func()", safe, local_vars)
        assert local_vars["r"] == 42
