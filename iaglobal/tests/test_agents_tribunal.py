# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""⚖️ TRIBUNAL DE GÊNESIS — Auditoria de conformidade dos agentes."""

import ast
import sys
import pytest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "iaglobal"

GENESIS_HASH = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"

AGENTS_DIR = PACKAGE_DIR / "agents"
SKIP_DIRS = {"__pycache__", ".mypy_cache", ".git", "venv", "node_modules"}
GLOBBED_AGENTS: list[Path] = []


def _collect_agent_files():
    if GLOBBED_AGENTS:
        return GLOBBED_AGENTS
    for pyfile in AGENTS_DIR.rglob("*.py"):
        rel = pyfile.relative_to(PACKAGE_DIR)
        if any(p.name in SKIP_DIRS for p in rel.parents):
            continue
        GLOBBED_AGENTS.append(pyfile)
    return GLOBBED_AGENTS


def _first_line(file: Path) -> str:
    try:
        with file.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    return stripped
    except Exception:
        pass
    return ""


def test_lineage_marker_present():
    violations = []
    for pyfile in _collect_agent_files():
        rel = pyfile.relative_to(PACKAGE_DIR)
        first = _first_line(pyfile)
        if GENESIS_HASH not in first:
            violations.append(str(rel))
    if violations:
        msg = "\n".join(f"  ❌ {v}" for v in violations)
        pytest.fail(
            f"\n{len(violations)} agentes sem LINEAGE_MARKER:\n{msg}"
        )


def test_lineage_marker_hash_correct():
    violations = []
    for pyfile in _collect_agent_files():
        rel = pyfile.relative_to(PACKAGE_DIR)
        first = _first_line(pyfile)
        if "LINEAGE_MARKER" in first and GENESIS_HASH not in first:
            violations.append(str(rel))
    if violations:
        msg = "\n".join(f"  ❌ {v}" for v in violations)
        pytest.fail(
            f"\n{len(violations)} agentes com hash divergente:\n{msg}"
        )


def test_no_print_in_code():
    violations = []
    for pyfile in _collect_agent_files():
        rel = pyfile.relative_to(PACKAGE_DIR)
        try:
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            violations.append(f"{rel} — syntax error")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Name) and call.func.id == "print":
                    violations.append(f"{rel}:{call.lineno}  print()")
                    break
    if violations:
        msg = "\n".join(f"  ❌ {v}" for v in violations)
        pytest.fail(
            f"\n{len(violations)} violacoes de print():\n{msg}"
        )


def test_logger_import_compliant():
    violations = []
    for pyfile in _collect_agent_files():
        rel = pyfile.relative_to(PACKAGE_DIR)
        try:
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            continue

        has_get_logger_import = False
        has_getlogger_call = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if getattr(node, "module", "") == "iaglobal.utils.logger":
                    has_get_logger_import = True
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "logger":
                        if isinstance(node.value, ast.Call):
                            call = node.value
                            if isinstance(call.func, ast.Name):
                                if call.func.id == "get_logger":
                                    has_getlogger_call = True
                                elif call.func.id == "getLogger":
                                    pass

        uses_logger = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "logger":
                    if node.attr in ("info", "error", "warning", "debug", "exception", "critical"):
                        uses_logger = True

        bad_logging = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "logging":
                        if node.func.attr == "getLogger":
                            if isinstance(node, ast.Assign):
                                pass
                            bad_logging = True

        if uses_logger and not has_get_logger_import:
            violations.append(f"{rel} — usa logger mas nao importa get_logger")
        if bad_logging:
            violations.append(f"{rel} — usa logging.getLogger() em vez de get_logger")

    if violations:
        msg = "\n".join(f"  ⚠️  {v}" for v in sorted(set(violations)))
        pytest.fail(
            f"\n{len(set(violations))} violacoes de logging:\n{msg}"
        )


def test_agent_imports_valid():
    errors = []
    for pyfile in _collect_agent_files():
        rel = pyfile.relative_to(PACKAGE_DIR)
        try:
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            ast.parse(source)
        except SyntaxError as e:
            errors.append(f"{rel} — SyntaxError: {e}")
    if errors:
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        pytest.fail(
            f"\n{len(errors)} erros de sintaxe:\n{msg}"
        )


def _print_summary():
    files = _collect_agent_files()
    total = len(files)
    markers = sum(1 for f in files if GENESIS_HASH in _first_line(f))
    print(f"\n{'='*55}")
    print(f"  ⚖️  TRIBUNAL DE GENESIS — agentes/")
    print(f"  Arquivos: {total} | Com LINEAGE_MARKER: {markers}/{total}")
    print(f"{'='*55}\n")


def test_summary():
    _print_summary()
    files = _collect_agent_files()
    markers = sum(1 for f in files if GENESIS_HASH in _first_line(f))
    assert markers == len(files), f"{len(files) - markers} arquivos sem LINEAGE_MARKER"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
