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
            "latency": 0.0,
            "reward_total": 0.0,
            "reward_count": 0,
        })

    def record(self, event: ExecutionEvent):
        key = (event.node, event.model, event.strategy)

        self.stats[key]["latency"] += event.latency

        if event.success:
            self.stats[key]["success"] += 1
        else:
            self.stats[key]["fail"] += 1

        if hasattr(event, "reward") and event.reward != 0.0:
            self.stats[key]["reward_total"] += event.reward
            self.stats[key]["reward_count"] += 1

    def score(self, node: str, model: str, strategy: str) -> float:
        key = (node, model, strategy)
        s = self.stats[key]

        total = s["success"] + s["fail"]

        if total == 0:
            return 0.5

        success_rate = s["success"] / total

        # Integra reward signal (Betaine layer) se disponível
        if s["reward_count"] > 0:
            avg_reward = s["reward_total"] / s["reward_count"]
            return (success_rate * 0.7) + (avg_reward * 0.3)

        return success_rate


class ContextualCreditMemory:
    def __init__(self):
        # context_key → model → stats
        self.data = defaultdict(lambda: defaultdict(list))

    def record(self, context: str, model: str, reward: float):
        self.data[context][model].append(reward)

    def get_expected_reward(self, context: str, model: str) -> float:
        values = self.data[context][model]

        if not values:
            return 0.0

        return sum(values) / len(values)
