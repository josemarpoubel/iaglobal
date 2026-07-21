# iaglobal/pipeline/context/serializers/context_serializer.py
"""
ContextSerializer — formato markdown/legível para LLMs locais.

Para cada NodeSection:
  - Primeiro item é tratado como descrição principal
  - Itens subsequentes são renderizados como lista
  - Seção vazia é omitida
"""

from __future__ import annotations

from typing import Optional

from ..protocol import NodeContext, NodeSection, CharTokenEstimator


class ContextSerializer:
    """Serializa NodeContext em texto markdown-style."""

    def __init__(self, estimator: Optional[CharTokenEstimator] = None):
        self._estimator = estimator or CharTokenEstimator()

    def serialize(
        self,
        ctx: NodeContext,
        system_role: Optional[str] = None,
        include_node_name: bool = True,
    ) -> str:
        ordered = sorted(ctx.sections, key=lambda s: -s.priority)
        parts: list[str] = []

        if system_role:
            parts.append(system_role)
            parts.append("")

        for section in ordered:
            if section.is_empty:
                continue
            parts.append(f"{section.title}:")
            for item in section.content:
                if item is None or (isinstance(item, str) and not item.strip()):
                    continue
                parts.append(f"- {item}")
            parts.append("")

        return "\n".join(parts).strip()

    def estimate(self, ctx: NodeContext) -> int:
        """Estima tokens que serialize() produziria."""
        return self._estimator.estimate(self.serialize(ctx))
