# iaglobal/graphs/nodes/no_risk_analysis.py

"""
Risk Analysis Node — Analisa e mitiga riscos do plano técnico antes da execução.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_risk_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise de riscos de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "risk_analysis_planner_llm"
    
    # Lazy import mantido para preservar o ciclo de inicialização limpa do ecossistema
    from iaglobal.agents.planner_agent import PlannerAgent

    logger.info("[RISK_ANALYSIS] Iniciando ciclo de análise e mitigação de riscos técnicos...")
    
    # Coleta de dados de entrada de forma resiliente do contexto ou memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente especializado em planejamento e riscos
        agent = PlannerAgent()
        
        # Como análises de riscos realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.criar_plano_execucao):
            result = await agent.criar_plano_execucao(task)
        else:
            result = await asyncio.to_thread(agent.criar_plano_execucao, task)
            
        logger.info("[RISK_ANALYSIS] Análise de riscos finalizada com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("output", "Análise de riscos concluída") if isinstance(result, dict) else str(result or ""),
            "risk_analysis": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Processamento analítico consome tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[RISK_ANALYSIS] Falha crítica no pipeline do Risk Analysis Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de análise de riscos",
            "risk_analysis": {"error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

