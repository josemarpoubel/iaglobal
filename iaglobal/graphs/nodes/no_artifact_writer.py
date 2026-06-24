# iaglobal/graphs/nodes/no_artifact_writer.py

"""
Artifact Writer Node — Consolida e persiste em disco os artefatos finais do pipeline.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio

from typing import Dict, Any

from iaglobal.agents.result_agent import ResultAgent

logger = logging.getLogger(__name__)


async def run_artifact_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a consolidação e persistência de artefatos finais em disco de forma assíncrona.
    Mapeia latência e sucesso operacional para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "artifact_writer_deterministic_io"
    
    logger.info("[ARTIFACT_WRITER] Iniciando consolidação e gravação dos entregáveis finais em disco...")

    try:
        # Inicializa o agente responsável pelo empacotamento do resultado
        agent = ResultAgent()
        
        # Como a consolidação e escrita de arquivos em disco realizam I/O síncrono pesado,
        # desviamos a execução para uma thread pool isolada para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.build_result):
            result = await agent.build_result(ctx=ctx)
        else:
            result = await asyncio.to_thread(agent.build_result, ctx=ctx)
            
        logger.info("[ARTIFACT_WRITER] Artefatos e entregáveis finais persistidos com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se o agente conseguiu gerar o dicionário de resultado
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result.get("summary", "Artefatos consolidados com sucesso") if isinstance(result, dict) else str(result),
            "artifact_writer": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0  # Processamento de infraestrutura local de disco
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[ARTIFACT_WRITER] Falha crítica no pipeline do Artifact Writer Node: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de gravação de artefatos",
            "artifact_writer": {"status": "failed", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

