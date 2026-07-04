# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_retrospective.py

"""
Retrospective Node — Executa a análise retrospectiva e consolidação de aprendizado do ciclo.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)


async def run_retrospective(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a retrospectiva técnica de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "retrospective_reflexion_llm_core"
    
    logger.info("[RETROSPECTIVE] Iniciando ciclo de análise retrospectiva e consolidação de aprendizado...")
    
    # Coleta de dados de entrada de forma resiliente do contexto ou memórias estruturadas
    memory = ctx.get("memory", {}) or {}
    coder_data = ctx.get("coder", {}) or memory.get("coder", {}) or memory.get("multi_coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else str(coder_data or "")
    
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente especializado em reflexão e retrospectiva
        agent = ReflexionAgent()
        
        # Como análises retrospectivas realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.analisar_resultado):
            result = await agent.analisar_resultado(code, {}, task)
        else:
            result = await asyncio.to_thread(agent.analisar_resultado, code, {}, task)
            
        analysis_str = str(result or "")
        logger.info("[RETROSPECTIVE] Ciclo finalizado com sucesso: %d caracteres de aprendizado gerados.", len(analysis_str))
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = bool(analysis_str and len(analysis_str.strip()) > 5)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": analysis_str,
            "retrospective": {
                "analysis": result
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Processamento reflexivo consome mais tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[RETROSPECTIVE] Falha crítica no pipeline do Retrospective Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de retrospectiva técnica",
            "retrospective": {"analysis": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

