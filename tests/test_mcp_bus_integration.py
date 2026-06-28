# tests/test_mcp_bus_integration.py
"""
Teste de integração entre MCP Server e AcetylcholineBus.

Verifica:
- Publicação de métricas
- Escuta de comandos
- Resposta assíncrona
"""

import asyncio
import json
import time
import pytest
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus


@pytest.mark.asyncio
async def test_mcp_bus_integration():
    """Testa a integração MCP ↔ AcetylcholineBus."""
    bus = AcetylcholineBus.get_instance()
    bus.start_background_purger(interval_sec=1.0)  # Purge a cada 1s
    
    print("🔄 Testando AcetylcholineBus (simulação)")
    
    # --- Testar publicação e escuta ---
    collected = []
    
    def listener(payload: dict):
        collected.append(payload)
        print(f"📬 Mensagem recebida: {payload.payload}")
    
    bus.subscribe("test/topic", listener)
    
    # Publicar mensagem
    from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage
    msg = AgentMessage(
        sender="test/agent",
        receiver="test/topic",
        type="test",
        payload={"hello": "world", "value": 42}
    )
    await bus.publish(msg)
    
    # Aguardar processamento
    await asyncio.sleep(0.5)
    
    assert len(collected) == 1, "Mensagem não foi entregue"
    assert collected[0].payload.get("hello") == "world", "Payload incorreto"
    print("✅ Publicação e escuta funcionando")
    
    # --- Testar TTL ---
    await bus.publish("test/agent", "test/ttl", {"ttl_test": True}, ttl=0.1)
    await asyncio.sleep(0.2)
    
    expired = []
    def expired_listener(payload: dict):
        expired.append(payload)
    
    bus.subscribe("test/ttl", expired_listener)
    await asyncio.sleep(0.1)
    
    assert len(expired) == 0, "Mensagem expirada não deveria ser entregue"
    print("✅ TTL funcionando")
    
    # --- Testar MCP Server (simulação) ---
    from iaglobal.server.mcp_server import MCPServer
    mcp = MCPServer()
    
    # Simular handler de comando
    async def mock_correction(payload: dict):
        print(f"⚡ Comando MCP recebido: {payload}")
        await bus.publish("mcp", f"mcp/autocorrect/response/{payload['command_id']}", {
            "status": "success",
            "corrections": 1
        })
    
    # Substituir handler real
    mcp._handle_autocorrect_command = mock_correction
    
    command_id = f"test-{int(time.time())}"
    await bus.publish("test/agent", "mcp/autocorrect", {
        "command_id": command_id,
        "target": "vault"
    })
    
    # Coletar resposta
    response_collected = []
    def response_listener(payload: dict):
        response_collected.append(payload)
    
    bus.subscribe(f"mcp/autocorrect/response/{command_id}", response_listener)
    await asyncio.sleep(0.5)
    
    assert len(response_collected) == 1, "Resposta ao comando não recebida"
    assert response_collected[0].payload["status"] == "success", "Comando falhou"
    print(f"✅ Integração MCP ↔ Bus: {response_collected[0].payload['corrections']} correções")
    
    # Limpar
    bus.unsubscribe("test/topic", listener)
    bus.unsubscribe("test/ttl", expired_listener)
    bus.unsubscribe(f"mcp/autocorrect/response/{command_id}", response_listener)