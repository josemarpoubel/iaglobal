# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Storage Backend v3.1.5 — Abstração de persistência backend-agnostic.

Todos os engines acessam dados exclusivamente via operações semânticas deste módulo.
Nenhum engine importa sqlite3 diretamente.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PersistenceBackend(ABC):
    """Interface abstrata para backend de persistência.

    Implementações: SQLiteBackend (atual), DuckDBBackend (futuro),
                    PostgresBackend (futuro), RedisStreamsBackend (futuro).
    """

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> Any:
        """Executa SQL sem retorno (INSERT, UPDATE, DELETE, DDL)."""
        ...

    @abstractmethod
    def executemany(self, sql: str, params_list: list[tuple]) -> Any:
        """Executa SQL com múltiplos conjuntos de parâmetros."""
        ...

    @abstractmethod
    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Executa SELECT e retorna lista de dicts."""
        ...

    @abstractmethod
    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Executa SELECT e retorna a primeira linha (ou None)."""
        ...

    @abstractmethod
    def commit(self) -> None:
        """Persiste transação."""
        ...

    @abstractmethod
    def backup(self) -> bytes:
        """Retorna snapshot binário completo do estado."""
        ...

    @abstractmethod
    def restore(self, data: bytes) -> None:
        """Restaura estado a partir de snapshot binário."""
        ...


class SQLiteBackend(PersistenceBackend):
    """Implementação SQLite da camada de persistência.

    Encapsula conexão SQLite em memória com schema inicializado.
    """

    def __init__(self, db: Any) -> None:
        self._db = db

    def execute(self, sql: str, params: tuple = ()) -> Any:
        return self._db.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> Any:
        return self._db.executemany(sql, params_list)

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cursor = self._db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        cursor = self._db.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def commit(self) -> None:
        self._db.commit()

    def backup(self) -> bytes:
        import io

        buf = io.BytesIO()
        self._db.backup(buf)
        return buf.getvalue()

    def restore(self, data: bytes) -> None:
        import io

        src = __import__("sqlite3").connect(":memory:")
        src.backup(self._db)
