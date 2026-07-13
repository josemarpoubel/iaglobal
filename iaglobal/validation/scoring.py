# iaglobal/validation/scoring.py

"""Code quality scoring module - AST centralized via ValidationEngine."""

import ast
from typing import Dict, Any
from iaglobal.utils.logger import logger
from iaglobal.validation.engine import ValidationEngine


class CodeScorer:
    """Scores code quality using validated AST from central engine."""

    def __init__(self):
        self.engine = ValidationEngine()

        self.PESOS = {
            "SINTAXE": 40.0,
            "DOC": 20.0,
            "EXC": 20.0,
            "ESTRUTURA": 20.0,
        }

    def _analisar_tree(self, tree) -> Dict[str, Any]:
        metrics = {
            "total_funcoes": 0,
            "funcoes_com_try": 0,
            "complexidade": 0,
            "possui_docstring": False,
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                metrics["total_funcoes"] += 1

                if ast.get_docstring(node):
                    metrics["possui_docstring"] = True

                if any(isinstance(c, ast.Try) for c in node.body):
                    metrics["funcoes_com_try"] += 1

            if isinstance(
                node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.BoolOp)
            ):
                metrics["complexidade"] += 1

        return metrics

    def analyze_code(self, codigo: str) -> Dict[str, Any]:
        if not codigo or not codigo.strip():
            return {"score": 0.0, "valid": False}

        result = self.engine.validate(codigo)
        if not result.valid:
            return {"score": 0.0, "valid": False, "errors": result.errors}

        try:
            tree = ast.parse(result.code or codigo)
        except SyntaxError as e:
            logger.error(f"AST inválido: {e}")
            return {"score": 0.0, "valid": False, "error": str(e)}

        metrics = self._analisar_tree(tree)
        metrics["lines"] = len(codigo.splitlines())
        metrics["valid"] = True

        metrics["score"] = self._calcular_score_final(metrics, metrics["lines"])

        return metrics

    def _calcular_score_final(self, m: Dict[str, Any], lines: int) -> float:
        score = self.PESOS["SINTAXE"]

        if m["possui_docstring"]:
            score += self.PESOS["DOC"]

        proporcao = (
            m["funcoes_com_try"] / m["total_funcoes"] if m["total_funcoes"] > 0 else 0.5
        )

        score += proporcao * self.PESOS["EXC"]

        score_est = self.PESOS["ESTRUTURA"]

        if m["complexidade"] > 8:
            score_est -= (m["complexidade"] - 8) * 2.0

        if lines > 60:
            score_est -= (lines - 60) * 0.5

        score += max(0.0, score_est)

        return round(min(100.0, max(0.0, score)), 2)


# -----------------------------
# SINGLETON GLOBAL (clean API)
# -----------------------------

_scorer = CodeScorer()


def calculate_score(codigo: str) -> float:
    return _scorer.analyze_code(codigo).get("score", 0.0)
