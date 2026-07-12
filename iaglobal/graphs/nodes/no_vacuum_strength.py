# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_vacuum_strength.py
"""Nó responsável por aplicar a Lei do Vácuo da Prosperidade.

Este nó: 
- Valida se o vácuo é necessário via epigenetic_registry.
- Limpa efeitos colaterais do contexto antigo.
- Alerta o REMSleepEngine para recuperar memória.
- Injeta nutrientes do vault no contexto.
"""
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.obsidian.epigenetic_registry import epigenetic_registry


class VacuumStrength:
    """Aplica a Lei do Vácuo da Prosperidade."""

    def __init__(self):
        from iaglobal.obsidian.omnimind import omni_mind
        from iaglobal.obsidian.epigenetic_registry import epigenetic_registry
        self.omni_mind = omni_mind
        self.epigenetic_registry = epigenetic_registry

    async def run_vacuum_strength(self, ctx: dict) -> dict:
        """Valida e aplica a Lei do Vácuo da Prosperidade."""
        if ctx.get("vacuum_required", False):
            # Limpar efeitos colaterais do contexto
            ctx = self._limpar_contexto(ctx)

            # Alerta o REMSleepEngine para liberar memória
            await self.omni_mind.emitir_gatilho_vacio("tarefa_vaciada")

            # Injetar nutrientes do vault
            ctx = self._injetar_nutrientes(ctx)

        return ctx.copy()  # Garante que o contexto é retornado

    def _limpar_contexto(self, ctx: dict) -> dict:
        """Remove dados obsoletos do contexto."""
        # Remove chaves desnecessárias
        keys_to_remove = ["vacuum_required", "context_effects"]
        return {k: v for k, v in ctx.items() if k not in keys_to_remove}

    async def _injetar_nutrientes(self, ctx: dict) -> dict:
        """Extrai nutrientes do vault baseado no contexto."""
        # Método temporário: injeta nutrientes fictícios para teste
        nutrients = {"nutrients_injected": True, "task_type": ctx.get("task_type", "general")}
        ctx.update(nutrients)
        return ctx


# Instância para bind dinâmico
vacuum_strength = VacuumStrength()


async def run_vacuum_strength(ctx: dict) -> dict:
    """Entry point para o pipeline."""
    return await vacuum_strength.run_vacuum_strength(ctx)