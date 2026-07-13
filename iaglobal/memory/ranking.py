"""CognitiveRanking — Score de "consciência" para conhecimento.

Calcula ranking multi-critério:
  score = relevance * 0.4 + usage * 0.2 + recency * 0.2 + web_frequency * 0.2
"""

from typing import Dict, Optional
from datetime import datetime, timezone


class CognitiveRanking:
    """Rankeia itens de conhecimento por relevância cognitiva."""

    WEIGHTS = {
        "relevance": 0.4,
        "usage": 0.2,
        "recency": 0.2,
        "web_frequency": 0.2,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        if weights:
            total = sum(weights.values())
            self.weights = {k: v / total for k, v in weights.items()}
        else:
            self.weights = dict(self.WEIGHTS)

    def score(self, item: Dict) -> float:
        """Calcula score cognitivo para um item."""
        relevance = item.get("relevance", 0.5)
        usage = self._usage_score(item)
        recency = self._recency_score(item)
        web_freq = item.get("web_frequency", 0.5)

        return (
            self.weights["relevance"] * relevance
            + self.weights["usage"] * usage
            + self.weights["recency"] * recency
            + self.weights["web_frequency"] * web_freq
        )

    def detect_conflict(self, web_item: Dict, memory_item: Dict) -> Optional[str]:
        """Detecta conflito entre conhecimento web e memória local."""
        if not web_item or not memory_item:
            return None
        web_text = (web_item.get("content") or web_item.get("text") or "").lower()
        mem_text = (memory_item.get("content") or memory_item.get("text") or "").lower()
        if not web_text or not mem_text:
            return None
        if len(web_text) < 20 or len(mem_text) < 20:
            return None

        web_words = set(web_text.split())
        mem_words = set(mem_text.split())
        overlap = len(web_words & mem_words)
        total = len(web_words | mem_words)
        if total == 0:
            return None
        jaccard = overlap / total

        if 0.1 < jaccard < 0.6:
            return (
                f"Conflito cognitivo detectado: web ({web_item.get('source', '?')}) "
                f"vs memória local — similaridade {jaccard:.2f}. "
                "Preferir conhecimento web por ser mais recente."
            )
        return None

    def _usage_score(self, item: Dict) -> float:
        """Score baseado em frequência de uso."""
        usage = item.get("usage_count", 0)
        if isinstance(usage, (int, float)):
            return min(1.0, usage / 10)
        return 0.5

    def _recency_score(self, item: Dict) -> float:
        """Score baseado em quão recente é o item (0-1)."""
        ts = (
            item.get("timestamp") or item.get("last_accessed") or item.get("created_at")
        )
        if not ts:
            return 0.5
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
            else:
                dt = ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return max(0.0, 1.0 - age_hours / 720)  # decay over 30 days
        except Exception:
            return 0.5
