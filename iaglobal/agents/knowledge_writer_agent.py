# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""KnowledgeWriterAgent — Agente que escreve a própria base de conhecimento.

Extrai conhecimento de conversas, gera entries estruturadas
(conceitos, definições, código, FAQs, relações) e persiste
no KnowledgeGraph + memória vetorial.
"""

import re
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime, timezone
from collections import Counter

from iaglobal._paths import CORE_DB, get_db_connection as _norm_path
from iaglobal.agents.agent_base import AgentBase
from iaglobal.memory.fusion_engine import KnowledgeGraph, FakeNoiseDetector
from iaglobal.memory.memory_vector import store as vector_store, search as vector_search
from iaglobal.utils.logger import logger


class KnowledgeWriterAgent(AgentBase):
    """Agente que escreve e mantém a base de conhecimento automaticamente."""

    ENTRY_TYPES = ["concept", "definition", "code_snippet", "faq", "relation", "summary"]

    def __init__(self, db_path: Union[str, Path] = CORE_DB):
        super().__init__(agent_name="knowledgewriter")
        p = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path = _norm_path(p)
        self.kg = KnowledgeGraph(db_path)
        self.noise = FakeNoiseDetector()
        self._init_tables()
        self._session_insights: List[Dict] = []

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'auto',
                    tags TEXT DEFAULT '[]',
                    confidence REAL DEFAULT 0.5,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_type ON kb_entries(entry_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_title ON kb_entries(title)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_faq (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT UNIQUE,
                    answer TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    frequency INTEGER DEFAULT 1,
                    created_at TIMESTAMP,
                    last_asked TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # API PÚBLICA
    # =========================================================================

    def learn_from_conversation(self, prompt: str, response: str, source: str = "dialog") -> Dict:
        """Extrai conhecimento de uma conversa e armazena."""
        import time
        start = time.time()
        prompt_lower = prompt.lower()
        combined = f"{prompt}\n{response}"

        results = {
            "concepts": [],
            "definitions": [],
            "code_snippets": [],
            "faqs": [],
            "relations": [],
        }

        concepts = self.kg.extract_and_store(combined, source)
        results["concepts"] = concepts
        logger.debug(f"[KB-WRITER] Conceitos extraídos: {len(concepts)} ({', '.join(concepts[:3])})")
        # Auto-inicializa vector store se necessário (fix: evita "no such table: memory")
        try:
            from iaglobal.memory.memory_vector import init_db
            init_db()
        except Exception:
            pass


        if self._is_definition_query(prompt_lower):
            defn = self._write_definition(prompt, response, source)
            if defn:
                self._store_entry(defn)
                results["definitions"].append(defn["title"])
                logger.info(f"[KB-WRITER] Definição armazenada: {defn['title'][:50]}")

        code = self._extract_code_snippet(combined)
        if code:
            self._store_entry(code)
            results["code_snippets"].append(code["title"])
            self._code_to_concepts(code, concepts)
            logger.info(f"[KB-WRITER] Código extraído: {code['title'][:50]}")

        if prompt.endswith("?") or prompt_lower.startswith(("what", "how", "why", "qual", "como", "o que")):
            faq = self._write_faq(prompt, response)
            if faq:
                results["faqs"].append(faq["question"])
                logger.info(f"[KB-WRITER] FAQ armazenada: {faq['question'][:50]}")
            else:
                logger.debug(f"[KB-WRITER] FAQ já existia (frequência incrementada)")

        relations = self._extract_relations(combined, concepts)
        for rel in relations:
            self._store_entry(rel)
        results["relations"] = relations
        if relations:
            logger.debug(f"[KB-WRITER] Relações extraídas: {len(relations)}")

        vector_store(text=f"KB:{combined[:500]}", mtype="knowledge")

        insight = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt[:100],
            "extracted": {k: v for k, v in results.items() if v}
        }
        self._session_insights.append(insight)

        elapsed = time.time() - start
        total = sum(len(v) for v in results.values() if isinstance(v, list))
        logger.info(f"[KB-WRITER] Conversa processada: {total} extrações "
                    f"em {elapsed:.2f}s (conceitos={len(concepts)} "
                    f"defs={len(results['definitions'])} faqs={len(results['faqs'])})")
        return results

    def learn_from_text(self, text: str, source: str = "auto", entry_type: str = "concept") -> Dict:
        """Aprende a partir de um texto arbitrário."""
        import time
        start = time.time()
        concepts = self.kg.extract_and_store(text, source)
        entry = {
            "entry_type": entry_type,
            "title": concepts[0] if concepts else self._summarize_title(text),
            "content": text[:2000],
            "source": source,
            "tags": json.dumps(concepts[:5]),
            "confidence": self.noise.score_confidence({"content": text, "source": source}),
        }
        self._store_entry(entry)
        vector_store(text=f"KB:{text[:500]}", mtype="knowledge")
        elapsed = time.time() - start
        logger.info(f"[KB-WRITER] Texto aprendido: type={entry_type} "
                    f"conceitos={len(concepts)} confiança={entry['confidence']:.2f} "
                    f"elapsed={elapsed:.2f}s")
        return {"entry": entry, "concepts": concepts}

    def consolidate_session(self) -> Dict:
        """Consolida aprendizados da sessão atual em um resumo."""
        import time
        start = time.time()
        if not self._session_insights:
            logger.debug("[KB-WRITER] Sessão vazia, nada a consolidar")
            return {"status": "empty", "entries": 0}

        all_concepts = []
        all_faqs = []
        for ins in self._session_insights:
            all_concepts.extend(ins.get("extracted", {}).get("concepts", []))
            all_faqs.extend(ins.get("extracted", {}).get("faqs", []))

        summary = self._generate_session_summary(self._session_insights)
        if summary:
            self._store_entry(summary)

        result = {
            "status": "consolidated",
            "entries": len(self._session_insights),
            "total_concepts": len(set(all_concepts)),
            "total_faqs": len(set(all_faqs)),
            "summary_title": summary["title"] if summary else None,
        }
        self._session_insights = []
        elapsed = time.time() - start
        logger.info(f"[KB-WRITER] Sessão consolidada: {result['entries']} interações, "
                    f"{result['total_concepts']} conceitos, {result['total_faqs']} FAQs "
                    f"elapsed={elapsed:.2f}s")
        return result

    def get_knowledge_base_stats(self) -> Dict:
        """Estatísticas completas da base de conhecimento."""
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM kb_entries").fetchone()[0]
            by_type = conn.execute(
                "SELECT entry_type, COUNT(*) FROM kb_entries GROUP BY entry_type"
            ).fetchall()
            faq_count = conn.execute("SELECT COUNT(*) FROM kb_faq").fetchone()[0]
            top_faqs = conn.execute(
                "SELECT question, frequency FROM kb_faq ORDER BY frequency DESC LIMIT 5"
            ).fetchall()
            return {
                "total_entries": total,
                "by_type": dict(by_type),
                "faq_count": faq_count,
                "top_faqs": [{"q": r[0][:60], "freq": r[1]} for r in top_faqs],
            }
        finally:
            conn.close()

    def search_kb(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca entries na base de conhecimento."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT entry_type, title, content, source, confidence, tags
                   FROM kb_entries
                   WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                   ORDER BY confidence DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit)
            ).fetchall()
            return [
                {"type": r[0], "title": r[1], "content": r[2][:200],
                 "source": r[3], "confidence": r[4], "tags": r[5]}
                for r in rows
            ]
        finally:
            conn.close()

    # =========================================================================
    # ESCRITA DE ENTRIES
    # =========================================================================

    def _write_definition(self, prompt: str, response: str, source: str) -> Optional[Dict]:
        """Cria entry de definição a partir de uma pergunta conceitual."""
        title = self._extract_topic(prompt)
        if not title:
            return None
        content = response[:1000] if len(response) > 1000 else response
        return {
            "entry_type": "definition",
            "title": f"O que é {title}",
            "content": content,
            "source": source,
            "tags": json.dumps([title]),
            "confidence": 0.7,
        }

    def _write_faq(self, question: str, answer: str) -> Optional[Dict]:
        """Cria ou atualiza entry de FAQ."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        try:
            existing = conn.execute(
                "SELECT id, frequency FROM kb_faq WHERE question = ?",
                (question.strip()[:200],)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE kb_faq SET frequency = ?, last_asked = ? WHERE id = ?",
                    (existing[1] + 1, now, existing[0])
                )
                conn.commit()
                return None
            conn.execute(
                "INSERT INTO kb_faq (question, answer, frequency, created_at, last_asked) VALUES (?, ?, 1, ?, ?)",
                (question.strip()[:200], answer[:1000], now, now)
            )
            conn.commit()
            return {"question": question[:80], "answer": answer[:100]}
        finally:
            conn.close()

    def _extract_relations(self, text: str, concepts: List[str]) -> List[Dict]:
        """Extrai relações explícitas entre conceitos."""
        relations = []
        patterns = [
            (r"\b(?:é|e|um|uma)\s+(\w+)\s+(?:de|do|da|para)\s+(\w+)", "type_of"),
            (r"\b(?:usa|utiliza|uses|built with)\s+(\w+)", "uses"),
            (r"\b(?:parte|part of|componente de)\s+(\w+)", "part_of"),
        ]
        for pattern, rel_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    a, b = m[0], m[1]
                else:
                    a, b = m, ""
                if a and b and a != b:
                    relations.append({
                        "entry_type": "relation",
                        "title": f"{a} {rel_type} {b}",
                        "content": f"{a} → ({rel_type}) → {b}",
                        "source": "auto",
                        "tags": json.dumps([a, b]),
                        "confidence": 0.5,
                    })
        return relations

    def _generate_session_summary(self, insights: List[Dict]) -> Optional[Dict]:
        """Gera resumo consolidado da sessão."""
        if not insights:
            return None
        topics = Counter()
        for ins in insights:
            for cat, items in ins.get("extracted", {}).items():
                topics[cat] += len(items)
        content = (
            f"Sessão com {len(insights)} interações. "
            f"Conceitos: {topics.get('concepts', 0)}, "
            f"Definições: {topics.get('definitions', 0)}, "
            f"FAQs: {topics.get('faqs', 0)}, "
            f"Relações: {topics.get('relations', 0)}."
        )
        return {
            "entry_type": "summary",
            "title": f"Session summary {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            "content": content,
            "source": "consolidation",
            "tags": json.dumps(list(topics.keys())),
            "confidence": 0.8,
        }

    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================

    def _store_entry(self, entry: Dict):
        """Persiste entry na kb_entries."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO kb_entries
                   (entry_type, title, content, source, tags, confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry["entry_type"], entry["title"][:200],
                 entry["content"][:2000], entry.get("source", "auto"),
                 entry.get("tags", "[]"), entry.get("confidence", 0.5),
                 now, now)
            )
            conn.commit()
        finally:
            conn.close()

    def _extract_code_snippet(self, text: str) -> Optional[Dict]:
        """Extrai bloco de código do texto."""
        blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.DOTALL)
        if not blocks:
            blocks = re.findall(r"(def \w+.*?:\n(?:    .*\n?)*)", text, re.DOTALL)
        if not blocks:
            return None

        lang, code = blocks[0] if len(blocks[0]) == 2 else ("python", blocks[0])
        title_line = code.strip().split("\n")[0][:60] if code.strip() else "código"
        return {
            "entry_type": "code_snippet",
            "title": f"Code: {title_line}",
            "content": code[:2000],
            "source": "extracted",
            "tags": json.dumps([lang] if lang else ["python"]),
            "confidence": 0.8,
        }

    def _code_to_concepts(self, code_entry: Dict, concepts: List[str]):
        """Associa snippet de código a conceitos no KG."""
        code_text = code_entry.get("content", "")
        for c in concepts:
            if c.lower() in code_text.lower():
                self.kg.extract_and_store(
                    f"{c} implements: {code_text[:200]}", source="code"
                )

    def _is_definition_query(self, text: str) -> bool:
        return bool(re.search(
            r"\b(o que é|what is|explique|define|conceito|definição|meaning)\b",
            text
        ))

    def _extract_topic(self, prompt: str) -> Optional[str]:
        """Extrai o tópico principal de uma pergunta."""
        patterns = [
            r"(?:o que é|what is|explique|define|conceito de|sobre)\s+([A-Za-zÀ-ü][A-Za-zÀ-ü\s]{2,40}?)(?:\?|$|,|\.)",
            r"(?:o que é|what is)\s+([A-Za-zÀ-ü]+)",
        ]
        for p in patterns:
            m = re.search(p, prompt, re.IGNORECASE)
            if m:
                return m.group(1).strip().split("?")[0].strip()
        return None

    def _summarize_title(self, text: str) -> str:
        words = re.findall(r"\b[A-Z][a-z]+\b", text)
        if words:
            return " ".join(words[:5])
        words = text.split()[:8]
        return " ".join(words)
