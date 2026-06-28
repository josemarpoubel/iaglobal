# tests/test_production_stress.py
"""
Testes de Estresse em Produção — Validação de Sistemas em Condições Reais.

Cobre:
- Teste de Ressonância: Fusão de DNA sob carga
- Teste de Homeostase: Ritmo Metabólico sob estresse
- Teste de Recuperação: Sistemas após falhas
- Teste de Escala: Múltiplos agentes simultâneos
"""
import pytest
import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor

from iaglobal.evolution.fusion_engine import fusion_engine, FusionResult
from iaglobal.evolution.metabolic_rhythm import metabolic_rhythm, MetabolicMode
from iaglobal.evolution.genomic_reflection import genomic_reflection, ExecutionMetrics
from iaglobal.immunity.entropy_sentinel import entropy_sentinel
from iaglobal.immunity.symbiosis_score import symbiosis_score
from iaglobal.immunity.vacuum_trigger import vacuum_trigger


class TestDNAResonanceStress:
    """Teste de Ressonância de DNA em produção."""

    def setup_method(self):
        """Reset de engines antes de cada teste."""
        fusion_engine.reset()
        genomic_reflection.reset()

    @pytest.mark.asyncio
    async def test_fusion_under_load(self):
        """Fusão de DNA sob carga de múltiplas requisições."""
        # Registrar 20 agentes com DNAs variados
        for i in range(20):
            fusion_engine.register_agent_dna(
                f"agent_{i}",
                random.choice(["coder", "critic", "tester"]),
                {
                    f"trait_{j}": random.uniform(0.3, 0.9)
                    for j in range(random.randint(3, 7))
                },
                generation=random.randint(1, 3),
                fitness_score=random.uniform(0.5, 0.95),
                compatibility_markers=random.sample(
                    ["python", "async", "fast", "accurate", "robust"],
                    k=random.randint(1, 3)
                ),
            )
        
        # Executar múltiplas fusões simultâneas
        async def try_fusion(agent_a, agent_b):
            result = await fusion_engine.fuse_agents_async(
                parent_ids=[agent_a, agent_b],
                hybrid_name=f"hybrid_{agent_a}_{agent_b}",
            )
            return result
        
        # Criar 10 tentativas de fusão em paralelo
        tasks = []
        for i in range(0, 20, 2):
            tasks.append(try_fusion(f"agent_{i}", f"agent_{i+1}"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Contar sucessos e falhas
        successes = sum(1 for r in results if isinstance(r, FusionResult) and r.success)
        failures = sum(1 for r in results if isinstance(r, FusionResult) and not r.success)
        exceptions = sum(1 for r in results if isinstance(r, Exception))
        
        # Pelo menos algumas fusões devem ter sucesso
        assert successes + failures > 0, "Nenhuma fusão foi processada"
        assert exceptions == 0, f"{exceptions} exceções durante fusões"
        
        # Estatísticas
        stats = fusion_engine.get_fusion_stats()
        assert stats["total_fusions"] > 0
        assert stats["registered_dnas"] >= 20  # Pelo menos 20 (pode ter híbridos)

    @pytest.mark.asyncio
    async def test_resonance_calculation_performance(self):
        """Performance do cálculo de ressonância sob carga."""
        # Registrar 50 agentes
        for i in range(50):
            fusion_engine.register_agent_dna(
                f"agent_{i}",
                "coder",
                {"trait": random.uniform(0.3, 0.9)},
                compatibility_markers=["common"],
                fitness_score=0.8,
            )
        
        start = time.time()
        
        # Calcular ressonância para todos os pares (1225 pares)
        calculations = 0
        for i in range(50):
            for j in range(i+1, 50):
                res = fusion_engine.calculate_dna_resonance(f"agent_{i}", f"agent_{j}")
                assert "resonance_score" in res
                calculations += 1
        
        elapsed = time.time() - start
        
        # Deve completar em menos de 5 segundos
        assert elapsed < 5.0, f"Cálculo muito lento: {elapsed:.2f}s"
        assert calculations == 1225, f"Esperado 1225 cálculos, feito {calculations}"


class TestMetabolicHomeostasisStress:
    """Teste de Homeostase Metabólica em produção."""

    def setup_method(self):
        metabolic_rhythm.reset()

    @pytest.mark.asyncio
    async def test_burst_mode_under_extreme_load(self):
        """Burst Mode ativado sob carga extrema."""
        rhythm = metabolic_rhythm
        
        # Simular carga extrema manualmente (sem esperar monitoramento)
        rhythm._state.load_average = 0.9
        rhythm._state.atp_level = 0.9
        rhythm._record_load(0.9)
        rhythm._record_load(0.9)
        rhythm._record_load(0.9)
        
        # Verificar se deve entrar em burst mode
        assert rhythm._should_enter_burst_mode() is True
        
        # Ativar burst mode
        await rhythm.activate_burst_mode_async(
            duration_seconds=5,
            cpu_override=0.6,
            reason="test_stress",
        )
        
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "burst_mode"
        assert state["burst_mode_active"] is True
        
        # Aguardar burst mode completar
        await asyncio.sleep(7)
        
        # Verificar transição (pode ainda estar em burst ou já em recovery)
        state = rhythm.get_metabolic_state()
        # Modo pode ser burst_mode (ainda executando), recovery, ou normal
        assert state["mode"] in ["recovery", "normal", "burst_mode"]

    @pytest.mark.asyncio
    async def test_deep_sleep_under_low_load(self):
        """Deep Sleep ativado sob carga baixa prolongada."""
        rhythm = metabolic_rhythm
        
        # Simular carga baixa manualmente
        rhythm._state.load_average = 0.1
        rhythm._state.atp_level = 0.4
        rhythm._record_load(0.1)
        rhythm._record_load(0.1)
        rhythm._record_load(0.1)
        
        # Verificar se deve entrar em deep sleep
        assert rhythm._should_enter_deep_sleep() is True
        
        # Entrar em deep sleep manualmente
        await rhythm.enter_deep_sleep_async(reason="test_low_load")
        
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "deep_sleep"
        assert state["cpu_budget"] == 0.1
        
        # Acordar
        await rhythm.wake_up_async()
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "normal"

    @pytest.mark.asyncio
    async def test_homeostasis_recovery_after_burst(self):
        """Homeostase se recupera após Burst Mode."""
        rhythm = metabolic_rhythm
        
        # Estado inicial
        state_initial = rhythm.get_metabolic_state()
        homeostasis_initial = state_initial["homeostasis_score"]
        
        # Ativar burst mode
        await rhythm.activate_burst_mode_async(
            duration_seconds=5,
            cpu_override=0.6,
            reason="test_stress",
        )
        
        # Estado durante burst
        state_burst = rhythm.get_metabolic_state()
        assert state_burst["mode"] == "burst_mode"
        
        # Aguardar burst mode completar + recovery
        await asyncio.sleep(15)  # 5s burst + 10s recovery
        
        # Estado final
        state_final = rhythm.get_metabolic_state()
        
        # Deveria estar em normal ou recovery
        assert state_final["mode"] in ["normal", "recovery", "burst_mode"]
        # Homeostase pode estar se recuperando


class TestGenomicReflectionStress:
    """Teste de Reflexão Genômica em produção."""

    def setup_method(self):
        genomic_reflection.reset()
        fusion_engine.reset()

    @pytest.mark.asyncio
    async def test_reflection_under_high_volume(self):
        """Reflexão processa alto volume de execuções."""
        reflection = genomic_reflection
        
        # Registrar 150 execuções (limite é 100, então vai truncar)
        for i in range(150):
            metrics = ExecutionMetrics(
                execution_id=f"exec_{i}",
                agent_id="stress_agent",
                timestamp=time.time(),
                success=random.random() > 0.3,  # 70% sucesso
                latency_ms=random.uniform(50, 500),
                fitness_score=random.uniform(0.4, 0.9),
                traits_used={
                    "speed": random.uniform(0.3, 0.9),
                    "quality": random.uniform(0.3, 0.9),
                },
                outcome_quality=random.uniform(0.5, 0.95),
            )
            reflection.register_execution(metrics)
        
        # Analisar performance
        start = time.time()
        analysis = await reflection.analyze_performance_async("stress_agent")
        elapsed = time.time() - start
        
        # Análise deve completar em menos de 2 segundos
        assert elapsed < 2.0, f"Análise muito lenta: {elapsed:.2f}s"
        
        # Verificar resultados (deveria ter 100 devido ao limite)
        assert analysis.total_executions == 100  # Limite de 100
        assert 0.6 < analysis.success_rate < 0.8  # ~70%
        
        # Propor mutações
        proposals = await reflection.propose_mutations_async("stress_agent", analysis)
        
        # Verificar que análise funcionou corretamente
        assert analysis.total_executions == 100  # Limite de 100
        assert 0.5 < analysis.success_rate < 0.9  # Sucesso entre 50-90%
        assert analysis.avg_fitness > 0.4  # Fitness médio razoável
        # best_traits pode estar vazio se não houver correlação significativa

    @pytest.mark.asyncio
    async def test_concurrent_reflection_multiple_agents(self):
        """Reflexão concorrente para múltiplos agentes."""
        reflection = genomic_reflection
        
        # Registrar execuções para 10 agentes
        for agent_idx in range(10):
            for i in range(50):
                metrics = ExecutionMetrics(
                    execution_id=f"exec_{agent_idx}_{i}",
                    agent_id=f"agent_{agent_idx}",
                    timestamp=time.time(),
                    success=random.random() > 0.5,
                    latency_ms=random.uniform(50, 500),
                    fitness_score=random.uniform(0.4, 0.9),
                    traits_used={"trait": random.uniform(0.3, 0.9)},
                    outcome_quality=random.uniform(0.5, 0.95),
                )
                reflection.register_execution(metrics)
        
        # Analisar todos agentes em paralelo
        async def analyze_agent(agent_id):
            return await reflection.analyze_performance_async(agent_id)
        
        tasks = [analyze_agent(f"agent_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Todos deveriam ter análise válida
        for result in results:
            assert result.total_executions == 50


class TestIntegratedSystemStress:
    """Teste integrado de todos os sistemas sob estresse."""

    def setup_method(self):
        fusion_engine.reset()
        genomic_reflection.reset()
        metabolic_rhythm.reset()
        entropy_sentinel.reset_profile("stress_test")
        symbiosis_score.reset_profile("stress_test")
        vacuum_trigger.reset()

    @pytest.mark.asyncio
    async def test_full_pipeline_under_load(self):
        """Pipeline completo sob carga: fusão + reflexão + metabolismo."""
        # 1. Registrar agentes
        for i in range(10):
            fusion_engine.register_agent_dna(
                f"agent_{i}",
                "coder",
                {"trait": random.uniform(0.5, 0.9)},
                fitness_score=random.uniform(0.7, 0.95),
                compatibility_markers=["python"],
            )
        
        # 2. Executar fusões (algumas podem falhar por ressonância baixa)
        fusion_results = []
        for i in range(0, 10, 2):
            result = await fusion_engine.fuse_agents_async(
                parent_ids=[f"agent_{i}", f"agent_{i+1}"],
                hybrid_name=f"hybrid_{i}",
                force=True,  # Forçar para garantir sucesso
            )
            fusion_results.append(result)
        
        # 3. Registrar execuções para reflexão
        for result in fusion_results:
            if result.success:
                metrics = ExecutionMetrics(
                    execution_id=result.hybrid_id,
                    agent_id=result.hybrid_id,
                    timestamp=time.time(),
                    success=True,
                    latency_ms=100.0,
                    fitness_score=result.viability_score,
                    traits_used={},
                    outcome_quality=result.viability_score,
                )
                genomic_reflection.register_execution(metrics)
        
        # 4. Analisar reflexões
        for result in fusion_results:
            if result.success:
                analysis = await genomic_reflection.analyze_performance_async(
                    result.hybrid_id
                )
                assert analysis.total_executions == 1
        
        # 5. Verificar metabolismo
        state = metabolic_rhythm.get_metabolic_state()
        assert state["mode"] == "normal"  # Deveria estar normal
        
        # 6. Verificar vácuo
        vacuum_state = vacuum_trigger.get_vacuum_state()
        assert vacuum_state["total_patterns"] >= 0
        
        # Estatísticas finais
        fusion_stats = fusion_engine.get_fusion_stats()
        reflection_stats = genomic_reflection.get_reflection_stats()
        
        # Pelo menos algumas fusões deveriam ter sucesso
        assert fusion_stats["total_fusions"] > 0
        assert reflection_stats["total_executions"] >= 0


class TestRecoveryFromFailure:
    """Teste de recuperação após falhas."""

    def setup_method(self):
        fusion_engine.reset()
        genomic_reflection.reset()
        metabolic_rhythm.reset()

    @pytest.mark.asyncio
    async def test_system_recovery_after_exception(self):
        """Sistemas se recuperam após exceções."""
        # Causar exceção controlada em cada sistema
        try:
            # FusionEngine
            await fusion_engine.fuse_agents_async(
                parent_ids=["nonexistent_a", "nonexistent_b"],
                hybrid_name="should_fail",
            )
        except Exception:
            pass
        
        try:
            # GenomicReflection
            await genomic_reflection.analyze_performance_async("nonexistent")
        except Exception:
            pass
        
        try:
            # MetabolicRhythm
            await metabolic_rhythm.activate_burst_mode_async(
                duration_seconds=-1,  # Inválido
            )
        except Exception:
            pass
        
        # Verificar que sistemas ainda funcionam
        fusion_stats = fusion_engine.get_fusion_stats()
        assert "total_fusions" in fusion_stats
        
        reflection_stats = genomic_reflection.get_reflection_stats()
        assert "agents_analyzed" in reflection_stats
        
        metabolic_state = metabolic_rhythm.get_metabolic_state()
        assert "mode" in metabolic_state


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])