#!/bin/bash
# ~/projeto-iaglobal/run_mcp.sh

# Exporta as variáveis de ambiente
export MCP_USER="iaglobal"
export MCP_PASSWORD="homeostasis"
export PYTHONPATH="/home/kitohamachi/projeto-iaglobal"

# Executa o módulo Python
# O $@ permite que o script repasse quaisquer argumentos do OpenCode, se houver
exec /home/kitohamachi/projeto-iaglobal/venv/bin/python -m iaglobal.api.mcp_server "$@"
