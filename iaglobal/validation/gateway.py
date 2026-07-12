# 📁 iaglobal/validation/gateway.py

import ast
from dataclasses import dataclass
from typing import Optional, Dict, Any

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

        try:
            tree = ast.parse(code)

            metrics = {
                "nodes": len(list(ast.walk(tree))),
                "functions": sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
            }

            return ASTResult(True, tree, None, metrics)

        except SyntaxError as e:
            return ASTResult(False, None, str(e), {})
