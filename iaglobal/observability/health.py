import logging
from iaglobal._paths import CORE_DB, CACHE_DB, LOG_DIR
from pathlib import Path

logger = logging.getLogger("OBSERVABILITY")


class HealthCheck:
    """Health checks básicos do sistema."""

    @staticmethod
    def check_database():
        return {
            "core_db_exists": Path(CORE_DB).exists(),
            "cache_db_exists": Path(CACHE_DB).exists(),
        }

    @staticmethod
    def check_logs():
        return {"log_dir_exists": LOG_DIR.exists()}

    @staticmethod
    def summary():
        return {
            "db": HealthCheck.check_database(),
            "logs": HealthCheck.check_logs(),
        }
