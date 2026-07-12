#!/usr/bin/env python3
# cli.py

import sys
import asyncio

# Garante que o projeto esteja no path (portável)
from iaglobal._paths import PACKAGE_DIR
sys.path.insert(0, str(PACKAGE_DIR.parent))

from iaglobal.cli.main import run_cli

if __name__ == "__main__":
    # O asyncio.run() é o "motor" que gerencia o ciclo de vida assíncrono.
    # Ele inicializa o loop, aguarda a corrotina 'run_cli' e finaliza o loop.
    try:
        sys.exit(asyncio.run(run_cli()))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)