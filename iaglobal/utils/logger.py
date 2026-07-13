import logging
import sys

from iaglobal import _paths

# Configura o logging root-level no import do módulo (garante visibilidade em todas as camadas)
# Apenas uma vez por sessão
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.WARNING,  # Produção: apenas WARNING+
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
    )

# Cache de broadcasters WebSocket registrados
_web_log_broadcasters = []


def register_web_log_broadcast(broadcast_func):
    """Registra função assíncrona para broadcast de logs para a UI."""
    _web_log_broadcasters.append(broadcast_func)


async def _broadcast_web_log(message: str, level: str = "info"):
    """Envia log para todos os broadcasters registrados."""
    for broadcaster in _web_log_broadcasters:
        try:
            await broadcaster(message, level)
        except Exception:
            pass


class WebSocketHandler(logging.Handler):
    """Handler que envia logs para o terminal da UI via WebSocket."""

    def emit(self, record: logging.LogRecord):
        try:
            message = self.format(record)
            level = record.levelname.lower()
            if level in ("warning", "error", "critical"):
                asyncio.get_running_loop().create_task(
                    _broadcast_web_log(message, level)
                )
        except Exception:
            pass


def setup_logger(name="iaglobal"):
    logger = logging.getLogger(name)
    # Evita propagação para o root logger (previne duplicação)
    logger.propagate = False

    # Garante nível INFO para sinais de observabilidade (ex: [MEMBRANA]).
    # Corrige bug: logger recém-criado tem nível NOTSET (0), nunca == WARNING,
    # então a subida de nível nunca ocorria e INFO era silenciosamente
    # suprimido (nível efetivo = WARNING do root) — escondendo decisões de
    # membrana/IVM em produção. INFO é o piso de visibilidade do CLI.
    if logger.level < logging.INFO:
        logger.setLevel(logging.INFO)

    # Evita handlers duplicados
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        )

        # Handler para Console (STDERR, para não poluir STDOUT do MCP/CLI)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler para Arquivo
        try:
            _paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_file = _paths.LOG_DIR / "app.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

        # Handler para WebSocket (UI)
        try:
            ws_handler = WebSocketHandler()
            ws_handler.setFormatter(formatter)
            ws_handler.setLevel(logging.WARNING)
            logger.addHandler(ws_handler)
        except Exception:
            pass

    return logger


def get_logger(name="iaglobal"):
    return logging.getLogger(name)


def start_session_log():
    """Inicia o log de uma nova sessão."""
    logger = logging.getLogger("iaglobal")
    logger.info("--- 🚀 Nova Sessão Iniciada ---", stacklevel=2)


def stop_session_log():
    """Finaliza o log da sessão atual."""
    logger = logging.getLogger("iaglobal")
    logger.info("--- 🏁 Sessão Finalizada ---", stacklevel=2)


logger = setup_logger()
