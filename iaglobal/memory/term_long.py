"""Long-term memory storage with semantic search, importance ranking, and consolidation."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from collections import Counter

class LongTermMemory:
    """Stores important information for long-term retrieval with scoring."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.memories: List[Dict] = []

    def store(self, content: str, metadata: Optional[Dict] = None, source: str = "internal") -> None:
        """Store a long-term memory with importance and source tracking."""
        memory = {
            "id": len(self.memories),
            "content": content,
            "metadata": metadata or {},
            "source": source,
            "importance": 0.5,
            "usage_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat()
        }
        self.memories.append(memory)
        if len(self.memories) > self.max_size:
            self._prune()

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Retrieve memories matching a query, updating usage stats."""
        query_lower = query.lower()
        results = []
        for m in self.memories:
            score = self._match_score(m["content"], query_lower)
            adjusted = score * (0.5 + 0.5 * m["importance"])
            if adjusted > 0:
                results.append((adjusted, m))

        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:top_k]

        for _, m in top:
            m["usage_count"] += 1
            m["last_accessed"] = datetime.now(timezone.utc).isoformat()

        return [m for _, m in top]

    def consolidate(self, new_content: str, metadata: Optional[Dict] = None) -> bool:
        """Consolidate by merging if similar content exists, else store new."""
        for m in self.memories:
            sim = self._match_score(m["content"], new_content.lower())
            if sim > 0.7:
                m["content"] = f"{m['content']}\n---\n{new_content}"
                m["importance"] = min(1.0, m["importance"] + 0.1)
                m["last_accessed"] = datetime.now(timezone.utc).isoformat()
                if metadata:
                    m["metadata"].update(metadata)
                return True
        self.store(new_content, metadata)
        return False

    def update_importance(self, index: int, importance: float) -> None:
        """Update importance score of a memory."""
        if 0 <= index < len(self.memories):
            self.memories[index]["importance"] = max(0.0, min(1.0, importance))

    def get_stats(self) -> Dict:
        """Return memory statistics."""
        if not self.memories:
            return {"count": 0, "avg_importance": 0, "top_sources": []}
        avg_imp = sum(m["importance"] for m in self.memories) / len(self.memories)
        sources = Counter(m["source"] for m in self.memories)
        return {
            "count": len(self.memories),
            "avg_importance": round(avg_imp, 3),
            "top_sources": sources.most_common(5),
            "total_usage": sum(m["usage_count"] for m in self.memories)
        }

    def get_all(self) -> List[Dict]:
        """Return all memories."""
        return list(self.memories)

    def clear(self) -> None:
        """Clear all memories."""
        self.memories.clear()

    def _match_score(self, content: str, query: str) -> float:
        """Simple keyword match score between 0 and 1."""
        if not query or not content:
            return 0.0
        content_lower = content.lower()
        words = query.split()
        if not words:
            return 0.0
        matches = sum(1 for w in words if w in content_lower)
        return matches / len(words) if words else 0.0

    def _prune(self) -> None:
        """Remove least important memories when over capacity."""
        self.memories.sort(key=lambda m: (m["importance"], m["usage_count"]))
        self.memories = self.memories[-(self.max_size // 2):]
