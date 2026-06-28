# scripts/start_mcp_with_opencode.py
"""
Inicia o MCP Server com suporte a asyncio.run().
Compatível com OpenCode e execução local.
"""

import asyncio
import threading
import time
import requests
from iaglobal.server.mcp_server import mcp_server


def check_mcp_health(max_retries: int = 5, interval: int = 3) -> bool:
    """Verifica se o MCP Server está saudável."""
    url = "http://localhost:8000/mcp/health"
    for _ in range(max_retries):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                status = response.json()
                if status.get("status") == "✅ OK":
                    return True
        except:
            pass
        time.sleep(interval)
    return False


def start_mcp_server():
    """Inicia o MCP Server de forma bloqueante."""
    # Configurar logger
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Iniciar servidor
    mcp_server.start_blocking()


if __name__ == "__main__":
    # Iniciar MCP Server em thread separada
    threading.Thread(target=start_mcp_server, daemon=True).start()
    
    # Verificar saúde
    if check_mcp_health():
        print("✅ MCP Server pronto e saudável")
        
        # Registrar agente MCP Monitor
        try:
            from opencode.mind.epigenetic_registry import register_agent
            register_agent(
                name="mcp_monitor",
                purpose="Monitorar homeostase do OpenCode via MCP",
                endpoints=["http://localhost:8000/mcp"],
                epigenetic_weights={
                    "temperature": 0.0,
                    "reliability": 1.0,
                    "proactivity": 0.9
                }
            )
            print("🛡️ MCP Monitor registrado no EpigeneticRegistry")
        except ImportError:
            print("⚠️ EpigeneticRegistry não disponível — MCP Monitor não registrado")
    else:
        print("❌ MCP Server falhou ao iniciar")
        exit(1)