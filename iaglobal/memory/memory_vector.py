# memory/memory_vector.py (Memory vector module for semantic search and embeddings.)

import os
import sqlite3
import logging
import struct
import iaglobal._paths as _paths

from typing import List, Tuple, Dict, Any, Optional, Union
from iaglobal.utils.logger import logger
from iaglobal.core.artifact import ArtifactKind

# 1. Configuração de Silenciamento de Logs
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# 2. Garantia de estrutura de pastas
os.makedirs(_paths.DATA_DIR, exist_ok=True)

# 3. Mapeamento de tipos legados para ArtifactKind
_MTYPE_TO_KIND = {
    "code": ArtifactKind.CODE,
    "python": ArtifactKind.CODE,
    "javascript": ArtifactKind.CODE,
    "html": ArtifactKind.HTML,
    "json": ArtifactKind.JSON,
    "fact": ArtifactKind.TEXT,
    "knowledge": ArtifactKind.DOCUMENTATION,
    "search": ArtifactKind.SEARCH_RESULT,
    "documentation": ArtifactKind.DOCUMENTATION,
    "markdown": ArtifactKind.MARKDOWN,
    "plan": ArtifactKind.PLAN,
}

# 3. Inicialização do Modelo (Lazy) — fastembed carregado sob demanda
_model_instance = None


def _get_model():
    global _model_instance
    if _model_instance is None:
        from fastembed import TextEmbedding

        _model_instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model_instance


def get_vector_db() -> sqlite3.Connection:
    """Retorna uma conexão otimizada com o core.db usando modo WAL."""
    conn = sqlite3.connect(_paths.CORE_DB, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;")  # ~64MB cache em RAM
    except sqlite3.OperationalError:
        pass
    return conn


def init_db() -> None:
    """Initialize vector memory table and optimize database settings."""
    try:
        # Abre conexão usando o caminho centralizado do _paths
        conn = sqlite3.connect(_paths.CORE_DB, timeout=30.0)

        # Otimiza para escrita concorrente (Write-Ahead Logging)
        conn.execute("PRAGMA journal_mode=WAL;")

        with conn:
            # Adiciona coluna 'kind' se não existir (para compatibilidade retroativa)
            try:
                conn.execute("ALTER TABLE memory ADD COLUMN kind TEXT DEFAULT 'TEXT'")
            except sqlite3.OperationalError:
                pass  # Coluna já existe

            # Cria a tabela de memória vetorial (com kind)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    kind TEXT DEFAULT 'TEXT',
                    content TEXT,
                    embedding BLOB,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Índices para acelerar consultas
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory(kind)")
            # Índice composto para busca por tipo E kind
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_type_kind ON memory(type, kind)"
            )

        logger.info("✅ Banco de vetores inicializado em: %s", _paths.CORE_DB)
    except sqlite3.Error as e:
        logger.error(f"💥 Erro ao inicializar banco de vetores: {e}")
        raise
    finally:
        if "conn" in locals():
            conn.close()


