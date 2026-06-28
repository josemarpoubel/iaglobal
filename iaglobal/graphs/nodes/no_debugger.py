# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_debugger.py

"""
Debugger Node — Componente de autocorreção e depuração do iaglobal.
Analisa falhas de código com telemetria ativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.debugger_agent import DebuggerAgent, DebugResult
from iaglobal.models.task import Task

logger = logging.getLogger(__name__)


async def run_debugger(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente depurador de forma assíncrona e não-bloqueante.
    Mapeia tentativas, latência e custo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "debugger_agent_llm"
    
    memory = ctx.get("memory", {})
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
        logger.warning("[DEBUGGER] Nenhum código encontrado nas memórias para depuração.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", 
            "debug_result": None,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

    # Inicializa o modelo de tarefa core
    task = Task(objective=task_str, context={"code": code})

    try:
        logger.info("[DEBUGGER] Disparando agente de depuração para varredura de bugs...")
        agent = DebuggerAgent()
        
        # Garante execução assíncrona ou desvia para thread pool caso o run seja síncrono
        if asyncio.iscoroutinefunction(agent.run):
            result: DebugResult = await agent.run(task)
        else:
            result = await asyncio.to_thread(agent.run, task)
            
        logger.info("[DEBUGGER] Ciclo finalizado. Sucesso=%s | Tentativas=%d | Tempo=%.2fs", 
                    result.success, result.attempts, result.execution_time)
        
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo a Seção 1, 3 e 5 do AGENTS.md
        return {
            "output": result.code,
            "debug_result": {
                "success": result.success,
                "code": result.code,
                "error": result.error,
                "attempts": result.attempts,
                "execution_time": result.execution_time,
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": bool(result.success),
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.01) * max(1, result.attempts)  # Multiplica o custo pelas tentativas de correção
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DEBUGGER] Falha crítica no pipeline do Debugger Agent: %s", e)
        
        return {
            "output": code,
            "debug_result": {"success": False, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.005)
            }
        }

