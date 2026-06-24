"""Evolution Backlog — prioriza gaps por frequência, impacto e reuso antes de gerar skills."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from iaglobal._paths import EVOLUTION_BACKLOG_FILE
from iaglobal.utils.logger import logger

BACKLOG_FILE = EVOLUTION_BACKLOG_FILE


class EvolutionBacklog:
    """Mantém backlog priorizado de evoluções.
    Thresholds configuráveis via environment:
    - EVO_FREQ_THRESHOLD (default: 2)
    - EVO_IMPACT_THRESHOLD (default: 3)
    - EVO_REUSE_THRESHOLD (default: 1)
    """

    FREQUENCY_THRESHOLD = int(os.getenv("EVO_FREQ_THRESHOLD", "2"))
    IMPACT_THRESHOLD = int(os.getenv("EVO_IMPACT_THRESHOLD", "3"))
    REUSE_THRESHOLD = int(os.getenv("EVO_REUSE_THRESHOLD", "1"))

    def __init__(self, path: Optional[Path] = None):
        self.path = path or BACKLOG_FILE
        self.items = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        try:
            if self.path.exists():
                with open(self.path) as f:
                    return json.load(f)
        except Exception as e:
            logger.debug("[BACKLOG] Erro ao carregar: %s", e)
        return []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.items, f, indent=2)
        except Exception as e:
            logger.debug("[BACKLOG] Erro ao salvar: %s", e)

    def add_or_update(self, gap: Dict[str, Any]) -> Dict[str, Any]:
        desc = gap.get("description", gap.get("error", ""))
        existing = next((i for i in self.items if i.get("description") == desc), None)

        if existing:
            existing["frequency"] = existing.get("frequency", 1) + 1
            existing["last_seen"] = datetime.now(timezone.utc).isoformat()
            existing["impact"] = max(existing.get("impact", 1), _parse_impact(gap))
            item = existing
        else:
            item = {
                "description": desc,
                "type": gap.get("type", "unknown"),
                "severity": gap.get("severity", "low"),
                "frequency": 1,
                "impact": _parse_impact(gap),
                "reuse": _estimate_reuse(desc),
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "resolved": False,
            }
            self.items.append(item)

        self._update_priority(item)
        self._save()
        return item

    def _update_priority(self, item: Dict[str, Any]):
        freq = item.get("frequency", 1)
        impact = item.get("impact", 1)
        reuse = item.get("reuse", 1)
        item["priority"] = round(freq * impact * reuse, 1)

    def should_generate_skill(self, item: Dict[str, Any]) -> bool:
        # 1ª execução: backlog vazio → aprova sem gates
        if not self.items or all(i.get("resolved", False) for i in self.items):
            return True
        return (
            item.get("frequency", 0) >= self.FREQUENCY_THRESHOLD
            and item.get("impact", 0) >= self.IMPACT_THRESHOLD
            and item.get("reuse", 0) >= self.REUSE_THRESHOLD
            and not item.get("resolved", False)
        )

    def get_pending(self) -> List[Dict[str, Any]]:
        return sorted(
            [i for i in self.items if not i.get("resolved", False)],
            key=lambda i: i.get("priority", 0),
            reverse=True,
        )

    def mark_resolved(self, description: str):
        for item in self.items:
            if item.get("description") == description:
                item["resolved"] = True
                item["resolved_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                return


def _parse_impact(gap: Dict[str, Any]) -> int:
    sev = gap.get("severity", "low")
    return {"critical": 10, "high": 7, "medium": 4, "low": 1}.get(sev, 1)


def _estimate_reuse(desc: str) -> int:
    keywords = ["import", "class", "def ", "function", "api", "database",
                "security", "login", "form", "validation"]
    return sum(1 for kw in keywords if kw in desc.lower()) or 1
