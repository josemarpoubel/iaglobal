"""RewardAggregator — combina múltiplos RewardSignals em score único ponderado."""

import logging
from typing import Dict, List, Optional

from iaglobal.feedback.reward_signal import RewardSignal, RewardSource

logger = logging.getLogger(__name__)

WEIGHTS = {
    RewardSource.USER: 0.4,
    RewardSource.BENCHMARK: 0.3,
    RewardSource.PRODUCTION: 0.2,
    RewardSource.VALIDATION: 0.1,
}


class RewardAggregator:
    """Agrega múltiplos sinais de recompensa em score composto."""

    def __init__(self, weights: Optional[Dict[RewardSource, float]] = None):
        self.weights = weights or WEIGHTS

    def aggregate(self, signals: List[RewardSignal]) -> float:
        if not signals:
            return 0.5

        total = 0.0
        weight_sum = 0.0

        for signal in signals:
            w = self.weights.get(signal.source, 0.1)
            total += signal.score * w
            weight_sum += w

        return round(total / max(weight_sum, 0.01), 2)

    def aggregate_by_source(self, signals: List[RewardSignal]) -> Dict[str, float]:
        by_source: Dict[str, List[float]] = {}
        for s in signals:
            key = s.source.value
            by_source.setdefault(key, []).append(s.score)

        return {k: round(sum(v) / len(v), 2) for k, v in by_source.items()}
