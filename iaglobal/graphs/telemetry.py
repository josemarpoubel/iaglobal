# iaglobal/graphs/telemetry.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionEvent:
    node: str
    success: bool
    latency: float
    model: str
    strategy: str
    error: Optional[str] = None
    reward: float = 0.0  # Reward signal (Betaine layer)
    metadata: Optional[dict] = None  # Epigenetic context (domain, score, etc.)
