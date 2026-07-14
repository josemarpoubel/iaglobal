# 📁 iaglobal/validation/gateway.py

import ast
from dataclasses import dataclass
from typing import Optional, Dict, Any

from iaglobal.security.ast_gateway import ASTGateway

_ast_gateway = ASTGateway()


@dataclass
class ASTResult:
    valid: bool
    tree: Optional[ast.AST]
    error: Optional[str]
    metrics: Dict[str, Any]


class SyntaxValidator:
    """
    🔒 Syntax-only validator. No security checks — use ASTGateway from security/ for that.
    """

    def validate(self, code: str) -> ASTResult:
        if not code or not code.strip():
            return ASTResult(False, None, "Empty code", {})

        result = _ast_gateway.parse(code)
        if not result.valid or not result.tree:
            return ASTResult(False, None, "; ".join(result.errors), {})

        metrics = {
            "nodes": len(list(ast.walk(result.tree))),
            "functions": sum(
                isinstance(n, ast.FunctionDef) for n in ast.walk(result.tree)
            ),
        }

        return ASTResult(True, result.tree, None, metrics)
