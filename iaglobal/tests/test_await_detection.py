import ast
import pytest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "iaglobal"

SKIP_DIRS = {"__pycache__", ".mypy_cache", ".git", "venv", "node_modules", "memory"}
SKIP_FILES = {"__init__.py", "__main__.py"}

ASYNC_NAMES_CACHE: dict[str, set[str]] = {}

_SAFE_BUILTINS = {
    "super",
    "range",
    "len",
    "type",
    "isinstance",
    "getattr",
    "hasattr",
    "setattr",
    "print",
    "open",
    "min",
    "max",
    "sum",
    "list",
    "dict",
    "set",
    "str",
    "int",
    "float",
    "bool",
    "repr",
    "zip",
    "map",
    "filter",
    "enumerate",
    "sorted",
    "reversed",
    "any",
    "all",
    "issubclass",
    "property",
    "classmethod",
    "staticmethod",
    "object",
    "callable",
    "iter",
    "next",
    "input",
    "format",
    "bytes",
    "bytearray",
    "tuple",
    "frozenset",
    "memoryview",
    "abs",
    "round",
    "pow",
    "divmod",
    "hex",
    "oct",
    "bin",
    "ord",
    "chr",
    "ascii",
    "vars",
    "dir",
    "locals",
    "globals",
    "compile",
    "eval",
    "exec",
    "__import__",
}

ASYNC_GATHER_FUNCS = {
    "create_task",
    "gather",
    "wait",
    "as_completed",
    "ensure_future",
    "run_coroutine_threadsafe",
}


def _build_async_names_cache():
    if ASYNC_NAMES_CACHE:
        return
    for pyfile in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = pyfile.relative_to(PACKAGE_DIR)
        if any(p.name in SKIP_DIRS for p in rel.parents):
            continue
        if pyfile.name in SKIP_FILES:
            continue
        try:
            tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    ASYNC_NAMES_CACHE.setdefault(str(rel), set()).add(node.name)
                for base in getattr(node, "bases", []):
                    if isinstance(base, ast.Name):
                        ASYNC_NAMES_CACHE.setdefault(str(rel), set()).add(base.id)
        except SyntaxError:
            pass


def _parent_chain(node: ast.AST, max_depth: int = 8) -> list[ast.AST]:
    chain = []
    current = getattr(node, "parent", None)
    for _ in range(max_depth):
        if current is None:
            break
        chain.append(current)
        current = getattr(current, "parent", None)
    return chain


