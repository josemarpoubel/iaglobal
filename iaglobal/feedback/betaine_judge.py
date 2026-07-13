"""Betaína — LLM-as-a-Judge + métricas de execução."""

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class BetaineJudge:
    """Avaliador multidimensional de resultados."""

    @classmethod
    def evaluate(
        cls, code: str, task: str = "", execution_time: float = 0
    ) -> Dict[str, Any]:
        metrics = {}

        syntax_ok = cls._check_syntax(code)
        metrics["syntax_score"] = 1.0 if syntax_ok else 0.0

        perf_score = cls._score_performance(execution_time)
        metrics["performance_score"] = perf_score

        llm_score = cls._llm_judge(code, task)
        metrics["llm_score"] = llm_score

        overall = round(
            (
                metrics["syntax_score"] * 0.3
                + metrics["performance_score"] * 0.2
                + metrics["llm_score"] * 0.5
            ),
            2,
        )

        return {"overall": overall, "metrics": metrics, "syntax_ok": syntax_ok}

    @classmethod
    def _check_syntax(cls, code: str) -> bool:
        try:
            compile(code, "<betaine>", "exec")
            return True
        except SyntaxError:
            return False

    @classmethod
    def _score_performance(cls, execution_time: float) -> float:
        if execution_time <= 0:
            return 0.5
        if execution_time < 1:
            return 1.0
        if execution_time < 5:
            return 0.8
        if execution_time < 15:
            return 0.6
        return 0.3

    @classmethod
    def _llm_judge(cls, code: str, task: str) -> float:
        if not code or len(code.strip()) < 10:
            return 0.0
        has_def = "def " in code
        has_class = "class " in code
        has_return = "return" in code
        score = 0.3
        if has_def:
            score += 0.25
        if has_class:
            score += 0.15
        if has_return:
            score += 0.15
        if len(code) > 200:
            score += 0.15
        return min(score, 1.0)
