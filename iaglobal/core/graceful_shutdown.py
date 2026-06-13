# iaglobal/core/graceful_shutdown.py

from __future__ import annotations

import atexit
import asyncio
import logging
import signal
import threading
import traceback

from contextlib import suppress
from typing import Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    Shutdown Manager do IAGlobal.

    Objetivos:

    - Nunca chamar sys.exit()
    - Nunca cancelar asyncio.all_tasks()
    - Cancelar apenas tarefas registradas pelo IAGlobal
    - Mostrar a origem da falha antes do shutdown
    - Funcionar em ambientes:
        * FastAPI
        * LangGraph
        * Workers
        * Scripts
        * Jupyter
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):

        if self._initialized:
            return

        self._initialized = True

        self._active_tasks: Dict[str, asyncio.Task] = {}

        self._sync_callbacks: List[Callable] = []
        
        self._async_callbacks: List[Callable[..., Awaitable]] = []

        self._shutdown_lock = threading.Lock()

        self._is_shutting_down = False

        self._shutdown_timeout = 30.0

        atexit.register(self.sync_cleanup)

    # ============================================================
    # TASK REGISTRY
    # ============================================================

    def register_task(
        self,
        name: str,
        task: asyncio.Task,
    ) -> None:

        self._active_tasks[name] = task

    def unregister_task(
        self,
        name: str,
    ) -> None:

        self._active_tasks.pop(name, None)

    # ============================================================
    # CALLBACKS
    # ============================================================

    def add_callback(
        self,
        callback: Callable,
    ) -> None:

        self._sync_callbacks.append(callback)

    def add_async_callback(
        self,
        callback: Callable[..., Awaitable],
    ) -> None:

        self._async_callbacks.append(callback)

    # ============================================================
    # DIAGNÓSTICO
    # ============================================================

    def _dump_registered_tasks(self) -> None:

        if not self._active_tasks:
            logger.warning(
                "[SHUTDOWN] Nenhuma task registrada."
            )
            return

        logger.error(
            "[SHUTDOWN] Snapshot das tasks registradas:"
        )

        for name, task in self._active_tasks.items():

            try:

                coro = task.get_coro()

                logger.error(
                    "[TASK] %s | done=%s | cancelled=%s | coro=%s",
                    name,
                    task.done(),
                    task.cancelled(),
                    getattr(
                        coro,
                        "__qualname__",
                        repr(coro),
                    ),
                )

            except Exception as e:

                logger.error(
                    "[TASK] %s | erro=%s",
                    name,
                    e,
                )

    def report_failure(
        self,
        reason: str,
        exc: Exception | None = None,
    ) -> None:

        logger.critical(
            "❌ CRITICAL FAILURE: %s",
            reason,
        )

        if exc:

            logger.critical(
                "Exception: %s",
                repr(exc),
            )

            logger.critical(
                traceback.format_exc()
            )

        else:

            logger.critical(
                "".join(
                    traceback.format_stack(limit=50)
                )
            )

        self._dump_registered_tasks()

    # ============================================================
    # CLEANUP SÍNCRONO
    # ============================================================

    def sync_cleanup(self) -> None:

        if self._is_shutting_down:
            return

        self._is_shutting_down = True

        logger.info(
            "[SHUTDOWN] limpeza síncrona iniciada"
        )

        for callback in self._sync_callbacks:

            try:

                callback()

            except Exception:

                logger.exception(
                    "[SHUTDOWN] callback falhou"
                )

        logger.info(
            "[SHUTDOWN] limpeza síncrona concluída"
        )

    # ============================================================
    # SHUTDOWN ASSÍNCRONO
    # ============================================================

    async def async_shutdown(self) -> None:

        with self._shutdown_lock:

            if self._is_shutting_down:
                return

            self._is_shutting_down = True

        logger.warning(
            "[SHUTDOWN] iniciado"
        )

        self._dump_registered_tasks()

        # ----------------------------------------------------
        # FECHAMENTO DOS PROVIDERS
        # ----------------------------------------------------

        with suppress(ImportError):

            try:

                from iaglobal.providers.async_http import (
                    close_all_sessions,
                )

                await asyncio.wait_for(
                    close_all_sessions(),
                    timeout=self._shutdown_timeout,
                )

            except Exception:

                logger.exception(
                    "[SHUTDOWN] erro close_all_sessions"
                )

        with suppress(ImportError):

            try:

                from iaglobal.providers.perplexity_provider import (
                    shutdown_browser,
                )

                await asyncio.wait_for(
                    shutdown_browser(),
                    timeout=self._shutdown_timeout,
                )

            except Exception:

                logger.exception(
                    "[SHUTDOWN] erro shutdown_browser"
                )

        # ----------------------------------------------------
        # CALLBACKS ASSÍNCRONOS
        # ----------------------------------------------------

        for callback in self._async_callbacks:

            try:

                await asyncio.wait_for(
                    callback(),
                    timeout=self._shutdown_timeout,
                )

            except Exception:

                logger.exception(
                    "[SHUTDOWN] async callback falhou"
                )

        # ----------------------------------------------------
        # CANCELA APENAS TASKS REGISTRADAS
        # ----------------------------------------------------

        tasks_to_cancel = []

        for name, task in list(
            self._active_tasks.items()
        ):

            if task.done():
                continue

            logger.warning(
                "[SHUTDOWN] cancelando task %s",
                name,
            )

            task.cancel()

            tasks_to_cancel.append(task)

        if tasks_to_cancel:

            try:

                await asyncio.wait_for(
                    asyncio.gather(
                        *tasks_to_cancel,
                        return_exceptions=True,
                    ),
                    timeout=self._shutdown_timeout,
                )

            except asyncio.TimeoutError:

                logger.error(
                    "[SHUTDOWN] timeout aguardando tasks"
                )

        logger.warning(
            "[SHUTDOWN] concluído"
        )

    # ============================================================
    # SIGNAL HANDLERS
    # ============================================================

    def setup_signal_handlers(self) -> None:

        def _handler(signum, frame):

            logger.warning(
                "[SHUTDOWN] sinal recebido: %s",
                signum,
            )

            self.report_failure(
                f"Sinal recebido: {signum}"
            )

            try:

                loop = asyncio.get_running_loop()

                if loop.is_running():

                    loop.create_task(
                        self.async_shutdown()
                    )

                    return

            except RuntimeError:
                pass

            self.sync_cleanup()

        signal.signal(
            signal.SIGTERM,
            _handler,
        )

        signal.signal(
            signal.SIGINT,
            _handler,
        )


graceful_shutdown = GracefulShutdown()
