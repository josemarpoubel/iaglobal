from iaglobal.obsidian.omnimind import omni_mind
from typing import Any, Optional

# Sincronizado com IVMAxiom.IVM_EXCELENTE (0.9) e IVM_CRITICO (0.3)
_THRESHOLD_EXCELENCIA = 0.9
_THRESHOLD_CRITICO = 0.3


class IvmCompliance:
    """Gerencia o feedback entre IVM e OmniMind.

    Thresholds sincronizados com IVMAxiom (0.9 excelente / 0.3 crítico).
    """

    def __init__(self, omni_mind_instance=None):
        self.omni_mind = omni_mind_instance or omni_mind
        self.ivm_threshold_excelencia = _THRESHOLD_EXCELENCIA
        self.ivm_threshold_critico = _THRESHOLD_CRITICO

    async def on_ivm_calculated(
        self,
        agent_id: str,
        ivm: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Reage ao IVM calculado com feedback completo.

        Fluxo (alinhado com IVMAxiom.get_classificacao):
        1. IVM >= 0.9 → Gatilho de Sucesso + Registro Epigenético Positivo
        2. IVM < 0.3 → Gatilho de Vazio + Registro Epigenético para Adaptação
        3. 0.3 ≤ IVM < 0.9 → Monitoramento Contínuo
        """
        result = {
            "agent_id": agent_id,
            "ivm": ivm,
            "trigger": None,
            "epigenetic_updated": False,
        }

        await self.omni_mind.update_ivm_metric(agent_id, ivm, metadata)
        result["epigenetic_updated"] = True

        if ivm >= self.ivm_threshold_excelencia:
            trigger_data = self.omni_mind.emitir_gatilho_sucesso(agent_id, ivm)
            result["trigger"] = "SUCCESS_MANIFEST"
            result["trigger_data"] = trigger_data

        elif ivm < self.ivm_threshold_critico:
            trigger_data = self.omni_mind.emitir_gatilho_vacio(agent_id)
            result["trigger"] = "VACIO_STATE"
            result["trigger_data"] = trigger_data

        else:
            result["trigger"] = "MONITORING"

        return result

    async def atualizar_metrica(
        self, agent_id: str, ivm: float, metadata: Optional[dict[str, Any]] = None
    ):
        """Atualiza os níveis de métrica no OmniMind e EpigeneticRegistry."""
        await self.omni_mind.update_ivm_metric(agent_id, ivm, metadata)


ivm_compliance = IvmCompliance()
