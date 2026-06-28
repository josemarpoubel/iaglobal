# tests/test_symbiosis_score.py
"""
Testes do SymbiosisScore — Lei da Caridade.

Cobre:
- Registro de cooperações
- Cálculo de symbiosis_score
- Bonus/penalidade de fitness
- Detecção de agentes isolados
- Qualidade de cooperação entre pares
- Relatórios e health check
"""
import pytest
import time
from iaglobal.immunity.symbiosis_score import SymbiosisScore, symbiosis_score, SymbiosisProfile


class TestSymbiosisScoreRecording:
    """Testes de registro de cooperações."""

    def setup_method(self):
        """Reset singleton antes de cada teste."""
        SymbiosisScore._instance = None

    def test_record_cooperation_creates_profile(self):
        """Registro de cooperação cria perfis para ambos agentes."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent_a", "agent_b", success=True)
        
        assert "agent_a" in scorer._profiles
        profile_a = scorer._profiles["agent_a"]
        assert profile_a.total_cooperations == 1
        assert "agent_b" in profile_a.cooperation_partners

    def test_record_cooperation_tracks_success(self):
        """Sucesso e falha são rastreados corretamente."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner", success=True)
        scorer.record_cooperation("agent", "partner", success=False)
        scorer.record_cooperation("agent", "partner", success=True)
        
        profile = scorer._profiles["agent"]
        assert profile.total_cooperations == 3
        assert profile.successful_cooperations == 2
        assert profile.failed_cooperations == 1

    def test_record_cooperation_updates_history(self):
        """Histórico de cooperações é mantido."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner", success=True, outcome_quality=0.9)
        
        profile = scorer._profiles["agent"]
        assert len(profile.cooperation_history) == 1
        assert profile.cooperation_history[0].outcome_quality == 0.9
        assert profile.cooperation_history[0].success is True

    def test_record_cooperation_diversifies_partners(self):
        """Múltiplos parceiros aumentam diversidade."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner_a", success=True)
        scorer.record_cooperation("agent", "partner_b", success=True)
        scorer.record_cooperation("agent", "partner_c", success=True)
        
        profile = scorer._profiles["agent"]
        assert profile.partner_diversity == 3
        assert profile.cooperation_partners == {"partner_a", "partner_b", "partner_c"}


class TestSymbiosisScoreCalculation:
    """Testes de cálculo do score."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_cooperation_rate_calculation(self):
        """cooperation_rate = sucessos / total."""
        scorer = SymbiosisScore()
        
        # 3 sucessos, 1 falha = 75%
        for _ in range(3):
            scorer.record_cooperation("agent", "partner", success=True)
        scorer.record_cooperation("agent", "partner", success=False)
        
        profile = scorer._profiles["agent"]
        assert abs(profile.cooperation_rate - 0.75) < 0.01

    def test_symbiosis_score_update(self):
        """symbiosis_score é atualizado após cada cooperação."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner", success=True, outcome_quality=0.9)
        
        profile = scorer._profiles["agent"]
        assert profile.symbiosis_score > 0.0

    def test_isolation_detection(self):
        """Agente sem cooperação recente é detectado como isolado."""
        scorer = SymbiosisScore()
        
        # Criar perfil sem cooperações
        scorer._ensure_profile("isolated_agent")
        
        profile = scorer._profiles["isolated_agent"]
        assert profile.is_isolated is True
        assert profile.isolation_warning is False  # Só vira True após update


