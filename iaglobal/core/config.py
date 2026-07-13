# iaglobal/core/config.py

# Re-export centralizado dos paths do sistema.
# Módulos que quiserem paths devem importar daqui (em vez de _paths.py)
# para evitar acoplamento direto com a estrutura interna do _paths.py.
from iaglobal._paths import (
    DATA_DIR,
    BACKUP_DIR,
)

# Injetado automaticamente para resolver assinaturas ausentes
# Nota: estes nomes coincidem com imports de _paths.py mas são relativos ao CWD.
# Módulos que precisam de paths absolutos devem importar de iaglobal._paths diretamente.
DATA_DIR = "data"
BACKUP_DIR = "backup"
