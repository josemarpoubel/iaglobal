# iaglobal/pipeline/context/serializers/json_serializer.py
"""
JSONSerializer — formato JSON estruturado para APIs de LLM.

Cada seção vira uma chave no JSON de saída.
"""

from __future__ import annotations

import json
from typing import Dict

from ..protocol import NodeContext, CharTokenEstimator


class JSONSerializer:
    """Serializa NodeContext em JSON."""

    def __init__(self, estimator=None):
        self._estimator = estimator or CharTokenEstimator()
        self._indent = 2

    def serialize(self, ctx: NodeContext, **kwargs: str) -> str:
        ordered = sorted(ctx.sections, key=lambda s: -s.priority)
        data: Dict[str, object] = {}

        for section in ordered:
            if section.is_empty:
                continue
            if len(section.content) == 1:
                data[section.id] = section.content[0]
            else:
                data[section.id] = [str(c) for c in section.content if c is not None]

        return json.dumps(data, ensure_ascii=False, indent=self._indent)

    def estimate(self, ctx: NodeContext) -> int:
        return self._estimator.estimate(self.serialize(ctx))
