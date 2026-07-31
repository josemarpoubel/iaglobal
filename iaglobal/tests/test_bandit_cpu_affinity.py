# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes da integração BanditPolicy ↔ CpuAffinityManager (gate global de CPU).

Requisito: o BanditPolicy deve ENXERGAR o cpu_affinity e trabalharem juntos.
Enquanto o semáforo por modelo (`MODEL_SEMAPHORES`) limita a concorrência POR
MODELO, o CpuAffinityManager passa a limitar a concorrência GLOBAL de gerações
LLM respeitando os budgets metabólicos (estase, sobrevivência, ADRENALINE,
DEEP_SLEEP e teto configurável via env `CPU_GENERATION_CEILING`).

Contrato:
1. `begin_generation`/`end_generation` equilibram o contador de slots ativos.
2. Acima do teto (carga agregada) a reserva é REJEITADA.
3. Modo sobrevivência e DEEP_SLEEP bloqueiam novas gerações.
4. `generate()` degrada como synthetic_success (retorna "") quando o teto de
   CPU é atingido — sem estourar o event loop e SEM chamar o provider.
5. `generate()` reserva durante a geração e libera no finally.
"""

import asyncio

import pytest

from iaglobal.execution.cpu_affinity import (
    CPU_CEILING_DEEP_SLEEP,
    CpuAffinityManager,
    cpu_affinity,
)


@pytest.fixture
def bandit_module():
    import iaglobal.graphs.bandit as b

    return b


@pytest.fixture
def cpu_manager():
    """Manager limpo por teste (não-singleton) para testes do gate puro."""
    manager = CpuAffinityManager()
    yield manager


# ── 1. Reserva/libera equilibrados no gate puro ──


@pytest.mark.asyncio
async def test_begin_end_generation_equilibra_contador(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    assert await cpu_manager.begin_generation("critic") is True
    assert await cpu_manager.active_generation_count() == 1
    await cpu_manager.end_generation("critic", sucesso=True)
    assert await cpu_manager.active_generation_count() == 0


@pytest.mark.asyncio
async def test_end_generation_nao_vai_abaixo_de_zero(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    await cpu_manager.end_generation("critic", sucesso=False)
    metrics = await cpu_manager.get_metrics("critic")
    assert metrics["generations_ativas"] == 0


@pytest.mark.asyncio
async def test_generations_ativas_exposto_no_to_dict(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    await cpu_manager.begin_generation("critic")
    metrics = await cpu_manager.get_metrics("critic")
    assert metrics["generations_ativas"] == 1
    await cpu_manager.end_generation("critic", sucesso=True)


# ── 2. Teto global rejeita carga excedente ──


@pytest.mark.asyncio
async def test_teto_global_rejeita_carga_excedente(cpu_manager, monkeypatch):
    monkeypatch.setenv("CPU_GENERATION_CEILING", "0.2")
    await cpu_manager.map_balanced(["critic"])
    # Budget 25% (0.25) > teto 0.2 → primeira reserva já é rejeitada
    assert await cpu_manager.begin_generation("critic") is False


@pytest.mark.asyncio
async def test_teto_default_aceita_geracao_unica(cpu_manager, monkeypatch):
    monkeypatch.delenv("CPU_GENERATION_CEILING", raising=False)
    await cpu_manager.map_balanced(["critic"])
    assert await cpu_manager.begin_generation("critic") is True
    await cpu_manager.end_generation("critic", sucesso=True)


@pytest.mark.asyncio
async def test_teto_default_usa_todos_os_cores(cpu_manager, monkeypatch):
    monkeypatch.delenv("CPU_GENERATION_CEILING", raising=False)
    # Teto default = TODOS os núcleos da máquina (não metade, não 1 núcleo)
    assert cpu_manager._generation_ceiling() == float(cpu_manager._total_cores)
    # Com budget 25% por agente, cabem 4×cores gerações locais concorrentes
    assert cpu_manager._generation_ceiling() / 0.25 == cpu_manager._total_cores * 4


@pytest.mark.asyncio
async def test_utilizacao_alocada_pct_relativa_a_maquina(cpu_manager):
    await cpu_manager.map_balanced(["critic", "coder", "tester", "planner"])
    rep = await cpu_manager.dispersion_report()
    assert rep["capacidade_total_core_equivalentes"] == cpu_manager._total_cores
    assert rep["total_budget_alocado"] == 1.0
    assert rep["utilizacao_alocada_pct"] == pytest.approx(100.0 / cpu_manager._total_cores)


def test_local_model_concurrency_escala_com_cores(bandit_module):
    import os

    cores = os.cpu_count() or 4
    expected = max(2, cores // 2)
    assert bandit_module.BanditPolicy.LOCAL_MODEL_CONCURRENCY == expected
    # Em qualquer máquina >= 2 cores, o valor fica entre 2 e o total de cores
    assert 2 <= bandit_module.BanditPolicy.LOCAL_MODEL_CONCURRENCY <= cores


@pytest.mark.asyncio
async def test_carga_agregada_soma_budgets_dos_slots(cpu_manager, monkeypatch):
    # Teto 0.45: comporta critic (0.25) + planner (0.20), mas não um terceiro
    monkeypatch.setenv("CPU_GENERATION_CEILING", "0.45")
    await cpu_manager.map_balanced(["critic", "planner", "coder"])
    await cpu_manager.set_cpu_budget("critic", 0.25)
    await cpu_manager.set_cpu_budget("planner", 0.20)
    await cpu_manager.set_cpu_budget("coder", 0.25)
    assert await cpu_manager.begin_generation("critic") is True
    assert await cpu_manager.begin_generation("planner") is True
    assert await cpu_manager.begin_generation("coder") is False


# ── 3. Modos metabólicos: sobrevivência e DEEP_SLEEP bloqueiam ──


@pytest.mark.asyncio
async def test_sobrevivencia_rejeita_slot(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    await cpu_manager.survival_mode("critic")
    assert await cpu_manager.begin_generation("critic") is False
    await cpu_manager.restore_budget("critic")
    assert await cpu_manager.begin_generation("critic") is True


@pytest.mark.asyncio
async def test_deep_sleep_limita_a_uma_geracao(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    cpu_manager._metabolic_state = "DEEP_SLEEP"
    assert cpu_manager._generation_ceiling() == CPU_CEILING_DEEP_SLEEP
    # DEEP_SLEEP restringe a 1 geração ativa (0.25 core-equivalente)
    assert await cpu_manager.begin_generation("critic") is True
    assert await cpu_manager.begin_generation("critic") is False


@pytest.mark.asyncio
async def test_adrenalina_expande_teto_para_cores(cpu_manager):
    await cpu_manager.map_balanced(["critic"])
    cpu_manager._metabolic_state = "ADRENALINE"
    assert cpu_manager._generation_ceiling() == float(cpu_manager._total_cores)


# ── 4. Integração com generate(): degradação quando CPU saturada ──


def test_generate_degrada_quando_cpu_saturada(monkeypatch, bandit_module):
    import iaglobal.providers.provider_router as pr

    called = {"provider": 0}

    async def fake_generate(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        called["provider"] += 1
        return "não deveria ser chamado"

    async def _run():
        monkeypatch.setattr(pr, "async_route_generate", fake_generate)
        monkeypatch.setenv("CPU_GENERATION_CEILING", "0.01")
        bp = bandit_module._get_bandit()
        bp.weights.clear()
        bp.rewards.clear()
        bp.circuit_breakers.clear()
        if bp.credit_engine is not None:
            try:
                bp.credit_engine.stats.clear()
            except Exception:
                pass

        async def _fake_acquire(self, model_name, node_id="", execution_id=""):
            return True

        monkeypatch.setattr(bandit_module.BanditPolicy, "acquire_model", _fake_acquire)
        out = await bp.generate(
            node_id="critic",
            prompt="hello",
            candidates=[
                "groq/llama-3.3-70b-versatile",
                "ollama/qwen2.5:0.5b",
            ],
        )
        assert bp._cpu_slot_acquired is False
        return out

    out = asyncio.run(_run())
    assert out == ""
    assert called["provider"] == 0
    assert asyncio.run(cpu_affinity.active_generation_count()) == 0


def test_generate_atravessa_gate_e_libera_slot(monkeypatch, bandit_module):
    import iaglobal.providers.provider_router as pr

    captured = {}

    async def fake_generate(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        captured["model"] = model
        captured["active_during_gen"] = await cpu_affinity.active_generation_count()
        return "ok"

    async def _run():
        monkeypatch.setattr(pr, "async_route_generate", fake_generate)
        monkeypatch.setenv("CPU_GENERATION_CEILING", "4.0")
        bp = bandit_module._get_bandit()
        bp.weights.clear()
        bp.rewards.clear()
        bp.circuit_breakers.clear()
        if bp.credit_engine is not None:
            try:
                bp.credit_engine.stats.clear()
            except Exception:
                pass

        async def _fake_acquire(self, model_name, node_id="", execution_id=""):
            return True

        monkeypatch.setattr(bandit_module.BanditPolicy, "acquire_model", _fake_acquire)
        return await bp.generate(
            node_id="critic",
            prompt="hello",
            candidates=["groq/llama-3.3-70b-versatile", "ollama/qwen2.5:0.5b"],
        )

    out = asyncio.run(_run())
    assert out == "ok"
    assert captured["model"] is not None
    # Durante a geração o bandit mantém o slot reservado no cpu_affinity
    assert captured["active_during_gen"] == 1
    # Após o finally, o slot é liberado
    assert asyncio.run(cpu_affinity.active_generation_count()) == 0
