"""MTAPool — armazenamento temporário de resíduos antes da reciclagem."""

import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal._paths import TEMP_DIR

logger = logging.getLogger(__name__)

from iaglobal._paths import MTA_POOL_FILE

POOL_FILE = MTA_POOL_FILE


class MTAPool:
    """Pool de resíduos (failed prompts, obsolete skills, dead agents) para reciclagem."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or POOL_FILE
        self.items: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                with open(self.path) as f:
                    self.items = json.load(f)
        except Exception:
            self.items = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.items[-200:], f, indent=2)
        except Exception as e:
            logger.debug("[MTA] Erro ao salvar: %s", e)

    def add(self, item_type: str, content: str, metadata: Optional[Dict] = None):
        self.items.append({
            "type": item_type,
            "content": content[:2000],
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        self._save()

    def flush(self, item_type: str = "") -> List[Dict[str, Any]]:
        if item_type:
            batch = [i for i in self.items if i["type"] == item_type]
            self.items = [i for i in self.items if i["type"] != item_type]
        else:
            batch = list(self.items)
            self.items = []
        self._save()
        return batch

    def count(self, item_type: str = "") -> int:
        if item_type:
            return sum(1 for i in self.items if i["type"] == item_type)
        return len(self.items)

    def extract_negative_prompts(self) -> List[str]:
        """Extrai padrões de 'o que NÃO fazer' de prompts que falharam."""
        negatives = []
        for item in self.items:
            if item.get("type") == "failed_prompt":
                content = item.get("content", "")
                if "não" in content.lower() or "evite" in content.lower() or "proibido" in content.lower():
                    negatives.append(f"- {content[:200]}")
        return negatives[:10]

    def generate_negative_instruction(self) -> str:
        """Gera instrução global de 'o que NÃO fazer' baseada em falhas passadas."""
        negatives = self.extract_negative_prompts()
        if not negatives:
            return ""
        return "[NEGATIVE PROMPTS — Padrões a evitar]\n" + "\n".join(negatives)


mta_pool = MTAPool()