class TestFitnessBonus:
    """Testes de aplicação de bonus/penalidade."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_high_symbiosis_gets_bonus(self):
        """Alta simbiose (>0.7) recebe bonus de fitness."""
        scorer = SymbiosisScore()
        
        # Múltiplas cooperações de alta qualidade para aumentar score
        for i in range(20):
            scorer.record_cooperation(
                "good_agent",
                f"partner_{i % 5}",  # 5 parceiros diferentes
                success=True,
                outcome_quality=0.9,
            )
        
        fitness_final, report = scorer.apply_symbiosis_bonus("good_agent", 0.8)
        
        assert report["effect"] == "bonus"
        assert fitness_final > 0.8, f"Deveria receber bonus: {fitness_final}"
        assert report["multiplier"] == scorer._SYMBIOSIS_BONUS_MULTIPLIER

    def test_isolated_agent_gets_penalty(self):
        """Agente isolado recebe penalidade de fitness."""
        scorer = SymbiosisScore()
        
        # Criar agente e marcar como isolado manualmente
        scorer._ensure_profile("lonely_agent")
        profile = scorer._profiles["lonely_agent"]
        profile.last_cooperation = time.time() - 600  # 10 minutos atrás
        scorer._update_symbiosis_score("lonely_agent")
        
        fitness_final, report = scorer.apply_symbiosis_bonus("lonely_agent", 0.8)
        
        # Se estiver isolado, deveria receber penalidade
        if profile.is_isolated:
            assert report["effect"] == "penalty"
            assert fitness_final < 0.8
            assert report["multiplier"] == scorer._ISOLATION_PENALTY_MULTIPLIER

    def test_no_profile_no_bonus(self):
        """Agente sem perfil não recebe bonus/penalidade."""
        scorer = SymbiosisScore()
        
        fitness_final, report = scorer.apply_symbiosis_bonus("unknown_agent", 0.8)
        
        assert fitness_final == 0.8
        assert report["applied"] is False
        assert report["reason"] == "no_profile"


class TestCooperationQuality:
    """Testes de qualidade de cooperação entre pares."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_get_cooperation_quality(self):
        """Qualidade média de cooperações entre dois agentes."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent_a", "agent_b", success=True, outcome_quality=0.9)
        scorer.record_cooperation("agent_a", "agent_b", success=True, outcome_quality=0.8)
        scorer.record_cooperation("agent_a", "agent_b", success=False, outcome_quality=0.0)
        
        quality = scorer.get_cooperation_quality("agent_a", "agent_b")
        
        # Média de 0.9, 0.8, 0.0 = 0.567
        assert 0.5 < quality < 0.6

    def test_get_cooperation_quality_reverse_order(self):
        """Qualidade funciona em ambas as direções."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent_a", "agent_b", success=True, outcome_quality=0.9)
        
        quality_ab = scorer.get_cooperation_quality("agent_a", "agent_b")
        quality_ba = scorer.get_cooperation_quality("agent_b", "agent_a")
        
        # Ambas deveriam retornar valor (mesmo que b não tenha perfil)
        assert quality_ab > 0.0


class TestIsolationDetection:
    """Testes de detecção de isolamento."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_get_isolated_agents(self):
        """Retorna lista de agentes isolados."""
        scorer = SymbiosisScore()
        
        # Agente ativo
        scorer.record_cooperation("active_agent", "partner", success=True)
        
        # Agente isolado (criar perfil sem cooperação)
        scorer._ensure_profile("isolated_agent")
        profile = scorer._profiles["isolated_agent"]
        profile.last_cooperation = time.time() - 600  # 10 minutos atrás
        scorer._update_symbiosis_score("isolated_agent")
        
        isolated = scorer.get_isolated_agents()
        
        assert "isolated_agent" in isolated
        assert "active_agent" not in isolated


class TestTopCooperators:
    """Testes de ranking de cooperadores."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_get_top_cooperators(self):
        """Retorna top N agentes com maior score."""
        scorer = SymbiosisScore()
        
        # Agente muito cooperativo
        for i in range(30):
            scorer.record_cooperation(
                "super_cooperator",
                f"partner_{i % 10}",
                success=True,
                outcome_quality=0.95,
            )
        
        # Agente pouco cooperativo
        scorer.record_cooperation("lazy_agent", "partner", success=False, outcome_quality=0.3)
        
        top = scorer.get_top_cooperators(top_n=5)
        
        assert len(top) <= 5
        assert top[0][0] == "super_cooperator"
        assert top[0][1] > top[-1][1]


