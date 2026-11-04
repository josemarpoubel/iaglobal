# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
TechnologyAdapter — protocolo para adaptadores de ecossistema.

Cada adaptador descobre tecnologias em um ecossistema específico:
- PythonAdapter: PyPI, pip index, importlib.metadata
- npmAdapter: npm registry
- cratesAdapter: crates.io
- DockerAdapter: Docker Hub

O protocolo garante que nenhum adaptador precise conhecer o KnowledgeEngine,
e que o KnowledgeEngine possa alternar entre adaptadores sem mudar contratos.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iaglobal.knowledge.capability import Capability
from iaglobal.knowledge.technology import TechnologyDescriptor


@runtime_checkable
class TechnologyAdapter(Protocol):
    ecosystem: str

    async def discover(
        self,
        capability: Capability,
    ) -> list[TechnologyDescriptor]: ...
