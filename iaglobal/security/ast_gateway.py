# iaglobal/security/ast_gateway.py

import ast

from dataclasses import dataclass
from typing import List, Set, Optional
from iaglobal.utils.logger import logger
from iaglobal.security.sandbox_rules import SandboxRules


@dataclass
class ASTResult:
    valid: bool
    tree: Optional[ast.AST]
    errors: List[str]


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

    def parse(self, code: str) -> ASTResult:
        """
        ÚNICO método permitido de parsing no sistema.
        """

        if not code or not code.strip():
            return ASTResult(False, None, ["Empty code"])

        try:
            tree = ast.parse(code)

            errors = self._scan(tree)

            if errors:
                logger.warning(f"AST BLOCKED: {errors}")
                return ASTResult(False, tree, errors)

            return ASTResult(True, tree, [])

        except SyntaxError as e:
            logger.error(f"Syntax error: {e}")
            return ASTResult(False, None, [str(e)])

    def _scan(self, tree: ast.AST) -> List[str]:
            errors = []

            for node in ast.walk(tree):

                # 1. Validação de imports contra SandboxRules
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if module_name not in self.sandbox_rules.allowed_modules:
                            errors.append(
                                f"Module '{alias.name}' is not in allowed_modules"
                            )

                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if module_name not in self.sandbox_rules.allowed_modules:
                            errors.append(
                                f"Module '{node.module}' is not in allowed_modules"
                            )

                # 2. Bloqueio de nós proibidos (Exec, etc.)
                if isinstance(node, tuple(self.blocked_nodes)):
                    errors.append(f"Blocked node: {type(node).__name__}")

                # 3. Verificação de Chamadas de Funções (Call)
                if isinstance(node, ast.Call):
                    # Verificação simples de nome (ex: exec())
                    if isinstance(node.func, ast.Name):
                        if node.func.id in {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr"}:
                            errors.append(f"Unsafe function call: {node.func.id}")

                    # 4. Verificação de Acesso a Atributos (ex: os.system())
                    # Captura padrões como: objeto.atributo()
                    elif isinstance(node.func, ast.Attribute):
                        # Bloqueia métodos específicos, independentemente de quem os chama
                        if node.func.attr in {"system", "popen", "spawn", "execute", "eval", "exec"}:
                            errors.append(f"Unsafe attribute access: {node.func.attr}")

                        # Bloqueia o uso de __subclasses__ ou outros métodos de introspecção perigosos
                        if node.func.attr.startswith("__"):
                            errors.append(f"Forbidden dunder access: {node.func.attr}")

            return errors
