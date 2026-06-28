class ClarityDirective:
    """Gerencia o clareamento automático de tarefas com base em IVM."""

    THRESHOLD_VAZIO = 0.1  # IVM mínimo para evitar apoptose

    def __init__(self):
        from iaglobal.obsidian.epigenetic_registry import epigenetic_registry
        from iaglobal.obsidian.omnimind import omni_mind
        self.epigenetic_registry = epigenetic_registry
        self.omni_mind = omni_mind

    async def avaliar_tarefa(self, agent_id: str, ivm: float) -> bool:
        """Avalia se a tarefa deve ser clareada.

        Args:
            agent_id: Identificador do agente/tarefa.
            ivm: Índice de Viabilidade Metabólica.

        Returns:
            bool: True se a tarefa deve ser clareada.
        """
        if ivm < self.THRESHOLD_VAZIO:
            await self.epigenetic_registry.registrar_violação_lei(
                agent_id,
                "Lei do Vácuo",
                {"ivm": ivm, "motivo": "IVM abaixo do threshold_vazio"},
            )
            return True
        return False

    async def marcar_para_clareamento(self, agent_id: str) -> None:
        """Marca um agente/tarefa para clareamento."""
        await self.epigenetic_registry.salvar_marca_epigenetica(
            chave=f"{agent_id}_clareance_pending",
            valor=True,
            metadata={"motivo": "IVM baixo", "acao": "apoptose"},
        )
        await self.omni_mind.emitir_gatilho_vacio(agent_id)

    async def executar_clareamento(self, agent_id: str) -> None:
        """Executa a apoptose da tarefa."""
        await self.epigenetic_registry.salvar_marca_epigenetica(
            chave=f"{agent_id}_clareance_executed",
            valor=True,
            metadata={"acao": "apoptose", "status": "concluido"},
        )