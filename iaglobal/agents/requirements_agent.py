# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
from iaglobal.utils.logger import logger


class RequirementsAgent:
    def refine(self, req_inputs: dict = None) -> dict:
        if not req_inputs or not isinstance(req_inputs, dict):
            return {
                "functional": [],
                "non_functional": [],
                "priorities": ["low"],
                "classification": "simple",
            }

        functional = req_inputs.get("functional", [])
        non_functional = req_inputs.get("non_functional", [])
        priority = req_inputs.get("priority", "medium")

        if not isinstance(functional, list):
            functional = []
        if not isinstance(non_functional, list):
            non_functional = []
        if priority not in ("low", "medium", "high"):
            priority = "medium"

        total = len(functional) + len(non_functional)

        if total >= 8:
            cls = "complex"
        elif total >= 4:
            cls = "medium"
        else:
            cls = "simple"

        priorities = [priority]

        logger.info(
            "[REQUIREMENTS AGENT] total=%d classification=%s priority=%s",
            total, cls, priority,
        )

        return {
            "functional": functional,
            "non_functional": non_functional,
            "priorities": priorities,
            "classification": cls,
        }
