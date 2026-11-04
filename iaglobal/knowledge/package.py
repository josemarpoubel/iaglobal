# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Package Intelligence — descoberta e metadados de pacotes PyPI.

Contratos para o que o PyPI Intelligence adapter produz.
Sem executor — apenas tipos.
"""

from __future__ import annotations

from dataclasses import dataclass

from iaglobal.knowledge.contracts import KnowledgeProvenance


@dataclass(frozen=True)
class PyPIMetadata:
    name: str
    version: str
    summary: str
    license: str
    python_versions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    classifiers: tuple[str, ...] = ()
    home_page: str = ""
    documentation_url: str = ""
    source_url: str = ""

    @property
    def is_installed(self) -> bool:
        try:
            __import__(self.name.replace("-", "_"))
            return True
        except ImportError:
            return False


@dataclass(frozen=True)
class PackageHealth:
    downloads_monthly: int = 0
    stars: int = 0
    last_release_days: int = 0
    open_issues: int = 0
    has_tests: bool = False
    has_documentation: bool = False

    @property
    def maintenance_score(self) -> float:
        if self.last_release_days > 365:
            return 0.2
        if self.last_release_days > 180:
            return 0.5
        if self.last_release_days > 30:
            return 0.8
        return 1.0

    @property
    def community_score(self) -> float:
        score = 0.0
        if self.downloads_monthly > 1_000_000:
            score += 0.5
        elif self.downloads_monthly > 100_000:
            score += 0.3
        elif self.downloads_monthly > 10_000:
            score += 0.1
        if self.stars > 10_000:
            score += 0.3
        elif self.stars > 1_000:
            score += 0.2
        elif self.stars > 100:
            score += 0.1
        return min(score, 1.0)


@dataclass(frozen=True)
class PackageDescriptor:
    metadata: PyPIMetadata
    health: PackageHealth | None = None
    provenance: KnowledgeProvenance | None = None

    @property
    def overall_score(self) -> float:
        base = 0.5
        if self.health:
            base += self.health.maintenance_score * 0.3
            base += self.health.community_score * 0.2
        return min(base, 1.0)
