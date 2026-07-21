# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Awareness Cache Schema v3.1

Schema SQLite estendido para:
- Consciência causal (causal_chains)
- Atenção seletiva (idx por domínio)
- Memória episódica (executions)
- Temporal versioning (activity_events)
- Epistemologia operacional (confidence_history)
- Schema versioning (schema_version)
"""

from __future__ import annotations

import cbor2
import sqlite3


SCHEMA_SQL = """
-- ============================================================
-- TABELA BASE: activities (v1/v2 - inalterada)
-- ============================================================
CREATE TABLE IF NOT EXISTS activities (

    execution_id TEXT NOT NULL,

    node_id TEXT NOT NULL,

    status TEXT NOT NULL,

    summary TEXT,

    metadata BLOB,

    updated_at REAL,

    PRIMARY KEY(
        execution_id,
        node_id
    )
);

CREATE INDEX IF NOT EXISTS idx_activities_execution
ON activities(execution_id);

CREATE INDEX IF NOT EXISTS idx_activities_status
ON activities(status);


-- ============================================================
-- MEMÓRIA EPISÓDICA (v2 - inalterada)
-- ============================================================
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL,
    final_status TEXT,
    ivm_score REAL,
    lessons_learned BLOB
);

CREATE TABLE IF NOT EXISTS causal_chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    blocked_node TEXT NOT NULL,
    blocking_chain TEXT NOT NULL,  -- JSON array
    root_cause TEXT,
    depth INTEGER NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_causal_execution
ON causal_chains(execution_id);


-- ============================================================
-- v3.1 TEMPORAL VERSIONING: activity_events
-- Fatos operacionais com confidence snapshot
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    execution_id TEXT NOT NULL,

    node_id TEXT NOT NULL,

    event_type TEXT NOT NULL,           -- 'status_change', 'publish', 'snapshot'

    old_status TEXT,

    new_status TEXT,

    confidence REAL NOT NULL DEFAULT 0.5
        CHECK(confidence >= 0.0 AND confidence <= 1.0),

    confidence_trace BLOB,               -- CBOR2: ConfidenceTrace completo

    metadata BLOB,                       -- CBOR2: detalhes do evento

    created_at REAL NOT NULL,

    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_events_execution_node
ON activity_events(execution_id, node_id);

CREATE INDEX IF NOT EXISTS idx_activity_events_created_at
ON activity_events(created_at);


-- ============================================================
-- v3.1 EPISTEMOLOGIA OPERACIONAL: confidence_history
-- Evolução epistemológica (separada de fatos operacionais)
-- ============================================================
CREATE TABLE IF NOT EXISTS confidence_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    execution_id TEXT NOT NULL,

    node_id TEXT NOT NULL,

    artifact_id TEXT,

    domain TEXT,

    confidence REAL NOT NULL
        CHECK(confidence >= 0.0 AND confidence <= 1.0),

    reason BLOB,                         -- CBOR2: ConfidenceTrace completo

    contributors BLOB,                   -- CBOR2/JSON: lista de agentes

    created_at REAL NOT NULL,

    FOREIGN KEY (execution_id) REFERENCES executions(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_confidence_history_execution_node
ON confidence_history(execution_id, node_id);

CREATE INDEX IF NOT EXISTS idx_confidence_history_domain
ON confidence_history(domain);

CREATE INDEX IF NOT EXISTS idx_confidence_history_artifact
ON confidence_history(artifact_id);

CREATE INDEX IF NOT EXISTS idx_confidence_history_created_at
ON confidence_history(created_at);


-- ============================================================
-- SCHEMA VERSIONING: migrations idempotentes
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at REAL NOT NULL
);

-- Inicializa versão se não existe
INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (3, strftime('%s', 'now'));
"""

CURRENT_SCHEMA_VERSION = 3


def init_schema(db: sqlite3.Connection) -> None:
    """Inicializa schema completo no banco de dados."""
    db.executescript(SCHEMA_SQL)


def migrate_schema(db: sqlite3.Connection) -> None:
    """
    Aplica migrations pendentes até CURRENT_SCHEMA_VERSION.
    Idempotente: seguro executar múltiplas vezes.
    """
    # Garante tabela de versão
    db.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at REAL NOT NULL
        )
    """)

    # Lê versão atual
    cursor = db.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    current_version = cursor.fetchone()[0]

    if current_version >= CURRENT_SCHEMA_VERSION:
        return  # Já está atualizado

    # Aplica schema completo (CREATE IF NOT EXISTS é idempotente)
    init_schema(db)

    # Atualiza versão
    import time

    db.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
        (CURRENT_SCHEMA_VERSION, time.time()),
    )
    db.commit()


def serialize_metadata(metadata: dict | None) -> bytes | None:
    """Serializa metadata para CBOR2."""
    if metadata is None:
        return None
    return cbor2.dumps(metadata)


def deserialize_metadata(blob: bytes | None) -> dict:
    """Deserializa metadata de CBOR2."""
    if blob is None:
        return {}
    return cbor2.loads(blob)


def serialize_json(data: list | dict) -> str:
    """Serializa para JSON string."""
    import json

    return json.dumps(data)


def deserialize_json(text: str | None) -> list | dict:
    """Deserializa de JSON string."""
    import json

    if text is None:
        return []
    return json.loads(text)
