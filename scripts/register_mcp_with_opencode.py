#!/usr/bin/env python3
"""
Registra o MCP Server local manualmente no OpenCode.
"""

import os
import json
from pathlib import Path

# Caminho para configuração OpenCode
OPENCODE_CONFIG = Path.home() / ".config/opencode/opencode.json"


def load_config():
    """Carrega configuração OpenCode existente."""
    if not OPENCODE_CONFIG.exists():
        return {"mcp": {}}
    
    with open(OPENCODE_CONFIG, "r") as f:
        return json.load(f)


def save_config(config):
    """Salva configuração OpenCode."""
    OPENCODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(OPENCODE_CONFIG, "w") as f:
        json.dump(config, f, indent=2)


def register_server():
    """Registra o MCP Server iaglobal no OpenCode."""
    config = load_config()
    
    # Servidor MCP local
    config["mcp"] = config.get("mcp", {})
    config["mcp"]["iaglobal-local"] = {
        "type": "local",
        "command": ["python", "-m", "iaglobal.asgi"],
        "enabled": True,
        "cwd": os.getcwd(),
        "env": {
            "MCP_USER": "iaglobal",
            "MCP_PASSWORD": "homeostasis"
        }
    }
    
    # Agente MCP Monitor
    config["agent"] = config.get("agent", {})
    config["agent"]["mcp_monitor"] = {
        "description": "Monitors OpenCode's integrity via iaglobal MCP",
        "mode": "primary",
        "model": "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
        "permission": {
            "task": "allow"
        },
        "options": {
            "temperature": 0.0,
            "ivm_threshold": 0.8
        }
    }
    
    # Comando MCP (definido em .opencode.json local)
    
    save_config(config)
    print("✅ MCP Server registrado com sucesso!")
    print(f"   Configuração salva em: {OPENCODE_CONFIG}")


if __name__ == "__main__":
    register_server()