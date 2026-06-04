from typing import Any, Dict, Optional


PENDING = "PENDING"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"


class StateStore:
    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}

    def set(self, node: str, status: str, output: Optional[Any] = None,
            error: Optional[str] = None, attempt: int = 0) -> None:
        self.state[node] = {
            "status": status,
            "output": output,
            "error": error,
            "attempt": attempt,
        }

    def get(self, node: str) -> Dict[str, Any]:
        return self.state.get(node, {"status": PENDING, "output": None, "error": None, "attempt": 0})

    def is_ready(self, node: str, depends_on: list) -> bool:
        entry = self.get(node)
        if entry["status"] in (SUCCESS, FAILED):
            return False

        for dep in depends_on:
            dep_status = self.get(dep)["status"]
            if dep_status != SUCCESS:
                return False

        return True
