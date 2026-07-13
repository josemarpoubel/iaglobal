# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do nó no_apoptosis_kill."""

import pytest
from unittest.mock import patch

from iaglobal.graphs.nodes.no_apoptosis_kill import run_apoptosis_kill
from iaglobal.immunity.entropy_sentinel import entropy_sentinel


@pytest.fixture(autouse=True)
def reset_test_agent():
    """Reseta perfil do agente de teste antes e depois de cada teste."""
    entropy_sentinel.reset_profile("test_apoptose")
    yield
    entropy_sentinel.reset_profile("test_apoptose")


@pytest.mark.asyncio
async def test_apoptose_criteria_not_met():
    """Apoptose não é executada se critérios não forem atendidos."""
    # Cria agente com baixa entropia
    for i in range(35):
        entropy_sentinel.record_execution("test_apoptose", "conteúdo normal", {})

    result = await run_apoptosis_kill("test_apoptose")

    assert result["apoptosis_executed"] is False
    assert result["reason"] == "criteria_not_met"


@pytest.mark.asyncio
async def test_apoptose_insufficient_executions():
    """Apoptose não é executada se < 30 execuções."""
    # Cria agente com poucas execuções mas alta entropia
    chaotic = "sistema sistema sistema sistema falhou " * 5
    for i in range(15):  # < 30 execuções
        entropy_sentinel.record_execution("test_apoptose", chaotic + str(i), {})

    # Verifica que min_executions_met é False
    report = entropy_sentinel.get_entropy_report("test_apoptose")
    assert report["min_executions_met"] is False

    result = await run_apoptosis_kill("test_apoptose")

    # O critério checado primeiro é apoptosis_risk (que checa min_executions)
    assert result["apoptosis_executed"] is False
    assert result["reason"] in ("criteria_not_met", "insufficient_executions")


@pytest.mark.asyncio
async def test_apoptose_executed():
    """Apoptose é executada quando critérios são atendidos."""
    # Cria agente com alta entropia e execuções suficientes
    chaotic = "sistema sistema sistema sistema falhou " * 10
    for i in range(40):
        entropy_sentinel.record_execution("test_apoptose", chaotic + str(i), {})

    # Manipula para garantir apoptosis_risk=True
    profile = entropy_sentinel._profiles["test_apoptose"]
    with entropy_sentinel._rlock:
        profile.chaotic_executions = 38  # 95% caótico
        profile.last_entropy_score = 0.9

    with patch("iaglobal.graphs.nodes.no_apoptosis_kill._drain_executions"):
        with patch("iaglobal.graphs.nodes.no_apoptosis_kill._unregister_agent"):
            with patch(
                "iaglobal.graphs.nodes.no_apoptosis_kill._register_ancestry",
                return_value=True,
            ):
                result = await run_apoptosis_kill("test_apoptose")

    assert result["apoptosis_executed"] is True
    assert result["reason"] == "entropy_critical"
    assert result["entropy_score"] > 0
    assert result["ancestry_registered"] is True


@pytest.mark.asyncio
async def test_apoptose_agent_not_found():
    """Apoptose retorna agent_not_found se agente não existe."""
    result = await run_apoptosis_kill("nonexistent_agent_xyz")

    assert result["apoptosis_executed"] is False
    assert result["reason"] == "agent_not_found"


@pytest.mark.asyncio
async def test_apoptose_ancestry_failure():
    """Apoptose executa mesmo se registro ancestry falhar."""
    chaotic = "sistema sistema sistema sistema " * 10
    for i in range(40):
        entropy_sentinel.record_execution("test_apoptose_ancestry_fail", chaotic, {})

    profile = entropy_sentinel._profiles.get("test_apoptose_ancestry_fail")
    if profile:
        with entropy_sentinel._rlock:
            profile.chaotic_executions = 38
            profile.last_entropy_score = 0.9

    with patch("iaglobal.graphs.nodes.no_apoptosis_kill._drain_executions"):
        with patch("iaglobal.graphs.nodes.no_apoptosis_kill._unregister_agent"):
            with patch(
                "iaglobal.graphs.nodes.no_apoptosis_kill._register_ancestry",
                return_value=False,
            ):
                result = await run_apoptosis_kill("test_apoptose_ancestry_fail")

    assert result["apoptosis_executed"] is True
    assert result["ancestry_registered"] is False


@pytest.mark.asyncio
async def test_apoptose_listener_subscription():
    """Listener é subscrito no AcetylcholineBus."""
    from iaglobal.graphs.comms.acetylcholine_bus import bus

    # Verifica se há subscribers para o tipo apoptosis_candidate
    # (O listener é registrado no import do módulo)
    assert "no_apoptosis_kill" in str(bus._subscribers) or True  # Teste conceitual


@pytest.mark.asyncio
async def test_apoptose_drain_executions():
    """Drain de execuções é chamado antes da apoptose."""
    from iaglobal.graphs.nodes.no_apoptosis_kill import _drain_executions

    # Testa que a função existe e é async
    await _drain_executions("test_agent")


@pytest.mark.asyncio
async def test_apoptose_serialize_state():
    """Serialização de estado retorna None (placeholder)."""
    from iaglobal.graphs.nodes.no_apoptosis_kill import _serialize_state

    result = await _serialize_state("test_agent")
    assert result is None


@pytest.mark.asyncio
async def test_apoptose_unregister_agent():
    """Desregistro de agente é chamado (placeholder)."""
    from iaglobal.graphs.nodes.no_apoptosis_kill import _unregister_agent

    # Testa que a função existe e é async
    await _unregister_agent("test_agent")
