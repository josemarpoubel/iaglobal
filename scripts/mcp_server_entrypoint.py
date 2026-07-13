#!/usr/bin/env python3
"""Wrapper script para executar MCP Server no OpenCode sem reload."""

import os
import sys
import uvicorn

# Garantir venv
os.chdir("/home/kitohamachi/projeto-iaglobal")
sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    uvicorn.run(
        "iaglobal.asgi:application",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False
    )