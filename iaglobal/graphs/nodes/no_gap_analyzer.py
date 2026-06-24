# iaglobal/graphs/nodes/no_gap_analyzer.py

"""
Gap Analyzer Node — Executa a análise cognitiva de lacunas e reflexão sobre o código gerado.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)


async def run_gap_analyzer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise de lacunas estruturais de forma assíncrona e não-bloqueante.
    Mapeia latência, custo e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "gap_analyzer_reflexion_llm"
    
    logger.info("[GAP_ANALYZER] Iniciando ciclo de reflexão e análise de lacunas no código...")
    
    # Coleta de dados de entrada de forma resiliente do contexto ou memórias estruturadas
    memory = ctx.get("memory", {})
    coder_data = ctx.get("coder", {}) or memory.get("coder", {}) or memory.get("multi_coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else str(coder_data or "")
    
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    requirements_data = ctx.get("requirements", {}) or memory.get("requirements", {})

    try:
        # Inicializa o agente especializado em reflexão
        agent = ReflexionAgent()
        
        # Como análises reflexivas realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.analisar_resultado):
            result = await agent.analisar_resultado(code, requirements_data, task)
        else:
            result = await asyncio.to_thread(agent.analisar_resultado, code, requirements_data, task)
            
        logger.info("[GAP_ANALYZER] Ciclo analítico de reflexão finalizado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = result is not None and len(str(result)) > 5

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "gap_analyzer": {
                "analysis": result
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.006)  # Processamento reflexivo consome mais tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[GAP_ANALYZER] Falha crítica no pipeline do Gap Analyzer Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de reflexão técnica",
            "gap_analyzer": {"analysis": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

