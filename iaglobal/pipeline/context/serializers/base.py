# iaglobal/pipeline/context/serializers/base.py
"""
Serializer protocol — estratégia de serialização de NodeContext.

Cada LLM (ou formato de saída) pode ter seu próprio serializer.
O provider não decide formato — o serializer sim.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..protocol import NodeContext


@runtime_checkable
class Serializer(Protocol):
    """Serializa NodeContext para string."""

    def serialize(self, ctx: NodeContext, **kwargs: str) -> str: ...

    def estimate(self, ctx: NodeContext) -> int:
        """Retorna número estimado de tokens."""
        ...