def _link_parents(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node


def _is_awaited(node: ast.Call) -> bool:
    chain = _parent_chain(node)
    if any(isinstance(p, ast.Await) for p in chain):
        return True
    return False


def _is_within_async_gather(node: ast.Call) -> bool:
    chain = _parent_chain(node, max_depth=12)
    for p in chain:
        if isinstance(p, ast.Call):
            if isinstance(p.func, ast.Attribute) and p.func.attr in ASYNC_GATHER_FUNCS:
                return True
            if isinstance(p.func, ast.Name) and p.func.id in ASYNC_GATHER_FUNCS:
                return True
    return False


def _is_value_discarded(node: ast.Call) -> bool:
    chain = _parent_chain(node, max_depth=4)
    if chain and isinstance(chain[0], ast.Expr):
        return True
    return False


def _is_in_comprehension(node: ast.Call) -> bool:
    chain = _parent_chain(node, max_depth=12)
    for p in chain:
        if isinstance(p, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return True
    return False


def _is_self_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    )


def _is_async_def_local(
    call_name: str, file_key: str, file_async_defs: set[str]
) -> bool:
    if call_name in file_async_defs:
        return True
    return False


def test_missing_await_across_codebase():
    _build_async_names_cache()
    violations = []
    total_files = 0
    total_async_funcs = 0
    total_async_all = sum(len(v) for v in ASYNC_NAMES_CACHE.values())

    for pyfile in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = pyfile.relative_to(PACKAGE_DIR)
        if any(p.name in SKIP_DIRS for p in rel.parents):
            continue
        if pyfile.name in SKIP_FILES:
            continue
        total_files += 1
        file_key = str(rel)

        try:
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except SyntaxError:
            violations.append(
                {
                    "file": file_key,
                    "line": 0,
                    "func": "<syntax-error>",
                    "call": "<syntax-error>",
                    "reason": "syntax_error",
                }
            )
            continue

        _link_parents(tree)

        file_async_defs = ASYNC_NAMES_CACHE.get(file_key, set())
        class_methods: dict[str, set[str]] = {}
        class_stack: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_stack.append(node.name)
                class_methods[node.name] = set()
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods[node.name].add(item.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                pass

        async_funcs = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
        total_async_funcs += len(async_funcs)

        for func in async_funcs:
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                if _is_awaited(node):
                    continue
                if _is_within_async_gather(node):
                    continue

                if isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    call_name = node.func.id
                else:
                    continue

                if call_name in _SAFE_BUILTINS:
                    continue

                is_async_def = _is_async_def_local(call_name, file_key, file_async_defs)

                if _is_self_call(node):
                    class_name = _get_enclosing_class(func, tree)
                    if class_name and class_name in class_methods:
                        is_async_def = call_name in class_methods.get(
                            class_name, set()
                        ) and _is_async_method(call_name, pyfile, class_name)

                if (
                    is_async_def
                    and _is_value_discarded(node)
                    and not _is_in_comprehension(node)
                ):
                    violations.append(
                        {
                            "file": file_key,
                            "line": node.lineno,
                            "func": func.name,
                            "call": call_name,
                            "reason": "async_def_discarded",
                        }
                    )
                elif is_async_def and _is_in_comprehension(node):
                    violations.append(
                        {
                            "file": file_key,
                            "line": node.lineno,
                            "func": func.name,
                            "call": call_name,
                            "reason": "async_def_collected",
                        }
                    )

    _print_report(violations, total_files, total_async_funcs, total_async_all)

    high_risk = [v for v in violations if v["reason"] == "async_def_discarded"]
    collected = [v for v in violations if v["reason"] == "async_def_collected"]

    if high_risk:
        pytest.fail(
            f"Encontradas {len(high_risk)} chamadas async sem await com valor descartado"
        )


def _get_enclosing_class(node: ast.AST, tree: ast.AST) -> str | None:
    chain = _parent_chain(node, max_depth=20)
    for p in chain:
        if isinstance(p, ast.ClassDef):
            return p.name
    return None


def _is_async_method(method_name: str, pyfile: Path, class_name: str) -> bool:
    try:
        tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if (
                        isinstance(item, ast.AsyncFunctionDef)
                        and item.name == method_name
                    ):
                        return True
        return False
    except SyntaxError:
        return True


def _print_report(violations, total_files, total_async_funcs, total_async_all):
    print(f"\n{'=' * 60}")
    print(f"  ANALISE DE AWAIT — iaglobal/{total_files} arquivos")
    print(
        f"  Funcoes async: {total_async_all} definidas | {total_async_funcs} analisadas"
    )
    print(f"{'=' * 60}")

    if not violations:
        print(f"\n  NENHUMA VIOLACAO ENCONTRADA")
        return

    categories = {}
    for v in violations:
        categories.setdefault(v["reason"], []).append(v)

    for reason, items in sorted(categories.items()):
        if reason == "syntax_error":
            print(f"\n  ⚠️  SYNTAX ERROR ({len(items)}):")
            for v in items[:5]:
                print(f"    {v['file']}: {v['call']}")
            if len(items) > 5:
                print(f"    ... e mais {len(items) - 5}")
        elif reason == "async_def_discarded":
            print(f"\n  🔴 VALOR DESCARADO (RETORNO PERDIDO) — {len(items)}:")
            print(f"  {'=' * 50}")
            for v in items:
                print(f"    {v['file']}:{v['line']}  {v['func']}() -> {v['call']}()")
        elif reason == "async_def_collected":
            print(
                f"\n  🟡 COROUTINAS EM COMPREHENSOES (revisar gather) — {len(items)}:"
            )
            print(f"  {'=' * 50}")
            for v in items:
                print(f"    {v['file']}:{v['line']}  {v['func']}() -> {v['call']}()")

    total_by_reason = ", ".join(f"{k}={len(v)}" for k, v in sorted(categories.items()))
    print(f"\n  Total: {len(violations)} ({total_by_reason})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
