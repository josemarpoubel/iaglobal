# iaglobal/core/config.py

# Re-export centralizado dos paths do sistema.
# Módulos que quiserem paths devem importar daqui (em vez de _paths.py)
# para evitar acoplamento direto com a estrutura interna do _paths.py.
from iaglobal._paths import (
    DATA_DIR,
    BACKUP_DIR,
    PROJECT_ROOT,
    LOG_DIR,
    DB_DIR,
    CORE_DB,
    CACHE_DB,
    MEMORIES_DB,
    JSON_DIR,
    CBOR2_DIR,
    TEMP_DIR,
    RESULTS_DIR,
    SNAPSHOTS_DIR,
    WORK_DIR,
    DOCS_DIR,
    PROVIDER_METRICS_DIR,
    KNOWLEDGE_FILE,
    META_EVOLUTION_FILE,
)
