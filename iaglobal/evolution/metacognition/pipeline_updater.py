import logging
from typing import Any, Dict

from iaglobal.graphs.node import Node
from iaglobal.evolution.skills.native.skill_registry import skill_registry

logger = logging.getLogger(__name__)


class PipelineUpdater:
    """Atualiza o pipeline dinamicamente com novas skills geradas."""

    @classmethod
    async def update(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        committee_result = memory.get("evolution_committee", {}).get("output", {})
        evaluations = (
            committee_result.get("evaluations", [])
            if isinstance(committee_result, dict)
            else []
        )
        graph = ctx.get("graph")

        updates = []
        for e in evaluations:
            if e.get("approved"):
                skill_name = e.get("skill_name", "")
                if skill_name:
                    updates.append(
                        {
                            "skill_name": skill_name,
                            "action": "registered",
                            "status": "ready",
                        }
                    )

        if graph and updates:
            cls._add_to_graph(graph, updates)

        return {
            "updates": updates,
            "update_count": len(updates),
            "rejected": sum(1 for e in evaluations if not e.get("approved")),
            "status": "updated",
        }

    @classmethod
    def _add_to_graph(cls, graph, updates: list) -> int:
        added = 0
        for upd in updates:
            skill_name = upd["skill_name"]
            if skill_name in graph.nodes:
                continue
            skill = skill_registry.get(skill_name)
            if skill is None:
                logger.warning(
                    "[PIPELINE] Skill '%s' não encontrada no registry", skill_name
                )
                continue
            run_fn = (
                skill.run_fn
                if skill.run_fn and callable(skill.run_fn)
                else (
                    lambda ctx, n=skill_name: {"output": f"skill:{n}", "success": True}
                )
            )
            try:
                node = Node(
                    name=skill_name,
                    run=run_fn,
                    depends_on=["evolution_trigger"],
                    strategy="general",
                    node_type="dynamic_skill",
                )
                graph.add_node(node)
                added += 1
                logger.info("[PIPELINE] Nó dinâmico adicionado: %s", skill_name)
            except ValueError:
                logger.warning("[PIPELINE] Nó '%s' já existe no grafo", skill_name)
        return added


async def _run_pipeline_updater(ctx: dict) -> dict:
    logger.info(
        "[LIFE-SIGNAL] _run_pipeline_updater invoked | ctx_keys=%s", sorted(ctx.keys())
    )
    return await PipelineUpdater.update(ctx)
