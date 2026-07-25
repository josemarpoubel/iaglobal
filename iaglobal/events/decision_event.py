# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/events/decision_event.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional

from iaglobal.events.event_types import EventType
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
        logger.debug(
            f"📝 [EVENT] Criado evento para {self.step} (ID: {self.execution_id})"
        )

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


@dataclass(frozen=True)
class CapabilityDecisionEvent:
    """Emitted when the CapabilityResolver picks a technology.

    Carries the full decision trace so downstream consumers (EventStore,
    CausalEngine, Bandit feedback, episodic memory) can reconstruct *why*
    a technology was chosen for a given capability.

    Spec-aligned fields (``mission_id``, ``selected_provider``,
    ``selected_technology``, ``fallback_used``, ``timestamp``) coexist
    with the evidence-projection (``validation_confidence``,
    ``effective_score``, ``bandit_score``, ``reason``, ``evidence``,
    ``candidate_count``, ``filtered_count``,
    ``decision_confidence``).

    The ``evidence`` field is internally a :class:`MappingProxyType`
    so the contract is *truly* immutable — not only is the dataclass
    frozen, but the underlying mapping cannot be mutated either.
    """

    mission_id: str
    capability: str
    selected_technology: str | None
    validation_confidence: float
    effective_score: float
    bandit_score: float
    reason: tuple[str, ...]
    fallback_used: bool
    candidate_count: int
    filtered_count: int
    selected_provider: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        # Freeze the evidence mapping so consumers cannot silently mutate
        # the decision trace after emission. ``frozen=True`` on the
        # dataclass only protects the *slots* — inner dicts are still
        # mutable unless we wrap them.
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))

    @property
    def event_type(self) -> str:
        return EventType.CAPABILITY_SELECTED

    @property
    def decision_confidence(self) -> float:
        """Aggregate confidence for *this specific decision* (0..1).

        Combines epistemological signal (validation confidence 40%),
        operational score (effective score 30%) and exploratory policy
        (bandit score 30%). Returns the type's invariant 0 when no
        signal is present.
        """
        return round(
            self.validation_confidence * 0.4
            + self.effective_score * 0.3
            + self.bandit_score * 0.3,
            4,
        )

    def to_dict(self) -> Dict[str, Any]:
        # Manual field-by-field copy — ``asdict()`` deep-copies via
        # pickle and MappingProxyType is not picklable. ``reason``
        # stays as ``tuple`` so the serialized form preserves the
        # dataclass type contract; downstream JSON encoding will
        # naturally promote it to array.
        return {
            "mission_id": self.mission_id,
            "capability": self.capability,
            "selected_technology": self.selected_technology,
            "validation_confidence": self.validation_confidence,
            "effective_score": self.effective_score,
            "bandit_score": self.bandit_score,
            "reason": tuple(self.reason),
            "fallback_used": self.fallback_used,
            "candidate_count": self.candidate_count,
            "filtered_count": self.filtered_count,
            "selected_provider": self.selected_provider,
            "evidence": dict(self.evidence),
            "timestamp": self.timestamp,
            "decision_confidence": self.decision_confidence,
        }
