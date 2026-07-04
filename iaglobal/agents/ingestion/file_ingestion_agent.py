# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from iaglobal._paths import TEMP_DIR

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".txt": "text", ".md": "markdown", ".py": "python",
    ".json": "json", ".csv": "csv", ".html": "html",
    ".css": "css", ".js": "javascript", ".yaml": "yaml",
    ".yml": "yaml", ".xml": "xml", ".ini": "ini",
    ".cfg": "config", ".log": "log", ".env": "env",
    ".php": "php", ".sql": "sql", ".sh": "shell", ".bash": "shell",
    ".ts": "typescript", ".jsx": "react", ".tsx": "react-ts",
    ".java": "java", ".kt": "kotlin", ".swift": "swift",
    ".rb": "ruby", ".go": "go", ".rs": "rust", ".c": "c",
    ".cpp": "cpp", ".h": "header", ".hpp": "header",
    ".vue": "vue", ".svelte": "svelte", ".astro": "astro",
    ".scss": "scss", ".less": "less", ".styl": "stylus",
    ".dockerfile": "docker", ".toml": "toml",
    ".lock": "lock", ".patch": "patch", ".diff": "diff",
    ".rst": "rst", ".tex": "latex", ".bib": "bibtex",
    ".asp": "asp", ".aspx": "aspnet", ".cshtml": "razor",
    ".pdf": "pdf",
}


class FileIngestionAgent:
    """Ingere arquivos do filesystem e extrai conteúdo estruturado."""

    @classmethod
    def detect_file_paths(cls, text: str) -> List[str]:
        """Detecta caminhos de arquivo no texto (ex: /home/user/file.py, ./src/main.ts)."""
        patterns = [
            r'(?:/[^\s/\'"]*)+\.\w+',
            r'(?:\.\.?/[^\s\'"]*)+\.\w+',
            r'(?:~/[^\s\'"]*)+\.\w+',
        ]
        found = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                path = m.group().strip("'\"(),.;")
                p = Path(path).expanduser().resolve()
                if p.exists() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    found.add(str(p))
        return list(found)

    @classmethod
    def ingest(cls, paths: List[str], max_size_kb: int = 2000) -> Dict[str, Any]:
        results = []
        errors = []
        total_chars = 0

        for path_str in paths:
            p = Path(path_str).expanduser().resolve()
            if not p.exists():
                errors.append({"path": path_str, "error": "Arquivo não encontrado"})
                continue

            if p.is_dir():
                for child in sorted(p.rglob("*")):
                    if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                        result = cls._ingest_file(child, max_size_kb)
                        if result:
                            results.append(result)
                            total_chars += result.get("char_count", 0)
                continue

            if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append({"path": path_str, "error": f"Extensão não suportada: {p.suffix}"})
                continue

            result = cls._ingest_file(p, max_size_kb)
            if result:
                results.append(result)
                total_chars += result.get("char_count", 0)

        return {
            "files": results,
            "file_count": len(results),
            "errors": errors,
            "error_count": len(errors),
            "total_chars": total_chars,
            "status": "ingested",
        }

    @classmethod
    def _ingest_file(cls, path: Path, max_size_kb: int) -> Optional[Dict[str, Any]]:
        try:
            size_kb = path.stat().st_size / 1024
            if size_kb > max_size_kb:
                logger.warning("[INGEST] Arquivo muito grande: %s (%.1f KB)", path.name, size_kb)
                return None

            ext = path.suffix.lower()

            if ext == ".pdf":
                content = cls._extract_pdf_text(path)
            else:
                content = path.read_text(encoding="utf-8", errors="replace")

            return {
                "filename": path.name,
                "path": str(path),
                "extension": ext,
                "type": SUPPORTED_EXTENSIONS.get(ext, "unknown"),
                "content": content,
                "char_count": len(content),
                "size_kb": round(size_kb, 1),
            }
        except Exception as e:
            logger.warning("[INGEST] Erro ao ler %s: %s", path.name, e)
            return None

    @classmethod
    def _extract_pdf_text(cls, path: Path) -> str:
        try:
            import pdfminer.high_level
            return pdfminer.high_level.extract_text(str(path))
        except ImportError:
            pass
        try:
            import PyPDF2
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                return "\n".join(page.extract_text() for page in reader.pages)
        except ImportError:
            pass
        try:
            import fitz
            doc = fitz.open(str(path))
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            pass
        logger.warning("[INGEST] Nenhum extrator de PDF disponível (tente: pip install pdfminer.six)")
        return "[PDF NÃO EXTRAÍDO — instale pdfminer.six ou PyPDF2]"
