# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

from typing import Optional

from iaglobal.knowledge.constraints.extractor import ConstraintSet
from iaglobal.knowledge.technology import TechnologyDescriptor


def filter_technologies(
    candidates: list[TechnologyDescriptor],
    constraints: ConstraintSet,
) -> list[TechnologyDescriptor]:
    """Remove technologies that violate the given constraints.

    Keeps technologies that satisfy ALL specified constraints.
    Unspecified constraints (``None``) are treated as "accept all".
    Preserves relative order.
    """
    if constraints.is_empty:
        return list(candidates)
    return [t for t in candidates if satisfies_constraints(t, constraints)]


def satisfies_constraints(
    tech: TechnologyDescriptor,
    constraints: ConstraintSet,
) -> bool:
    """Check if a single TechnologyDescriptor meets all constraints."""
    if constraints.offline is True and not tech.offline:
        return False
    if constraints.offline is False and tech.offline:
        return False
    if constraints.network is True and tech.offline:
        return False
    if constraints.network is False and not tech.offline:
        return False
    if constraints.runtime is not None:
        if constraints.runtime not in tech.execution_runtime:
            return False
    if constraints.gpu is True and not _has_gpu_tag(tech):
        return False
    if constraints.tags:
        if not tech.tags or not constraints.tags.issubset(tech.tags):
            return False
    # artifact constraint: check if the artifact type is in tech.supports
    if constraints.artifact is not None:
        if not _matches_artifact(tech, constraints.artifact):
            return False
    return True


def _matches_artifact(tech: TechnologyDescriptor, artifact: str) -> bool:
    """Check if the technology's capabilities match the artifact type."""
    cap_to_artifact: dict[str, str] = {
        "pdf_generation": "pdf",
        "html_to_pdf": "pdf",
        "pdf_reading": "pdf",
        "pdf_merging": "pdf",
        "web_backend": "api",
        "rest_api": "api",
        "api_development": "api",
        "cli_application": "cli",
        "command_line": "cli",
        "spreadsheet": "spreadsheet",
        "excel_reading": "spreadsheet",
        "excel_writing": "spreadsheet",
        "image_processing": "image",
        "image_manipulation": "image",
        "dashboard": "dashboard",
        "web_application": "html",
    }
    for cap in tech.supports:
        if cap in cap_to_artifact and cap_to_artifact[cap] == artifact:
            return True
    if artifact == "pdf" and any("pdf" in cap for cap in tech.supports):
        return True
    return False


def _has_gpu_tag(tech: TechnologyDescriptor) -> bool:
    """Check if a technology mentions GPU capability."""
    combined = (
        " ".join(tech.supports).lower()
        + " "
        + " ".join(tech.tags or frozenset()).lower()
    )
    combined += " " + " ".join(tech.pros or ()).lower()
    return any(hint in combined for hint in {"gpu", "cuda", "gpu-accelerated"})
