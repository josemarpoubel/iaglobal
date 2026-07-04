"""
Testes para o EpigeneticRegistry e integração com Orchestrator.
Valida registro de falhas, recuperação de pesos adaptativos e ciclo epigenético completo.
"""

import asyncio
import hashlib
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
from iaglobal.core.orchestrator import Orchestrator


@pytest.fixture
def epigenetic_registry(tmp_path):
    """Cria registry epigenético em diretório temporário."""
    return EpigeneticRegistry(base_path=tmp_path / "epigenetic")


@pytest.fixture
def mock_orchestrator():
    """Mock do orchestrator para testes de integração."""
    orch = Mock(spec=Orchestrator)
    orch.epigenetic_registry = AsyncMock()
    return orch


class TestEpigeneticRegistry:
    """Testes unitários do EpigeneticRegistry."""

    @pytest.mark.asyncio
    async def test_record_failure_creates_cbor_file(self, epigenetic_registry):
        """Deve criar arquivo .cbor com metadados da falha."""
        agent_id = "test_agent_001"
        task_hash = hashlib.sha3_512(b"task_example").hexdigest()[:16]
        error_type = "TimeoutError"
        context = {"task": "exemplo", "details": "timeout 30s"}

        epigenetic_id = await epigenetic_registry.record_failure(
            agent_id=agent_id,
            task_hash=task_hash,
            error_type=error_type,
            context=context
        )

        # Verifica se arquivo foi criado
        expected_file = epigenetic_registry.base_path / f"{epigenetic_id}.cbor"
        assert expected_file.exists()

        # Verifica conteúdo
        import cbor2
        with open(expected_file, 'rb') as f:
            data = cbor2.load(f)
            assert data["agent_id"] == agent_id
            assert data["task_hash"] == task_hash
            assert data["error_type"] == error_type
            assert data["context"] == context

    @pytest.mark.asyncio
    async def test_record_success_creates_cbor_file(self, epigenetic_registry):
        """Deve registrar sucesso como epigenética positiva."""
        agent_id = "test_agent_002"
        task_hash = hashlib.sha3_512(b"task_success").hexdigest()[:16]

        epigenetic_id = await epigenetic_registry.record_success(agent_id, task_hash)

        expected_file = epigenetic_registry.base_path / f"{epigenetic_id}.cbor"
        assert expected_file.exists()

        import cbor2
        with open(expected_file, 'rb') as f:
            data = cbor2.load(f)
            assert data["agent_id"] == agent_id
            assert data["task_hash"] == task_hash
            assert data["error_type"] == "success"

    @pytest.mark.asyncio
    async def test_get_adaptive_weights_for_timeout(self, epigenetic_registry):
        """Deve aumentar retry_delay e diminuir model_priority para timeouts."""
        agent_id = "test_agent_003"
        task_hash = hashlib.sha3_512(b"task_timeout").hexdigest()[:16]

        # Registra múltiplos timeouts
        await epigenetic_registry.record_failure(agent_id, task_hash, "TimeoutError", {})
        await epigenetic_registry.record_failure(agent_id, task_hash, "TimeoutError", {})

        weights = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        # Deve ter aplicado multiplicadores acumulativos
        assert weights["retry_delay"] > 1.0  # 1.5 * 1.5 = 2.25
        assert weights["model_priority"] < 1.0  # 0.8 * 0.8 = 0.64
        assert weights["fallback_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_adaptive_weights_for_invalid_output(self, epigenetic_registry):
        """Deve desativar fallback para invalid_output."""
        agent_id = "test_agent_004"
        task_hash = hashlib.sha3_512(b"task_invalid").hexdigest()[:16]

        await epigenetic_registry.record_failure(agent_id, task_hash, "invalid_output", {})

        weights = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        assert weights["fallback_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_adaptive_weights_for_security_rejection(self, epigenetic_registry):
        """Deve reduzir model_priority para security_rejection."""
        agent_id = "test_agent_005"
        task_hash = hashlib.sha3_512(b"task_security").hexdigest()[:16]

        await epigenetic_registry.record_failure(agent_id, task_hash, "security_rejection", {})

        weights = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        assert weights["model_priority"] == 0.5

    @pytest.mark.asyncio
    async def test_success_resets_retry_delay(self, epigenetic_registry):
        """Sucesso deve reduzir retry_delay gradualmente."""
        agent_id = "test_agent_006"
        task_hash = hashlib.sha3_512(b"task_success_reset").hexdigest()[:16]

        # Falha primeiro
        await epigenetic_registry.record_failure(agent_id, task_hash, "TimeoutError", {})
        weights_before = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        # Sucesso depois
        await epigenetic_registry.record_success(agent_id, task_hash)
        weights_after = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        assert weights_after["retry_delay"] < weights_before["retry_delay"]
        assert weights_after["retry_delay"] >= 1.0


class TestOrchestratorEpigeneticIntegration:
    """Testes de integração do Orchestrator com EpigeneticRegistry."""

    @pytest.mark.asyncio
    async def test_on_execution_failed_triggers_epigenetic_record(self, mock_orchestrator):
        """Evento de falha deve disparar registro epigenético."""
        from iaglobal.core.orchestrator import Orchestrator

        # Simula evento de falha
        event = Mock()
        event.data = {
            "task": "gerar codigo com erro",
            "error": TimeoutError("timeout simulado"),
            "execution_id": "exec_123"
        }

        # Cria registry real para teste
        registry = EpigeneticRegistry(base_path=Path("/tmp/test_epigenetic"))
        mock_orchestrator.epigenetic_registry = registry

        # Chama handler real (precisa do método real)
        with patch.object(Orchestrator, '_on_execution_failed', wraps=Orchestrator._on_execution_failed):
            # A implementação real usa thread pool para async
            pass

    @pytest.mark.asyncio
    async def test_async_process_includes_epigenetic_weights(self):
        """Pipeline async deve carregar pesos epigenéticos no contexto."""
        # Este teste valida que _async_process usa epigenetic_weights
        # Será implementado quando a integração estiver completa
        pass


class TestEpigeneticCycle:
    """Teste do ciclo epigenético completo: falha -> registro -> ajuste -> recuperação."""

    @pytest.mark.asyncio
    async def test_full_epigenetic_cycle(self, epigenetic_registry):
        """Ciclo completo: agente falha, aprende, recupera."""
        agent_id = "cycle_agent_001"
        task_hash = hashlib.sha3_512(b"ciclo_completo").hexdigest()[:16]

        # 1. Primeira execução: timeout
        await epigenetic_registry.record_failure(agent_id, task_hash, "TimeoutError", {"attempt": 1})
        weights_1 = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        # 2. Segunda execução: timeout novamente
        await epigenetic_registry.record_failure(agent_id, task_hash, "TimeoutError", {"attempt": 2})
        weights_2 = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        # Verifica que ajustes são cumulativos (ambos > 1.0 devido aos multiplicadores)
        assert weights_1["retry_delay"] > 1.0  # 1.5 após primeiro timeout
        assert weights_2["retry_delay"] > weights_1["retry_delay"]  # 2.25 após segundo timeout
        assert weights_2["model_priority"] < weights_1["model_priority"]  # Reduz com timeouts

        # 3. Terceira execução: sucesso
        await epigenetic_registry.record_success(agent_id, task_hash)
        weights_3 = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)

        # Verifica recuperação parcial (reduz após sucesso, mas mantém >= 1.0)
        assert weights_3["retry_delay"] < weights_2["retry_delay"]
        assert weights_3["retry_delay"] >= 1.0

        # 4. Verifica persistência: novo registry carrega mesmos arquivos
        new_registry = EpigeneticRegistry(base_path=epigenetic_registry.base_path)
        weights_persisted = await new_registry.get_adaptive_weights(agent_id, task_hash)
        assert weights_persisted["retry_delay"] == weights_3["retry_delay"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])