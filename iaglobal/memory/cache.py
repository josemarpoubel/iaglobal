"""Cache module for L1 and L2 memory layers."""

import hashlib

from typing import Optional, Dict, Any
from iaglobal.memory.memory_storage import storage, get_success_by_task


_cache = {}

def hash_prompt(prompt: str) -> str:
    """Hash prompt using MD5 for speed in L1 memory."""
    return hashlib.md5(prompt.encode()).hexdigest()

def get(prompt: str) -> Optional[str]:
    """Get cached response for a prompt."""
    # 1. Try L1 cache (RAM)
    res = _cache.get(hash_prompt(prompt))
    if res:
        return res
    
    # 2. Try L2 cache (SQLite Persistent)
    try:
        l2_res = get_success_by_task(prompt)
        if l2_res:
            # Populate L1 for next time
            _cache[hash_prompt(prompt)] = l2_res.get("codigo")
            return l2_res.get("codigo")
    except:
        pass
    
    return None

def set(prompt: str, response: str) -> None:
    """Set cache entry for a prompt (L1 RAM + L2 SQLite)."""
    _cache[hash_prompt(prompt)] = response
    try:
        from iaglobal.memory.memory_storage import store_success
        store_success(prompt, response, metadata={"source": "cache"})
    except Exception:
        pass

class Cache:
    """Cache class for centralized caching operations."""
    
    def __init__(self):
        self.data = {}
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.data:
            self.hits += 1
            return self.data[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        self.data[key] = value
    
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self.data:
            del self.data[key]
    
    def clear(self) -> None:
        """Clear all cache."""
        self.data.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total': total,
            'hit_rate': f"{hit_rate:.2f}%"
        }
