# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
NodeResult é o contrato interno de retorno de todos os nós do pipeline.

to_dict() existe apenas para persistência, logs e compatibilidade externa.
NUNCA usar como transporte interno entre componentes do pipeline.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from iaglobal.core.artifact import GeneratedArtifact


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "ok"}
    return bool(value)


@dataclass(slots=True)
class NodeResult:
    success: bool
    output: Optional[str] = None

    artifacts: list[GeneratedArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "output":
            return self.output
        if key == "success":
            return self.success
        if key == "artifact":
            return self.artifacts[0] if self.artifacts else None
        if key in ("metrics", "execution_metrics"):
            return dict(self.metrics)
        if key == "metadata":
            return dict(self.metadata)
        if key == "warnings":
            return list(self.warnings)
        if key == "errors":
            return list(self.errors)
        return self.metadata.get(key, self.metrics.get(key, default))

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


def normalize_node_result(raw: Any, warnings: Optional[list[str]] = None) -> NodeResult:
    if isinstance(raw, NodeResult):
        return raw

    if not isinstance(raw, dict):
        raise TypeError(
            f"Expected NodeResult or dict, got {type(raw).__name__}: {raw!r}"
        )

    acc_warnings = list(warnings) if warnings else []

    artifacts_raw = raw.get("artifacts") or []
    artifacts: list[GeneratedArtifact] = []
    for a in artifacts_raw:
        if isinstance(a, GeneratedArtifact):
            artifacts.append(a)
        elif isinstance(a, dict):
            content = a.get("content", "")
            if not content:
                acc_warnings.append(
                    "Artifact sem conteúdo recebido durante normalização"
                )
            artifacts.append(GeneratedArtifact(content=content, metadata={}))
        else:
            artifacts.append(GeneratedArtifact(content=str(a), metadata={}))

    return NodeResult(
        success=_normalize_bool(raw.get("success")),
        output=str(raw["output"])
        if "output" in raw and raw["output"] is not None
        else None,
        artifacts=artifacts,
        warnings=acc_warnings + list(raw.get("warnings") or []),
        errors=list(
            raw.get("errors")
            or ([str(raw["error"])] if "error" in raw and raw["error"] else [])
        ),
        metrics=dict(raw.get("metrics") or raw.get("execution_metrics") or {}),
        metadata=dict(raw.get("metadata") or {}),
    )
