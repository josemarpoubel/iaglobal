from typing import Any, Dict, List


class ExecutionContext:
    def __init__(self, task_id: str, graph_state: Dict[str, Any]):
        self.task_id = task_id
        self.state = graph_state
        self.data: Dict[str, Any] = {}
        self.logs: List[str] = []

    def log(self, message: str) -> None:
        self.logs.append(message)
