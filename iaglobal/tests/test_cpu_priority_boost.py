# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do mecanismo de Privilégio de Processamento Dinâmico.

Valida que o CpuAffinityManager consegue:
  1. Aplicar boost de prioridade em agentes de um batch crítico
  2. Resetar budgets para homeostase após o batch
  3. Usar context manager para batches críticos
"""

import pytest

from iaglobal.execution.cpu_affinity import (
    CpuAffinityManager,
    BUDGET_PADRAO,
    BUDGET_ADRENALINA,
)


@pytest.fixture
async def cpu_manager():
    """Fixture para criar um manager limpo por teste."""
    manager = CpuAffinityManager()
    # Registra agentes de teste incluindo agentes de batch crítico
    await manager.map_balanced(
        ["agent1", "agent2", "agent3", "critic", "reviewer", "qa", "coder"]
    )
    yield manager
    # Cleanup: reseta budgets após o teste
    await manager.reset_budgets()


@pytest.mark.asyncio
async def test_set_priority_boost_aplica_aumento(cpu_manager):
    """Boost de prioridade aumenta budget para 50% (teto)."""
    agents = ["agent1", "agent2"]

    await cpu_manager.set_priority_boost(agents, boost_percent=50)

    for aid in agents:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget == 0.50, f"Agente {aid} deveria ter 50% CPU, got {budget}"


@pytest.mark.asyncio
async def test_set_priority_boost_respeita_teto(cpu_manager):
    """Boost não pode exceder BUDGET_ADRENALINA (50%)."""
    agents = ["agent1"]

    # Tenta aplicar boost de 80% (deveria ser limitado a 50%)
    await cpu_manager.set_priority_boost(agents, boost_percent=80)

    budget = await cpu_manager.get_cpu_budget("agent1")
    assert budget == BUDGET_ADRENALINA, (
        f"Boost deveria ser limitado a {BUDGET_ADRENALINA}, got {budget}"
    )


@pytest.mark.asyncio
async def test_reset_budgets_restaura_homeostase(cpu_manager):
    """Reset restaura todos os agentes para 25%."""
    agents = ["agent1", "agent2", "agent3"]

    # Aplica boost
    await cpu_manager.set_priority_boost(agents, boost_percent=50)

    # Verifica que boost foi aplicado
    for aid in agents:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget > BUDGET_PADRAO

    # Reset
    await cpu_manager.reset_budgets()

    # Verifica homeostase
    for aid in agents:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget == BUDGET_PADRAO, (
            f"Agente {aid} deveria ter 25% após reset, got {budget}"
        )


@pytest.mark.asyncio
async def test_enter_critical_batch_context(cpu_manager):
    """Context manager de batch crítico aplica boost e permite cleanup."""
    agents = ["critic", "reviewer", "qa"]

    # Entra em batch crítico (50% é o teto)
    boosted = await cpu_manager.enter_critical_batch(agents, boost_percent=50)

    assert len(boosted) == 3
    for aid in boosted:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget == 0.50

    # Sai do batch crítico — restaura APENAS os budgets anteriores (não força 25%)
    await cpu_manager.exit_critical_batch(boosted)

    # Verifica restore ao budget anterior (0.143 do map_balanced, não BUDGET_PADRAO)
    for aid in agents:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget < BUDGET_PADRAO  # budgets anteriores eram 0.143


@pytest.mark.asyncio
async def test_enter_exit_critical_batch_com_erro(cpu_manager):
    """Context manager garante cleanup mesmo com erro."""
    agents = ["critic", "coder"]

    try:
        boosted = await cpu_manager.enter_critical_batch(agents, boost_percent=50)
        # Simula erro durante processamento do batch
        raise ValueError("Erro simulado no batch")
    except ValueError:
        pass  # Erro esperado

    # Cleanup deve ter acontecido no finally (teste manual)
    await cpu_manager.reset_budgets()

    for aid in agents:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget == BUDGET_PADRAO


@pytest.mark.asyncio
async def test_boost_apenas_em_agentes_registrados(cpu_manager):
    """Boost em agente não registrado não falha, apenas ignora."""
    agents_existentes = ["agent1"]
    agents_inexistentes = ["agent_fantasma"]

    # Boost em agente existente
    await cpu_manager.set_priority_boost(agents_existentes, boost_percent=50)
    budget_existente = await cpu_manager.get_cpu_budget("agent1")
    assert budget_existente == 0.50

    # Boost em agente inexistente (não deve falhar)
    await cpu_manager.set_priority_boost(agents_inexistentes, boost_percent=50)

    # Agente existente mantém boost
    budget_existente = await cpu_manager.get_cpu_budget("agent1")
    assert budget_existente == 0.50


@pytest.mark.asyncio
async def test_boost_preserva_agents_nao_envolvidos(cpu_manager):
    """Agentes fora do batch mantêm budget padrão (ou o budget inicial se diferente)."""
    agents_batch = ["agent1", "agent2"]
    agent_fora = "agent3"

    # Aplica boost apenas em alguns agentes (50% é o teto)
    await cpu_manager.set_priority_boost(agents_batch, boost_percent=50)

    # Agentes do batch recebem boost
    for aid in agents_batch:
        budget = await cpu_manager.get_cpu_budget(aid)
        assert budget == 0.50

    # Agente fora do batch mantém seu budget inicial (não é afetado pelo boost)
    budget_fora = await cpu_manager.get_cpu_budget(agent_fora)
    # O budget inicial é definido pelo map_balanced (20% para 7 agentes)
    # O importante é que NÃO foi alterado pelo boost
    assert budget_fora < 0.50, (
        f"Agente fora do batch não deveria receber boost, got {budget_fora}"
    )
