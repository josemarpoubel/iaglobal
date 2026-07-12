# iaglobal/events/event_dispatcher.py

import asyncio
import logging
from typing import Callable, Dict, List, Any, Coroutine, Union

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

# Tipo que aceita funções normais ou corrotinas
HandlerType = Union[Callable[[dict], Any], Callable[[dict], Coroutine[Any, Any, Any]]]

class DecisionEventDispatcher:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers: Dict[str, List[HandlerType]] = {}
            cls._instance._subscribed = False
        return cls._instance

    def _route(self, event):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._process_event_sync(event)
            return
        
        # Log de recepção de evento no roteador
        logger.debug(f"📥 [DISPATCHER] Evento roteado para processamento assíncrono")
        coro = self._process_event(event)
        loop.create_task(coro)

    async def _process_event(self, event):
        from iaglobal.models.event_bus import Event
        if not isinstance(event, Event):
            return
        
        data = event.data or {}
        step = data.get("step")
        
        # Log de início de execução dos handlers
        logger.info(f"⚡ [DISPATCHER] Executando handlers para: {step}")
        
        handlers = self._handlers.get(step, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"❌ [DISPATCHER] Falha crítica no handler de {step}: {e}")

    def start(self):
        if self._subscribed:
            return
        # FAÇA A IMPORTAÇÃO AQUI (Lazy Import)
        from iaglobal.models.event_bus import bus, EventType
        bus.subscribe(EventType.PIPELINE_STAGE, self._route)
        self._subscribed = True
        logger.info("📬 [DISPATCHER] Roteamento assíncrono ativo")

    def stop(self):
        if not self._subscribed:
            return
        # FAÇA A IMPORTAÇÃO AQUI (Lazy Import)
        from iaglobal.models.event_bus import bus, EventType
        bus.unsubscribe(EventType.PIPELINE_STAGE, self._route)
        self._subscribed = False


dispatcher = DecisionEventDispatcher()
