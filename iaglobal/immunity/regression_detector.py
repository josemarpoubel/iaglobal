"""RegressionDetector — compara fitness atual vs histórico, alerta se score cai > 20%."""

import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

REGRESSION_THRESHOLD = 0.2


class RegressionDetector:
    """Detecta regressões comparando scores atuais com média histórica."""

    def __init__(self, threshold: float = REGRESSION_THRESHOLD):
        self.threshold = threshold
        self._history: Dict[str, List[float]] = defaultdict(list)

    def record_score(self, node_name: str, score: float):
        self._history[node_name].append(score)

    def check(self, node_name: str, current_score: float) -> Dict[str, Any]:
        self.record_score(node_name, current_score)
        history = self._history.get(node_name, [])

        if len(history) < 3:
            return {"regression": False, "node": node_name, "reason": "histórico insuficiente"}

        avg_past = sum(history[:-1]) / (len(history) - 1)
        delta = avg_past - current_score

        if delta > self.threshold:
            return {
                "regression": True,
                "node": node_name,
                "previous_avg": round(avg_past, 2),
                "current": current_score,
                "delta": round(delta, 2),
                "threshold": self.threshold,
            }

        return {"regression": False, "node": node_name, "delta": round(delta, 2)}

    def recent_regressions(self, min_records: int = 3) -> List[Dict[str, Any]]:
        results = []
        for node, scores in self._history.items():
            if len(scores) < min_records:
                continue
            avg = sum(scores) / len(scores)
            last = scores[-1]
            if avg - last > self.threshold:
                results.append({"node": node, "avg": round(avg, 2), "last": last})
        return results
