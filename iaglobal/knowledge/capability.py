# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Capability Graph — capacidades como nós de uma árvore hierárquica.

Uma capacidade representa o *que* pode ser feito, não *como*.
Exemplo: "pdf_generation" é uma capacidade; "reportlab" é uma tecnologia
que a implementa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet


@dataclass(frozen=True)
class Capability:
    id: str
    parent: str | None = None
    children: tuple[str, ...] = ()
    aliases: frozenset[str] = frozenset()
    keywords: frozenset[str] = frozenset()
    description: str = ""


@dataclass
class CapabilityGraph:
    _nodes: dict[str, Capability] = field(default_factory=dict)

    def register(self, cap: Capability) -> None:
        self._nodes[cap.id] = cap

    def get(self, cap_id: str) -> Capability:
        if cap_id not in self._nodes:
            raise KeyError(f"Capability '{cap_id}' not registered")
        return self._nodes[cap_id]

    def ancestors(self, cap_id: str) -> list[Capability]:
        result: list[Capability] = []
        current = self._nodes.get(cap_id)
        while current and current.parent:
            parent = self._nodes.get(current.parent)
            if parent:
                result.append(parent)
                current = parent
            else:
                break
        return result

    def descendants(self, cap_id: str) -> list[Capability]:
        result: list[Capability] = []
        node = self._nodes.get(cap_id)
        if not node:
            return result
        for child_id in node.children:
            child = self._nodes.get(child_id)
            if child:
                result.append(child)
                result.extend(self.descendants(child_id))
        return result

    def has_cycles(self) -> bool:
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _dfs(nid: str) -> bool:
            visited.add(nid)
            rec_stack.add(nid)
            node = self._nodes.get(nid)
            if node:
                for child in node.children:
                    if child not in visited:
                        if _dfs(child):
                            return True
                    elif child in rec_stack:
                        return True
            rec_stack.discard(nid)
            return False

        return any(_dfs(nid) for nid in self._nodes if nid not in visited)

    @property
    def roots(self) -> list[Capability]:
        return [n for n in self._nodes.values() if n.parent is None]

    def resolve(self, text: str) -> list[Capability]:
        matched: list[Capability] = []
        text_lower = text.lower()
        for cap in self._nodes.values():
            if cap.id in text_lower:
                matched.append(cap)
                continue
            if any(a in text_lower for a in cap.aliases):
                matched.append(cap)
                continue
            if any(kw in text_lower for kw in cap.keywords):
                matched.append(cap)
                continue
        return matched
