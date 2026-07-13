"""
iaglobal/cli/ui_cli.py
======================
Comando CLI para iniciar a interface web própria do IAGLOBAL.

Uso:
    iaglobal ui                    # Inicia em 127.0.0.1:8001
    iaglobal ui --port 8080        # Porta customizada
    iaglobal ui --host 0.0.0.0     # Host customizado
"""

import argparse
import logging
import sys

from iaglobal.ui.fastapi_app import run_server

logger = logging.getLogger("iaglobal")


def main():
    parser = argparse.ArgumentParser(
        prog="iaglobal ui",
        description="Inicia a interface web própria do IAGLOBAL (100% gratuita)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Endereço de bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Porta de listen (default: 8001)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload em desenvolvimento (requer uvicorn com reload)",
    )

    args = parser.parse_args()

    logger.info(
        "🚀 [UI] Iniciando IAGLOBAL Agent Workspace em http://%s:%d",
        args.host,
        args.port,
    )
    logger.info(
        "   [UI] Startup pode demorar ~40s em primeiro acesso; se falhar, tente novamente."
    )
    logger.info("   [UI] Dashboard: http://localhost:%d", args.port)
    logger.info("   [UI] API Docs: http://localhost:%d/docs", args.port)
    logger.info(
        "   [UI] WebSocket: ws://localhost:%d/ws/progress/{execution_id}", args.port
    )

    try:
        run_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("[UI] Servidor interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        logger.error("[UI] Falha ao iniciar servidor: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
