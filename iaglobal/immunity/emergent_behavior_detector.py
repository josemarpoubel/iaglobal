"""EmergentBehaviorDetector — monitora comportamento inesperado de agentes."""

import logging
from typing import Any, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class EmergentBehaviorDetector:
    """Detecta comportamentos emergentes: dependências circulares, skills maliciosas, loops evolutivos."""

    def __init__(self):
        self._dependency_history: Dict[str, List[str]] = defaultdict(list)
        self._circular_count = 0

    def check_dependencies(
        self, node_name: str, depends_on: List[str]
    ) -> Dict[str, Any]:
        issues = []

        if node_name in depends_on:
            issues.append({"type": "self_dependency", "node": node_name})
            self._circular_count += 1

        self._dependency_history[node_name].extend(depends_on)

        for dep in depends_on:
            chain = self._dependency_history.get(dep, [])
            if node_name in chain:
                issues.append(
                    {
                        "type": "circular_dependency",
                        "chain": f"{node_name} → {dep} → ... → {node_name}",
                    }
                )
                self._circular_count += 1

        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "issue_count": len(issues),
            "total_circular": self._circular_count,
        }

    def check_skill_name(self, skill_name: str) -> Dict[str, Any]:
        suspicious = [
            "malware",
            "trojan",
            "backdoor",
            "hack",
            "exploit",
            "ransomware",
            "keylogger",
        ]
        found = [s for s in suspicious if s in skill_name.lower()]
        return {"suspicious": len(found) > 0, "matches": found}

    def summary(self) -> Dict[str, Any]:
        return {
            "circular_dependencies_detected": self._circular_count,
            "tracked_nodes": len(self._dependency_history),
        }
