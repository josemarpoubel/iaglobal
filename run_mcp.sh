#!/bin/bash

export PYTHONPATH="/home/kitohamachi/iaglobal-main"

exec /home/kitohamachi/iaglobal-main/venv/bin/python -u -m iaglobal.mcp.server --mode stdio "$@"
