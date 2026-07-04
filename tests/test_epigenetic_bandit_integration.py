"""
Testes de integração: EpigeneticRegistry + BanditPolicy.
Valida o ciclo completo: Falha → Peso → Adaptação → Reward → Epigenética.
"""

import asyncio
import hashlib
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry, EpigeneticMarker
from iaglobal.graphs.bandit import BanditPolicy


@pytest.fixture
def epigenetic_registry(tmp_path):
    """Cria registry epigenético em diretório temporário."""
    return EpigeneticRegistry(base_path=tmp_path / "epigenetic")


@pytest.fixture
def bandit_policy():
    """Cria instância do BanditPolicy."""
    return BanditPolicy(epsilon=0.1, decay=0.99)


class TestEpigeneticBanditIntegration:
    """Testes de integração entre EpigeneticRegistry e BanditPolicy."""

    @pytest.mark.asyncio
    async def test_apply_bandit_reward_updates_marker(self, epigenetic_registry):
        """Deve aplicar reward do Bandit e atualizar marcador epigenético."""
        agent_id = "test_agent_001"
        task_hash = hashlib.sha3_512(b"task_example").hexdigest()[:16]
        reward = 0.85
        ivm = 0.92

        # Aplica reward
        await epigenetic_registry.apply_bandit_reward(agent_id, task_hash, reward, ivm)

        # Verifica se marker foi criado no cache (agora usa ID único com timestamp)
        # Como o ID é único por evento, verificamos que há pelo menos um marker para este agente
        assert len(epigenetic_registry._memory_cache) >= 1
        
        # Encontra o marker correto no cache
        marker_found = None
        for key, marker in epigenetic_registry._memory_cache.items():
            if marker.agent_id == agent_id and marker.task_hash == task_hash:
                marker_found = marker
                break
        
        assert marker_found is not None
        assert marker_found.reward_value == reward
        assert marker_found.ivm_score == ivm
        assert marker_found.adaptation_count == 1

        # Verifica perfil epigenético
        profile = await epigenetic_registry.get_agent_epigenetic_profile(agent_id)
        assert profile["total_markers"] >= 1
        assert profile["successes"] >= 1
        assert profile["avg_ivm"] == pytest.approx(ivm, rel=0.01)
        assert profile["avg_reward"] == reward

    @pytest.mark.asyncio
    async def test_failure_then_success_cycle(self, epigenetic_registry):
        """Ciclo completo: falha → adaptação → sucesso → reward."""
        agent_id = "test_agent_002"
        task_hash = hashlib.sha3_512(b"task_cycle").hexdigest()[:16]

        # Registra falha com IVM baixo
        await epigenetic_registry.record_failure(
            agent_id, task_hash, "TimeoutError", 
            context={"attempt": 1},
            ivm_score=0.45
        )

        # Recupera pesos adaptativos (devem estar ajustados para falha)
        weights = await epigenetic_registry.get_adaptive_weights(agent_id, task_hash)
        assert weights["retry_delay"] > 1.0  # Aumentado devido ao timeout
        assert weights["model_priority"] < 1.0  # Reduzido devido ao timeout

        # Simula sucesso após adaptação
        await epigenetic_registry.record_success(
            agent_id, task_hash,
            ivm_score=0.88,
            reward_value=0.75
        )

        # Verifica perfil completo
        profile = await epigenetic_registry.get_agent_epigenetic_profile(agent_id)
        assert profile["total_markers"] == 2
        assert profile["successes"] == 1
        assert profile["failures"] == 1
        assert profile["avg_ivm"] > 0.45  # Melhorou após adaptação

    @pytest.mark.asyncio
    async def test_multiple_rewards_accumulate(self, epigenetic_registry):
        """Múltiplos rewards devem acumular adaptações."""
        agent_id = "test_agent_003"
        task_hash = hashlib.sha3_512(b"task_multi").hexdigest()[:16]

        # Aplica múltiplos rewards
        for i in range(5):
            await epigenetic_registry.apply_bandit_reward(
                agent_id, task_hash,
                reward=0.8 + (i * 0.02),
                ivm=0.9 + (i * 0.01)
            )

        # Verifica acumulação
        profile = await epigenetic_registry.get_agent_epigenetic_profile(agent_id)
        assert profile["successes"] == 5
        assert profile["avg_reward"] == pytest.approx(0.84, rel=0.01)
        assert profile["avg_ivm"] == pytest.approx(0.92, rel=0.01)

    @pytest.mark.asyncio
    async def test_bandit_policy_integration(self, epigenetic_registry, bandit_policy):
        """Integração completa: Bandit seleciona → Executa → Reward → Epigenética."""
        agent_id = "bandit_test_agent"
        task_hash = hashlib.sha3_512(b"bandit_task").hexdigest()[:16]
        
        # Bandit seleciona um provider
        providers = ["gpt-4", "claude-3", "gemini-pro"]
        selected = bandit_policy.select_arm(providers)
        
        # Simula execução bem-sucedida
        reward = 0.9
        ivm = 0.88
        
        # Bandit atualiza reward
        bandit_policy.update_reward(selected, reward, ivm)
        
        # Epigenetic registra o reward
        await epigenetic_registry.apply_bandit_reward(
            agent_id, task_hash, reward, ivm
        )
        
        # Verifica se ambos registraram
        assert bandit_policy.weights[selected] > 0
        profile = await epigenetic_registry.get_agent_epigenetic_profile(agent_id)
        assert profile["successes"] == 1
        assert profile["avg_ivm"] == ivm


class TestEpigeneticProfile:
    """Testes de perfil epigenético de agentes."""

    @pytest.mark.asyncio
    async def test_empty_profile(self, epigenetic_registry):
        """Perfil de agente sem registros deve retornar zeros."""
        profile = await epigenetic_registry.get_agent_epigenetic_profile("unknown_agent")
        
        assert profile["total_markers"] == 0
        assert profile["successes"] == 0
        assert profile["failures"] == 0
        assert profile["avg_ivm"] == 0.0
        assert profile["avg_reward"] == 0.0

    @pytest.mark.asyncio
    async def test_mixed_profile(self, epigenetic_registry):
        """Perfil com sucessos e falhas misturados."""
        agent_id = "mixed_agent"
        
        # Registra 3 sucessos
        for i in range(3):
            await epigenetic_registry.record_success(
                agent_id, f"task_{i}",
                ivm_score=0.8 + (i * 0.05),
                reward_value=0.7 + (i * 0.1)
            )
        
        # Registra 2 falhas
        for i in range(2):
            await epigenetic_registry.record_failure(
                agent_id, f"task_fail_{i}",
                error_type="SecurityRejection",
                context={"reason": "unsafe_code"},
                ivm_score=0.3
            )
        
        profile = await epigenetic_registry.get_agent_epigenetic_profile(agent_id)
        
        assert profile["total_markers"] == 5
        assert profile["successes"] == 3
        assert profile["failures"] == 2
        assert profile["avg_ivm"] > 0.7  # Média dos sucessos
        assert len(profile["adaptation_events"]) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
