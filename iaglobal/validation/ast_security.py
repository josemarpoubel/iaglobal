# validation/ast_security.py

import ast
from typing import List, Set

FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
}


FORBIDDEN_ATTRS = {
    "__class__",
    "__dict__",
    "__mro__",
    "__subclasses__",
}


def validate_ast_security(tree: ast.AST) -> None:
    """
    Apenas inspeção, SEM parse.
    """

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                raise ValueError(f"Forbidden name: {node.id}")

        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                raise ValueError(f"Forbidden attribute: {node.attr}")


class RealASTValidator:
    """
    Validador AST real que detecta:
    - Variáveis usadas antes de serem definidas (undefined)
    - Mutação de lista/dict durante iteração
    - TypeError potencial (ex: str.join em dicts)
    - Código morto após return
    """

    def __init__(self):
        self.errors: List[str] = []

    def validate(self, code: str) -> List[str]:
        self.errors = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.errors.append(f"SyntaxError: {e}")
            return self.errors

        self._check_undefined_vars(tree)
        self._check_mutation_during_iteration(tree)
        self._check_join_type_error(tree)
        self._check_dead_code_after_return(tree)
        self._check_scope_errors(tree)

        return self.errors

    def _get_defined_names(self, tree: ast.AST) -> Set[str]:
        """Coleta todos os nomes definidos no escopo global da AST."""
        defined: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
                for arg in node.args.args:
                    defined.add(arg.arg)
                if node.args.vararg:
                    defined.add(node.args.vararg.arg)
                if node.args.kwarg:
                    defined.add(node.args.kwarg.arg)
            elif isinstance(node, ast.ClassDef):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    self._collect_target_names(target, defined)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    defined.add(node.target.id)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    defined.add(node.target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
        return defined

    def _collect_target_names(self, node: ast.AST, defined: Set[str]) -> None:
        if isinstance(node, ast.Name):
            defined.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self._collect_target_names(elt, defined)
        elif isinstance(node, ast.Starred):
            self._collect_target_names(node.value, defined)

    def _check_undefined_vars(self, tree: ast.AST) -> None:
        """Verifica se variáveis são usadas antes de serem definidas."""
        defined = self._get_defined_names(tree)
        builtins = {
            "True",
            "False",
            "None",
            "print",
            "len",
            "range",
            "int",
            "str",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "type",
            "isinstance",
            "hasattr",
            "getattr",
            "setattr",
            "open",
            "super",
            "property",
            "staticmethod",
            "classmethod",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "min",
            "max",
            "sum",
            "abs",
            "round",
            "any",
            "all",
            "hash",
            "id",
            "repr",
            "ord",
            "chr",
            "bytes",
            "bytearray",
            "memoryview",
            "iter",
            "next",
            "input",
            "format",
            "vars",
            "dir",
            "help",
            "__import__",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "Exception",
            "BaseException",
        }
        defined.update(builtins)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in defined and not node.id.startswith("_"):
                    self.errors.append(
                        f"Possível variável undefined: '{node.id}' na linha {getattr(node, 'lineno', '?')}"
                    )

    def _check_mutation_during_iteration(self, tree: ast.AST) -> None:
        """Detecta mutação de lista/dict durante iteração."""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                iter_name = None
                if isinstance(node.iter, ast.Name):
                    iter_name = node.iter.id
                elif isinstance(node.iter, ast.Call) and isinstance(
                    node.iter.func, ast.Name
                ):
                    if node.iter.func.id in ("iter", "enumerate"):
                        if node.iter.args and isinstance(node.iter.args[0], ast.Name):
                            iter_name = node.iter.args[0].id

                if iter_name:
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Attribute):
                                if child.func.attr in (
                                    "append",
                                    "extend",
                                    "insert",
                                    "pop",
                                    "remove",
                                    "__setitem__",
                                    "__delitem__",
                                ):
                                    if (
                                        isinstance(child.func.value, ast.Name)
                                        and child.func.value.id == iter_name
                                    ):
                                        self.errors.append(
                                            f"Mutação da lista '{iter_name}' durante iteração na linha "
                                            f"{getattr(child, 'lineno', '?')} — causa loop infinito"
                                        )
                        elif isinstance(child, ast.Delete):
                            for target in child.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == iter_name
                                ):
                                    self.errors.append(
                                        f"Deleção de '{iter_name}' durante iteração na linha "
                                        f"{getattr(child, 'lineno', '?')}"
                                    )

    def _check_join_type_error(self, tree: ast.AST) -> None:
        """Detecta str.join() em listas de não-strings (daria TypeError)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "join":
                    if node.args:
                        if isinstance(node.args[0], ast.List):
                            for elt in node.args[0].elts:
                                if isinstance(elt, ast.Dict):
                                    self.errors.append(
                                        f"str.join() em lista contém dict na linha "
                                        f"{getattr(node, 'lineno', '?')} — causará TypeError"
                                    )
                                elif isinstance(elt, ast.List):
                                    self.errors.append(
                                        f"str.join() em lista contém list na linha "
                                        f"{getattr(node, 'lineno', '?')} — causará TypeError"
                                    )

    def _check_dead_code_after_return(self, tree: ast.AST) -> None:
        """Detecta código morto após return em funções."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._check_dead_code_in_body(node.body)

    def _check_dead_code_in_body(self, body: List[ast.stmt]) -> None:
        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.Return):
                for dead in body[i + 1 :]:
                    if not isinstance(dead, (ast.FunctionDef, ast.ClassDef)):
                        self.errors.append(
                            f"Código morto após return na linha {getattr(dead, 'lineno', '?')}"
                        )
                break

    def _check_scope_errors(self, tree: ast.AST) -> None:
        """Detecta variáveis de escopo usadas incorretamente."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
                pass


# Wrapper de compatibilidade
def validate_code_real(code: str) -> List[str]:
    validator = RealASTValidator()
    return validator.validate(code)


class ASTSecurityEngine:
    """
    DEV+ SAFE MODE:
    Leve, rápido, mas cobre bypass comuns de IA.
    """

    def __init__(self):

        # imports perigosos (root-level)
        self.forbidden_imports = {
            "os",
            "subprocess",
            "shutil",
            "importlib",
            "ctypes",
            "socket",
        }

        # execução dinâmica perigosa
        self.forbidden_calls = {
            "exec",
            "eval",
            "__import__",
            "compile",
        }

        # reflexão perigosa
        self.forbidden_attributes = {
            "__dict__",
            "__class__",
            "__globals__",
            "__subclasses__",
            "__mro__",
            "__builtins__",
        }

        # padrões perigosos em strings (LLM bypass clássico)
        self.forbidden_string_patterns = [
            "__import__",
            "eval(",
            "exec(",
            "subprocess",
            "os.system",
            "popen",
            "/etc/passwd",
            "rm -rf",
            "https://",
            "http://",
            "curl ",
            "wget ",
            "bash -",
            "powershell",
        ]

    def analyze(self, code: str) -> List[str]:
        violations = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ["SyntaxError"]

        for node in ast.walk(tree):
            # -----------------------
            # IMPORTS
            # -----------------------
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self.forbidden_imports:
                        violations.append(f"Forbidden import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in self.forbidden_imports:
                        violations.append(f"Forbidden from-import: {node.module}")

            # -----------------------
            # FUNCTION CALLS
            # -----------------------
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.forbidden_calls:
                        violations.append(f"Forbidden call: {node.func.id}()")

                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in self.forbidden_calls:
                        violations.append(f"Forbidden method: .{node.func.attr}()")

            # -----------------------
            # ATTRIBUTE ACCESS
            # -----------------------
            elif isinstance(node, ast.Attribute):
                if node.attr in self.forbidden_attributes:
                    violations.append(f"Forbidden attribute: .{node.attr}")

            # -----------------------
            # STRING-BASED BYPASS DETECTION
            # -----------------------
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    lowered = node.value.lower()
                    for pattern in self.forbidden_string_patterns:
                        if pattern in lowered:
                            violations.append(f"Suspicious string pattern: {pattern}")
                            break

        return violations

    def is_safe(self, code: str) -> bool:
        return len(self.analyze(code)) == 0


# =========================================================
# COMPAT LAYER (IMPORT SAFE - CLI NÃO QUEBRA)
# =========================================================

_engine = ASTSecurityEngine()


class _CheckerCompat:
    def verificar_codigo(self, codigo: str):
        violacoes = _engine.analyze(codigo)
        seguro = len(violacoes) == 0
        return seguro, violacoes


_checker = _CheckerCompat()


def validate_ast_security_str(codigo: str):
    return _engine.is_safe(codigo), _engine.analyze(codigo)


def inspecionar_seguranca_codigo(codigo: str) -> bool:
    return _engine.is_safe(codigo)


def get_security_report(codigo: str):
    violations = _engine.analyze(codigo)
    return {
        "safe": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }
