# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Health Check Unificado (Fase S1).

Cobertura:
  - Health aggregator coleta saúde de todos os serviços
  - Timeout de um serviço não quebra health check inteiro
  - Status geral é calculado corretamente
  - Estado metabólico (IVM) é coletado
  - Estado de CPU é coletado
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from iaglobal.server.health_aggregator import (
    HealthAggregator,
    ServiceHealth,
)


@pytest.fixture
def aggregator():
    """Fixture para criar um aggregator de teste."""
    return HealthAggregator()


@pytest.mark.asyncio
async def test_health_aggregator_check_all(aggregator):
    """Health aggregator consulta todos os serviços em paralelo."""
    # Mock das respostas HTTP
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "uptime": 100.0,
    }

    with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
        health_map = await aggregator.check_all()

    # Verifica que todos os serviços foram consultados
    assert len(health_map) == 4
    assert set(health_map.keys()) == {"gateway", "mcp", "ui", "evolution"}

    # Verifica que todos estão healthy (mock)
    for name, health in health_map.items():
        assert health.status == "healthy"
        assert health.name == name


@pytest.mark.asyncio
async def test_health_timeout_doesnt_crash(aggregator):
    """Timeout de um serviço não quebra health check inteiro."""

    # Mock: MCP tem timeout, outros OK
    async def mock_get(url, **kwargs):
        if "8100" in url:  # MCP
            raise httpx.TimeoutException("Timeout")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "uptime": 100.0}
        return mock_response

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        health_map = await aggregator.check_all()

    # MCP está unhealthy, outros healthy
    assert health_map["mcp"].status == "unhealthy"
    assert "timeout" in health_map["mcp"].error.lower()

    assert health_map["gateway"].status == "healthy"
    assert health_map["ui"].status == "healthy"
    assert health_map["evolution"].status == "healthy"


@pytest.mark.asyncio
async def test_compute_overall_status_all_healthy(aggregator):
    """Status geral é 'healthy' quando todos estão healthy."""
    health_map = {
        "gateway": ServiceHealth("gateway", "healthy"),
        "mcp": ServiceHealth("mcp", "healthy"),
        "ui": ServiceHealth("ui", "healthy"),
        "evolution": ServiceHealth("evolution", "healthy"),
    }

    status = aggregator.compute_overall_status(health_map)
    assert status == "healthy"


@pytest.mark.asyncio
async def test_compute_overall_status_degraded(aggregator):
    """Status geral é 'degraded' quando algum está degraded."""
    health_map = {
        "gateway": ServiceHealth("gateway", "healthy"),
        "mcp": ServiceHealth("mcp", "degraded"),
        "ui": ServiceHealth("ui", "healthy"),
        "evolution": ServiceHealth("evolution", "healthy"),
    }

    status = aggregator.compute_overall_status(health_map)
    assert status == "degraded"


@pytest.mark.asyncio
async def test_compute_overall_status_unhealthy(aggregator):
    """Status geral é 'unhealthy' quando algum está unhealthy."""
    health_map = {
        "gateway": ServiceHealth("gateway", "healthy"),
        "mcp": ServiceHealth("mcp", "unhealthy"),
        "ui": ServiceHealth("ui", "healthy"),
        "evolution": ServiceHealth("evolution", "healthy"),
    }

    status = aggregator.compute_overall_status(health_map)
    assert status == "unhealthy"


@pytest.mark.asyncio
async def test_compute_overall_status_gateway_critical(aggregator):
    """Gateway unhealthy é crítico → status 'unhealthy'."""
    health_map = {
        "gateway": ServiceHealth("gateway", "unhealthy"),
        "mcp": ServiceHealth("mcp", "healthy"),
        "ui": ServiceHealth("ui", "healthy"),
        "evolution": ServiceHealth("evolution", "healthy"),
    }

    status = aggregator.compute_overall_status(health_map)
    assert status == "unhealthy"


@pytest.mark.asyncio
async def test_get_metabolic_state(aggregator):
    """Estado metabólico coleta IVM e agentes."""
    # Mock do IVMAxiom
    mock_ivm = MagicMock()
    mock_ivm.get_ranking.return_value = [
        {"agent_name": "coder", "current_ivm": 0.85},  # excelente (>= 0.8)
        {"agent_name": "debugger", "current_ivm": 0.75},  # bom
        {"agent_name": "orchestrator", "current_ivm": 0.25},  # critico (< 0.3)
    ]

    mock_chappie = {"ivm": mock_ivm}

    # Mock _get_chappie dentro do módulo health_aggregator
    with patch("iaglobal.chappie._get_chappie", return_value=mock_chappie):
        metabolic = await aggregator.get_metabolic_state()

    assert metabolic["ivm_medio"] > 0
    assert metabolic["peak_ivm"] == 0.85
    assert metabolic["agents_ativos"] == 3
    assert metabolic["agents_excelentes"] == 1  # >= 0.8 (apenas coder)
    assert metabolic["agents_criticos"] == 1  # < 0.3 (orchestrator)


