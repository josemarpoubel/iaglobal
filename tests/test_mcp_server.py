"""
Teste de sanidade do MCP Server (HTTP).
Verifica se o servidor MCP responde via HTTP e se os endpoints funcionam.
"""

import requests
import sys

MCP_URL = "http://localhost:8000/mcp/jsonrpc"


def run_tests() -> dict:
    """Executa bateria de testes contra o MCP Server."""
    results = {
        "server_reachable": False,
        "initialize_ok": False,
        "tools_list_ok": False,
        "tool_count": 0,
        "server_name": None,
        "error": None,
    }

    print("\n🔮 TESTE MCP SERVER — HTTP ENDPOINT")
    print("=" * 70)

    # 1. Verificar se o servidor está acessível
    try:
        response = requests.get("http://localhost:8000/")
        if response.status_code == 200:
            results["server_reachable"] = True
            print("✅ Servidor ASGI principal disponível")
        else:
            print(f"⚠️  Servidor ASGI retornou status: {response.status_code}")
    except Exception as e:
        results["error"] = f"ASGI Server inacessível: {e}"
        print(f"❌ ASGI Server inacessível: {e}")
        return results

    # 2. Teste JSON-RPC: initialize
    try:
        response = requests.post(
            MCP_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                results["initialize_ok"] = True
                results["server_name"] = data["result"].get("serverInfo", {}).get("name")
                print(f"✅ Handshake MCP: {results['server_name']}")
            else:
                print(f"⚠️  Handshake falhou: {data}")
        else:
            print(f"⚠️  Handshake retornou status {response.status_code}")
            
    except Exception as e:
        results["error"] = f"Erro no handshake: {e}"
        print(f"❌ Erro no handshake: {e}")
        return results

    # 3. Teste JSON-RPC: tools/list
    try:
        response = requests.post(
            MCP_URL,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                tools = data["result"].get("tools", [])
                results["tools_list_ok"] = True
                results["tool_count"] = len(tools)
                print(f"✅ Ferramentas MCP: {len(tools)} disponíveis")
                for tool in tools[:5]:
                    desc = (tool.get("description") or "")[:70]
                    print(f"   - {tool.get('name')}: {desc}")
                if len(tools) > 5:
                    print(f"   ... e mais {len(tools) - 5} ferramentas")
            else:
                print(f"⚠️  Lista de ferramentas falhou: {data}")
        else:
            print(f"⚠️  Lista de ferramentas retornou status {response.status_code}")
            
    except Exception as e:
        results["error"] = f"Erro ao listar ferramentas: {e}"
        print(f"❌ Erro ao listar ferramentas: {e}")

    return results


if __name__ == "__main__":
    result = run_tests()

    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    for k, v in result.items():
        print(f" {k}: {v}")

    if result.get("initialize_ok") and result.get("tools_list_ok"):
        print("\n✅ MCP SERVER ESTÁ FUNCIONAL NO MODO HTTP")
        sys.exit(0)
    else:
        print("\n❌ MCP SERVER COM FALHAS")
        if result.get("error"):
            print(f" Erro: {result['error']}")
        sys.exit(1)