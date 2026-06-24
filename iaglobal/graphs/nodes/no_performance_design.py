# iaglobal/graphs/nodes/no_performance_design.py

"""
Performance Design Node — Executa o desenho analítico de performance cruzando designs do grafo.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.performance_design_agent import PerformanceDesignAgent

logger = logging.getLogger(__name__)


async def run_performance_design(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o desenho analítico de performance de forma assíncrona e não-bloqueante.
    Mapeia latência, custos de inferência e scores de eficiência para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "performance_design_agent_llm"
    
    memory = ctx.get("memory", {}) or {}
    task_str = str(ctx.get("input", {}).get("task", ""))

    # Consolida a árvore completa de design de forma resiliente
    design_context = {
        "architecture": memory.get("architect", {}).get("output", {}) or memory.get("architecture", {}).get("output", {}),
        "requirements": memory.get("requirements", {}).get("output", {}),
        "system_design": memory.get("system_design", {}).get("output"),
        "api_design": memory.get("api_design", {}).get("output"),
        "database_design": memory.get("database_design", {}).get("output"),
        "dependency_analysis": memory.get("dependency", {}).get("output"),
    }

    logger.info("[PERF_DESIGN] Iniciando modelagem e validação cruzada de performance de sistemas...")

    try:
        # Inicializa o agente especializado em performance
        agent = PerformanceDesignAgent()
        
        # Como análises cruzadas realizam inferências pesadas de IA,
        # desviamos para Thread Pool se o método for síncrono para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.analyze):
            result = await agent.analyze(design_context=design_context, knowledge_context="", error_context="")
        else:
            result = await asyncio.to_thread(agent.analyze, design_context=design_context, knowledge_context="", error_context="")
            
        score = result.get("score", "N/A") if isinstance(result, dict) else "N/A"
        logger.info("[PERF_DESIGN] Modelagem concluída com sucesso. Score de eficiência: %s", score)
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict)

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "performance_design": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)  # Desenhos complexos de arquitetura gastam mais tokens
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[PERF_DESIGN] Falha crítica no pipeline do Performance Design Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": {"performance_design_report": {}, "score": 0},
            "performance_design": {"performance_design_report": {}, "score": 0, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

