# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PaperParser — Extrai metadados e abstracts de papers científicos.

Suporta:
- PDF (via pdfminer, PyPDF2, ou fitz)
- HTML (PubMed, Hugging Face Papers)
- Texto puro

Extrai: título, autores, data, abstract, tópicos/keywords.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.ingestion.paper_parser")


@dataclass
class PaperMetadata:
    """Metadados de paper científico."""
    paper_id: str
    title: str
    abstract: str
    authors: List[str]
    published_date: str
    repository: str
    topics: List[str]
    full_text: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PaperParser:
    """Extrai metadados e abstract de papers."""

    def __init__(self):
        pass

    async def parse(self, text: str, paper_id: str, repository: str = "arxiv") -> Optional[PaperMetadata]:
        """
        Extrai metadados de paper.

        Args:
            text: Conteúdo do paper (PDF extraído ou HTML)
            paper_id: ID do paper
            repository: Repositório de origem

        Returns:
            PaperMetadata ou None se falhar
        """
        try:
            # Extrair metadados via regex + heurística
            metadata = self._extract_metadata(text, paper_id, repository)

            if not metadata.get("abstract"):
                logger.warning("[PARSER] Paper %s: abstract não encontrado", paper_id)
                return None

            return PaperMetadata(
                paper_id=paper_id,
                title=metadata.get("title", "Título não encontrado"),
                abstract=metadata["abstract"],
                authors=metadata.get("authors", []),
                published_date=metadata.get("published_date", ""),
                repository=repository,
                topics=metadata.get("topics", []),
                full_text=text[:50000],  # Limitar a 50k chars
                doi=metadata.get("doi"),
                journal=metadata.get("journal"),
            )
        except Exception as e:
            logger.error("[PARSER] Erro ao extrair metadados de %s: %s", paper_id, e)
            return None

    def _extract_metadata(self, text: str, paper_id: str, repository: str) -> Dict[str, Any]:
        """Extrai metadados via regex + heurística."""
        metadata = {
            "title": "",
            "abstract": "",
            "authors": [],
            "published_date": "",
            "topics": [],
            "doi": None,
            "journal": None,
        }

        # Extrair abstract (padrões comuns)
        abstract_patterns = [
            r"(?:abstract|resumo)\s*(?:[:\-]|\n)\s*(.+?)(?:\n\n|\n{2,}|$)",
            r"(?:abstract|resumo)\s*\n\s*(.+?)(?:\n\n|\n{2,}|$)",
        ]

        for pattern in abstract_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                metadata["abstract"] = match.group(1).strip()
                break

        # Se não encontrou abstract, tentar padrão arXiv (primeiro parágrafo após título)
        if not metadata["abstract"] and repository == "arxiv":
            # arXiv PDFs extraídos geralmente têm abstract no início
            lines = text.split("\n")
            for i, line in enumerate(lines[:50]):
                if len(line) > 100 and i > 0:  # Parágrafo longo
                    metadata["abstract"] = line.strip()
                    break

        # Extrair título (primeira linha não-vazia significativa)
        lines = text.split("\n")
        for line in lines[:20]:
            line = line.strip()
            if line and len(line) > 20 and len(line) < 300:
                # Evitar capturar "arXiv:..." ou URLs
                if not line.startswith("arXiv:") and not line.startswith("http"):
                    metadata["title"] = line
                    break

        # Extrair autores (padrões comuns)
        author_patterns = [
            r"(?:authors?|by)\s*(?:[:\-]|\n)\s*(.+?)(?:\n\n|\n|$)",
            r"(\d{4})\s*[-·]\s*(.+?)(?:\n|$)",  # "2024 - Author1, Author2"
        ]

        for pattern in author_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                authors_text = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
                # Separar por vírgulas ou "and"
                authors = re.split(r",\s*|\s+and\s+", authors_text)
                metadata["authors"] = [a.strip() for a in authors if len(a.strip()) > 2][:10]
                break

        # Extrair data de publicação
        date_patterns = [
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",  # YYYY-MM-DD
            r"(\w+\s+\d{1,2},?\s+\d{4})",  # "Month DD, YYYY"
            r"(\d{1,2}\s+\w+\s+\d{4})",  # "DD Month YYYY"
            r"(?:published|submitted|received)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["published_date"] = match.group(1)
                break

        # Se não encontrou data, usar ano do paper_id (arXiv)
        if not metadata["published_date"] and repository == "arxiv":
            arxiv_year_match = re.match(r"(\d{2})(\d{2})", paper_id.replace("arxiv:", "").split(".")[0])
            if arxiv_year_match:
                year = int(arxiv_year_match.group(1))
                year = 2000 + year if year < 50 else 1900 + year
                metadata["published_date"] = f"{year}"

        # Extrair tópicos/keywords
        keyword_patterns = [
            r"(?:keywords?|topics?|subjects?)\s*(?:[:\-]|\n)\s*(.+?)(?:\n\n|\n|$)",
            r"(?:ccs concepts?|acm classification)\s*(?:[:\-]|\n)\s*(.+?)(?:\n\n|\n|$)",
        ]

        for pattern in keyword_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                keywords_text = match.group(1)
                # Separar por vírgulas, ponto-e-vírgula, ou nova linha
                keywords = re.split(r"[,;\n]", keywords_text)
                metadata["topics"] = [k.strip().lower() for k in keywords if len(k.strip()) > 2][:20]
                break

        # Se não encontrou keywords, extrair do abstract (top 10 palavras mais freqüentes)
        if not metadata["topics"] and metadata["abstract"]:
            metadata["topics"] = self._extract_keywords_from_text(metadata["abstract"])

        # Extrair DOI
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.IGNORECASE)
        if doi_match:
            metadata["doi"] = doi_match.group(0)

        return metadata

    def _extract_keywords_from_text(self, text: str, top_n: int = 10) -> List[str]:
        """Extrai keywords do texto via frequência de palavras."""
        # Remover stopwords comuns
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "we", "our", "you", "your", "he", "she", "his", "her",
            "which", "who", "whom", "whose", "what", "where", "when", "why", "how",
            "all", "each", "every", "both", "few", "more", "most", "other", "some",
            "such", "no", "not", "only", "same", "so", "than", "too", "very",
            "just", "also", "now", "here", "there", "then", "once", "if", "any",
        }

        # Tokenizar
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Contar frequência
        freq = {}
        for word in words:
            if word not in stopwords:
                freq[word] = freq.get(word, 0) + 1

        # Top N
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:top_n]]

    def save_metadata(self, metadata: PaperMetadata, output_path: Optional[Path] = None) -> Path:
        """Salva metadados em JSON."""
        if output_path is None:
            output_path = JSON_DIR / "papers" / f"{metadata.paper_id.replace(':', '_')}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        logger.info("[PARSER] Metadados salvas em: %s", output_path)
        return output_path


# Funções utilitárias
async def parse_paper_file(file_path: Path, paper_id: Optional[str] = None) -> Optional[PaperMetadata]:
    """
    Parse de arquivo de paper (PDF ou HTML).

    Args:
        file_path: Caminho do arquivo
        paper_id: ID do paper (opcional, derivado do filename se None)

    Returns:
        PaperMetadata ou None
    """
    from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent

    # Extrair texto do arquivo
    result = FileIngestionAgent.ingest([str(file_path)])
    if not result.get("files"):
        logger.error("[PARSER] Falha ao ler arquivo: %s", file_path)
        return None

    file_data = result["files"][0]
    content = file_data.get("content", "")

    if not content or content.startswith("[PDF NÃO EXTRAÍDO"):
        logger.error("[PARSER] Conteúdo vazio ou não extraído: %s", file_path)
        return None

    # Extrair paper_id do filename se não fornecido
    if not paper_id:
        paper_id = file_path.stem

    # Detectar repositório
    repository = "arxiv"
    if "pubmed" in file_path.name.lower():
        repository = "pubmed"
    elif "hf_" in file_path.name.lower():
        repository = "hf"

    # Parse
    parser = PaperParser()
    return await parser.parse(content, paper_id, repository)