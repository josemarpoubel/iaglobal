# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PaperIngestor — Baixa papers científicos de repositórios públicos.

Suporta:
- arXiv (CS, AI, ML)
- PubMed (biologia computacional)
- Hugging Face Papers
- RSS feeds de conferências (NeurIPS, ICML, ICLR)

Integra com FileIngestionAgent para extração de texto de PDF/HTML.
"""

import aiohttp
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from iaglobal._paths import TEMP_DIR, JSON_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.ingestion.paper_ingestor")

REPOSITORIES = {
    "arxiv": "https://arxiv.org/abs/",
    "arxiv_pdf": "https://arxiv.org/pdf/",
    "pubmed": "https://pubmed.ncbi.nlm.nih.gov/",
    "hf": "https://huggingface.co/papers/",
}

RESEARCH_QUEUE_FILE = JSON_DIR / "research_queue.json"


@dataclass
class PaperRecord:
    """Registro de paper na fila de pesquisa."""
    paper_id: str
    repository: str
    status: str = "pending"  # pending|ingested|parsed|hypothesized|validated|consolidated
    local_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PaperIngestor:
    """Baixa papers de repositórios públicos."""

    def __init__(self, download_dir: Optional[Path] = None):
        self.download_dir = download_dir or (TEMP_DIR / "papers")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_queue_file()

    def _ensure_queue_file(self):
        """Garante arquivo da fila de pesquisa."""
        if not RESEARCH_QUEUE_FILE.exists():
            RESEARCH_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                "queue": [],
                "stats": {
                    "total": 0,
                    "pending": 0,
                    "ingested": 0,
                    "parsed": 0,
                    "hypothesized": 0,
                    "validated": 0,
                    "consolidated": 0,
                }
            }
            RESEARCH_QUEUE_FILE.write_text(json.dumps(initial_data, indent=2))

    def _load_queue(self) -> Dict[str, Any]:
        """Carrega fila de pesquisa."""
        try:
            return json.loads(RESEARCH_QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"queue": [], "stats": {}}

    def _save_queue(self, data: Dict[str, Any]):
        """Salva fila de pesquisa."""
        RESEARCH_QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _update_stats(self, queue_data: Dict[str, Any]):
        """Atualiza estatísticas da fila."""
        stats = {
            "total": len(queue_data["queue"]),
            "pending": 0,
            "ingested": 0,
            "parsed": 0,
            "hypothesized": 0,
            "validated": 0,
            "consolidated": 0,
        }
        for record in queue_data["queue"]:
            status = record.get("status", "pending")
            if status in stats:
                stats[status] += 1
        queue_data["stats"] = stats

    async def ingest(self, paper_id: str, repository: str = "arxiv") -> Optional[Path]:
        """
        Baixa paper e retorna caminho do arquivo local.

        Args:
            paper_id: ID do paper (ex: "2401.12345" para arXiv)
            repository: Repositório ("arxiv", "pubmed", "hf")

        Returns:
            Path do arquivo baixado ou None se falhar
        """
        import datetime

        # Registrar na fila
        queue_data = self._load_queue()
        record = PaperRecord(
            paper_id=paper_id,
            repository=repository,
            status="pending",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        # Verificar se já existe na fila
        existing = next((r for r in queue_data["queue"] if r["paper_id"] == paper_id), None)
        if existing:
            logger.info("[INGEST] Paper %s já está na fila (status: %s)", paper_id, existing["status"])
            if existing.get("local_path"):
                return Path(existing["local_path"])
            return None

        queue_data["queue"].append(record.to_dict())
        self._update_stats(queue_data)
        self._save_queue(queue_data)

        # Baixar paper
        try:
            local_path = await self._download_paper(paper_id, repository)
            if local_path:
                # Atualizar registro
                for r in queue_data["queue"]:
                    if r["paper_id"] == paper_id:
                        r["status"] = "ingested"
                        r["local_path"] = str(local_path)
                        r["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        break

                self._update_stats(queue_data)
                self._save_queue(queue_data)
                logger.info("[INGEST] Paper %s baixado em: %s", paper_id, local_path)
                return local_path
            else:
                logger.warning("[INGEST] Falha ao baixar paper %s", paper_id)
                return None
        except Exception as e:
            logger.error("[INGEST] Erro ao baixar paper %s: %s", paper_id, e)
            return None

    async def _download_paper(self, paper_id: str, repository: str) -> Optional[Path]:
        """Baixa paper do repositório."""
        if repository == "arxiv":
            return await self._download_arxiv(paper_id)
        elif repository == "pubmed":
            return await self._download_pubmed(paper_id)
        elif repository == "hf":
            return await self._download_huggingface(paper_id)
        else:
            logger.warning("[INGEST] Repositório não suportado: %s", repository)
            return None

    async def _download_arxiv(self, paper_id: str) -> Optional[Path]:
        """Baixa PDF do arXiv."""
        # Normalizar paper_id (remover "arxiv:" prefixo se existir)
        paper_id = paper_id.replace("arxiv:", "").strip()

        pdf_url = f"{REPOSITORIES['arxiv_pdf']}{paper_id}.pdf"
        local_path = self.download_dir / f"{paper_id.replace('/', '_')}.pdf"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url, timeout=60) as response:
                    if response.status == 200:
                        content = await response.read()
                        local_path.write_bytes(content)
                        logger.info("[INGEST] arXiv %s: %.1f KB", paper_id, len(content) / 1024)
                        return local_path
                    else:
                        logger.warning("[INGEST] arXiv %s retornou status %d", paper_id, response.status)
                        return None
        except aiohttp.ClientError as e:
            logger.error("[INGEST] Erro de rede ao baixar arXiv %s: %s", paper_id, e)
            return None
        except Exception as e:
            logger.error("[INGEST] Erro ao baixar arXiv %s: %s", paper_id, e)
            return None

    async def _download_pubmed(self, paper_id: str) -> Optional[Path]:
        """Baixa página HTML do PubMed."""
        paper_id = paper_id.replace("pubmed:", "").strip()
        
        html_url = f"{REPOSITORIES['pubmed']}{paper_id}/"
        local_path = self.download_dir / f"pubmed_{paper_id}.html"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(html_url, timeout=60) as response:
                    if response.status == 200:
                        content = await response.text()
                        local_path.write_text(content, encoding="utf-8")
                        logger.info("[INGEST] PubMed %s: %.1f KB", paper_id, len(content) / 1024)
                        return local_path
                    else:
                        logger.warning("[INGEST] PubMed %s retornou status %d", paper_id, response.status)
                        return None
        except Exception as e:
            logger.error("[INGEST] Erro ao baixar PubMed %s: %s", paper_id, e)
            return None

    async def _download_huggingface(self, paper_id: str) -> Optional[Path]:
        """Baixa página HTML do Hugging Face Papers."""
        paper_id = paper_id.replace("hf:", "").strip()
        
        html_url = f"{REPOSITORIES['hf']}{paper_id}"
        local_path = self.download_dir / f"hf_{paper_id.replace('/', '_')}.html"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(html_url, timeout=60) as response:
                    if response.status == 200:
                        content = await response.text()
                        local_path.write_text(content, encoding="utf-8")
                        logger.info("[INGEST] HF Papers %s: %.1f KB", paper_id, len(content) / 1024)
                        return local_path
                    else:
                        logger.warning("[INGEST] HF Papers %s retornou status %d", paper_id, response.status)
                        return None
        except Exception as e:
            logger.error("[INGEST] Erro ao baixar HF Papers %s: %s", paper_id, e)
            return None

    def get_queue_status(self) -> Dict[str, Any]:
        """Retorna status da fila de pesquisa."""
        queue_data = self._load_queue()
        return queue_data.get("stats", {})

    def get_pending_papers(self) -> List[Dict[str, Any]]:
        """Retorna lista de papers pendentes."""
        queue_data = self._load_queue()
        return [r for r in queue_data.get("queue", []) if r.get("status") == "pending"]

    def get_paper_record(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Retorna registro de um paper específico."""
        queue_data = self._load_queue()
        return next((r for r in queue_data.get("queue", []) if r["paper_id"] == paper_id), None)


# Funções utilitárias para ingestão em lote
async def ingest_batch(paper_ids: List[str], repository: str = "arxiv") -> List[Optional[Path]]:
    """
    Baixa múltiplos papers em paralelo.

    Args:
        paper_ids: Lista de IDs de papers
        repository: Repositório (padrão: "arxiv")

    Returns:
        Lista de paths baixados (None para falhas)
    """
    ingestor = PaperIngestor()
    tasks = [ingestor.ingest(pid, repository) for pid in paper_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    paths = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("[INGEST] Batch: paper %s falhou: %s", paper_ids[i], result)
            paths.append(None)
        else:
            paths.append(result)
    
    return paths


import asyncio