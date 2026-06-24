# iaglobal/events/decision_event.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from iaglobal.utils.logger import logger

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

    def __post_init__(self):
        """Validação pós-inicialização."""
        logger.debug(f"📝 [EVENT] Criado evento para {self.step} (ID: {self.execution_id})")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionEvent":
        try:
            return cls(**data)
        except Exception as e:
            logger.error(f"❌ [EVENT] Falha ao reconstruir DecisionEvent: {e}")
            raise

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
        # Evita mutação e lida com o campo gerado automaticamente
        data = dict(data)
        data.pop("locked_at", None)
        return cls(**data)


