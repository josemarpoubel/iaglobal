# memory/memory_vector.py (Memory vector module for semantic search and embeddings.)

import os
import sqlite3
import logging
import struct
import iaglobal._paths as _paths

from typing import List, Tuple, Dict, Any, Optional
from iaglobal.utils.logger import logger

# 1. Configuração de Silenciamento de Logs
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# 2. Garantia de estrutura de pastas
os.makedirs(_paths.DATA_DIR, exist_ok=True)

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
            # Cria a tabela de memória vetorial
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    content TEXT,
                    embedding BLOB,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Índice para acelerar consultas por tipo de memória
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)")

        logger.info("✅ Banco de vetores inicializado em: %s", _paths.CORE_DB)
    except sqlite3.Error as e:
        logger.error(f"💥 Erro ao inicializar banco de vetores: {e}")
        raise
    finally:
        if "conn" in locals():
            conn.close()


def store(text: str, mtype: str = "fact") -> None:
    """Store text with embedding and sync to CBOR binary for the LLM pipeline."""
    if not text or not text.strip():
        return

    # Embedding fora do lock do banco
    emb = list(_get_model().embed(text))[0]
    vec = struct.pack(f"{len(emb)}f", *emb)

    conn = get_vector_db()
    try:
        conn.execute(
            "INSERT INTO memory (type, content, embedding) VALUES (?, ?, ?)",
            (mtype, text.strip(), vec),
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Tabela memory pode não existir se init_db() não foi chamado ainda
        conn.close()
        init_db()
        conn = get_vector_db()
        conn.execute(
            "INSERT INTO memory (type, content, embedding) VALUES (?, ?, ?)",
            (mtype, text.strip(), vec),
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


def search(query: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
    """Perform vector similarity search using dot product (K-NN)."""
    if not query or not query.strip():
        return []

    qvec = list(_get_model().embed(query))[0]

    conn = get_vector_db()
    try:
        rows = conn.execute(
            "SELECT content, embedding, type, timestamp FROM memory"
        ).fetchall()
    except sqlite3.OperationalError:
        init_db()
        return []
    finally:
        conn.close()

    results = []

    for content, emb_blob, mtype, timestamp in rows:
        if not emb_blob:
            continue

        v = list(struct.unpack(f"{len(emb_blob) // 4}f", emb_blob))

        # segurança de shape
        if len(v) != len(qvec):
            continue

        score = sum(a * b for a, b in zip(qvec, v))

        results.append(
            (score, {"text": content, "type": mtype, "timestamp": timestamp})
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
        self, text: str, mtype: str = "fact", metadata: Optional[Dict] = None
    ) -> None:
        store(text, mtype)
        self.embeddings.append(list(self.model.embed(text))[0])
        self.metadata.append({"type": mtype, "metadata": metadata or {}})

    def query(self, query: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        return search(query, top_k)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        return self.query(query, top_k)

    def clear(self) -> None:
        self.embeddings = []
        self.metadata = []
        conn = sqlite3.connect(_paths.CORE_DB, timeout=30.0)
        try:
            conn.execute("DELETE FROM memory")
            conn.commit()
        finally:
            conn.close()
