"""Membrane — camada de isolamento entre subsistemas (organelas)."""

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CORE_ORGANELLES = {"core", "delivery"}


class Organelle(Enum):
    INGESTION = "ingestion"
    CORE = "core"
    EVOLUTION = "evolution"
    IMMUNITY = "immunity"
    DELIVERY = "delivery"
    METACOGNITION = "metacognition"


@dataclass
class MembraneMessage:
    source: Organelle
    target: Organelle
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    critical: bool = False


class Membrane:
    """Membrana Celular — isola organelas e roteia mensagens entre elas.
    Falha em uma organela não propaga para as outras.
    Agentes de nível inferior (ex: ingestion) não podem alterar o core diretamente."""

    def __init__(self):
        self._routes: Dict[str, Callable] = {}

    def register_handler(self, organelle: Organelle, handler: Callable):
        self._routes[organelle.value] = handler

    def send(self, message: MembraneMessage) -> Optional[Any]:
        if message.source.value not in CORE_ORGANELLES and message.target.value in CORE_ORGANELLES:
            if message.event_type not in ("query", "read"):
                logger.warning("[MEMBRANE] BLOQUEADO: '%s' tentou modificar core '%s'",
                              message.source.value, message.target.value)
                return None
        handler = self._routes.get(message.target.value)
        if not handler:
            logger.warning("[MEMBRANE] Organela '%s' sem handler registrado", message.target.value)
            return None
        try:
            return handler(message)
        except Exception as e:
            logger.error("[MEMBRANE] Falha em '%s' — isolada (erro: %s)", message.target.value, e)
            return None


