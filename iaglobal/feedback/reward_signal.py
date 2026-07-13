"""RewardSignal — representação de feedback de múltiplas fontes."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
import time


class RewardSource(Enum):
    USER = "user"
    BENCHMARK = "benchmark"
    PRODUCTION = "production"
    VALIDATION = "validation"


@dataclass
class RewardSignal:
    score: float
    source: RewardSource
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    task: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def is_positive(self) -> bool:
        return self.score >= 0.6

    def is_negative(self) -> bool:
        return self.score < 0.4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "source": self.source.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "task": self.task,
        }
