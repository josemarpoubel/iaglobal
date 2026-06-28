#!/usr/bin/env python3
# scripts/opencode_mcp_integration.py
"""
Integra o MCP Server iaglobal com OpenCode via MCP Local.

Fluxo:
1. Inicia MCP Server.
2. Registra ferramentas via JSON-RPC.
3. Notifica OpenCode.
"""

import asyncio
import subprocess
import json
import requests
import time
import signal
import sys

# Configuração
MCP_URL = "http://localhost:8000/mcp"
MCP_USER = "iaglobal"
MCP_PASSWORD = "homeostasis"
TIMEOUT = 10


def start_mcp_server():
    """Inicia o MCP Server em background."""
    cmd = ["python", "-m", "iaglobal.asgi"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
    )
    return proc


def register_mcp_tools():
    """Registra ferramentas no OpenCode via MCP Server."""
    tools = [
        {
            "name": "metabolic_audit",
            "description": "Executa auditoria metabólica via MCPAgent",
            "endpoint": f"{MCP_URL}/audit",
            "auth": {
                "type": "basic",
                "user": MCP_USER,
                "password": MCP_PASSWORD
            }
        },
        {
            "name": "metabolic_status",
            "description": "Retorna status do MCP Server e métricas de saúde",
            "endpoint": f"{MCP_URL}/health"
        },
        {
            "name": "metabolic_fix",
            "description": "Aciona correção automática para target específico",
            "endpoint": f"{MCP_URL}/fix",
            "params": {
                "target": {
                    "type": "string",
                    "enum": ["vault", "latency", "toxins", "ivm"]
                }
            }
        }
    ]
    
    # Registrar via JSON-RPC
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/register",
        "params": {"tools": tools},
        "id": 1
    }
    
    response = requests.post(
        f"{MCP_URL}/jsonrpc",
        json=payload,
        auth=(MCP_USER, MCP_PASSWORD),
        timeout=TIMEOUT
    )
    
    if response.status_code == 200:
        result = response.json().get("result", {})
        print(f"✅ Ferramentas registradas: {result.get('success_count', 0)} ferramentas")
        return True
    else:
        print(f"❌ Falha ao registrar ferramentas: {response.status_code}")
        return False


def check_mcp_health():
    """Verifica se o MCP Server está saudável."""
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=TIMEOUT)
        if response.status_code == 200:
            status = response.json().get("status")
            print(f"✅ MCP Server saudável: {status}")
            return True
    except Exception as e:
        print(f"❌ MCP Server indisponível: {e}")
    return False


def notify_opencode():
    """Notifica OpenCode sobre disponibilidade do MCP Server."""
    try:
        # Simular notificação via MCP (OpenCode escuta no barramento)
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "opencode/notify",
                "params": {"service": "mcp_server", "status": "online"},
                "id": 1
            },
            timeout=TIMEOUT
        )
        if response.status_code == 200:
            print("✅ OpenCode notificado")
            return True
    except Exception as e:
        print(f"⚠️ Falha ao notificar OpenCode: {e}")
    return False


def main():
    print("🔄 Iniciando integração MCP iaglobal ↔ OpenCode")
    print("=" * 60)
    
    # Iniciar MCP Server
    proc = start_mcp_server()
    time.sleep(2)  # Aguardar inicialização
    
    if not check_mcp_health():
        print("❌ MCP Server falhou ao iniciar")
        proc.terminate()
        sys.exit(1)
    
    # Registrar ferramentas
    if not register_mcp_tools():
        proc.terminate()
        sys.exit(1)
    
    # Notificar OpenCode
    notify_opencode()
    
    print("✅ Integração MCP concluída")
    print("Acesse:")
    print(f"- MCP Server: {MCP_URL}")
    print(f"- OpenCode: opencode mcp list")
    
    # Manter processo vivo
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()