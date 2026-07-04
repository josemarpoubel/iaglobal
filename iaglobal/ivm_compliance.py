from iaglobal.obsidian.omnimind import omni_mind
from typing import Any, Optional

class IvmCompliance:
    """Gerencia o feedback entre IVM e OmniMind.
    
    Implementa o ciclo completo:
    1. Calcula IVM (Índice de Viabilidade Metabólica)
    2. Emite gatilhos para OmniMind (sucesso/vazio/perdão)
    3. Atualiza EpigeneticRegistry com métricas
    4. Gera aprendizado contínuo baseado em leis universais
    """
    
    def __init__(self, omni_mind_instance=None):
        self.omni_mind = omni_mind_instance or omni_mind
        self.ivm_threshold_excelencia = 0.85
        self.ivm_threshold_critico = 0.60
    
    async def on_ivm_calculated(
        self,
        agent_id: str,
        ivm: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Reage ao IVM calculado com feedback completo.
        
        Fluxo:
        1. IVM > 0.85 → Gatilho de Sucesso + Registro Epigenético Positivo
        2. IVM < 0.60 → Gatilho de Vazio + Registro Epigenético para Adaptação
        3. 0.60 ≤ IVM ≤ 0.85 → Monitoramento Contínuo
        
        Args:
            agent_id: ID do agente
            ivm: Índice de Viabilidade Metabólica (0.0-1.0)
            metadata: Contexto adicional (task_hash, error_type, etc.)
            
        Returns:
            Dict com trigger emitido e status do processamento
        """
        result = {
            "agent_id": agent_id,
            "ivm": ivm,
            "trigger": None,
            "epigenetic_updated": False,
        }
        
        # Atualiza métrica no EpigeneticRegistry (sempre executa)
        await self.omni_mind.update_ivm_metric(agent_id, ivm, metadata)
        result["epigenetic_updated"] = True
        
        # Emite gatilho apropriado
        if ivm > self.ivm_threshold_excelencia:
            trigger_data = self.omni_mind.emitir_gatilho_sucesso(agent_id, ivm)
            result["trigger"] = "SUCCESS_MANIFEST"
            result["trigger_data"] = trigger_data
            
        elif ivm < self.ivm_threshold_critico:
            trigger_data = self.omni_mind.emitir_gatilho_vacio(agent_id)
            result["trigger"] = "VACIO_STATE"
            result["trigger_data"] = trigger_data
            
        else:
            # IVM intermediário: apenas monitoramento
            result["trigger"] = "MONITORING"
            
        return result
    
    async def atualizar_metrica(self, agent_id: str, ivm: float, metadata: Optional[dict[str, Any]] = None):
        """Atualiza os níveis de métrica no OmniMind e EpigeneticRegistry."""
        await self.omni_mind.update_ivm_metric(agent_id, ivm, metadata)

ivm_compliance = IvmCompliance()