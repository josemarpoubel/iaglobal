from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from iaglobal.utils.logger import get_logger
from iaglobal.cognition.awareness.awareness_cache import AwarenessCache

logger = get_logger("iaglobal.cognition.awareness.persistence")


class AwarenessPersistence:
    """
    Conversor de persistência: SQLite :memory: -> awareness.db (arquivo CBOR2).

    Executa backup periódico do banco em memória para arquivo persistente.
    Permite replay, auditoria e recuperação de estado.
    """

    def __init__(
        self,
        cache: AwarenessCache,
        db_path: Path | str | None = None,
        interval: float | None = None,
    ):
        self._cache = cache
        self._interval = interval or float(os.getenv("AWARENESS_BACKUP_INTERVAL", "2"))
        self._db_path = Path(db_path or "awareness.db")
        self._running = False
        self._task: asyncio.Task | None = None

        # Inicializa schema no arquivo persistente
        self._dest_db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        from iaglobal.cognition.awareness.awareness_schema import init_schema

        init_schema(self._dest_db)

        logger.info(
            f"AwarenessPersistence inicializado: {self._db_path} (intervalo={self._interval}s)"
        )

    async def start(self) -> None:
        """Inicia task de backup em background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("AwarenessPersistence iniciado")

    async def stop(self) -> None:
        """Para task e faz backup final."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._backup()
        self._dest_db.close()
        logger.info("AwarenessPersistence parado")

    async def _run(self) -> None:
        """Loop principal de backup periódico."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._running:
                    await self._backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no backup de awareness: {e}")

    async def _backup(self) -> None:
        """Faz backup do banco em memória para arquivo (sqlite3.backup)."""
        source = self._cache.get_memory_db()

        def _do_backup():
            source.backup(self._dest_db)

        # sqlite3.backup é blocking, roda em thread
        await asyncio.to_thread(_do_backup)
        logger.debug(f"Awareness backup concluído: {self._db_path}")

    async def restore(self, cache: AwarenessCache) -> None:
        """Restaura estado do arquivo para banco em memória (para recovery)."""

        def _do_restore():
            self._dest_db.backup(cache.get_memory_db())

        await asyncio.to_thread(_do_restore)
        logger.info(f"Awareness restaurado de {self._db_path}")

    @property
    def db_path(self) -> Path:
        return self._db_path
