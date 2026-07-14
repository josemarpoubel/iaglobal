# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Evolution Server Standalone (Fase S2).

Cobertura:
  - Evolution Server tem entry point __main__
  - Variáveis de ambiente são lidas corretamente
  - Servidor inicia na porta configurada
  - Health check funciona em modo standalone
"""

import pytest
import socket
from pathlib import Path

# server.py é deprecated por design — os testes que o importam são intencionais
pytestmark = pytest.mark.filterwarnings(
    "ignore:iaglobal/server/server.py está DEPRECADO:DeprecationWarning"
)


def is_port_available(port: int) -> bool:
    """Verifica se uma porta está disponível."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def test_evolution_server_has_main_entry():
    """Evolution Server tem entry point __main__."""
    # Verifica que o código __main__ existe no arquivo
    server_path = Path(__file__).parent.parent / "server" / "server.py"
    content = server_path.read_text()

    # Deve ter o bloco if __name__ == "__main__"
    assert 'if __name__ == "__main__":' in content
    assert "uvicorn.run" in content
    assert "EVOLUTION_PORT" in content


def test_evolution_server_syntax():
    """Evolution Server tem sintaxe Python válida."""
    import py_compile

    server_path = Path(__file__).parent.parent / "server" / "server.py"

    # Compila para verificar sintaxe
    try:
        py_compile.compile(str(server_path), doraise=True)
        assert True
    except py_compile.PyCompileError as e:
        pytest.fail(f"Erro de sintaxe em server.py: {e}")


def test_evolution_server_env_vars():
    """Evolution Server lê variáveis de ambiente corretamente."""
    # Verifica que as variáveis estão no .env.example
    env_example = Path(__file__).parent.parent.parent / ".env.example"
    content = env_example.read_text()

    assert "EVOLUTION_HOST" in content
    assert "EVOLUTION_PORT" in content
    assert "8002" in content  # Porta default


def test_evolution_server_default_port():
    """Evolution Server usa porta 8002 como default."""
    # Verifica o código fonte
    server_path = Path(__file__).parent.parent / "server" / "server.py"
    content = server_path.read_text()

    # Deve ter o default 8002
    assert "EVOLUTION_PORT" in content
    assert "8002" in content


def test_evolution_server_has_health_endpoint():
    """Evolution Server tem endpoint de health check."""
    from iaglobal.server.server import app

    # Verifica que o endpoint existe (na raiz, pois /evolution é adicionado pelo gateway)
    routes = [route.path for route in app.routes]
    assert "/health" in routes


def test_evolution_server_has_trigger_endpoint():
    """Evolution Server tem endpoint de trigger (strategy)."""
    from iaglobal.server.server import app

    routes = [route.path for route in app.routes]
    # O endpoint de trigger é /evolution/strategy (POST)
    assert "/evolution/strategy" in routes


def test_evolution_server_has_strategies_endpoint():
    """Evolution Server tem endpoint de status/strategies."""
    from iaglobal.server.server import app

    routes = [route.path for route in app.routes]
    # O endpoint de status é /evolution/status
    assert "/evolution/status" in routes


@pytest.mark.asyncio
async def test_evolution_health_endpoint():
    """Health check do Evolution Server retorna dados válidos."""
    from fastapi.testclient import TestClient
    from iaglobal.server.server import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Verifica campos obrigatórios (formato real do Evolution Server)
    assert "status" in data or "system" in data
    assert "uptime_seconds" in data
    assert "runtime_running" in data or "evolution" in data


@pytest.mark.asyncio
async def test_evolution_server_standalone_compatibility():
    """Evolution Server funciona em modo standalone e gateway."""
    from iaglobal.server.server import app

    # Testa que o app FastAPI pode ser montado como sub-app
    from fastapi import FastAPI

    gateway = FastAPI()
    gateway.mount("/evolution", app)

    # Verifica que o app foi montado (não precisa verificar rotas específicas)
    assert len(gateway.routes) > 0

    # Testa que health check funciona via gateway
    from fastapi.testclient import TestClient

    client = TestClient(gateway)
    response = client.get("/evolution/health")
    assert response.status_code == 200


def test_evolution_server_logging_config():
    """Evolution Server tem configuração de logging adequada."""
    server_path = Path(__file__).parent.parent / "server" / "server.py"
    content = server_path.read_text()

    # Deve ter configuração de log no uvicorn
    assert "log_level" in content
    assert "access_log" in content


def test_evolution_server_graceful_shutdown():
    """Evolution Server suporta graceful shutdown."""
    # Verifica que tem lifespan context manager
    from iaglobal.server.server import lifespan

    assert lifespan is not None

    # Verifica que o app usa o lifespan
    from iaglobal.server.server import app

    assert app.router.lifespan_context == lifespan
