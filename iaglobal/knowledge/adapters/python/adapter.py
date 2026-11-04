# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import importlib.metadata as _ilm
import logging
from typing import Optional

import aiohttp

from iaglobal.knowledge.adapters.python.package_mapper import (
    package_to_technology,
    pypi_health,
    pypi_to_package,
)
from iaglobal.knowledge.adapters.python.pypi_client import fetch_metadata, search_pypi
from iaglobal.knowledge.capability import Capability
from iaglobal.knowledge.package import PackageDescriptor
from iaglobal.knowledge.technology import TechnologyDescriptor

logger = logging.getLogger(__name__)


class PythonAdapter:
    """Discover Python packages from PyPI that match a capability.

    Two-phase discovery:

    1. **Local scan** — ``importlib.metadata`` lists installed distributions;
       any whose name or description contains a capability keyword is a
       candidate.
    2. **PyPI search** — queries the PyPI simple index for package names
       containing each keyword.

    Every candidate is enriched via ``fetch_metadata()`` (PyPI JSON API).
    The result is a list of ``TechnologyDescriptor`` instances,
    each marked with ``composite_score`` derived from real metadata.
    """

    ecosystem = "python"

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        self._session = session

    async def discover(
        self,
        capability: Capability,
    ) -> list[TechnologyDescriptor]:
        candidates: set[str] = set()

        # Phase 1 — installed packages
        candidates.update(_installed_matching(capability))

        # Phase 2 — PyPI search
        for kw in capability.keywords:
            pkgs = await search_pypi(kw, limit=5, session=self._session)
            candidates.update(pkgs)

        # Phase 3 — also try the capability id as a search term
        id_pkgs = await search_pypi(
            capability.id.replace("_", "-"), limit=3, session=self._session
        )
        candidates.update(id_pkgs)

        # Enrich each candidate with PyPI metadata
        results: list[TechnologyDescriptor] = []
        for name in sorted(candidates):
            raw = await fetch_metadata(name, session=self._session)
            if raw is None:
                continue
            meta = pypi_to_package(raw)
            health = pypi_health(raw)
            desc = package_to_technology(
                PackageDescriptor(metadata=meta, health=health),
                supports=frozenset({capability.id}),
                tags=frozenset({f"keyword:{kw}" for kw in capability.keywords}),
            )
            results.append(desc)

        return results


def _installed_matching(capability: Capability) -> set[str]:
    """Return names of installed distributions whose metadata matches the capability."""
    matched: set[str] = set()
    kw_lower = {k.lower() for k in capability.keywords}
    for dist in _ilm.distributions():
        name = dist.metadata.get("Name", "")
        summary = (dist.metadata.get("Summary", "") or "").lower()
        if name.lower() in kw_lower:
            matched.add(name)
            continue
        if any(kw in summary for kw in kw_lower):
            matched.add(name)
    return matched
