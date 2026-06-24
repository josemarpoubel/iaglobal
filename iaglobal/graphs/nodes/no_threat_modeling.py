# iaglobal/graphs/nodes/no_threat_modeling.py

"""
Threat Modeling Node — Executa a modelagem cognitiva de ameaças e brechas de segurança.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.security_design_agent import SecurityDesignAgent

logger = logging.getLogger(__name__)


async def run_threat_modeling(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a modelagem de ameaças de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso de mitigação para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "threat_modeling_agent_llm"
    
    logger.info("[THREAT_MODELING] Iniciando modelagem proativa de ameaças do sistema...")
    
    # Coleta o contexto de design de forma resiliente
    design_context = ctx.get("design_context") or ctx.get("memory", {}).get("security_design", ctx)

    try:
        # Inicializa o agente modelador de segurança
        agent = SecurityDesignAgent()
        
        # Como modelagens de ameaças realizam análises estáticas pesadas de riscos,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.analyze):
            result = await agent.analyze(design_context=design_context)
        else:
            result = await asyncio.to_thread(agent.analyze, design_context=design_context)
            
        logger.info("[THREAT_MODELING] Modelagem de ameaças finalizada com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se o agente conseguiu emitir um relatório válido
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx)
        return {
            "output": result.get("security_design_report", result),
            "threat_modeling": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.004)  # Custo de inferência estimado para modelagem de ameaças
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[THREAT_MODELING] Falha crítica no pipeline do Threat Modeling Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {},
            "threat_modeling": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

