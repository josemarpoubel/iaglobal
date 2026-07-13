# scripts/test_mcp_endpoints.py
"""
Testa os endpoints do MCP Server sem dependências.
"""

import requests


BASE_URL = "http://localhost:8000/mcp"


def test_health():
    """Testa endpoint /health."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP Health: {data.get('status')}")
            print(f"   Metabolic Health: {data.get('metabolic_health', {}).get('status', 'N/A')}")
            return True
        else:
            print(f"❌ Health retornou status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha ao acessar /health: {e}")
    return False


def test_metrics():
    """Testa endpoint /metrics."""
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=2)
        if response.status_code == 200:
            print("✅ MCP Metrics:")
            print(response.text[:200] + "...")
            return True
        else:
            print(f"❌ Metrics retornou status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha ao acessar /metrics: {e}")
    return False


def test_audit():
    """Testa endpoint /audit."""
    try:
        response = requests.get(
            f"{BASE_URL}/audit",
            auth=("iaglobal", "homeostasis"),
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP Audit: Score={data.get('score', 'N/A')}")
            print(f"   Correções: {len(data.get('corrections', []))}")
            return True
        else:
            print(f"❌ Audit retornou status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha ao acessar /audit: {e}")
    return False


if __name__ == "__main__":
    print("🔄 Testando MCP Server Endpoints")
    print("=" * 50)
    
    test_health()
    test_metrics()
    test_audit()
    
    print("=" * 50)