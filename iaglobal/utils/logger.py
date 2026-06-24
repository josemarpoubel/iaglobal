import logging
import sys
from iaglobal import _paths

# Configura o logging root-level no import do módulo (garante visibilidade em todas as camadas)
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

def setup_logger(name="iaglobal"):
    logger = logging.getLogger(name)
    # Garante nível DEBUG para capturar todos os logs internos
    if logger.level == logging.WARNING:
        logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
        
        # Handler para Console
        console_handler = logging.StreamHandler(sys.stdout)
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
            
    return logger

# Adicione estas funções que estão faltando para resolver o ImportError:
def get_logger(name="iaglobal"):
    return logging.getLogger(name)


def start_session_log():
    """Inicia o log de uma nova sessão."""
    logger = logging.getLogger("iaglobal")
    logger.info("--- 🚀 Nova Sessão Iniciada ---")

def stop_session_log():
    """Finaliza o log da sessão atual."""
    logger = logging.getLogger("iaglobal")
    logger.info("--- 🏁 Sessão Finalizada ---")

logger = setup_logger()
