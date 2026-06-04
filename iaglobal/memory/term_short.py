"""Short-term memory for immediate context and conversation history."""

from typing import List, Dict, Any, Optional
from collections import deque
from datetime import datetime, timezone

class ShortTermMemory:
    """Manages short-term memory with limited capacity and auto-expire."""

    def __init__(self, max_size: int = 100, ttl_seconds: Optional[int] = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.buffer = deque(maxlen=max_size)
        self.timestamps = deque(maxlen=max_size)

    def add(self, item: Any, metadata: Optional[Dict] = None) -> None:
        """Add item to short-term memory with optional metadata."""
        entry = {
            "content": item,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.buffer.append(entry)
        self.timestamps.append(datetime.now(timezone.utc))

    def get_recent(self, n: int = 10) -> List[Any]:
        """Get n most recent items, auto-expiring stale ones."""
        self._expire()
        return [entry["content"] for entry in list(self.buffer)[-n:]]

    def get_recent_with_metadata(self, n: int = 10) -> List[Dict]:
        """Get recent items with full metadata."""
        self._expire()
        return list(self.buffer)[-n:]

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Simple keyword search within short-term memory."""
        self._expire()
        query_lower = query.lower()
        results = []
        for entry in self.buffer:
            if query_lower in entry["content"].lower():
                results.append(entry)
        return results[:top_k]

    def clear(self) -> None:
        """Clear short-term memory."""
        self.buffer.clear()
        self.timestamps.clear()

    def is_full(self) -> bool:
        """Check if memory buffer is full."""
        return len(self.buffer) == self.max_size

    def count(self) -> int:
        """Return current number of items."""
        return len(self.buffer)

    def _expire(self) -> None:
        """Remove items older than TTL."""
        if self.ttl_seconds is None:
            return
        now = datetime.now(timezone.utc)
        while self.timestamps and (now - self.timestamps[0]).total_seconds() > self.ttl_seconds:
            self.timestamps.popleft()
            self.buffer.popleft()
