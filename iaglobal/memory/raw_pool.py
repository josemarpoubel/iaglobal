"""Raw Choline Pool — armazenamento temporário de informação bruta antes da metabolização."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from threading import Lock

from iaglobal._paths import TEMP_DIR

from iaglobal._paths import CHOLINE_POOL_FILE

POOL_FILE = CHOLINE_POOL_FILE


class RawCholinePool:
    """Pool volátil de informação bruta (arquivos, APIs, logs) antes do processamento."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or POOL_FILE
        self._lock = Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                with open(self.path) as f:
                    self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._entries[-100:], f, indent=2)
        except Exception:
            pass

    def add(self, source: str, content: str, metadata: Optional[Dict] = None):
        with self._lock:
            self._entries.append({
                "source": source,
                "content": content[:5000],
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            self._save()

    def flush(self, keep_last: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            entries = list(self._entries)
            self._entries = self._entries[-keep_last:]
            self._save()
        return entries

    def count(self) -> int:
        return len(self._entries)

    def clear(self):
        with self._lock:
            self._entries = []
            self._save()


raw_choline_pool = RawCholinePool()
