"""Query expansion — gera múltiplas queries focadas a partir de uma task."""
import re
from typing import List

_TECH_KEYWORDS = [
    "tutorial", "how to", "guide", "documentation", "docs", "reference",
    "api", "library", "framework", "example", "using", "implementation",
    "best practice", "patterns", "getting started",
]

_CONCEPT_KEYWORDS = [
    "what is", "definition", "concept", "overview", "introduction",
    "architecture", "design", "theory", "fundamentals", "principles",
]

_CODE_KEYWORDS = [
    "example", "code", "snippet", "github", "source", "implementation",
    "demo", "sample", "repository", "gist",
]

_LANG_MAP = {
    "python": "python", "js": "javascript", "ts": "typescript",
    "react": "react", "vue": "vue", "angular": "angular",
    "java": "java", "php": "php", "ruby": "ruby", "go": "golang",
    "rust": "rust", "cpp": "c++", "csharp": "c#", "sql": "sql",
}

_STOP_WORDS = {
    "criar", "função", "funcao", "como", "fazer", "gerar", "código",
    "codigo", "algoritmo", "programa", "para", "com", "uma", "um",
    "de", "em", "que", "é", "e", "do", "da", "dos", "das",
    "no", "na", "os", "as", "se", "mais", "mas", "por", "ser",
    "create", "function", "how", "to", "make", "generate", "code",
    "using", "with", "the", "a", "an", "in", "of", "for",
}


def _clean_query(task: str) -> str:
    words = task.lower().split()
    cleaned = " ".join(w for w in words if w not in _STOP_WORDS and len(w) > 1)
    return cleaned if cleaned else task


def _detect_language(task: str) -> str:
    task_lower = task.lower()
    for name, eng in _LANG_MAP.items():
        if name in task_lower:
            return eng
    return ""


def _detect_domain(task: str) -> str:
    domains = {
        "web": ["web", "html", "css", "frontend", "backend", "site", "pagina", "api", "rest"],
        "data": ["data", "database", "sql", "nosql", "analytics", "etl", "pipeline", "query"],
        "automation": ["script", "automation", "bot", "crawler", "scraper", "cli", "batch"],
        "ml": ["machine learning", "deep learning", "neural", "train", "model", "ai", "ia"],
    }
    task_lower = task.lower()
    for domain, keywords in domains.items():
        if any(k in task_lower for k in keywords):
            return domain
    return "general"


def generate_queries(task: str) -> dict:
    """Generate 4 focused queries from a task string."""
    base = _clean_query(task)
    lang = _detect_language(task)
    domain = _detect_domain(task)
    lang_tag = f" {lang}" if lang else ""

    queries = {
        "general": task,
        "technical": base,
        "conceptual": f"what is {base} definition overview",
        "practical": f"{base} example code snippet",
    }

    if lang:
        queries["general"] = task
        queries["technical"] = f"{base} tutorial documentation{lang_tag}"
        queries["conceptual"] = f"what is {base} {lang} overview"
        queries["practical"] = f"{base} {lang} example code github"

    if domain == "web":
        queries["technical"] = f"{base} web development tutorial{lang_tag}"
        queries["practical"] = f"{base} web example code{lang_tag}"
    elif domain == "data":
        queries["technical"] = f"{base} database tutorial{lang_tag}"
        queries["practical"] = f"{base} data example code{lang_tag}"
    elif domain == "automation":
        queries["technical"] = f"{base} script automation tutorial{lang_tag}"
        queries["practical"] = f"{base} script example automation{lang_tag}"

    return queries


__all__ = ["generate_queries"]
