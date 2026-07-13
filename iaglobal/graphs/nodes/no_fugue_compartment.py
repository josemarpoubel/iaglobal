# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_fugue_compartment.py
"""Nó para processamento de tarefas críticas em segundo plano.

Este nó:
- Encaminha tarefas para o FugueCompartment.
- Registra metadados no SubconsciousAPI.
- Garante zero impacto no pipeline consciente.
"""

from iaglobal.obsidian.fugue_compartment import FugueCompartment


class FugueCompartmentNode:
    """Nó para processamento de tarefas em compartimento de fuga."""

    def __init__(self):
        self.fugue = FugueCompartment()

    async def run_fugue_compartment(self, ctx: dict) -> dict:
        """Encaminha tarefas críticas para processamento em segundo plano."""
        task_data = ctx.get("task_data")
        task_type = ctx.get("task_type")
        agent_id = ctx.get("agent_id")

        if task_data and task_type:
            fugue_id = await self.fugue.processar_em_segundo_plano(
                agent_id=agent_id,
                task_data=task_data,
                task_type=task_type,
            )
            ctx["fugue_id"] = fugue_id
            ctx["fugue_status"] = "processing"

        return ctx


# Instância para bind dinâmico
fugue_compartment_node = FugueCompartmentNode()


async def run_fugue_compartment(ctx: dict) -> dict:
    """Entry point para o pipeline."""
    return await fugue_compartment_node.run_fugue_compartment(ctx)
