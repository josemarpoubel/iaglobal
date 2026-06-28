from iaglobal.obsidian.omnimind import omni_mind

class IvmCompliance:
    """Gerencia o feedback entre IVM e OmniMind"""
    def __init__(self, omni_mind_instance=None):
        self.omni_mind = omni_mind_instance or omni_mind
        self.ivm_threshold_excelencia = 0.85
        self.ivm_threshold_critico = 0.60

    async def on_ivm_calculated(self, agent_id: str, ivm: float) -> None:
        """Reage ao IVM calculado"""
        if ivm > self.ivm_threshold_excelencia:
            self.omni_mind.emitir_gatilho_sucesso(agent_id, ivm)
        elif ivm < self.ivm_threshold_critico:
            self.omni_mind.emitir_gatilho_vacio(agent_id)

    async def atualizar_metrica(self, agent_id: str, ivm: float):
        """Atualiza os níveis de métrica no OmniMind"""
        await self.omni_mind.update_ivm_metric(agent_id, ivm)

ivm_compliance = IvmCompliance()