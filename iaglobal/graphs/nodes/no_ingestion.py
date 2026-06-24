# iaglobal/graphs/nodes/no_ingestion.py

"""
Ingestion Node — Detecta, isola e ingere arquivos do contexto de disco de forma assíncrona.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent

logger = logging.getLogger(__name__)


async def run_ingestion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a detecção e ingestão de arquivos de disco de forma assíncrona.
    Mapeia latência, arquivos lidos e sucesso para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "ingestion_deterministic_disk_io"
    
    task = str(ctx.get("input", {}).get("task", ""))
    logger.info("[INGESTION] Iniciando varredura de caminhos de arquivos no escopo da task...")

    try:
        # Como varreduras de strings e checagens de arquivo em disco realizam I/O síncrono,
        # desviamos a detecção para uma thread pool isolada
        detected_paths = await asyncio.to_thread(FileIngestionAgent.detect_file_paths, task)

        if not detected_paths:
            logger.info("[INGESTION] Nenhum caminho de arquivo detectado na task. Ciclo pulado.")
            latency_ms = (time.time() - start_time) * 1000.0
            return {
                "output": {},
                "ingested": {"file_count": 0, "status": "no_paths"},
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": 0.0
                }
            }

        logger.info("[INGESTION] Detectados %d caminhos em potencial. Iniciando leitura de disco...", len(detected_paths))
        
        # Desvia a ingestão/leitura pesada de binários e textos para a thread pool
        result = await asyncio.to_thread(FileIngestionAgent.ingest, detected_paths)
        
        file_count = result.get("file_count", 0)
        error_count = result.get("error_count", 0)
        
        logger.info("[INGESTION] Sucesso! %d arquivos ingeridos com segurança (%d erros de leitura).", 
                    file_count, error_count)

        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se conseguiu varrer o disco sem quebrar a execução do nó
        is_success = error_count == 0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": result,
            "ingested": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0  # Processamento de infraestrutura local
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[INGESTION] Falha crítica no pipeline do Ingestion Node: %s", e)
        
        return {
            "output": {},
            "ingested": {"file_count": 0, "status": "failed", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