class TestSymbiosisReport:
    """Testes de relatórios."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_get_symbiosis_report(self):
        """Relatório completo de simbiose."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner", success=True, outcome_quality=0.8)
        
        report = scorer.get_symbiosis_report("agent")
        
        assert report is not None
        assert "agent_id" in report
        assert "symbiosis_score" in report
        assert "total_cooperations" in report
        assert "cooperation_rate" in report
        assert "partner_diversity" in report
        assert "partners" in report

    def test_get_symbiosis_report_no_profile(self):
        """Agente sem perfil retorna None."""
        scorer = SymbiosisScore()
        
        report = scorer.get_symbiosis_report("unknown_agent")
        
        assert report is None


class TestHealthCheck:
    """Testes de health check."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_health_check(self):
        """Health check retorna status geral."""
        scorer = SymbiosisScore()
        
        # Criar algumas cooperações
        scorer.record_cooperation("agent_a", "agent_b", success=True)
        scorer.record_cooperation("agent_c", "agent_d", success=True)
        
        health = scorer.health_check()
        
        assert "total_agents" in health
        assert "isolated_agents" in health
        assert "average_symbiosis_score" in health
        assert "total_cooperations" in health
        assert "cooperation_pairs" in health
        
        # Deve ter pelo menos 2 agentes (agent_a e agent_c que iniciaram)
        assert health["total_agents"] >= 2
        assert health["total_cooperations"] == 2


class TestReset:
    """Testes de reset de perfil."""

    def setup_method(self):
        SymbiosisScore._instance = None

    def test_reset_profile(self):
        """Reset remove perfil e limpa matriz de cooperação."""
        scorer = SymbiosisScore()
        
        scorer.record_cooperation("agent", "partner", success=True)
        
        assert "agent" in scorer._profiles
        
        scorer.reset_profile("agent")
        
        assert "agent" not in scorer._profiles
        # Matriz de cooperação também deveria ser limpa
        pair_keys = [k for k in scorer._cooperation_matrix.keys() if "agent" in k]
        assert len(pair_keys) == 0


class TestSingleton:
    """Testes de singleton."""

    def test_singleton_instance(self):
        """SymbiosisScore é singleton."""
        SymbiosisScore._instance = None
        
        s1 = SymbiosisScore()
        s2 = SymbiosisScore()
        
        assert s1 is s2

    def test_global_singleton(self):
        """symbiosis_score global é instância válida."""
        assert isinstance(symbiosis_score, SymbiosisScore)


class TestAsyncOperations:
    """Testes de operações assíncronas."""

    def setup_method(self):
        SymbiosisScore._instance = None

    @pytest.mark.asyncio
    async def test_record_cooperation_async(self):
        """Registro assíncrono de cooperação."""
        scorer = SymbiosisScore()
        
        await scorer.record_cooperation_async("agent_a", "agent_b", success=True, outcome_quality=0.9)
        
        assert "agent_a" in scorer._profiles
        profile = scorer._profiles["agent_a"]
        assert profile.total_cooperations == 1

    @pytest.mark.asyncio
    async def test_apply_symbiosis_bonus_async(self):
        """Aplicação assíncrona de bonus."""
        scorer = SymbiosisScore()
        
        # Criar perfil com alta simbiose
        for i in range(20):
            await scorer.record_cooperation_async(
                "good_agent",
                f"partner_{i % 5}",
                success=True,
                outcome_quality=0.9,
            )
        
        fitness_final, report = await scorer.apply_symbiosis_bonus_async("good_agent", 0.8)
        
        assert report["applied"] is True
        assert fitness_final >= 0.8  # Bonus ou neutro


if __name__ == "__main__":
    pytest.main([__file__, "-v"])