"""FusionEngine — Web + Memory Fusion Engine real.

Cache de web inteligente + anti-redundância global +
detecção de fake/ruído + knowledge graph automático +
atualização incremental de conceitos.
"""

import re
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Union
from datetime import datetime, timezone
from collections import defaultdict, Counter
from difflib import SequenceMatcher

from iaglobal._paths import CORE_DB, get_db_connection
from iaglobal.memory.memory_vector import search as vector_search
from iaglobal.utils.logger import logger


# =========================================================================
# 1. CACHE DE WEB INTELIGENTE (TTL adaptativo)
# =========================================================================

class WebCacheInteligente:
    """Cache com TTL adaptativo baseado em freshness do conteúdo."""

    def __init__(self, db_path: Union[str, Path] = CORE_DB, default_ttl: int = 3600):
        self.db_path = get_db_connection(Path(db_path))
        self.default_ttl = default_ttl
        self._ram: Dict[str, Dict] = {}
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS web_cache (
                    cache_key TEXT PRIMARY KEY,
                    url TEXT,
                    content TEXT,
                    source TEXT,
                    fetched_at TIMESTAMP,
                    ttl_seconds INTEGER,
                    access_count INTEGER DEFAULT 1,
                    last_access TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get(self, cache_key: str) -> Optional[Dict]:
        """Retorna cache se ainda válido (TTL adaptativo)."""
        now = datetime.now(timezone.utc)

        ram = self._ram.get(cache_key)
        if ram:
            age = (now - ram["ts"]).total_seconds()
            if age < ram["ttl"]:
                return ram["data"]

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT content, source, fetched_at, ttl_seconds, access_count FROM web_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            if row:
                content, source, fetched_str, ttl, acc = row
                fetched = datetime.fromisoformat(fetched_str)
                age = (now - fetched).total_seconds()
                if age < ttl:
                    conn.execute(
                        "UPDATE web_cache SET access_count = ?, last_access = ? WHERE cache_key = ?",
                        (acc + 1, now.isoformat(), cache_key)
                    )
                    conn.commit()
                    data = {"content": content, "source": source}
                    self._ram[cache_key] = {"data": data, "ts": now, "ttl": ttl}
                    return data
                conn.execute("DELETE FROM web_cache WHERE cache_key = ?", (cache_key,))
                conn.commit()
        finally:
            conn.close()
        return None

    def set(self, cache_key: str, url: str, content: str, source: str, ttl: Optional[int] = None):
        """Armazena com TTL adaptativo baseado em conteúdo."""
        ttl = ttl or self._adaptive_ttl(content, source)
        now = datetime.now(timezone.utc)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO web_cache
                (cache_key, url, content, source, fetched_at, ttl_seconds, last_access)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cache_key, url, content, source, now.isoformat(), ttl, now.isoformat()))
            conn.commit()
        finally:
            conn.close()
        self._ram[cache_key] = {"data": {"content": content, "source": source}, "ts": now, "ttl": ttl}

    def _adaptive_ttl(self, content: str, source: str) -> int:
        """Calcula TTL baseado em fonte e tamanho do conteúdo."""
        base = self.default_ttl
        if source == "wikipedia":
            base *= 24  # 24h
        elif source == "rss":
            base //= 2  # 30min
        if len(content) > 500:
            base = int(base * 1.5)
        if len(content) < 50:
            base //= 2
        return max(60, min(base, 86400))

    def stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), SUM(access_count) FROM web_cache"
            ).fetchone()
            return {"entries": row[0] or 0, "total_access": row[1] or 0}
        finally:
            conn.close()

    def clear_expired(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM web_cache WHERE datetime(fetched_at, '+' || ttl_seconds || ' seconds') < datetime('now')"
            )
            conn.commit()
        finally:
            conn.close()


# =========================================================================
# 2. ANTI-REDUNDÂNCIA GLOBAL (dedup + merge)
# =========================================================================

