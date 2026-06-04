# iaglobal/_paths.py

import os

from pathlib import Path

# =========================================================
# ROOT DO SISTEMA (SOURCE OF TRUTH)
# =========================================================

# Raiz do pacote iaglobal (onde _paths.py está)
PACKAGE_DIR = Path(__file__).resolve().parent

# Raiz do projeto (onde pyproject.toml, docs/, cli.py estão)
PROJECT_ROOT = PACKAGE_DIR.parent

# /iaglobal/memory/data/
# ├── core.db
# ├── cache.db
# ├── cache/
# ├── logs/
# ├── script/
# └── memory_backups/

# =========================================================
# DATA LAYER (SEMPRE DENTRO DO PACOTE iaglobal)
# =========================================================

DATA_ROOT = PACKAGE_DIR / "memory" / "data"

MEMORY_DIR = DATA_ROOT

BACKUP_DIR = DATA_ROOT / "memory_backups"

CACHE_DIR = DATA_ROOT / "cache"

LOG_DIR = DATA_ROOT / "logs"

SCRIPTS_DIR = DATA_ROOT / "script"

TEMP_DIR = DATA_ROOT / "temp"

# =========================================================
# COMPATIBILITY LAYER
# =========================================================

DATA_DIR = MEMORY_DIR

BACKUP_DIR_LEGACY = BACKUP_DIR

# =========================================================
# DATABASES (SINGLE SOURCE OF TRUTH)
# =========================================================

CORE_DB = MEMORY_DIR / "core.db"

CACHE_DB = MEMORY_DIR / "cache.db"

# =========================================================
# ARTIFACTS / EMBEDDINGS
# =========================================================

EMBEDDINGS_DB = MEMORY_DIR / "embeddings.cbor2"

ERROR_LOG = MEMORY_DIR / "errors.json"

# =========================================================
# DOCUMENTATION / OBSERVABILITY
# =========================================================

DOCS_DIR = PROJECT_ROOT / "docs"

EVOLUTION_DOC = DOCS_DIR / "evolucao_cerebral.md"

# =========================================================
# GUARANTEE LAYER (AUTO-BOOTSTRAP DO SISTEMA)
# =========================================================

def _ensure_dirs():
    """
    Garante estrutura mínima do sistema antes de qualquer execução.
    Isso elimina erro de path em runtime.
    """

    critical_dirs = [
        DATA_ROOT,
        MEMORY_DIR,
        BACKUP_DIR,
        CACHE_DIR,
        LOG_DIR,
        DOCS_DIR,
        SCRIPTS_DIR,
        TEMP_DIR,
    ]

    for d in critical_dirs:
        d.mkdir(parents=True, exist_ok=True)


# bootstrap automático
_ensure_dirs()


# =========================================================
# UTILITÁRIOS PADRÃO DO SISTEMA
# =========================================================

def get_db_connection(db_path: Path) -> str:
    """
    Normaliza caminhos para SQLite e engines externas.
    """
    return str(db_path.resolve())


def resolve_path(path: Path | str) -> str:
    """
    Resolve qualquer path para absoluto seguro.
    """
    return str(Path(path).expanduser().resolve())
