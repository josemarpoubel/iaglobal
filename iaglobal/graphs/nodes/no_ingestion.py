"""Ingestion handler — detecta e ingere arquivos do contexto."""
from typing import Dict, Any
import logging

from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent

logger = logging.getLogger(__name__)


async def run_ingestion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    task = str(ctx.get("input", {}).get("task", ""))
    detected_paths = FileIngestionAgent.detect_file_paths(task)

    if not detected_paths:
        logger.info("[INGESTION] Nenhum caminho de arquivo detectado na task")
        return {**ctx, "output": {}, "ingested": {"file_count": 0, "status": "no_paths"}}

    result = FileIngestionAgent.ingest(detected_paths)
    logger.info("[INGESTION] %d arquivos ingeridos, %d erros",
                result.get("file_count", 0), result.get("error_count", 0))

    return {
        **ctx,
        "output": result,
        "ingested": result,
    }
