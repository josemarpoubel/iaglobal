# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/_search_queries.py

"""
Query expansion — gera múltiplas queries focadas a partir de uma task.
Otimizado para imutabilidade total, tokenização resiliente e alta performance local.
"""
import re
from types import MappingProxyType
from typing import Dict, List, Set

# Coleções estáticas congeladas em memória para máxima performance de hash lookup
_TECH_KEYWORDS = frozenset([
    "tutorial", "how to", "guide", "documentation", "docs", "reference",
    "api", "library", "framework", "example", "using", "implementation",
    "best practice", "patterns", "getting started",
])

_CONCEPT_KEYWORDS = frozenset([
    "what is", "definition", "concept", "overview", "introduction",
    "architecture", "design", "theory", "fundamentals", "principles",
])

_CODE_KEYWORDS = frozenset([
    "example", "code", "snippet", "github", "source", "implementation",
    "demo", "sample", "repository", "gist",
])

_LANG_MAP = MappingProxyType({
    "python": "python", "js": "javascript", "ts": "typescript",
    "react": "react", "vue": "vue", "angular": "angular",
    "java": "java", "php": "php", "ruby": "ruby", "go": "golang",
    "rust": "rust", "cpp": "c++", "csharp": "c#", "sql": "sql",
})

_STOP_WORDS = frozenset([
    "criar", "função", "funcao", "como", "fazer", "gerar", "código",
    "codigo", "algoritmo", "programa", "para", "com", "uma", "um",
    "de", "em", "que", "é", "e", "do", "da", "dos", "das",
    "no", "na", "os", "as", "se", "mais", "mas", "por", "ser",
    "create", "function", "how", "to", "make", "generate", "code",
    "using", "with", "the", "a", "an", "in", "of", "for",
])

# Regex pré-compilado para extrair palavras puras ignorando pontuações
_WORD_REGEX = re.compile(r"\b\w+\b")


def _clean_query(task: str) -> str:
    """Extrai palavras puras via regex e remove stop-words com performance O(1)."""
    if not task:
        return ""
    words = _WORD_REGEX.findall(task.lower())
    cleaned = " ".join(w for w in words if w not in _STOP_WORDS and len(w) > 1)
    return cleaned if cleaned else task


def _detect_language(task: str) -> str:
    """Detecta a linguagem de programação de forma resiliente."""
    task_lower = task.lower()
    for name, eng in _LANG_MAP.items():
        if name in task_lower:
            return eng
    return ""


def _detect_domain(task: str) -> str:
    """Detecta o domínio técnico da tarefa aplicando casamento de padrões em loops otimizados."""
    domains = {
        "web": ("web", "html", "css", "frontend", "backend", "site", "pagina", "api", "rest"),
        "data": ("data", "database", "sql", "nosql", "analytics", "etl", "pipeline", "query"),
        "automation": ("script", "automation", "bot", "crawler", "scraper", "cli", "batch"),
        "ml": ("machine learning", "deep learning", "neural", "train", "model", "ai", "ia"),
    }
    task_lower = task.lower()
    for domain, keywords in domains.items():
        if any(k in task_lower for k in keywords):
            return domain
    return "general"


def generate_queries(task: str) -> MappingProxyType:
    """
    Gera 4 queries estruturadas e segmentadas a partir da string da tarefa.
    Retorna uma estrutura de visualização imutável (Read-Only) para segurança do grafo.
    """
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

    # Congela o dicionário de saída em modo Read-Only prevenindo mutações colaterais
    return MappingProxyType(queries)


__all__ = ["generate_queries"]

