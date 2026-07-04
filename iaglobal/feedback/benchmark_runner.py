"""BenchmarkRunner — executa suite de testes e produz score por categoria."""

import logging
from typing import Any, Dict, List, Optional

from iaglobal.feedback.reward_signal import RewardSignal, RewardSource

logger = logging.getLogger(__name__)

BENCHMARK_CATEGORIES = ["syntax", "security", "performance", "structure", "coverage"]


class BenchmarkRunner:
    """Executa suite de validações contra o resultado."""

    @classmethod
    def run(cls, code: str, task: str = "", categories: Optional[List[str]] = None) -> RewardSignal:
        cats = categories or BENCHMARK_CATEGORIES
        scores = {}

        for cat in cats:
            func = getattr(cls, f"_bench_{cat}", None)
            if func:
                scores[cat] = func(code)

        overall = sum(scores.values()) / max(len(scores), 1)

        return RewardSignal(
            score=overall,
            source=RewardSource.BENCHMARK,
            metadata={"categories": scores, "overall": overall},
            task=task,
        )

    @classmethod
    def _bench_syntax(cls, code: str) -> float:
        try:
            compile(code, "<benchmark>", "exec")
            return 1.0
        except SyntaxError:
            return 0.0

    @classmethod
    def _bench_security(cls, code: str) -> float:
        dangerous = ["eval(", "exec(", "__import__(", "os.system", "subprocess.call",
                      "pickle.loads", "shelve.open"]
        code_lower = code.lower()
        found = sum(1 for d in dangerous if d in code_lower)
        return max(0.0, 1.0 - (found * 0.2))

    @classmethod
    def _bench_performance(cls, code: str) -> float:
        lines = len(code.split("\n"))
        if lines < 5:
            return 0.5
        if lines > 500:
            return 0.6
        return 1.0

    @classmethod
    def _bench_structure(cls, code: str) -> float:
        score = 1.0
        if "def " not in code:
            score -= 0.3
        if "class " not in code and len(code) > 500:
            score -= 0.2
        return max(0.0, score)

    @classmethod
    def _bench_coverage(cls, code: str) -> float:
        has_docstring = '"""' in code or "'''" in code
        has_tests = "def test_" in code or "assert " in code
        score = 0.5
        if has_docstring:
            score += 0.25
        if has_tests:
            score += 0.25
        return score
