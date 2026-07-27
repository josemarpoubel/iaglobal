# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ResultAdapter — camada central de leitura de resultados de nós.

Substitui o padrão:
    coder_data.get("output", "") if isinstance(coder_data, dict) else str(...)

por:
    extract_output(coder_data)

Suporta dict legado e NodeResult. Depois que todos os consumidores
migrarem para as funções daqui, a compatibilidade com dict pode ser
removida em um único commit.
"""

from typing import Any, Optional, Dict, List

from iaglobal.core.node_result import NodeResult
from iaglobal.core.artifact import GeneratedArtifact


def extract_output(value: Any) -> str:
    if isinstance(value, NodeResult):
        return value.output or ""
    if isinstance(value, dict):
        return str(value.get("output", "") or "")
    return str(value or "")


def extract_artifact(value: Any) -> Optional[GeneratedArtifact]:
    if isinstance(value, NodeResult):
        if value.artifacts:
            return value.artifacts[0]
        if value.output:
            return GeneratedArtifact.from_str(value.output)
        return None
    if isinstance(value, dict):
        artifact = value.get("artifact")
        if isinstance(artifact, GeneratedArtifact):
            return artifact
        output = str(value.get("output", "") or "")
        if output:
            return GeneratedArtifact.from_str(output)
        return None
    if isinstance(value, GeneratedArtifact):
        return value
    if isinstance(value, str) and value.strip():
        return GeneratedArtifact.from_str(value)
    return None


def extract_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, NodeResult):
        return dict(value.metadata)
    if isinstance(value, dict):
        return dict(value.get("metadata", {}) or {})
    return {}


def extract_errors(value: Any) -> List[str]:
    if isinstance(value, NodeResult):
        return list(value.errors)
    if isinstance(value, dict):
        errors = value.get("errors") or (
            [str(value["error"])] if "error" in value and value["error"] else []
        )
        return list(errors)
    return []


def extract_warnings(value: Any) -> List[str]:
    if isinstance(value, NodeResult):
        return list(value.warnings)
    if isinstance(value, dict):
        return list(value.get("warnings") or [])
    return []


def is_successful(value: Any) -> bool:
    if isinstance(value, NodeResult):
        return value.success
    if isinstance(value, dict):
        return bool(value.get("success", False))
    return False


def extract_metric(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, NodeResult):
        return value.metrics.get(key, default)
    if isinstance(value, dict):
        metrics = value.get("metrics") or value.get("execution_metrics") or {}
        return metrics.get(key, default)
    return default


def is_skipped(value: Any) -> bool:
    if isinstance(value, NodeResult):
        return value.metadata.get("skipped", False) is True
    if isinstance(value, dict):
        return value.get("skipped", False) is True
    return False


def extract_field(value: Any, key: str, default: Any = None) -> Any:
    """Lê um campo arbitrário de dict legado ou NodeResult.

    Prioridade:
    1. atributo direto do NodeResult
    2. NodeResult.metadata
    3. NodeResult.metrics
    4. chave do dict legado
    5. default
    """
    if isinstance(value, NodeResult):
        if hasattr(value, key):
            attr = getattr(value, key)
            if attr is not None:
                return attr
        if key in value.metadata:
            return value.metadata[key]
        if key in value.metrics:
            return value.metrics[key]
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return default


def extract_one(memory: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Lê de ctx['memory'][key] de maneira compatível com dict | NodeResult."""
    if not isinstance(memory, dict):
        return default
    value = memory.get(key)
    if value is None:
        return default
    return value
