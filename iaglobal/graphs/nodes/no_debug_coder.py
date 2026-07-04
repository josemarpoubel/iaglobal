# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_debug_coder.py

"""
Debug Coder Node — Executa correções cirúrgicas de código guiadas por erros.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.debugger_agent import DebuggerAgent

logger = logging.getLogger(__name__)


async def run_debug_coder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de depuração e correção de código de forma assíncrona.
    Mapeia latência, custo e sucesso de correção para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "debug_coder_agent_llm"
    
    logger.info("[DEBUG_CODER] Iniciando ciclo de correção e depuração de código...")
    
    # Coleta os dados de forma resiliente do contexto ou das memórias
    code = ctx.get("coder", {}).get("output", ctx.get("multi_coder", {}).get("output", ""))
    if not code:
        memory = ctx.get("memory", {})
        code = memory.get("coder", {}).get("output", "") or memory.get("multi_coder", {}).get("output", "")
        
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    erro_contexto = str(ctx.get("exec_error", "") or ctx.get("memory", {}).get("code_executor", {}).get("exec_error", ""))

    try:
        # Inicializa o agente depurador
        agent = DebuggerAgent()
        
        # Como correções de código realizam inferências pesadas de IA,
        # desviamos para Thread Pool se o método for síncrono para proteger o laço de eventos
        if asyncio.iscoroutinefunction(agent.corrigir_codigo):
            result = await agent.corrigir_codigo(codigo=code, erro=erro_contexto, task=task)
        else:
            result = await asyncio.to_thread(agent.corrigir_codigo, codigo=code, erro=erro_contexto, task=task)
            
        code_output = str(result)
        
        # Portão de segurança: se o código gerado for nulo ou em branco, assume falha
        is_success = bool(code_output and len(code_output.strip()) > 5)
        
        if is_success:
            logger.info("[DEBUG_CODER] Código corrigido com sucesso: %d caracteres.", len(code_output))
        else:
            logger.warning("[DEBUG_CODER] Geração retornou um código de correção vazio.")

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desempacotar o ctx na RAM)
        return {
            "output": code_output,
            "debug_coder": {
                "output": code_output
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.012)  # Custo de inferência estimado para refatoração/correção
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DEBUG_CODER] Falha crítica no pipeline do Debug Coder Agent: %s", e)
        
        return {
            "output": code,
            "debug_coder": {"output": code, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

