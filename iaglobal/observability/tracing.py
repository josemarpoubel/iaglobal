import logging
import time

logger = logging.getLogger("OBSERVABILITY")

class Tracer:
    """Tracer simples para rastrear execução de agentes e pipelines."""

    @staticmethod
    def trace_event(event_name: str, context: dict = None):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(f"[TRACE] {ts} :: {event_name} :: {context or {}}")