@pytest.mark.asyncio
async def test_get_metabolic_state_ivm_unavailable(aggregator):
    """Estado metabólico lida com IVM indisponível."""
    with patch("iaglobal.chappie._get_chappie", return_value={}):
        metabolic = await aggregator.get_metabolic_state()

    assert metabolic["ivm_medio"] == 0
    assert metabolic["peak_ivm"] == 0
    assert metabolic["agents_ativos"] == 0
    assert metabolic["status"] == "ivm_unavailable"


@pytest.mark.asyncio
async def test_get_cpu_state(aggregator):
    """Estado de CPU coleta budgets e métricas."""
    # Mock do CpuAffinityManager
    mock_cpu = MagicMock()
    mock_cpu.get_all_budgets = AsyncMock(
        return_value={
            "agent1": 0.25,
            "agent2": 0.50,
            "agent3": 0.25,
        }
    )
    mock_cpu.get_all_metrics = AsyncMock(
        return_value={
            "agent1": {"em_modo_sobrevivencia": False},
            "agent2": {"em_modo_sobrevivencia": False},
            "agent3": {"em_modo_sobrevivencia": True},
        }
    )

    with patch("iaglobal.execution.cpu_affinity.cpu_affinity", mock_cpu):
        cpu_state = await aggregator.get_cpu_state()

    assert cpu_state["total_budget_alocado"] == 1.0
    assert cpu_state["agents_com_budget"] == 3
    assert cpu_state["agents_em_sobrevivencia"] == 1
    assert cpu_state["budget_medio"] > 0


@pytest.mark.asyncio
async def test_health_endpoint_consolidated():
    """Endpoint /health retorna saúde consolidada."""
    from fastapi.testclient import TestClient
    from iaglobal.server.asgi import app

    client = TestClient(app)

    # Mock do health aggregator
    mock_health_map = {
        "gateway": ServiceHealth("gateway", "healthy", uptime=100),
        "mcp": ServiceHealth("mcp", "healthy", uptime=200),
        "ui": ServiceHealth("ui", "healthy", uptime=300),
        "evolution": ServiceHealth("evolution", "healthy", uptime=400),
    }

    with patch.object(HealthAggregator, "check_all", return_value=mock_health_map):
        with patch.object(
            HealthAggregator,
            "get_metabolic_state",
            return_value={
                "ivm_medio": 0.75,
                "agents_ativos": 5,
            },
        ):
            with patch.object(
                HealthAggregator,
                "get_cpu_state",
                return_value={
                    "total_budget_alocado": 1.25,
                    "agents_com_budget": 5,
                },
            ):
                response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["organism"] == "iaglobal"
    assert data["overall_status"] == "healthy"
    assert "vital_signs" in data
    assert "metabolic_state" in data
    assert "cpu_state" in data
    assert "response_time_ms" in data


@pytest.mark.asyncio
async def test_health_endpoint_partial_failure():
    """Endpoint /health lida com falha parcial."""
    from fastapi.testclient import TestClient
    from iaglobal.server.asgi import app

    client = TestClient(app)

    # Mock: MCP está unhealthy
    mock_health_map = {
        "gateway": ServiceHealth("gateway", "healthy"),
        "mcp": ServiceHealth("mcp", "unhealthy", error="timeout"),
        "ui": ServiceHealth("ui", "healthy"),
        "evolution": ServiceHealth("evolution", "healthy"),
    }

    with patch.object(HealthAggregator, "check_all", return_value=mock_health_map):
        with patch.object(
            HealthAggregator,
            "get_metabolic_state",
            return_value={
                "ivm_medio": 0.75,
                "agents_ativos": 5,
            },
        ):
            with patch.object(
                HealthAggregator,
                "get_cpu_state",
                return_value={
                    "total_budget_alocado": 1.25,
                },
            ):
                response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Status geral é unhealthy (mcp está unhealthy)
    # Nota: gateway healthy protege, mas unhealthy de qualquer serviço → unhealthy
    assert data["overall_status"] == "unhealthy"
    assert data["vital_signs"]["mcp"]["status"] == "unhealthy"
    assert "error" in data["vital_signs"]["mcp"]