def store(
    text: str,
    mtype: str = "fact",
    kind: Optional[Union[ArtifactKind, str]] = None,
) -> None:
    """Store text with embedding and sync to CBOR binary for the LLM pipeline.

    Args:
        text: Texto a ser armazenado
        mtype: Tipo legado (ex: "fact", "code", "knowledge") — mantido para compat
        kind: ArtifactKind ou string do kind (ex: ArtifactKind.CODE, "CODE")
    """
    if not text or not text.strip():
        return

    # Inferir kind de mtype se não fornecido
    if kind is None:
        kind_str = _MTYPE_TO_KIND.get(mtype.lower(), "TEXT")
        if isinstance(kind_str, ArtifactKind):
            kind = kind_str
        else:
            kind = kind_str

    # Normalizar kind para string (para armazenamento no SQLite)
    if isinstance(kind, ArtifactKind):
        kind_value = kind.value
    else:
        kind_value = str(kind).upper()

    # Embedding fora do lock do banco
    emb = list(_get_model().embed(text))[0]
    vec = struct.pack(f"{len(emb)}f", *emb)

    conn = get_vector_db()
    try:
        conn.execute(
            "INSERT INTO memory (type, kind, content, embedding) VALUES (?, ?, ?, ?)",
            (mtype, kind_value, text.strip(), vec),
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Tabela memory pode não existir se init_db() não foi chamado ainda
        conn.close()
        init_db()
        conn = get_vector_db()
        conn.execute(
            "INSERT INTO memory (type, kind, content, embedding) VALUES (?, ?, ?, ?)",
            (mtype, kind_value, text.strip(), vec),
        )
        conn.commit()
    finally:
        conn.close()

    # Sync CBOR (fallback seguro)
    try:
        from iaglobal.storage.converter import DataBridge

        DataBridge.sincronizar_sqlite_para_cbor(
            os.path.basename(_paths.CORE_DB),
            "memory",
            os.path.basename(_paths.EMBEDDINGS_DB),
        )
    except Exception as e:
        # fallback simples sem logger obrigatório
        logger.error("[-] Erro na ponte CBOR2 no módulo vector: %s", e)


def search(
    query: str,
    top_k: int = 5,
    kinds: Optional[List[Union[ArtifactKind, str]]] = None,
) -> List[Tuple[float, Dict[str, Any]]]:
    """Perform vector similarity search using dot product (K-NN).

    Args:
        query: Texto da consulta
        top_k: Número de resultados
        kinds: Lista de ArtifactKind ou strings para filtrar (ex: [ArtifactKind.CODE, "HTML"])
              Se None, busca em todos os kinds (compatibilidade retroativa)
    """
    if not query or not query.strip():
        return []

    qvec = list(_get_model().embed(query))[0]

    # Normalizar kinds para strings
    kind_values = None
    if kinds:
        kind_values = []
        for k in kinds:
            if isinstance(k, ArtifactKind):
                kind_values.append(k.value)
            else:
                kind_values.append(str(k).upper())

    conn = get_vector_db()
    try:
        if kind_values:
            # Busca apenas nos kinds especificados
            placeholders = ", ".join("?" * len(kind_values))
            rows = conn.execute(
                f"SELECT content, embedding, type, kind, timestamp FROM memory "
                f"WHERE kind IN ({placeholders})",
                kind_values,
            ).fetchall()
        else:
            # Busca em todos (compatibilidade retroativa)
            rows = conn.execute(
                "SELECT content, embedding, type, kind, timestamp FROM memory"
            ).fetchall()
    except sqlite3.OperationalError:
        init_db()
        return []
    finally:
        conn.close()

    results = []

    for row in rows:
        content, emb_blob, mtype, kind, timestamp = row
        if not emb_blob:
            continue

        v = list(struct.unpack(f"{len(emb_blob) // 4}f", emb_blob))

        # segurança de shape
        if len(v) != len(qvec):
            continue

        score = sum(a * b for a, b in zip(qvec, v))

        results.append(
            (
                score,
                {"text": content, "type": mtype, "kind": kind, "timestamp": timestamp},
            )
        )

    return sorted(results, key=lambda x: x[0], reverse=True)[:top_k]


class MemoryVector:
    """Class for managing vector-based memory operations."""

    def __init__(self, db_path=None, model_name: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path or _paths.CORE_DB
        self.model = _get_model()
        self.embeddings = []
        self.metadata = []
        self._ensure_db_initialized()
        logger.info(f"🧠 MemoryVector inicializado com banco: {self.db_path}")

    def _ensure_db_initialized(self):
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    content TEXT,
                    embedding BLOB,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def add(
        self,
        text: str,
        mtype: str = "fact",
        kind: Optional[Union[ArtifactKind, str]] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        store(text, mtype, kind)
        self.embeddings.append(list(self.model.embed(text))[0])
        self.metadata.append(
            {
                "type": mtype,
                "kind": str(kind) if kind else None,
                "metadata": metadata or {},
            }
        )

    def query(self, query: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        return search(query, top_k)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        return self.query(query, top_k)

    def search_by_kind(
        self,
        query: str,
        kinds: List[Union[ArtifactKind, str]],
        top_k: int = 5,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Busca vetorial restrita a kinds específicos (ex: [ArtifactKind.CODE])."""
        return search(query, top_k, kinds)

    def search_code(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Busca apenas por código executável."""
        return self.search_by_kind(query, [ArtifactKind.CODE, ArtifactKind.HTML], top_k)

    def search_documentation(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Busca apenas por documentação."""
        return self.search_by_kind(
            query,
            [ArtifactKind.DOCUMENTATION, ArtifactKind.MARKDOWN, ArtifactKind.TEXT],
            top_k,
        )

    def search_knowledge(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Busca por conhecimento (documentação + resultados de busca)."""
        return self.search_by_kind(
            query,
            [
                ArtifactKind.DOCUMENTATION,
                ArtifactKind.MARKDOWN,
                ArtifactKind.SEARCH_RESULT,
                ArtifactKind.TEXT,
            ],
            top_k,
        )

    def clear(self) -> None:
        self.embeddings = []
        self.metadata = []
        conn = sqlite3.connect(_paths.CORE_DB, timeout=30.0)
        try:
            conn.execute("DELETE FROM memory")
            conn.commit()
        finally:
            conn.close()
