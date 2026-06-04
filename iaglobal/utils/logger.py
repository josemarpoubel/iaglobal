"""Logger utility module for application logging."""

import logging
import sys

FORMATO_LOG = "%(asctime)s [%(levelname)s] %(message)s"
DATA_FORMATO = "%Y-%m-%d %H:%M:%S"

_configured = False

def _ensure_configured():
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMATO_LOG, datefmt=DATA_FORMATO))
        root.addHandler(handler)
    logger = logging.getLogger("ia-global")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMATO_LOG, datefmt=DATA_FORMATO))
        logger.addHandler(handler)

logger = logging.getLogger("ia-global")
_ensure_configured()

def setup_logger(name: str = "ia-global", level: int = logging.INFO) -> logging.Logger:
    _ensure_configured()
    log = logging.getLogger(name)
    log.setLevel(level)
    return log

def get_logger(name: str = "ia-global") -> logging.Logger:
    return logging.getLogger(name)

def set_log_level(level: int) -> None:
    _ensure_configured()
    logging.getLogger("ia-global").setLevel(level)

def add_file_handler(filepath: str) -> None:
    _ensure_configured()
    file_handler = logging.FileHandler(filepath)
    file_handler.setFormatter(logging.Formatter(FORMATO_LOG, datefmt=DATA_FORMATO))
    logging.getLogger("ia-global").addHandler(file_handler)

def remove_handler(handler: logging.Handler) -> None:
    logging.getLogger("ia-global").removeHandler(handler)
