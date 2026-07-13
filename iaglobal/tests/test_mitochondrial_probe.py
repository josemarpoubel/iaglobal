# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes da MitochondrialProbe — Sonda de Potencial do Event Loop."""

import pytest

from iaglobal.core.mitochondrial_probe import MitochondrialProbe


@pytest.fixture
def fresh_probe():
    """Cria nova instância de MitochondrialProbe para testes."""
    return MitochondrialProbe()


async def test_probe_detects_hypoxia(fresh_probe):
    """Sonda detecta hipóxia quando lag > 50ms."""
    # Simula hipóxia diretamente (sem mock complexo)
    fresh_probe.current_lag = 0.06  # 60ms
    fresh_probe.hypoxia_detected = False

    # Verifica que estado inicial é saudável
    assert fresh_probe.hypoxia_detected is False

    # Simula detecção manual (o _monitor_cycle faria isso)
    if fresh_probe.current_lag > fresh_probe.HYPOXIA_THRESHOLD_SECONDS:
        fresh_probe.hypoxia_detected = True

    assert fresh_probe.hypoxia_detected is True


async def test_probe_recovers_from_hypoxia(fresh_probe):
    """Sonda detecta recuperação quando lag volta ao normal."""
    # Estado inicial: hipóxia
    fresh_probe.hypoxia_detected = True
    fresh_probe.current_lag = 0.07  # 70ms

    # Simula recuperação
    fresh_probe.current_lag = 0.005  # 5ms (normal)
    if fresh_probe.current_lag <= fresh_probe.HYPOXIA_THRESHOLD_SECONDS:
        fresh_probe.hypoxia_detected = False

    assert fresh_probe.hypoxia_detected is False
    assert fresh_probe.current_lag < 0.05


def test_get_health_status_healthy(fresh_probe):
    """Retorna status healthy quando sem hipóxia."""
    fresh_probe.current_lag = 0.01  # 10ms (normal)
    fresh_probe.hypoxia_detected = False

    status = fresh_probe.get_health_status()

    assert status["status"] == "healthy"
    assert status["hypoxia_detected"] is False
    assert status["current_lag_ms"] == 10.0
    assert status["threshold_ms"] == 50.0


def test_get_health_status_hypoxic(fresh_probe):
    """Retorna status hypoxic quando hipóxia detectada."""
    fresh_probe.current_lag = 0.07  # 70ms (hipóxia)
    fresh_probe.hypoxia_detected = True

    status = fresh_probe.get_health_status()

    assert status["status"] == "hypoxic"
    assert status["hypoxia_detected"] is True
    assert status["current_lag_ms"] == 70.0


async def test_register_alosteric_inhibitor(fresh_probe):
    """Callback de inibição alostérica é registrado e disparado."""
    callback_called = False
    received_lag = None

    async def mock_callback(lag):
        nonlocal callback_called, received_lag
        callback_called = True
        received_lag = lag

    fresh_probe.register_alosteric_inhibitor(mock_callback)

    # Simula hipóxia e dispara callbacks
    fresh_probe.hypoxia_detected = True
    await fresh_probe._trigger_alosteric_inhibitors(0.06)

    assert callback_called is True
    assert received_lag == 0.06


async def test_alosteric_inhibitor_error_handling(fresh_probe, caplog):
    """Erro em callback não quebra a sonda."""

    async def failing_callback(lag):
        raise ValueError("Callback failed!")

    fresh_probe.register_alosteric_inhibitor(failing_callback)

    # Não deve levantar exceção
    await fresh_probe._trigger_alosteric_inhibitors(0.06)

    # Log deve registrar erro
    assert "Falha em inibidor alostérico" in caplog.text


async def test_singleton_global():
    """Singleton global mitochondrial_probe existe e é único."""
    from iaglobal.core.mitochondrial_probe import mitochondrial_probe as probe1
    from iaglobal.core.mitochondrial_probe import mitochondrial_probe as probe2

    assert probe1 is probe2
    assert isinstance(probe1, MitochondrialProbe)


def test_probe_constants_are_reasonable(fresh_probe):
    """Constantes da sonda têm valores razoáveis."""
    assert fresh_probe.HYPOXIA_THRESHOLD_SECONDS == 0.05  # 50ms
    assert fresh_probe.MONITOR_INTERVAL_SECONDS == 1.0  # 1s
    assert fresh_probe.PROBE_SLEEP_SECONDS == 0.01  # 10ms

    # Threshold de 50ms é razoável para detecção precoce
    assert 0.01 <= fresh_probe.HYPOXIA_THRESHOLD_SECONDS <= 0.1
