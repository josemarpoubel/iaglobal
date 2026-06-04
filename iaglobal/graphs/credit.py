# iaglobal/graphs/credit.py

from collections import defaultdict
from iaglobal.graphs.telemetry import ExecutionEvent


class CreditAssignmentEngine:
    """
    🧠 Aprende quais decisões geram bons resultados
    """

    def __init__(self):
        self.stats = defaultdict(lambda: {
            "success": 0,
            "fail": 0,
            "latency": 0.0
        })

    def record(self, event: ExecutionEvent):

        key = (event.node, event.model, event.strategy)

        self.stats[key]["latency"] += event.latency

        if event.success:
            self.stats[key]["success"] += 1
        else:
            self.stats[key]["fail"] += 1

    def score(self, node, model, strategy) -> float:

        key = (node, model, strategy)
        s = self.stats[key]

        total = s["success"] + s["fail"]

        if total == 0:
            return 0.5

        return s["success"] / total
