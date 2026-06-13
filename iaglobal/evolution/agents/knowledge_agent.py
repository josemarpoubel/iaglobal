# iaglobal/evolution/agents/knowledge_agent.py

"""
Knowledge Agent — Memória operacional de longo prazo.

Armazena e recupera:
- Arquiteturas anteriores e decisoes de design
- Bugs recorrentes e solucoes
- Boas praticas e padroes internos
- LicOes aprendidas

Funciona como um banco de conhecimento que outros agentes consultam
para tomar decisoes mais informadas.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from iaglobal._paths import DATA_ROOT
from iaglobal.utils.logger import logger

from iaglobal._paths import KNOWLEDGE_FILE


class KnowledgeAgent:
    """
    Agente de conhecimento transversal.

    Mantém um arquivo JSON com entradas categorizadas.
    Cada entrada tem: tipo, titulo, conteudo, timestamp, tags.
    """

    CATEGORIES = {
        "architecture": "Arquiteturas e decisoes de design",
        "bug": "Bugs recorrentes e solucoes",
        "best_practice": "Boas praticas e padroes",
        "lesson": "Licoes aprendidas",
        "pattern": "Padroes internos e convencoes",
    }

    def __init__(self):
        self._cache: List[Dict[str, Any]] = []
        self._load()

    # ---------------------------------------------------------------
    # PERSISTENCIA
    # ---------------------------------------------------------------

    def _load(self) -> None:
        try:
            if KNOWLEDGE_FILE.exists():
                raw = KNOWLEDGE_FILE.read_text(encoding="utf-8")
                self._cache = json.loads(raw)
                logger.info("[KNOWLEDGE] %d entradas carregadas de %s", len(self._cache), KNOWLEDGE_FILE)
            else:
                self._cache = []
                logger.info("[KNOWLEDGE] Nenhum conhecimento persistido ainda")
        except Exception as e:
            logger.warning("[KNOWLEDGE] Erro ao carregar conhecimento: %s", e)
            self._cache = []

    def _save(self) -> None:
        try:
            KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            KNOWLEDGE_FILE.write_text(
                json.dumps(self._cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("[KNOWLEDGE] Erro ao salvar conhecimento: %s", e)

    # ---------------------------------------------------------------
    # API PUBLICA
    # ---------------------------------------------------------------

    def _is_duplicate(self, title: str, content: str, threshold: float = 0.85) -> bool:
        for e in self._cache:
            if e.get("title") == title.strip() and e.get("content") == content.strip():
                return True
            if e.get("title") == title.strip():
                from difflib import SequenceMatcher
                if SequenceMatcher(None, e.get("content", ""), content.strip()).ratio() > threshold:
                    return True
        return False

    def extract_and_store(self, task: str, source_data: str) -> None:
        """Extrai conhecimento de dados de busca e armazena automaticamente."""
        import re
        snippets = re.findall(r'(?:^|\n)[•\-\*]\s*(.{30,200})', source_data)
        if not snippets:
            snippets = [s.strip() for s in source_data.split("\n") if len(s.strip()) > 50][:5]
        for snippet in snippets[:5]:
            title = snippet[:60].strip()
            self.store("best_practice", title, snippet, tags=["auto_extracted"], source=task)

    def store(
        self,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> None:
        if category not in self.CATEGORIES:
            logger.warning("[KNOWLEDGE] Categoria desconhecida: %s", category)
            return
        if self._is_duplicate(title, content):
            logger.debug("[KNOWLEDGE] Duplicata ignorada: [%s] %s", category, title[:60])
            return
        cleaned_tags = [t for t in (tags or []) if t and t.strip()]
        entry = {
            "id": f"k_{int(time.time() * 1000)}_{len(self._cache)}",
            "category": category,
            "title": title.strip(),
            "content": content.strip(),
            "tags": cleaned_tags,
            "source": source or "",
            "timestamp": time.time(),
            "hits": 0,
        }
        self._cache.append(entry)
        self._save()
        logger.info("[KNOWLEDGE] Armazenado: [%s] %s", category, title[:60])

    def retrieve(
        self,
        query: str = "",
        category: Optional[str] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        results = self._cache

        if category and category in self.CATEGORIES:
            results = [e for e in results if e.get("category") == category]

        if query:
            q = query.lower()
            results = [
                e for e in results
                if q in e.get("title", "").lower()
                or q in e.get("content", "").lower()
                or any(q in t.lower() for t in e.get("tags", []))
            ]

        results.sort(key=lambda e: e.get("hits", 0), reverse=True)
        top = results[:max_results]

        # Incrementa hits para os retornados
        for e in top:
            e["hits"] = e.get("hits", 0) + 1
        self._save()

        return top

    def retrieve_relevant(self, task: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Busca conhecimento relevante para a task atual.
        Varre todas as categorias e retorna as mais relevantes por palavra-chave.
        """
        if not task or not self._cache:
            return []

        task_lower = task.lower()
        # Extrai palavras-chave relevantes (substantivos, tecnologias)
        keywords = set(w for w in task_lower.split() if len(w) > 3)

        scored = []
        for entry in self._cache:
            score = 0
            text = (entry.get("title", "") + " " + entry.get("content", "")).lower()
            for kw in keywords:
                if kw in text:
                    score += 1
            for tag in entry.get("tags", []):
                if tag and tag.lower() in task_lower:
                    score += 2
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:max_results]]

    def get_stats(self) -> Dict[str, Any]:
        stats = {"total": len(self._cache), "by_category": {}}
        for entry in self._cache:
            cat = entry.get("category", "unknown")
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        return stats

    def summarize(self, max_entries: int = 10) -> str:
        """Gera um resumo textual do conhecimento armazenado para contexto de outros agentes."""
        if not self._cache:
            return "Nenhum conhecimento armazenado ainda."

        lines = ["📚 Conhecimento disponível:\n"]
        by_cat = {}
        for e in self._cache:
            by_cat.setdefault(e.get("category", "outro"), []).append(e)

        for cat, entries in by_cat.items():
            label = self.CATEGORIES.get(cat, cat)
            lines.append(f"  [{label}] ({len(entries)} entradas)")
            for e in entries[:max_entries]:
                hits = e.get("hits", 0)
                lines.append(f"    • {e['title'][:70]} (consultado {hits}x)")
        return "\n".join(lines)


# Instância singleton
knowledge = KnowledgeAgent()
