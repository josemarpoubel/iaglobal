# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_clarity_directive.py
"""Nó de clareamento automático para tarefas com IVM abaixo do threshold.

Este nó:
- Avalia tarefas com IVM baixo.
- Marca para clareamento via EpigeneticRegistry.
- Emite gatilho de vácuo para OmniMind.
- Integra com ApoptosisEngine para remoção.
"""

from iaglobal.metabolism.clarity_directive import ClarityDirective


class ClarityDirectiveNode:
    """Nó para clareamento automático de tarefas."""

    def __init__(self):
        self.clarity = ClarityDirective()

    async def run_clarity_directive(self, ctx: dict) -> dict:
        """Avalia e marca tarefas para clareamento."""
        agent_id = ctx.get("agent_id")
        ivm = ctx.get("ivm", 0.0)

        if await self.clarity.avaliar_tarefa(agent_id, ivm):
            await self.clarity.marcar_para_clareamento(agent_id)
            ctx["clareance_status"] = "marked"
        else:
            ctx["clareance_status"] = "active"

        return ctx


# Instância para bind dinâmico
clarity_directive_node = ClarityDirectiveNode()


async def run_clarity_directive(ctx: dict) -> dict:
    """Entry point para o pipeline."""
    return await clarity_directive_node.run_clarity_directive(ctx)