class AntiRedundanciaGlobal:
    """Deduplicação global usando embeddings + texto + difflib."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self._seen_hashes: Set[str] = set()

    def is_duplicate(self, content: str, existing_items: List[Dict]) -> Tuple[bool, Optional[Dict]]:
        """Verifica se conteúdo já existe (hash exato + similaridade)."""
        h = self._content_hash(content)
        if h in self._seen_hashes:
            return True, None

        for item in existing_items:
            item_content = item.get("content") or item.get("text") or ""
            if not item_content:
                continue
            sim = SequenceMatcher(None, content.lower(), item_content.lower()).ratio()
            if sim > self.threshold:
                return True, item
        self._seen_hashes.add(h)
        return False, None

    def dedup_list(self, items: List[Dict]) -> List[Dict]:
        """Remove duplicatas de uma lista de itens."""
        seen_hashes: Set[str] = set()
        unique = []
        for item in items:
            content = item.get("content") or item.get("text") or ""
            h = self._content_hash(content)
            if h not in seen_hashes:
                is_dup, _ = self.is_duplicate(content, unique)
                if not is_dup:
                    seen_hashes.add(h)
                    unique.append(item)
        return unique

    def merge_similar(self, items: List[Dict], merge_threshold: float = 0.7) -> List[Dict]:
        """Merge itens similares em um único consolidado."""
        if len(items) < 2:
            return items
        merged = []
        used = set()
        for i, a in enumerate(items):
            if i in used:
                continue
            cluster = [a]
            used.add(i)
            a_content = (a.get("content") or a.get("text") or "").lower()
            for j, b in enumerate(items):
                if j in used or i == j:
                    continue
                b_content = (b.get("content") or b.get("text") or "").lower()
                if a_content and b_content:
                    sim = SequenceMatcher(None, a_content, b_content).ratio()
                    if sim > merge_threshold:
                        cluster.append(b)
                        used.add(j)
            if len(cluster) > 1:
                merged.append(self._merge_cluster(cluster))
            else:
                merged.append(a)
        return merged

    def _merge_cluster(self, cluster: List[Dict]) -> Dict:
        """Merge itens de um cluster em um único consolidado."""
        contents = []
        sources = set()
        titles = []
        for item in cluster:
            c = item.get("content") or item.get("text") or ""
            if c:
                contents.append(c)
            src = item.get("source", "?")
            sources.add(src)
            t = item.get("title", "")
            if t:
                titles.append(t)

        combined = "\n\n".join(contents)
        return {
            "content": combined[:1000],
            "title": titles[0] if titles else "(merged)",
            "source": "+".join(sorted(sources)),
            "merged_from": len(cluster),
        }

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def clear(self):
        self._seen_hashes.clear()


# =========================================================================
# 3. DETECTOR DE FAKE / RUÍDO (qualidade + confiança)
# =========================================================================

class FakeNoiseDetector:
    """Detecta informações de baixa qualidade, ruído e contradições."""

    SOURCE_AUTHORITY = {
        "wikipedia": 0.9,
        "duckduckgo": 0.6,
        "rss": 0.5,
        "web": 0.5,
        "consolidated": 0.7,
        "internal": 0.4,
        "memory": 0.3,
    }

    CLICKBAIT_PATTERNS = [
        r"você não vai acreditar",
        r"isso vai mudar tudo",
        r"inacreditável",
        r"chocante",
        r"revealed",
        r"you won't believe",
        r"mind blowing",
        r"game changer",
    ]

    def __init__(self):
        self._contradiction_cache: List[Dict] = []

    def score_confidence(self, item: Dict) -> float:
        """Score de confiança 0-1 para um item de conhecimento."""
        scores = []

        # Authoridade da fonte
        source = item.get("source", "web")
        scores.append(self.SOURCE_AUTHORITY.get(source, 0.4) * 0.3)

        # Tamanho do conteúdo
        content = item.get("content") or item.get("text") or ""
        if len(content) > 500:
            scores.append(0.3)
        elif len(content) > 100:
            scores.append(0.2)
        else:
            scores.append(0.05)

        # Detecção de clickbait
        if not self._is_clickbait(content):
            scores.append(0.2)

        # Presença de dados estruturados
        if re.search(r"\d{4}", content):
            scores.append(0.1)
        if re.search(r"\b(segundo|according|fonte|source)\b", content.lower()):
            scores.append(0.1)

        return min(1.0, sum(scores))

    def is_noise(self, item: Dict) -> bool:
        """Retorna True se o item é ruído (muito curto, vazio, sem sentido)."""
        content = item.get("content") or item.get("text") or ""
        if not content or len(content.strip()) < 20:
            return True
        if len(content.split()) < 5:
            return True
        # Apenas caracteres especiais
        if re.match(r"^[^a-zA-Z0-9]{10,}$", content):
            return True
        return False

    def detect_contradiction(self, new_item: Dict, existing_items: List[Dict]) -> Optional[Dict]:
        """Detecta contradições entre novo item e conhecimento existente."""
        new_text = (new_item.get("content") or new_item.get("text") or "").lower()
        if not new_text or len(new_text) < 30:
            return None

        for existing in existing_items:
            existing_text = (existing.get("content") or existing.get("text") or "").lower()
            if not existing_text or len(existing_text) < 30:
                continue

            new_keywords = set(re.findall(r"\b[a-z]{4,}\b", new_text))
            existing_keywords = set(re.findall(r"\b[a-z]{4,}\b", existing_text))
            overlap = len(new_keywords & existing_keywords)
            total = len(new_keywords | existing_keywords)
            if total == 0:
                continue
            jaccard = overlap / total

            if 0.2 < jaccard < 0.7:
                negation_new = bool(re.search(r"\b(não|not|never|nunca)\b", new_text))
                negation_existing = bool(re.search(r"\b(não|not|never|nunca)\b", existing_text))
                if negation_new != negation_existing:
                    return {
                        "new_item": new_item,
                        "existing_item": existing,
                        "jaccard": round(jaccard, 3),
                        "confidence": round(self.score_confidence(new_item), 2),
                    }
        return None

    def filter_noise(self, items: List[Dict]) -> List[Dict]:
        """Remove itens ruidosos de uma lista."""
        return [item for item in items if not self.is_noise(item)]

    def _is_clickbait(self, text: str) -> bool:
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in self.CLICKBAIT_PATTERNS)


# =========================================================================
# 4. KNOWLEDGE GRAPH AUTOMÁTICO
# =========================================================================

class KnowledgeGraph:
    """Grafo de conhecimento automático: extrai conceitos e relações."""

    def __init__(self, db_path: Union[str, Path] = CORE_DB):
        self.db_path = get_db_connection(Path(db_path))
        self._init_tables()

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    label TEXT,
                    frequency INTEGER DEFAULT 1,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    source TEXT DEFAULT 'unknown'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_concept TEXT,
                    target_concept TEXT,
                    relation TEXT DEFAULT 'related_to',
                    weight REAL DEFAULT 1.0,
                    UNIQUE(source_concept, target_concept),
                    FOREIGN KEY (source_concept) REFERENCES kg_concepts(name),
                    FOREIGN KEY (target_concept) REFERENCES kg_concepts(name)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_concept)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_concept)
            """)
            conn.commit()
        finally:
            conn.close()

    def extract_and_store(self, text: str, source: str = "auto") -> List[str]:
        """Extrai conceitos do texto e armazena no grafo."""
        concepts = self._extract_concepts(text)
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            for concept in concepts:
                conn.execute("""
                    INSERT INTO kg_concepts (name, label, frequency, first_seen, last_seen, source)
                    VALUES (?, ?, 1, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        frequency = frequency + 1,
                        last_seen = ?,
                        source = CASE WHEN ? != 'unknown' THEN ? ELSE source END
                """, (concept, concept, now, now, source, now, source, source))

            self._build_relationships(concepts, conn)
            conn.commit()
        finally:
            conn.close()
        return concepts

    def get_related(self, concept: str, max_results: int = 10) -> List[Dict]:
        """Retorna conceitos relacionados a um dado conceito."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT DISTINCT
                    CASE WHEN source_concept = ? THEN target_concept ELSE source_concept END,
                    relation, weight
                FROM kg_relationships
                WHERE source_concept = ? OR target_concept = ?
                ORDER BY weight DESC
                LIMIT ?
            """, (concept, concept, concept, max_results)).fetchall()
            return [
                {"concept": row[0], "relation": row[1], "weight": row[2]}
                for row in rows
            ]
        finally:
            conn.close()

    def get_top_concepts(self, limit: int = 50) -> List[Dict]:
        """Retorna conceitos mais frequentes."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT name, frequency, source FROM kg_concepts ORDER BY frequency DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [
                {"name": row[0], "frequency": row[1], "source": row[2]}
                for row in rows
            ]
        finally:
            conn.close()

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca conceitos por nome."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT name, frequency, source, last_seen FROM kg_concepts WHERE name LIKE ? ORDER BY frequency DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
            return [
                {"name": row[0], "frequency": row[1], "source": row[2], "last_seen": row[3]}
                for row in rows
            ]
        finally:
            conn.close()

    def _extract_concepts(self, text: str) -> List[str]:
        """Extrai conceitos (entidades nomeadas) de um texto."""
        concepts = set()

        patterns = [
            r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b",
            r"\b(?:Python|JavaScript|TypeScript|React|Django|Flask|SQL|NoSQL|Docker|Kubernetes|AWS|GCP|Azure|Linux|Windows|MacOS|GPT|BERT|Transformer|Ollama|DuckDuckGo|Wikipedia)\b",
        ]
        for p in patterns:
            for match in re.finditer(p, text):
                word = match.group().strip()
                if 3 < len(word) < 60 and not word.isupper():
                    concepts.add(word)

        return list(concepts)

    def _build_relationships(self, concepts: List[str], conn: sqlite3.Connection):
        """Cria relações entre conceitos que co-ocorrem."""
        if len(concepts) < 2:
            return
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                a, b = concepts[i], concepts[j]
                if a == b:
                    continue
                a, b = sorted([a, b])
                conn.execute("""
                    INSERT INTO kg_relationships (source_concept, target_concept, relation, weight)
                    VALUES (?, ?, 'related_to', 0.5)
                    ON CONFLICT(source_concept, target_concept) DO UPDATE SET
                        weight = MIN(1.0, weight + 0.1)
                """, (a, b))

    def stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        try:
            concepts = conn.execute("SELECT COUNT(*) FROM kg_concepts").fetchone()[0]
            relationships = conn.execute("SELECT COUNT(*) FROM kg_relationships").fetchone()[0]
            sources = conn.execute(
                "SELECT source, COUNT(*) FROM kg_concepts GROUP BY source ORDER BY COUNT(*) DESC"
            ).fetchall()
            return {
                "concepts": concepts,
                "relationships": relationships,
                "top_sources": [(s, c) for s, c in sources[:5]],
            }
        finally:
            conn.close()


# =========================================================================
# 5. ATUALIZAÇÃO INCREMENTAL DE CONCEITOS
# =========================================================================

class AtualizacaoIncremental:
    """Atualiza conhecimento incrementalmente — detecta novidades e mergeia."""

    def __init__(self, kg: KnowledgeGraph, dedup: AntiRedundanciaGlobal):
        self.kg = kg
        self.dedup = dedup

    def incorporate(self, new_content: str, source: str = "web",
                    existing_knowledge: Optional[List[Dict]] = None) -> Dict:
        """Incorporação incremental: dedup + noise check + KG + merge."""
        result = {
            "is_new": True,
            "is_noise": False,
            "contradiction": None,
            "concepts_extracted": [],
            "dedup_merged": False,
        }

        noise = FakeNoiseDetector()
        if noise.is_noise({"content": new_content}):
            result["is_noise"] = True
            result["is_new"] = False
            return result

        if existing_knowledge:
            is_dup, match = self.dedup.is_duplicate(new_content, existing_knowledge)
            if is_dup:
                result["is_new"] = False
                result["dedup_merged"] = True
                return result

        contradiction = noise.detect_contradiction(
            {"content": new_content, "source": source},
            existing_knowledge or []
        )
        if contradiction:
            result["contradiction"] = contradiction

        concepts = self.kg.extract_and_store(new_content, source)
        result["concepts_extracted"] = concepts

        return result

    def batch_incorporate(self, items: List[Dict]) -> List[Dict]:
        """Processa lote de itens incrementalmente."""
        results = []
        for item in items:
            content = item.get("content") or item.get("text") or ""
            source = item.get("source", "web")
            existing = [{"content": r.get("content", "")} for r in results]
            r = self.incorporate(content, source, existing)
            r["item"] = item
            results.append(r)
        return results


# =========================================================================
# 6. FUSION ENGINE (ORQUESTRADOR PRINCIPAL)
# =========================================================================

class FusionEngine:
    """Orquestrador do Web + Memory Fusion Engine.

    Integra: cache inteligente, anti-redundância, detecção de fake/ruído,
    knowledge graph, e atualização incremental.
    """

    def __init__(self, db_path: Union[str, Path] = CORE_DB):
        self.db_path = get_db_connection(Path(db_path))
        self.cache = WebCacheInteligente(self.db_path)
        self.dedup = AntiRedundanciaGlobal()
        self.noise = FakeNoiseDetector()
        self.kg = KnowledgeGraph(self.db_path)
        self.incremental = AtualizacaoIncremental(self.kg, self.dedup)

    def process_web_result(self, content: str, url: str, source: str) -> Dict:
        """Processa um resultado web completo: cache + dedup + KG + noise check."""
        cache_key = hashlib.md5(content.encode()).hexdigest()

        cached = self.cache.get(cache_key)
        if cached:
            return {"cached": True, "content": cached["content"], "status": "cached"}

        if self.noise.is_noise({"content": content, "source": source}):
            return {"cached": False, "content": content, "status": "noise"}

        concepts = self.kg.extract_and_store(content, source)

        self.cache.set(cache_key, url, content, source)

        confidence = self.noise.score_confidence({"content": content, "source": source})

        return {
            "cached": False,
            "content": content,
            "status": "stored",
            "concepts": concepts,
            "confidence": confidence,
            "source": source,
        }

    def process_knowledge_batch(self, items: List[Dict]) -> Dict:
        """Processa lote de conhecimento de uma vez."""
        filtered = self.noise.filter_noise(items)
        deduped = self.dedup.dedup_list(filtered)
        merged = self.dedup.merge_similar(deduped)
        incorporation = self.incremental.batch_incorporate(merged)

        stats = {
            "total_input": len(items),
            "noise_removed": len(items) - len(filtered),
            "duplicates_removed": len(filtered) - len(deduped),
            "merged": len(deduped) - len(merged),
            "new_concepts": sum(1 for r in incorporation if r["is_new"]),
            "contradictions": sum(1 for r in incorporation if r["contradiction"]),
        }
        return {
            "items": merged,
            "incorporation": incorporation,
            "stats": stats,
        }

    def get_knowledge_context(self, query: str) -> str:
        """Monta contexto enriquecido com KG + memória vetorial."""
        parts = []

        kg_results = self.kg.search(query, limit=5)
        if kg_results:
            parts.append("[KNOWLEDGE GRAPH]")
            for r in kg_results:
                related = self.kg.get_related(r["name"], 3)
                rel_str = ", ".join(rel["concept"] for rel in related) if related else "(sem relações)"
                parts.append(f"  • {r['name']} (freq={r['frequency']}) → {rel_str}")

        vec = vector_search(query, top_k=3)
        if vec:
            parts.append("\n[MEMÓRIA VETORIAL]")
            for score, data in vec:
                text = data.get("text", "") if isinstance(data, dict) else str(data)
                parts.append(f"  • {text[:120]}" if len(text) > 120 else f"  • {text}")

        return "\n".join(parts) if parts else "(sem contexto)"

    def stats(self) -> Dict:
        return {
            "cache": self.cache.stats(),
            "knowledge_graph": self.kg.stats(),
        }
