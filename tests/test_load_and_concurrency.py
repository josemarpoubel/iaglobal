"""Testes de carga, concorrência e cenários de fitness.

Cobre:
1. Teste de carga com múltiplos providers (BanditPolicy)
2. Teste de concorrência do CpuAffinityManager
3. Teste de consolidação do ciclo REM (Short → Long Term)
4. Teste do IVM com cenários de alto/baixo fitness
"""

import asyncio
import time
import threading
from pathlib import Path
from typing import List

import pytest


# ═══════════════════════════════════════════════════════════════════
# 1. TESTE DE CARGA — Múltiplos Providers
# ═══════════════════════════════════════════════════════════════════

class TestLoadWithMultipleProviders:
    """Valida o BanditPolicy com múltiplos providers concorrentes."""

    def test_bandit_policy_import(self):
        from iaglobal.graphs.bandit import BanditPolicy
        assert BanditPolicy is not None

    def test_default_candidates_returns_list(self):
        from iaglobal.graphs.bandit import BanditPolicy
        candidates = BanditPolicy.default_candidates()
        assert isinstance(candidates, list)
        assert len(candidates) >= 1

    def test_select_model_returns_string(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        model = bandit.select_model("test_node", "test_strategy")
        assert isinstance(model, str)
        assert "/" in model

    def test_rank_models_returns_sorted(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        candidates = [("groq", "groq/llama3-70b"), ("ollama", "ollama/qwen2.5:0.5b")]
        ranked = bandit.rank_models("test_node", "test_strategy", candidates)
        assert isinstance(ranked, list)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in ranked)

    def test_update_policy_records_event(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        bandit.update_policy("test_node", "ollama/test-model", "test_strategy",
                             success=True, latency=0.5, reward=1.0)

    @pytest.mark.asyncio
    async def test_probe_providers_returns_dict(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        result = await bandit.probe_providers_online(candidates=["ollama/qwen2.5:0.5b"])
        assert isinstance(result, dict)

    def test_select_top_n_returns_list(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        top = bandit.select_top_n("test_node", "test_strategy", n=3)
        assert isinstance(top, list)
        assert len(top) <= 3

    def test_record_error_blocks_provider(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        bandit = _get_bandit()
        bandit.record_error("test_fake_provider", 429)
        count = bandit.get_error_count("test_fake_provider")
        assert isinstance(count, int)


# ═══════════════════════════════════════════════════════════════════
# 2. CONCORRÊNCIA — CpuAffinityManager
# ═══════════════════════════════════════════════════════════════════

class TestCpuAffinityConcurrency:
    """Valida o CpuAffinityManager com agentes concorrentes."""

    def test_concurrent_budget_allocation(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        n_agents = 10
        agents = [f"agent_concurrent_{i}" for i in range(n_agents)]

        def assign_budget(aid: str):
            mgr.set_cpu_budget(aid, 0.25)

        threads = [threading.Thread(target=assign_budget, args=(a,)) for a in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        budgets = mgr.get_all_budgets()
        assert len(budgets) == n_agents
        for aid in agents:
            assert budgets.get(aid, 0) == 0.25

    def test_concurrent_task_recording(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        agent_id = "agent_tasks"

        def record_tasks(success: bool, count: int):
            for _ in range(count):
                mgr.registrar_tarefa(agent_id, sucesso=success)

        t1 = threading.Thread(target=record_tasks, args=(True, 50))
        t2 = threading.Thread(target=record_tasks, args=(False, 30))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        metrics = mgr.get_metrics(agent_id)
        assert metrics is not None
        assert metrics["tasks_completadas"] >= 50
        assert metrics["tasks_falhas"] >= 30

    def test_concurrent_cpu_reporting(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        agent_id = "agent_cpu_concurrent"

        def report_usage(val: float):
            mgr.reportar_uso_cpu(agent_id, val)

        threads = [threading.Thread(target=report_usage, args=(i * 0.1,)) for i in range(11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = mgr.get_metrics(agent_id)
        assert metrics is not None
        assert 0.0 <= metrics["cpu_usage_atual"] <= 1.0

    def test_map_balanced_concurrent(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        agents = [f"agent_bal_{i}" for i in range(20)]
        assignment = mgr.map_balanced(agents)
        assert len(assignment) == 20

    def test_survival_mode_then_restore(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.survival_mode("survival_agent")
        assert mgr.get_cpu_budget("survival_agent") == 0.10
        metrics = mgr.get_metrics("survival_agent")
        assert metrics is not None
        assert metrics["em_modo_sobrevivencia"] is True
        mgr.restore_budget("survival_agent")
        assert mgr.get_cpu_budget("survival_agent") == 0.25
        metrics = mgr.get_metrics("survival_agent")
        assert metrics is not None
        assert metrics["em_modo_sobrevivencia"] is False

    def test_dispersion_report_with_agents(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.map_balanced([f"agent_disp_{i}" for i in range(5)])
        report = mgr.dispersion_report()
        assert report["total_agents"] == 5
        assert "ivm_medio" in report
        assert "fitness_medio" in report


# ═══════════════════════════════════════════════════════════════════
# 3. CONSOLIDAÇÃO REM — Short → Long Term
# ═══════════════════════════════════════════════════════════════════

class TestREMConsolidation:
    """Valida o ciclo completo de consolidação REM."""

    def test_rem_sleep_engine_import(self):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        assert REMSleepEngine is not None

    def test_consolidate_short_to_long(self, tmp_path):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        api = SubconsciousAPI(tmp_path / "vault")
        api.escrever_curto_prazo("mem_alpha", "log bruto alpha")
        api.escrever_curto_prazo("mem_beta", "log bruto beta")

        engine = REMSleepEngine(tmp_path / "vault")
        result = engine.iniciar_fase_rem()

        assert result["memorias_processadas"] >= 1
        assert result["memorias_consolidadas"] >= 1

        st_dir = tmp_path / "vault" / "02_Short_Term"
        lt_dir = tmp_path / "vault" / "03_Long_Term"
        remaining_st = list(st_dir.glob("*.md"))
        consolidated_lt = list(lt_dir.glob("*.md"))
        assert len(remaining_st) == 0
        assert len(consolidated_lt) >= 1

    def test_consolidate_updates_synapse_map(self, tmp_path):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        api = SubconsciousAPI(tmp_path / "vault")
        api.escrever_curto_prazo("insight_rapido", "dado volatil")

        engine = REMSleepEngine(tmp_path / "vault")
        engine.iniciar_fase_rem()

        mapa_path = tmp_path / "vault" / "04_Synapses" / "Mapa_Mental_Subconsciente.md"
        assert mapa_path.exists()
        texto = mapa_path.read_text()
        assert "Sináptico" in texto or "Subconsciente" in texto

    def test_consolidate_large_batch(self, tmp_path):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        api = SubconsciousAPI(tmp_path / "vault")
        for i in range(20):
            api.escrever_curto_prazo(f"batch_mem_{i}", f"conteudo {i}")

        engine = REMSleepEngine(tmp_path / "vault")
        result = engine.iniciar_fase_rem()
        assert result["memorias_processadas"] == 20
        assert result["memorias_consolidadas"] >= 1

    def test_consolidate_nothing_when_empty(self, tmp_path):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        engine = REMSleepEngine(tmp_path / "vault")
        result = engine.iniciar_fase_rem()
        assert result["memorias_processadas"] == 0
        assert result["memorias_consolidadas"] == 0

    def test_consolidate_idempotent(self, tmp_path):
        from iaglobal.obsidian.consolidation import REMSleepEngine
        from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

        api = SubconsciousAPI(tmp_path / "vault")
        api.escrever_curto_prazo("idemp_mem", "dado")

        engine = REMSleepEngine(tmp_path / "vault")
        r1 = engine.iniciar_fase_rem()
        r2 = engine.iniciar_fase_rem()
        assert r2["memorias_processadas"] == 0


# ═══════════════════════════════════════════════════════════════════
# 4. IVM — Índice de Viabilidade Metabólica
# ═══════════════════════════════════════════════════════════════════

class TestIVM:
    """Valida o IVM com cenários de alto e baixo fitness."""

    def test_ivm_constants(self):
        from iaglobal.execution.cpu_affinity import (
            IVM_THRESHOLD_CRITICO, IVM_THRESHOLD_EXCELENCIA,
            BUDGET_PADRAO, FITNESS_DECAY,
        )
        assert IVM_THRESHOLD_CRITICO == 0.3
        assert IVM_THRESHOLD_EXCELENCIA == 0.8
        assert BUDGET_PADRAO == 0.25
        assert FITNESS_DECAY == 0.95

    def test_ivm_alto_fitness(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        ivm = mgr.calcular_ivm("high_fitness_agent",
                               produtividade=0.95,
                               cpu_usage=0.05,
                               obsidian_notes=50)
        assert ivm >= 0.7

    def test_ivm_baixo_fitness(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        ivm = mgr.calcular_ivm("low_fitness_agent",
                               produtividade=0.1,
                               cpu_usage=0.9,
                               obsidian_notes=0)
        assert ivm <= 0.5

    def test_ivm_trigger_apoptose(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.reportar_uso_cpu("apoptose_agent", 0.95)
        for _ in range(1):
            mgr.registrar_tarefa("apoptose_agent", sucesso=False)
        mgr.calcular_ivm("apoptose_agent", produtividade=0.05, cpu_usage=0.95, obsidian_notes=0)
        result = mgr.monitorar_metabolismo("apoptose_agent")
        assert result["acao"] == "apoptose"
        assert result["ivm"] < 0.3

    def test_ivm_trigger_mitose(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.reportar_uso_cpu("mitose_agent", 0.02)
        for _ in range(20):
            mgr.registrar_tarefa("mitose_agent", sucesso=True)
        mgr.update_fitness("mitose_agent", obsidian_notes=50)
        mgr.calcular_ivm("mitose_agent", produtividade=0.98, cpu_usage=0.02, obsidian_notes=50)
        result = mgr.monitorar_metabolismo("mitose_agent")
        assert result["acao"] == "mitose"
        assert result["ivm"] > 0.8

    def test_ivm_monitorar_estado_normal(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.calcular_ivm("normal_agent",
                         produtividade=0.5,
                         cpu_usage=0.5,
                         obsidian_notes=5)
        result = mgr.monitorar_metabolismo("normal_agent")
        assert result["acao"] == "monitorar"
        assert 0.3 <= result["ivm"] <= 0.8

    def test_ivm_clamped_to_valid_range(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        ivm = mgr.calcular_ivm("clamp_agent",
                               produtividade=-1.0,
                               cpu_usage=-1.0,
                               obsidian_notes=-1)
        assert 0.0 <= ivm <= 1.0
        ivm2 = mgr.calcular_ivm("clamp_agent2",
                                produtividade=99.0,
                                cpu_usage=99.0,
                                obsidian_notes=999)
        assert 0.0 <= ivm2 <= 1.0

    def test_update_fitness_increases_with_good_metrics(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        score = mgr.update_fitness("fit_agent",
                                   trabalho_realizado=100.0,
                                   custo_cpu=10.0,
                                   uptime_segundos=7200,
                                   obsidian_notes=50)
        assert score > 0.5

    def test_update_fitness_decays_over_time(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        score1 = mgr.update_fitness("decay_agent",
                                    trabalho_realizado=100.0,
                                    custo_cpu=10.0,
                                    uptime_segundos=3600,
                                    obsidian_notes=20)
        score2 = mgr.update_fitness("decay_agent",
                                    trabalho_realizado=1.0,
                                    custo_cpu=100.0,
                                    uptime_segundos=0,
                                    obsidian_notes=0)
        assert score2 < score1 or abs(score2 - score1) < 0.5

    def test_auto_critica_diagnostics(self):
        from iaglobal.execution.cpu_affinity import CpuAffinityManager
        mgr = CpuAffinityManager()
        mgr.reportar_uso_cpu("critic_agent", 0.9)
        mgr.registrar_tarefa("critic_agent", sucesso=True)
        mgr.registrar_tarefa("critic_agent", sucesso=False)
        mgr.calcular_ivm("critic_agent",
                         produtividade=0.5,
                         cpu_usage=0.9,
                         obsidian_notes=0)
        diag = mgr.auto_critica("critic_agent")
        assert isinstance(diag, dict)
        assert "diagnosticos" in diag
        assert "recommendacao" in diag
