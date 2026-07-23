# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
TaskRouter — Sistema nervoso central para mapeamento node_id → nível cognitivo.

Integração com Tribunal Cognitivo:
- Layer 1 (JUIZ): crítico → raciocínio profundo
- Layer 2 (OPERARIO): geração e escrita
- Layer 3 (SENTINELA): validação rápida
"""

import re
from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.providers.task_router")


class TaskRouter:
    """
    Router de tarefas que mapeia node_id para o tier cognitivo apropriado.

    Usa padrões de regex para classificar automaticamente os 121+ nós
    existentes sem manutenção manual de dicionário.
    """

    TIER_JUIZ = "critic"
    TIER_OPERARIO = "worker"
    TIER_SENTINELA = "sentinel"

    def __init__(self) -> None:
        self._rules = self._build_rules()

    def _build_rules(self) -> list[tuple[re.Pattern, str]]:
        return [
            (re.compile(r"^no_critic"), self.TIER_JUIZ),
            (re.compile(r"^critic"), self.TIER_JUIZ),
            (
                re.compile(
                    r"^no_.*(requirements|technology_selection|architecture_design|system_design)$"
                ),
                self.TIER_JUIZ,
            ),
            (
                re.compile(r"^no_.*(critic|arbitrar|correction|validation|judge)$"),
                self.TIER_JUIZ,
            ),
            (re.compile(r"^no_coder"), self.TIER_OPERARIO),
            (
                re.compile(
                    r"^no_.*(code|generate|execute|compile|write|artifact|api|backend|frontend|database|deploy|build|run|create|develop|implement|construct|design|architect|planner|task|breakdown)$"
                ),
                self.TIER_OPERARIO,
            ),
            (
                re.compile(
                    r"^no_.*(sentinel|entropy|syntax|auditor|validator|defender|guardian)$"
                ),
                self.TIER_SENTINELA,
            ),
            (
                re.compile(
                    r"^no_.*(audit|monitor|security|constraint|requirement|check|verify|test|debug|analyst|review|inspect|detect|analyze|detect|identify|assess|evaluate|profile|scan|guard|shield|watch|probe)$"
                ),
                self.TIER_SENTINELA,
            ),
            (re.compile(r"^no_dependency"), self.TIER_SENTINELA),
            (re.compile(r"^no_test"), self.TIER_SENTINELA),
            (re.compile(r"^tester"), self.TIER_SENTINELA),
            (re.compile(r"^no_"), self.TIER_OPERARIO),
        ]

    def get_role_for_node(self, node_id: str) -> str:
        if not node_id:
            return self.TIER_OPERARIO
        for pattern, tier in self._rules:
            if pattern.match(node_id):
                return tier
        return self.TIER_OPERARIO

    def get_tier_display(self, tier: str) -> str:
        return {
            self.TIER_JUIZ: "JUIZ (Qwen2.5-0.5B)",
            self.TIER_OPERARIO: "OPERARIO (Qwen2.5-0.5B)",
            self.TIER_SENTINELA: "SENTINELA (Qwen2.5-0.5B)",
        }.get(tier, "OPERARIO")

    def route_for_tier(self, tier: str) -> str:
        return {
            self.TIER_JUIZ: "ollama",
            self.TIER_OPERARIO: "ollama",
            self.TIER_SENTINELA: "ollama",
        }.get(tier, "ollama")

    def resolve_model(self, node_id: str, candidates: list[str]) -> list[str]:
        tier = self.get_role_for_node(node_id)
        route = self.route_for_tier(tier)
        prioritized = [route] + [c for c in candidates if c != route]
        return prioritized

    def get_timeout_for_tier(self, tier: str) -> float:
        return {
            self.TIER_JUIZ: 180.0,
            self.TIER_OPERARIO: 180.0,
            self.TIER_SENTINELA: 180.0,
        }.get(tier, 180.0)

    def is_critical_node(self, node_id: str) -> bool:
        return self.get_role_for_node(node_id) == self.TIER_JUIZ

    def get_all_nodes_for_role(self, role: str) -> list[str]:
        return [n for n in self._rules if n[1] == role]


_task_router: Optional[TaskRouter] = None


def get_task_router() -> TaskRouter:
    global _task_router
    if _task_router is None:
        _task_router = TaskRouter()
    return _task_router
