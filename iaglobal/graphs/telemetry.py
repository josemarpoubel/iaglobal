#iaglobal/graphs/telemetry.py

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
