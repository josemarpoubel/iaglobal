# iaglobal/core/structure.py

import os

from pathlib import Path

from iaglobal._paths import ensure_structure

REQUIRED_DIRS = [
    "memory/data/logs",
    "memory/data/db",
    "memory/data/vectors"
]

def ensure_structure():
    """Garante que a estrutura de pastas necessária para o runtime exista."""
    # Ajuste o caminho se necessário (o 'parent' sobe para iaglobal, 'parent' para projeto-iaglobal)
    base_path = Path(__file__).resolve().parent.parent.parent
    for d in REQUIRED_DIRS:
        path = base_path / d
        path.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    ensure_structure()
