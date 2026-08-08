# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

from typing import FrozenSet, Optional

from iaglobal.knowledge.contracts import MaturityLevel
from iaglobal.knowledge.package import PackageDescriptor, PackageHealth, PyPIMetadata
from iaglobal.knowledge.technology import TechnologyDescriptor, TechnologyScore

# Map common PyPI classifiers → MaturityLevel
_CLASSIFIER_MATURITY: dict[str, MaturityLevel] = {
    "Development Status :: 1 - Planning": MaturityLevel.EXPERIMENTAL,
    "Development Status :: 2 - Pre-Alpha": MaturityLevel.EXPERIMENTAL,
    "Development Status :: 3 - Alpha": MaturityLevel.EXPERIMENTAL,
    "Development Status :: 4 - Beta": MaturityLevel.IMMATURE,
    "Development Status :: 5 - Production/Stable": MaturityLevel.MATURE,
    "Development Status :: 6 - Mature": MaturityLevel.STABLE,
    "Development Status :: 7 - Inactive": MaturityLevel.EXPERIMENTAL,
}

# Hard-coded mapping: classifier key → maturity weight used in composite score
_MATURITY_TO_WEIGHT: dict[MaturityLevel, float] = {
    MaturityLevel.EXPERIMENTAL: 0.35,
    MaturityLevel.IMMATURE: 0.55,
    MaturityLevel.MATURE: 0.75,
    MaturityLevel.STABLE: 0.9,
    MaturityLevel.GOLD: 1.0,
}


def _classifier_maturity(classifiers: tuple[str, ...]) -> MaturityLevel:
    for cl in classifiers:
        if cl in _CLASSIFIER_MATURITY:
            return _CLASSIFIER_MATURITY[cl]
    return MaturityLevel.EXPERIMENTAL


def _compute_difficulty(pkg: PyPIMetadata) -> float:
    """Estimate difficulty from dependency count and description length."""
    deps = len(pkg.dependencies)
    if deps > 15:
        return 0.7
    if deps > 8:
        return 0.5
    if deps > 3:
        return 0.3
    desc_len = len(pkg.summary)
    if desc_len > 500:
        return 0.4
    if desc_len > 200:
        return 0.25
    return 0.15


def pypi_to_package(raw_info: dict) -> PyPIMetadata:
    """Convert raw PyPI JSON ``info`` dict → ``PyPIMetadata``."""
    return PyPIMetadata(
        name=raw_info.get("name", ""),
        version=raw_info.get("version", "0.0.0"),
        summary=raw_info.get("summary", ""),
        license=raw_info.get("license", ""),
        python_versions=tuple(
            raw_info.get("requires_python", "").replace(" ", "").split(",")
            if raw_info.get("requires_python")
            else ()
        ),
        dependencies=tuple(raw_info.get("requires_dist", []) or []),
        classifiers=tuple(raw_info.get("classifiers", []) or []),
        home_page=raw_info.get("home_page", ""),
        documentation_url=raw_info.get("docs_url", ""),
        source_url=raw_info.get("project_urls", {}).get("Source", ""),
    )


def pypi_health(raw_info: dict) -> PackageHealth:
    """Extract health indicators from PyPI JSON ``info`` dict.

    Note: PyPI JSON ``info`` does not include download counts or stars by
    default.  This method returns a best-effort snapshot.  Full health data
    requires the ``pip index`` subprocess or a third-party API (e.g.,
    libraries.io, pepy.tech).
    """
    classifiers = raw_info.get("classifiers", []) or []
    has_tests = any(
        "test" in cl.lower() or "ci" in cl.lower() or "coverage" in cl.lower()
        for cl in classifiers
    )
    has_doc = bool(raw_info.get("docs_url")) or bool(raw_info.get("home_page"))
    return PackageHealth(
        has_tests=has_tests,
        has_documentation=has_doc,
    )


def package_to_technology(
    pkg: PackageDescriptor,
    supports: Optional[FrozenSet[str]] = None,
    aliases: Optional[FrozenSet[str]] = None,
    tags: Optional[FrozenSet[str]] = None,
    pros: Optional[tuple[str, ...]] = None,
    cons: Optional[tuple[str, ...]] = None,
) -> TechnologyDescriptor:
    """Map a ``PackageDescriptor`` → ``TechnologyDescriptor``.

    Infers maturity, difficulty, and score from PyPI metadata.
    """
    meta = pkg.metadata
    classifiers = meta.classifiers
    maturity = _classifier_maturity(classifiers)
    difficulty = _compute_difficulty(meta)

    offline = "offline" in (tags or frozenset()) or not any(
        kw in meta.summary.lower()
        for kw in ("api", "cloud", "network", "webhook", "http")
    )

    static = _MATURITY_TO_WEIGHT.get(maturity, 0.5) * (1.0 - difficulty * 0.3)

    health = pkg.health
    ecosystem = (
        (health.community_score + health.maintenance_score) / 2 if health else None
    )

    comp = TechnologyScore(
        static=round(static, 4),
        ecosystem_health=round(ecosystem, 4) if ecosystem is not None else None,
    )

    return TechnologyDescriptor(
        name=meta.name,
        supports=supports or frozenset(),
        maturity=maturity,
        difficulty=difficulty,
        offline=offline,
        license=meta.license,
        python_only=True,
        pros=pros or (),
        cons=cons or (),
        provenance=pkg.provenance,
        aliases=aliases or frozenset(),
        tags=tags or frozenset(),
        composite_score=comp,
    )
