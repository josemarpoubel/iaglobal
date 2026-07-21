# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Awareness Cache Models v3.1

Modelos estendidos para:
- Consciência causal (v2)
- Atenção seletiva (v2)
- Memória episódica (v2)
- Temporal versioning (v3.1)
- Epistemologia operacional / Confiança cognitiva (v3.1)
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class NodeDomain(str, Enum):
    """Domínios de atuação dos nós para atenção seletiva."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    CODING = "coding"
    PLANNING = "planning"
    CRITIC = "critic"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    GENERAL = "general"


class NodeStatus(str, Enum):
    """Estados possíveis de um nó."""

    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    IDLE = "idle"


@dataclass(frozen=True)
class AgentActivity:
    """Atividade de um agente na execução atual (imutável)."""

    execution_id: str
    node_id: str
    status: str
    summary: str
    metadata: dict[str, Any]
    timestamp: float
    domain: str = NodeDomain.GENERAL.value
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    blocks: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.5  # v3.1: confiança cognitiva

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "status": self.status,
            "summary": self.summary,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "domain": self.domain,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "confidence": self.confidence,
        }

    @classmethod
    def from_row(cls, row: dict, execution_id: str) -> "AgentActivity":
        """Cria instância a partir de linha do SQLite."""
        import cbor2

        metadata = cbor2.loads(row["metadata"]) if row["metadata"] else {}
        domain = metadata.get("_domain", NodeDomain.GENERAL.value)
        depends_on = tuple(metadata.get("_depends_on", []))
        blocks = tuple(metadata.get("_blocks", []))
        confidence = metadata.get("_confidence", 0.5)
        return cls(
            execution_id=execution_id,
            node_id=row["node_id"],
            status=row["status"],
            summary=row["summary"] or "",
            metadata={k: v for k, v in metadata.items() if not k.startswith("_")},
            timestamp=row["updated_at"],
            domain=domain,
            depends_on=depends_on,
            blocks=blocks,
            confidence=confidence,
        )


@dataclass(frozen=True)
class CausalChain:
    """Cadeia causal de dependência entre nós."""

    execution_id: str
    blocked_node: str
    blocking_chain: tuple[str, ...]  # nó -> o que bloqueia -> ...
    root_cause: str | None
    depth: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "blocked_node": self.blocked_node,
            "blocking_chain": self.blocking_chain,
            "root_cause": self.root_cause,
            "depth": self.depth,
        }


@dataclass(frozen=True)
class DomainSnapshot:
    """Snapshot filtrado por domínio."""

    execution_id: str
    domain: str
    activities: tuple[AgentActivity, ...]
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "domain": self.domain,
            "activities": [a.to_dict() for a in self.activities],
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class EpisodicMemory:
    """Memória episódica de uma execução completa."""

    execution_id: str
    started_at: float
    ended_at: float
    nodes: dict[str, AgentActivity]
    causal_chains: tuple[CausalChain, ...]
    final_status: str  # completed, failed, partial
    ivm_score: float
    lessons_learned: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.ended_at - self.started_at,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "causal_chains": [c.to_dict() for c in self.causal_chains],
            "final_status": self.final_status,
            "ivm_score": self.ivm_score,
            "lessons_learned": self.lessons_learned,
        }


# ============================================================
# v3.1 — EPISTEMOLOGIA OPERACIONAL: Confiança Cognitiva
# ============================================================


@dataclass(frozen=True)
class ConfidenceTrace:
    """
    Trace completo do cálculo de confiança — explicabilidade nativa.

    Versão: 1.0
    Permite responder: "Por que essa confiança é 0.63?"
    """

    version: str = "1.0"
    domain: str = ""
    artifact_id: str | None = None
    base: float = 0.5
    positive: dict[str, float] = field(default_factory=dict)
    negative: dict[str, float] = field(default_factory=dict)
    final: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "domain": self.domain,
            "artifact_id": self.artifact_id,
            "base": self.base,
            "positive": self.positive,
            "negative": self.negative,
            "final": self.final,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfidenceTrace":
        return cls(
            version=data.get("version", "1.0"),
            domain=data.get("domain", ""),
            artifact_id=data.get("artifact_id"),
            base=data.get("base", 0.5),
            positive=data.get("positive", {}),
            negative=data.get("negative", {}),
            final=data.get("final", 0.5),
        )


@dataclass(frozen=True)
class ArtifactConfidence:
    """
    Confiança consolidada em um artefato produzido.

    Diferente da confiança no agente: esta é a confiança NO CONHECIMENTO
    gerado (ex: endpoint, schema, documento).
    """

    artifact_id: str
    artifact_type: str  # "endpoint", "schema", "document", "module"
    confidence: float
    contributors: tuple[str, ...]  # agentes que participaram
    domain: str
    trace: ConfidenceTrace
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "confidence": self.confidence,
            "contributors": list(self.contributors),
            "domain": self.domain,
            "trace": self.trace.to_dict(),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ConfidenceSnapshot:
    """
    Snapshot temporal de confiança para um nó/artefato.

    Usado para construir curvas de maturidade (confiança vs tempo).
    """

    execution_id: str
    node_id: str
    artifact_id: str | None
    domain: str
    confidence: float
    trace: ConfidenceTrace
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "artifact_id": self.artifact_id,
            "domain": self.domain,
            "confidence": self.confidence,
            "trace": self.trace.to_dict(),
            "timestamp": self.timestamp,
        }


# ============================================================
# v3.1 — Cálculo de Confiança (Determinístico, Composicional)
# ============================================================


@dataclass(frozen=True)
class AwarenessExecutionContext:
    """Contexto operacional para cálculo de confiança."""

    tests_passed: bool = False
    ast_valid: bool = False
    auditor_approved: bool = False
    consensus_reached: bool = False
    retry_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    warning_count: int = 0
    domain: str = ""
    artifact_id: str | None = None


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Limita valor ao intervalo [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def compute_confidence(
    context: AwarenessExecutionContext,
) -> tuple[float, ConfidenceTrace]:
    """
    Calcula confiança de forma determinística e composicional.

    Returns:
        (confidence_score, trace) — score clamped [0,1] + trace explicativo

    Fórmula:
        score = base + sum(positive_signals) - sum(penalties)
        clamp: [0.0, 1.0]

    Sinais positivos:
        +0.20  tests_passed
        +0.15  ast_valid
        +0.15  auditor_approved
        +0.10  consensus_reached

    Penalidades:
        -0.15 * retry_count
        -0.20 * failure_count
        -0.10 * timeout_count
        -0.05 * warning_count
    """
    trace = ConfidenceTrace(
        base=0.5,
        domain=context.domain,
        artifact_id=context.artifact_id,
    )
    score = 0.5

    # Sinais positivos (aditivos)
    if context.tests_passed:
        score += 0.20
        trace.positive["tests_passed"] = 0.20
    if context.ast_valid:
        score += 0.15
        trace.positive["ast_valid"] = 0.15
    if context.auditor_approved:
        score += 0.15
        trace.positive["auditor_approved"] = 0.15
    if context.consensus_reached:
        score += 0.10
        trace.positive["consensus_reached"] = 0.10

    # Penalidades (subtrativas)
    if context.retry_count:
        penalty = 0.15 * context.retry_count
        score -= penalty
        trace.negative["retry"] = penalty
    if context.failure_count:
        penalty = 0.20 * context.failure_count
        score -= penalty
        trace.negative["failure"] = penalty
    if context.timeout_count:
        penalty = 0.10 * context.timeout_count
        score -= penalty
        trace.negative["timeout"] = penalty
    if context.warning_count:
        penalty = 0.05 * context.warning_count
        score -= penalty
        trace.negative["validation_warning"] = penalty

    score = clamp(score)
    # Cria novo trace com final (frozen dataclass não permite mutação)
    final_trace = ConfidenceTrace(
        version=trace.version,
        domain=trace.domain,
        artifact_id=trace.artifact_id,
        base=trace.base,
        positive=trace.positive,
        negative=trace.negative,
        final=score,
    )
    return score, final_trace


def effective_confidence(
    historical_confidence: float,
    created_at: float,
    now: float,
    half_life_hours: float = 720,  # 30 dias default
) -> float:
    """
    Decaimento exponencial de confiança histórica.

    Args:
        historical_confidence: confiança registrada no evento
        created_at: timestamp do evento original
        now: timestamp atual
        half_life_hours: meia-vida em horas (configurável por domínio)

    Returns:
        Confiança efetiva ajustada por idade
    """
    age_hours = (now - created_at) / 3600.0
    decay = 0.5 ** (age_hours / half_life_hours)
    return historical_confidence * decay


# ============================================================
# Helpers de serialização CBOR2 para ConfidenceTrace
# ============================================================


def serialize_confidence_trace(trace: ConfidenceTrace) -> bytes:
    """Serializa ConfidenceTrace para CBOR2."""
    import cbor2

    return cbor2.dumps(trace.to_dict())


def deserialize_confidence_trace(blob: bytes | None) -> ConfidenceTrace | None:
    """Deserializa ConfidenceTrace de CBOR2."""
    if blob is None:
        return None
    import cbor2

    data = cbor2.loads(blob)
    return ConfidenceTrace.from_dict(data)


def serialize_contributors(contributors: list[str] | tuple[str, ...]) -> bytes:
    """Serializa lista de contribuidores para CBOR2."""
    import cbor2

    return cbor2.dumps(list(contributors))


def deserialize_contributors(blob: bytes | None) -> list[str]:
    """Deserializa lista de contribuidores de CBOR2."""
    if blob is None:
        return []
    import cbor2

    return cbor2.loads(blob)
