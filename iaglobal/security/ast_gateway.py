# iaglobal/security/ast_gateway.py

import ast

from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from iaglobal.utils.logger import logger
from iaglobal.security.sandbox_rules import SandboxRules


@dataclass
class ASTResult:
    valid: bool
    tree: Optional[ast.AST]
    errors: List[str]
    metadata: List[Dict[str, Any]] = field(default_factory=list)


class ASTGateway:
    """
    🔒 SINGLE ENTRY POINT para AST parsing no sistema inteiro.

    Nenhum outro módulo pode chamar ast.parse diretamente.
    """

    def __init__(self, sandbox_rules: Optional[SandboxRules] = None):
        self.blocked_nodes: Set[type] = set()
        if hasattr(ast, "Exec"):
            self.blocked_nodes.add(ast.Exec)
        self.sandbox_rules = sandbox_rules or SandboxRules()

    def parse(self, code: str, mode: str = "exec") -> ASTResult:
        """
        ÚNICO método permitido de parsing no sistema.

        Args:
            code: Código Python para parsear
            mode: Modo de parsing ('exec', 'eval', 'single') — igual ast.parse()
        """

        if not code or not code.strip():
            return ASTResult(False, None, ["Empty code"], [])

        try:
            tree = ast.parse(code, mode=mode)

            violations = self._scan(tree)

            if violations:
                errors = [v["message"] for v in violations]
                logger.warning(f"AST BLOCKED: {errors}")
                return ASTResult(False, tree, errors, violations)

            return ASTResult(True, tree, [], [])

        except SyntaxError as e:
            logger.error(f"Syntax error: {e}")
            return ASTResult(False, None, [str(e)], [])

    def validate(self, code: str) -> ASTResult:
        return self.parse(code)

    def _make_violation(
        self, node: ast.AST, vtype: str, message: str, suggestion: str
    ) -> Dict[str, Any]:
        return {
            "type": vtype,
            "message": message,
            "node_type": type(node).__name__,
            "line": getattr(node, "lineno", 0),
            "col_offset": getattr(node, "col_offset", 0),
            "suggestion": suggestion,
        }

    def _scan(self, tree: ast.AST) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []

        for node in ast.walk(tree):
            # 1. Validação de imports contra SandboxRules
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if not self.sandbox_rules.is_module_allowed(module_name):
                        violations.append(
                            self._make_violation(
                                node,
                                "BANNED_MODULE",
                                f"Module '{alias.name}' is not in allowed_modules",
                                f"Substitua '{alias.name}' por um módulo da lista de permitidos ou refatore para não depender dele",
                            )
                        )

            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    if not self.sandbox_rules.is_module_allowed(module_name):
                        violations.append(
                            self._make_violation(
                                node,
                                "BANNED_MODULE",
                                f"Module '{node.module}' is not in allowed_modules",
                                f"Substitua '{node.module}' por um módulo da lista de permitidos",
                            )
                        )

            # 2. Bloqueio de nós proibidos (Exec, etc.)
            if isinstance(node, tuple(self.blocked_nodes)):
                violations.append(
                    self._make_violation(
                        node,
                        "BANNED_NODE",
                        f"Blocked node: {type(node).__name__}",
                        f"Remova a instrução '{type(node).__name__}' — não é permitida no ambiente seguro",
                    )
                )

            # 3. Verificação de Chamadas de Funções (Call)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {
                        "eval",
                        "exec",
                        "compile",
                        "__import__",
                        "getattr",
                        "setattr",
                        "delattr",
                        "globals",
                        "vars",
                        "dir",
                    }:
                        violations.append(
                            self._make_violation(
                                node,
                                "UNSAFE_CALL",
                                f"Unsafe function call: {node.func.id}",
                                f"Substitua '{node.func.id}()' por uma alternativa segura ou refatore o código para não usar execução dinâmica",
                            )
                        )

                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in {
                        "system",
                        "popen",
                        "spawn",
                        "execute",
                        "eval",
                        "exec",
                    }:
                        violations.append(
                            self._make_violation(
                                node,
                                "UNSAFE_CALL",
                                f"Unsafe attribute access: {node.func.attr}",
                                f"Substitua chamada a '.{node.func.attr}()' por API segura equivalente",
                            )
                        )

                    dangerous_dunders = {
                        "__subclasses__", "__mro__", "__bases__",
                        "__globals__", "__closure__", "__code__",
                        "__func__", "__self__", "__class__", "__dict__",
                        "__getattribute__", "__getattr__", "__setattr__",
                        "__delattr__", "__new__", "__reduce__", "__reduce_ex__",
                        "__getstate__", "__setstate__", "__getitem__", "__setitem__",
                        "__delitem__", "__iter__", "__next__", "__enter__", "__exit__",
                        "__call__", "__instancecheck__", "__subclasscheck__",
                    }
                    if node.func.attr in dangerous_dunders:
                        violations.append(
                            self._make_violation(
                                node,
                                "FORBIDDEN_DUNDER",
                                f"Forbidden dunder access: {node.func.attr}",
                                f"Acesso a '{node.func.attr}' bloqueado por segurança — refatore para não usar introspecção de dunder",
                            )
                        )

        return violations
