# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_tester.py

"""
Tester Node — Componente de geração de suítes de testes do iaglobal.
Gera validações automatizadas com telemetria ativa para o Bandit Policy.
"""
import time
import asyncio
from typing import Dict, Any

from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.nodes.tester")


async def run_tester(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente testador de forma assíncrona e não-bloqueante.
    Mapeia a cobertura sintática, latência e custo para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "tester_agent_llm"
    
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    # Varre as memórias de forma resiliente em busca do código gerado
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
        logger.warning("[TESTER] Nenhum código encontrado nas memórias para geração de testes.")
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", 
            "test_output": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

    contexto_busca = memory.get("prompt_builder", {}).get("built_prompt", "")

    try:
        logger.info("[TESTER] Inicializando geração inteligente de suítes de teste...")
        agent = TesterAgent()
        
        if asyncio.iscoroutinefunction(agent.gerar_testes):
            test_output = await agent.gerar_testes(codigo=code, task=task_str, contexto=contexto_busca)
        else:
            test_output = await asyncio.to_thread(agent.gerar_testes, codigo=code, task=task_str)
            
        test_code = test_output.test_code if hasattr(test_output, 'test_code') else (test_output or "")
        test_len = len(test_code)
        logger.info("[TESTER] Ciclo finalizado com sucesso! Gerados %d caracteres de testes.", test_len)
        
        is_success = test_output.success if hasattr(test_output, 'success') else (test_len > 10)
        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "output": test_code,
            "test_output": test_code,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.01)  # Custo de inferência estimado para geração de testes
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[TESTER] Falha crítica no pipeline do Tester Agent: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "test_output": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)
            }
        }

