# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from dataclasses import dataclass, field
from typing import Any, Optional

from iaglobal.core.artifact import GeneratedArtifact


@dataclass(slots=True)
class NodeResult:
    success: bool
    output: Optional[str] = None

    artifacts: list[GeneratedArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "success": self.success,
            "output": self.output,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metrics": dict(self.metrics),
            "metadata": dict(self.metadata),
        }
        if self.artifacts:
            d["artifacts"] = [
                {
                    "content": a.content,
                    "kind": a.kind.value if hasattr(a.kind, "value") else str(a.kind),
                    "source": a.source,
                    "confidence": a.confidence,
                    "metadata": dict(a.metadata),
                }
                for a in self.artifacts
            ]
        return d


def normalize_node_result(raw: Any) -> NodeResult:
    if isinstance(raw, NodeResult):
        return raw

    if isinstance(raw, dict):
        artifacts_raw = raw.get("artifacts") or []
        artifacts = [
            a if isinstance(a, GeneratedArtifact) else GeneratedArtifact(
                content=a.get("content", "") if isinstance(a, dict) else str(a),
                metadata={},
            )
            for a in artifacts_raw
        ]

        return NodeResult(
            success=bool(raw.get("success", False)),
            output=str(raw["output"]) if "output" in raw and raw["output"] is not None else None,
            artifacts=artifacts,
            warnings=list(raw.get("warnings") or []),
            errors=list(raw.get("errors") or []),
            metrics=dict(raw.get("metrics") or raw.get("execution_metrics") or {}),
            metadata=dict(raw.get("metadata") or {}),
        )

    raise TypeError(
        f"Expected NodeResult or dict, got {type(raw).__name__}: {raw!r}"
    )
