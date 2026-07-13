# iaglobal/core/env_loader.py

from dotenv import load_dotenv
from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import logger


def load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path), override=True)
        logger.info(f"ENV loaded from {env_path}")
    else:
        load_dotenv(override=True)
        logger.warning(
            f".env não encontrado em {env_path}, usando fallback find_dotenv()"
        )
