# 🧠 iaglobal/memory/cognitive_cache.py

import time
import hashlib
import threading
from typing import Any, Optional

from iaglobal.memory.cache import Cache

# =========================================================
# 🧠 GLOBAL L1 MEMORY (RAM)
# =========================================================
_L1_CACHE: dict[str, Any] = {}

def l1_get(key: str) -> Optional[Any]:
    return _L1_CACHE.get(key)

def l1_set(key: str, value: Any):
    _L1_CACHE[key] = value


# =========================================================
# 💾 ASYNC L2 WRITER
# =========================================================
def async_l2_write(cache_layer: Cache, key: str, value: Any):
    def _write():
        try:
            cache_layer.set(key, value)
        except Exception:
            pass

    threading.Thread(target=_write, daemon=True).start()


# =========================================================
# 🧠 COGNITIVE CACHE CORE
# =========================================================
class CognitiveCache:

    def __init__(self, cache_layer: Cache, critic_fn=None):
        self.cache_layer = cache_layer
        self.critic_fn = critic_fn  # NeuroOrchestrator / DecisionEngine hook

    def get(self, node, task: str):
        key = self._make_key(node, task)

        # ---------------- L1 ----------------
        cached = l1_get(key)
        if cached is not None:
            return {
                "output": cached,
                "cached": True,
                "level": "L1",
                "latency": 0.0
            }

        # ---------------- L2 ----------------
        cached = self.cache_layer.get(key)
        if cached is not None:
            l1_set(key, cached)
            return {
                "output": cached,
                "cached": True,
                "level": "L2",
                "latency": 0.0
            }

        return None

    def set(self, node, task: str, output: Any, meta: dict = None):
        key = self._make_key(node, task)

        # sempre grava L1 (memória imediata)
        l1_set(key, output)

        # ---------------- CRITIC GATE ----------------
        score = 1.0

        if self.critic_fn:
            try:
                score = self.critic_fn(output, meta or {})
            except Exception:
                score = 0.0

        # só grava L2 se aprovado
        if score >= 0.6:
            async_l2_write(self.cache_layer, key, output)

        return score

    def _make_key(self, node, task: str) -> str:
        # Use SHA-256 instead of MD5 for security
        return hashlib.sha256(
            f"{node.name}:{node.strategy}:{task}".encode()
        ).hexdigest()
