# iaglobal/evolution/metabolic_lifecycle.py

import asyncio
import logging
from typing import Any, Dict
from iaglobal.execution.cpu_affinity import cpu_affinity
from iaglobal.immunity.apoptosis_engine import apoptosis_engine
from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolic_lifecycle")

class MetabolicLifecycleManager:
    """
    Orquestrador do Ciclo de Vida Metabólico.
    
    Fecha o loop: IVM -> Ação Evolutiva (Apoptose ou Mitose).
    """
    
    async def process_agent_viability(self, agent: EvoAgent):
        """
        Analisa a viabilidade de um agente e executa a ação correspondente.
        """
        # 1. Consulta o metabolismo (CPU Affinity)
        # Nota: EvoAgent usa lineage_id como ID único
        report = cpu_affinity.monitorar_metabolismo(agent.lineage_id)
        
        acao = report["acao"]
        motivo = report["motivo"]
        ivm = report["ivm"]
        
        logger.info(
            "[%s] Viabilidade Metabólica | IVM=%.3f | Ação=%s | Motivo=%s", 
            agent.name, ivm, acao, motivo
        )
        
        if acao == "apoptose":
            logger.warning("[%s] 💀 Gatilho de Apoptose ativado por IVM crítico.", agent.name)
            await agent.apoptose(reason=f"metabolic_collapse_{motivo}")
            
        elif acao == "mitose":
            logger.info("[%s] ✨ Gatilho de Mitose ativado por IVM de excelência.", agent.name)
            try:
                # Replicação baseada em sucesso
                child = await agent.replicate(mutation_hint="metabolic_excellence_clone")
                logger.info("[%s] Mitose concluída: Filho [%s] gerado.", agent.name, child.name)
            except Exception as e:
                logger.error("[%s] Falha na mitose: %s", agent.name, e)
                
        else:
            # Apenas monitorar
            pass

lifecycle_manager = MetabolicLifecycleManager()
