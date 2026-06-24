# iaglobal/graphs/nodes/no_reflexion.py

"""
Reflexion Node — Executa o loop de autorreflexão cognitiva cruzando código e sandbox.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)


async def run_reflexion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise de autorreflexão de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "reflexion_agent_llm_core"
    
    memory = ctx.get("memory", {}) or {}
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    # Varre as fontes de código anteriores de forma resiliente
    sources = ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder")
    for source in sources:
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[REFLEXION] Nenhum código encontrado nas memórias para ciclo de autorreflexão.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", 
            "reflexion_analysis": "",
            "execution_metrics": {
                "model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0
            }
        }

    # Consolida os feedbacks obtidos na Sandbox pelo executor
    code_exec_data = memory.get("code_executor", {}) or {}
    resultado_sandbox = {
        "sucesso": code_exec_data.get("success", True),
        "output": code_exec_data.get("output", ""),
        "erro": code_exec_data.get("error", "") or code_exec_data.get("exec_error", ""),
    }

    logger.info("[REFLEXION] Iniciando ciclo metacognitivo de autorreflexão...")

    try:
        # Inicializa o agente especializado em Reflexion
        agent = ReflexionAgent()
        
        # Como loops analíticos de reflexão realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.analisar_resultado):
            analysis = await agent.analisar_resultado(codigo=code, resultado_sandbox=resultado_sandbox, task=task_str)
        else:
            analysis = await asyncio.to_thread(agent.analisar_resultado, codigo=code, resultado_sandbox=resultado_sandbox, task=task_str)
            
        analysis_str = str(analysis or "")
        logger.info("[REFLEXION] Análise finalizada com sucesso: %d caracteres gerados.", len(analysis_str))
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = bool(analysis_str and len(analysis_str.strip()) > 5)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": analysis_str,
            "reflexion_analysis": analysis_str,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.006)  # Processamento de autorreflexão consome mais tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[REFLEXION] Falha crítica no pipeline do Reflexion Node: %s", e)
        
        return {
            "output": "",
            "reflexion_analysis": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

