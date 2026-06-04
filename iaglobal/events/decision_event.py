from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DecisionEvent:
    step: str
    execution_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    action: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None

    selected: Optional[str] = None
    candidates: Optional[List[str]] = None

    scores_snapshot: Optional[Dict[str, float]] = None
    exploration: Optional[bool] = None
    reward_signal: Optional[float] = None

    triggered: Optional[bool] = None
    result: Optional[str] = None

    latency_ms: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionEvent":
        return cls(**data)


@dataclass(frozen=True)
class DecisionLock:
    execution_id: str
    selected_model: str
    strategy: str
    score: float
    scores_snapshot: Dict[str, float] = field(default_factory=dict)
    locked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionLock":
        data = dict(data)
        data.pop("locked_at", None)
        return cls(**data)


def resolve_locked_model(ctx: dict, fallback: str = "") -> str:
    lock_data = ctx.get("input", {}).get("metadata", {}).get("decision_lock")
    if lock_data and isinstance(lock_data, dict):
        model = lock_data.get("selected_model")
        if model:
            return model
    model = ctx.get("input", {}).get("metadata", {}).get("model")
    if model:
        return model
    return fallback
