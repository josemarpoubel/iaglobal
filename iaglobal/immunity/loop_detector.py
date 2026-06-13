"""LoopDetector — detecta ciclos infinitos no DAG (mesmo nó executado N vezes sem progresso)."""

import logging
from typing import Any, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_EXECUTIONS_PER_NODE = 5


class LoopDetector:
    """Monitora execuções de nós e detecta loops."""

    def __init__(self, max_executions: int = MAX_EXECUTIONS_PER_NODE):
        self.max_executions = max_executions
        self._execution_count: Dict[str, int] = defaultdict(int)

    def record_execution(self, node_name: str, success: bool):
        if not success:
            self._execution_count[node_name] += 1
        else:
            self._execution_count[node_name] = 0

    def detect(self) -> List[Dict[str, Any]]:
        loops = []
        for node, count in self._execution_count.items():
            if count >= self.max_executions:
                loops.append({
                    "node": node,
                    "executions": count,
                    "threshold": self.max_executions,
                    "type": "loop",
                })
        return loops

    def check(self, node_name: str, success: bool) -> Dict[str, Any]:
        self.record_execution(node_name, success)
        count = self._execution_count.get(node_name, 0)
        in_loop = count >= self.max_executions
        return {
            "in_loop": in_loop,
            "node": node_name,
            "executions": count,
        }

    def reset(self, node_name: str = ""):
        if node_name:
            self._execution_count[node_name] = 0
        else:
            self._execution_count.clear()
