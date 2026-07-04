# iaglobal/core/graceful_shutdown.py

import atexit
import asyncio
import logging
import threading

from datetime import datetime, timezone
from typing import Callable, List, Dict, Any

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

        self._sync_callbacks: List[Callable] = []
        self._async_callbacks: List[Callable] = []

        self._shutdown_lock = threading.Lock()

        self._is_shutting_down = False

        atexit.register(self.sync_cleanup)

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
        callback: Callable,
    ) -> None:
        self._async_callbacks.append(callback)

    # ============================================================
    # CLEANUP SÍNCRONO
    # ============================================================

    def trigger_emergency_shutdown(self, reason: str, details: Dict[str, Any] = None) -> None:
        """
        Dispara shutdown preventivo em caso de violação grave.
        """
        logger.critical(f"[SHUTDOWN] Emergency triggered: {reason}")
        
        # Registrar violação no Obsidian Short Term
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
            api = SubconsciousAPI()
            api.escrever_curto_prazo_sync(
                f"emergency_shutdown_{reason}",
                {"reason": reason, "details": details, "timestamp": datetime.now(timezone.utc).isoformat()}
            )
        except Exception:
            pass  # Não interromper shutdown por erro de obsidian
        
        # Definir flag para evitar novas execuções
        self._is_shutting_down = True

    def sync_cleanup(self) -> None:
        """Cleanup síncrono no shutdown."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True

        # Flush de métricas síncrono antes de qualquer outra coisa
        try:
            from iaglobal.providers.provider_metrics import metrics
            metrics.flush()
        except Exception:
            pass

        for callback in self._sync_callbacks:
            try:
                callback()
            except Exception:
                pass  # Skip logging to avoid handler closed issues

        # Skip final logging to avoid ValueError on closed file

    # ============================================================
    # CLEANUP ASSÍNCRONO
    # ============================================================


graceful_shutdown = GracefulShutdown()
