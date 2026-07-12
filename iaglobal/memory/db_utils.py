# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Database Utils — Context managers para conexões SQLite.

Resolve ResourceWarning: unclosed database em todo o sistema.

Uso:
    from iaglobal.memory.db_utils import get_db_connection
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table")
        # Conexão fechada automaticamente
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.memory.db_utils")


@contextmanager
def get_db_connection(
    db_path: Path,
    timeout: float = 30.0,
    detect_types: int = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager para conexões SQLite.
    
    Fecha automaticamente a conexão ao sair do bloco 'with',
    evitando ResourceWarning: unclosed database.
    
    Args:
        db_path: Caminho para o banco de dados
        timeout: Timeout em segundos (default: 30.0)
        detect_types: Detecção de tipos (default: PARSE_DECLTYPES | PARSE_COLNAMES)
    
    Yields:
        sqlite3.Connection configurada
    
    Example:
        with get_db_connection(Path("data.db")) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
    """
    conn = None
    try:
        conn = sqlite3.connect(
            str(db_path),
            timeout=timeout,
            detect_types=detect_types,
        )
        conn.row_factory = sqlite3.Row
        logger.debug("[DB_UTILS] Conexão aberta | db=%s", db_path)
        yield conn
    except Exception as e:
        logger.error("[DB_UTILS] Erro na conexão | db=%s | error=%s", db_path, e)
        raise
    finally:
        if conn:
            conn.close()
            logger.debug("[DB_UTILS] Conexão fechada | db=%s", db_path)


@contextmanager
def get_db_cursor(
    conn: sqlite3.Connection,
) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager para cursores SQLite.
    
    Fecha automaticamente o cursor ao sair do bloco 'with'.
    
    Args:
        conn: Conexão SQLite ativa
    
    Yields:
        sqlite3.Cursor
    
    Example:
        with get_db_connection(db_path) as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("SELECT * FROM table")
    """
    cursor = None
    try:
        cursor = conn.cursor()
        yield cursor
    finally:
        if cursor:
            cursor.close()
