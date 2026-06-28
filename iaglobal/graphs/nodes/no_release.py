# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_release.py

"""
Release Node — Executa a consolidação final, empacotamento e homologação de entrega do pipeline.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.result_agent import ResultAgent

logger = logging.getLogger(__name__)


async def run_release(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a homologação e empacotamento final de entrega de forma assíncrona.
    Mapeia latência e sucesso operacional de infraestrutura para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "release_deterministic_io_infrastructure"
    
    logger.info("[RELEASE] Iniciando consolidação e fechamento dos entregáveis finais para deploy...")

    try:
        # Inicializa o agente responsável pela compilação do resultado
        agent = ResultAgent()
        
        # Como a estruturação de relatórios e manipulação de arquivos em disco realizam I/O síncrono,
        # desviamos a execução inteira do build para a Thread Pool salvaguardando o loop de eventos
        if asyncio.iscoroutinefunction(agent.build_result):
            result = await agent.build_result(ctx=ctx)
        else:
            result = await asyncio.to_thread(agent.build_result, ctx=ctx)
            
        logger.info("[RELEASE] Pacote de release estruturado e homologado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("summary", "Release gerada com sucesso") if isinstance(result, dict) else str(result or ""),
            "release": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0  # Processamento de infraestrutura offline local de disco
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[RELEASE] Falha crítica no pipeline do Release Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de fechamento de release",
            "release": {"status": "failed", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

