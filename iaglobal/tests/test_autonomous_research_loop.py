# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Autonomous Research Loop — Fase 1 (Ingestão).

Cobertura:
  - PaperIngestor: ingest, download, queue management
  - PaperParser: extração de metadados
  - Integração com FileIngestionAgent
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion.paper_ingestor import PaperIngestor, PaperRecord
from iaglobal.agents.ingestion.paper_parser import PaperParser, PaperMetadata


class TestPaperIngestor:
    """Testes do PaperIngestor."""

    def test_ensure_queue_file_creates_structure(self, tmp_path):
        """_ensure_queue_file deve criar arquivo da fila."""
        queue_file = tmp_path / "research_queue.json"
        with patch(
            "iaglobal.agents.ingestion.paper_ingestor.RESEARCH_QUEUE_FILE", queue_file
        ):
            ingestor = PaperIngestor(download_dir=tmp_path / "papers")
            # O _ensure_queue_file é chamado no __init__
            assert queue_file.exists()
            data = json.loads(queue_file.read_text())
            assert "queue" in data
            assert "stats" in data

    def test_load_queue_returns_structure(self, tmp_path):
        """_load_queue deve retornar estrutura correta."""
        queue_file = tmp_path / "research_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(json.dumps({"queue": [], "stats": {}}))

        with patch(
            "iaglobal.agents.ingestion.paper_ingestor.RESEARCH_QUEUE_FILE", queue_file
        ):
            ingestor = PaperIngestor(download_dir=tmp_path / "papers")
            data = ingestor._load_queue()
            assert isinstance(data.get("queue"), list)
            assert isinstance(data.get("stats"), dict)

    def test_paper_record_to_dict(self):
        """PaperRecord.to_dict deve retornar dict serializável."""
        record = PaperRecord(
            paper_id="2401.12345",
            repository="arxiv",
            status="pending",
        )
        data = record.to_dict()
        assert data["paper_id"] == "2401.12345"
        assert data["repository"] == "arxiv"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_ingest_registers_in_queue(self, tmp_path):
        """ingest deve registrar paper na fila."""
        queue_file = tmp_path / "research_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text(json.dumps({"queue": [], "stats": {}}))

        with patch(
            "iaglobal.agents.ingestion.paper_ingestor.RESEARCH_QUEUE_FILE", queue_file
        ):
            with patch.object(
                PaperIngestor, "_download_paper", new_callable=AsyncMock
            ) as mock_download:
                mock_download.return_value = None  # Simular falha no download

                ingestor = PaperIngestor(download_dir=tmp_path / "papers")
                await ingestor.ingest("2401.12345", "arxiv")

                data = ingestor._load_queue()
                assert len(data["queue"]) == 1
                assert data["queue"][0]["paper_id"] == "2401.12345"
                assert data["queue"][0]["status"] == "pending"

    def test_get_queue_status_returns_stats(self, tmp_path):
        """get_queue_status deve retornar estatísticas."""
        queue_file = tmp_path / "research_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        test_data = {
            "queue": [
                {"paper_id": "1", "status": "pending"},
                {"paper_id": "2", "status": "ingested"},
                {"paper_id": "3", "status": "ingested"},
            ],
            "stats": {},
        }
        queue_file.write_text(json.dumps(test_data))

        with patch(
            "iaglobal.agents.ingestion.paper_ingestor.RESEARCH_QUEUE_FILE", queue_file
        ):
            ingestor = PaperIngestor(download_dir=tmp_path / "papers")
            # Chamar _update_stats para garantir que stats estão atualizados
            queue_data = ingestor._load_queue()
            ingestor._update_stats(queue_data)
            ingestor._save_queue(queue_data)

            stats = ingestor.get_queue_status()
            assert stats["total"] == 3
            assert stats["pending"] == 1
            assert stats["ingested"] == 2


class TestPaperParser:
    """Testes do PaperParser."""

    def test_extract_abstract_from_text(self):
        """Parser deve extrair abstract via regex."""
        text = """
        Title: Deep Learning for NLP
        
        Abstract: This paper presents a novel approach to natural language processing.
        We demonstrate significant improvements over baseline methods.
        
        Introduction
        Natural language processing has...
        """
        parser = PaperParser()
        metadata = parser._extract_metadata(text, "test_001", "arxiv")
        assert "abstract" in metadata
        assert "novel approach" in metadata["abstract"].lower()

    def test_extract_keywords_from_abstract(self):
        """Parser deve extrair keywords do abstract."""
        abstract = """
        Machine learning and deep neural networks have revolutionized
        natural language processing. Our approach uses transformer architectures
        for machine translation tasks.
        """
        parser = PaperParser()
        keywords = parser._extract_keywords_from_text(abstract, top_n=5)
        assert len(keywords) <= 5
        assert "machine" in keywords or "learning" in keywords

    def test_paper_metadata_to_dict(self):
        """PaperMetadata.to_dict deve serializar corretamente."""
        metadata = PaperMetadata(
            paper_id="2401.12345",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author1", "Author2"],
            published_date="2024-01-15",
            repository="arxiv",
            topics=["machine learning", "nlp"],
        )
        data = metadata.to_dict()
        assert data["paper_id"] == "2401.12345"
        assert data["title"] == "Test Paper"
        assert len(data["authors"]) == 2
        assert len(data["topics"]) == 2


class TestIntegration:
    """Testes de integração Ingestão → Parser."""

    @pytest.mark.asyncio
    async def test_parse_downloaded_paper(self, tmp_path):
        """Deve fazer parse de paper baixado."""
        from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent

        # Criar arquivo de teste (texto simulando paper) - usar .txt para evitar erro de PDF
        test_paper = tmp_path / "test_paper.txt"
        test_content = """
        Deep Learning for Natural Language Processing
        
        Abstract: This paper presents deep learning methods for NLP tasks.
        We achieve state-of-the-art results on benchmark datasets.
        
        Keywords: deep learning, natural language processing, transformers
        
        Authors: John Doe, Jane Smith
        Published: 2024-01-15
        """
        test_paper.write_text(test_content)

        # Ingerir
        result = FileIngestionAgent.ingest([str(test_paper)])
        assert result["file_count"] == 1
        content = result["files"][0]["content"]

        # Parse
        parser = PaperParser()
        metadata = await parser.parse(content, "test_001", "arxiv")

        assert metadata is not None
        assert (
            "deep learning" in metadata.title.lower()
            or "natural language" in metadata.title.lower()
        )
        assert metadata.abstract
        assert len(metadata.topics) > 0
