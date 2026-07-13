# iaglobal/graphs/skill_node.py

import hashlib
from typing import Any, Dict

from iaglobal.evolution.skills.utils.dynamic_registry import dynamic_registry
from iaglobal.utils.logger import logger


def _compute_node_id(
    node_type: str,
    seed_id: str = "",
    mutation_id: str = "",
    version: str = "v1",
    name: str = "",
) -> str:
    raw = f"{node_type}::{seed_id}::{mutation_id}::{version}::{name}"
    return hashlib.sha3_256(raw.encode()).hexdigest()[:16]


class SkillNode:
    def __init__(self, name: str, skill_name: str = None, depends_on: list = None):
        self.name = name
        self.depends_on = depends_on or []
        self._skill_name = skill_name or name
        self.node_type = "general"
        self.seed_id = ""
        self.mutation_id = ""
        self.version = "v1"

    @property
    def node_id(self) -> str:
        effective_type = self.node_type if self.node_type != "general" else self.name
        effective_seed = self.seed_id if self.seed_id else self.name
        return _compute_node_id(
            node_type=effective_type,
            seed_id=effective_seed,
            mutation_id=self.mutation_id,
            version=self.version,
            name=self.name,
        )

    async def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await dynamic_registry.execute(self._skill_name, ctx)
            if result:
                return result
            return {"output": None, "success": True}
        except Exception as e:
            logger.warning(f"[SKILL-NODE] {self._skill_name} execute failed: {e}")
            return {"output": None, "success": False, "error": str(e)}
