# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConstraintSet:
    """Constraints extracted from a mission prompt.

    Each field is ``None`` when the prompt does not specify the constraint.
    None means "no constraint" (accept any), not "prohibit".
    """

    offline: bool | None = None
    artifact: str | None = None
    runtime: str | None = None
    network: bool | None = None
    memory_mb: int | None = None
    python_version: str | None = None
    gpu: bool | None = None
    tags: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_empty(self) -> bool:
        return (
            all(
                v is None
                for v in (
                    self.offline,
                    self.artifact,
                    self.runtime,
                    self.network,
                    self.memory_mb,
                    self.python_version,
                    self.gpu,
                )
            )
            and not self.tags
        )

    def apply_to(self, tech: "TechnologyDescriptor") -> bool:  # noqa: F821
        """Check if a TechnologyDescriptor satisfies these constraints.

        Imported lazily to avoid circular dependency.
        """
        from iaglobal.knowledge.constraints.filter import satisfies_constraints

        return satisfies_constraints(tech, self)


# Keyword maps for heuristic extraction
_RUNTIME_KEYWORDS: dict[str, str] = {
    "python": "python",
    "node": "node",
    "javascript": "node",
    "typescript": "node",
    "rust": "rust",
    "go": "go",
    "java": "java",
    "ruby": "ruby",
    "php": "php",
    "c++": "cpp",
    "c#": "dotnet",
}

_ARTIFACT_KEYWORDS: dict[str, str] = {
    "pdf": "pdf",
    "report": "pdf",
    "pdf generation": "pdf",
    "html": "html",
    "web page": "html",
    "api": "api",
    "rest api": "api",
    "restful": "api",
    "cli": "cli",
    "command line": "cli",
    "dashboard": "dashboard",
    "gui": "gui",
    "desktop": "gui",
    "mobile": "mobile",
    "spreadsheet": "spreadsheet",
    "excel": "spreadsheet",
    "chart": "chart",
    "graph": "chart",
    "database": "database",
    "image": "image",
    "video": "video",
}

_OFFLINE_HINTS = {
    "offline",
    "local",
    "no internet",
    "without network",
    "standalone",
    "disconnected",
    "air-gapped",
    "intranet",
}

_NETWORK_HINTS = {
    "online",
    "cloud",
    "saas",
    "api",
    "webhook",
    "remote",
    "server",
    "client-server",
    "distributed",
}

_GPU_HINTS = {
    "gpu",
    "cuda",
    "rocm",
    "tensor",
    "gpu-accelerated",
    "deep learning",
    "neural",
    "training",
}


class ConstraintExtractor:
    """Extract technology constraints from a mission prompt.

    Uses keyword heuristics only — no LLM, no NLP model.

    Boundary Rule compliant: deterministic, no external calls.
    """

    def extract(self, text: str) -> ConstraintSet:
        """Parse *text* and return the inferred ``ConstraintSet``."""
        lower = text.lower()

        offline = self._detect_offline(lower)
        network = self._detect_network(lower, offline)
        artifact = self._detect_artifact(lower)
        runtime = self._detect_runtime(lower)
        memory_mb = self._detect_memory(lower)
        python_version = self._detect_python_version(lower)
        gpu = self._detect_gpu(lower)
        tags = self._extract_tags(lower)

        return ConstraintSet(
            offline=offline,
            artifact=artifact,
            runtime=runtime,
            network=network,
            memory_mb=memory_mb,
            python_version=python_version,
            gpu=gpu,
            tags=frozenset(tags),
        )

    @staticmethod
    def _detect_offline(text: str) -> bool | None:
        for hint in _OFFLINE_HINTS:
            if hint in text:
                return True
        return None

    @staticmethod
    def _detect_network(text: str, offline: bool | None) -> bool | None:
        if offline:
            return False
        for hint in _NETWORK_HINTS:
            if hint in text:
                return True
        return None

    @staticmethod
    def _detect_artifact(text: str) -> str | None:
        for phrase, artifact in sorted(
            _ARTIFACT_KEYWORDS.items(), key=lambda x: -len(x[0])
        ):
            if phrase in text:
                return artifact
        return None

    @staticmethod
    def _detect_runtime(text: str) -> str | None:
        for keyword, runtime in _RUNTIME_KEYWORDS.items():
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, text):
                return runtime
        return None

    @staticmethod
    def _detect_memory(text: str) -> int | None:
        m = re.search(r"(\d+)\s*m[bg]", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _detect_python_version(text: str) -> str | None:
        m = re.search(r"python\s*([23]\.\d+(?:\.\d+)?)", text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _detect_gpu(text: str) -> bool | None:
        for hint in _GPU_HINTS:
            if hint in text:
                return True
        return None

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        """Extract meaningful tags from the text."""
        tags: list[str] = []
        if "test" in text:
            tags.append("testing")
        if "security" in text or "secure" in text:
            tags.append("security")
        if "performance" in text or "fast" in text or "speed" in text:
            tags.append("performance")
        if "async" in text or "concurrent" in text:
            tags.append("async")
        if "real-time" in text or "realtime" in text:
            tags.append("realtime")
        if "embedded" in text:
            tags.append("embedded")
        if "microservice" in text:
            tags.append("microservice")
        return tags
