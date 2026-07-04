"""
Testes do MethylationEngine — Ciclo de Metilação Explícito.

Valida:
1. Processamento de candidatos (production, guardrail, deferred, rejected)
2. Detecção de homocisteína elevada
3. Technical debt acumulado
4. Reset de homocisteína
5. Health report
6. Integração com EpigeneticRegistry
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from iaglobal.evolution.metabolism.methylation_engine import (
    MethylationEngine,
    MethylationState,
    MethylationDecision,
    methylation_engine,
)
from iaglobal.evolution.metabolism.homocysteine_pool import CandidateSkill, Skill


class TestMethylationState:
    """Testes do estado de metilação."""
    
    def test_initial_state(self):
        """Estado inicial deve ter valores padrão saudáveis."""
        state = MethylationState()
        assert state.sam_e_level == 100.0
        assert state.methylation_capacity == 100.0
        assert state.homocysteine_level == 0.0
        assert state.technical_debt_score == 0.0
        assert state.cycles_completed == 0
    
    def test_homocysteine_elevated_detection(self):
        """Detecta homocisteína elevada corretamente."""
        state = MethylationState()
        assert not state.is_homocysteine_elevated()
        
        state.homocysteine_level = 49.9
        assert not state.is_homocysteine_elevated()
        
        state.homocysteine_level = 50.0
        assert state.is_homocysteine_elevated()
        
        state.homocysteine_level = 75.0
        assert state.is_homocysteine_elevated()
    
    def test_technical_debt_critical_detection(self):
        """Detecta technical debt crítico."""
        state = MethylationState()
        assert not state.is_technical_debt_critical()
        
        state.technical_debt_score = 0.69
        assert not state.is_technical_debt_critical()
        
        state.technical_debt_score = 0.70
        assert state.is_technical_debt_critical()
    
    def test_can_operate(self):
        """Verifica capacidade operacional baseada em SAMe."""
        state = MethylationState()
        assert state.can_operate()
        
        state.sam_e_level = 20.0
        assert state.can_operate()
        
        state.sam_e_level = 19.9
        assert not state.can_operate()
        
        state.sam_e_level = 0.0
        assert not state.can_operate()
    
    def test_to_dict_from_dict_roundtrip(self):
        """Serialização e desserialização preservam dados."""
        original = MethylationState(
            sam_e_level=75.5,
            methylation_capacity=80.0,
            homocysteine_level=25.3,
            technical_debt_score=0.45,
            cycles_completed=42,
            successful_methylations=35,
            failed_methylations=7,
            guardrails_created=5,
        )
        
        data = original.to_dict()
        restored = MethylationState.from_dict(data)
        
        assert restored.sam_e_level == original.sam_e_level
        assert restored.methylation_capacity == original.methylation_capacity
        assert restored.homocysteine_level == original.homocysteine_level
        assert restored.technical_debt_score == original.technical_debt_score
        assert restored.cycles_completed == original.cycles_completed


class TestMethylationDecision:
    """Testes das decisões de metilação."""
    
    def test_decision_creation(self):
        """Cria decisão com todos os campos."""
        skill = Skill(name="test_skill", version="1.0.0", description="Test")
        candidate = CandidateSkill(skill=skill, score=85.0, generation=1)
        
        decision = MethylationDecision(
            candidate=candidate,
            decision="production",
            reason="Score alto",
            sam_e_consumed=5.0,
            homocysteine_generated=1.0,
        )
        
        assert decision.decision == "production"
        assert decision.reason == "Score alto"
        assert decision.sam_e_consumed == 5.0
        assert decision.homocysteine_generated == 1.0
        assert decision.timestamp is not None
    
    def test_decision_to_dict(self):
        """Converte decisão para dict."""
        skill = Skill(name="analyst_skill", version="1.0.0", description="Analysis")
        candidate = CandidateSkill(skill=skill, score=90.0, generation=1)
        
        decision = MethylationDecision(
            candidate=candidate,
            decision="guardrail",
            reason="Erros recorrentes",
            sam_e_consumed=5.0,
            homocysteine_generated=1.0,
        )
        
        data = decision.to_dict()
        assert data["candidate_name"] == "analyst_skill"
        assert data["decision"] == "guardrail"
        assert data["reason"] == "Erros recorrentes"
        assert data["sam_e_consumed"] == 5.0
        assert data["homocysteine_generated"] == 1.0


class TestMethylationEngine:
    """Testes do engine de metilação."""
    
    @pytest.fixture
    def engine(self):
        """Cria engine limpo para testes."""
        # Reseta singleton
        MethylationEngine._instance = None
        return MethylationEngine()
    
    def test_singleton_pattern(self):
        """Garante que é singleton."""
        MethylationEngine._instance = None
        engine1 = MethylationEngine()
        engine2 = MethylationEngine()
        assert engine1 is engine2
    
    def test_process_candidate_production(self, engine):
        """Candidato com score alto vai para production."""
        skill = Skill(name="good_skill", version="1.0.0", description="Good")
        candidate = CandidateSkill(skill=skill, score=95.0, generation=1)
        
        # Mock dos componentes
        with patch.object(engine.opportunity_detector, 'calculate_opportunity_cost', 
                         return_value={"is_parasite": False}):
            with patch.object(engine.transsulfuration_cycle, 'run', return_value=False):
                with patch.object(engine.methylation_cycle, 'run', return_value=True):
                    with patch.object(engine.epigenetic_registry, 'record_success', 
                                     new_callable=AsyncMock):
                        decision = engine.process_candidate(candidate)
        
        assert decision.decision == "production"
        assert "Score" in decision.reason
        assert decision.sam_e_consumed == 5.0
        assert decision.homocysteine_generated == 1.0
    
    def test_process_candidate_guardrail(self, engine):
        """Candidato com erros recorrentes recebe guardrail."""
        skill = Skill(name="error_prone_skill", version="1.0.0", description="Error prone")
        candidate = CandidateSkill(skill=skill, score=80.0, generation=1)
        
        with patch.object(engine.opportunity_detector, 'calculate_opportunity_cost',
                         return_value={"is_parasite": False}):
            with patch.object(engine.transsulfuration_cycle, 'run', return_value=True):
                decision = engine.process_candidate(candidate)
        
        assert decision.decision == "guardrail"
        assert "Erros recorrentes" in decision.reason
    
    def test_process_candidate_rejected_parasite(self, engine):
        """Candidato detectado como parasita é rejeitado."""
        skill = Skill(name="parasite_skill", version="1.0.0", description="Parasite")
        candidate = CandidateSkill(skill=skill, score=90.0, generation=1)
        
        with patch.object(engine.opportunity_detector, 'calculate_opportunity_cost',
                         return_value={"is_parasite": True, "parasite_score": 0.85}):
            decision = engine.process_candidate(candidate)
        
        assert decision.decision == "rejected"
        assert "Parasita" in decision.reason
    
    def test_process_candidate_deferred_low_sam(self, engine):
        """Candidato adiado quando SAMe insuficiente."""
        skill = Skill(name="deferred_skill", version="1.0.0", description="Deferred")
        candidate = CandidateSkill(skill=skill, score=95.0, generation=1)
        
        # Reduz SAMe abaixo do mínimo
        engine.state.sam_e_level = 15.0
        
        decision = engine.process_candidate(candidate)
        
        assert decision.decision == "deferred"
        assert "SAMe insuficiente" in decision.reason
        assert engine.state.technical_debt_score > 0
    
    def test_process_candidate_rejected_low_score(self, engine):
        """Candidato com score baixo é rejeitado."""
        skill = Skill(name="low_score_skill", version="1.0.0", description="Low score")
        candidate = CandidateSkill(skill=skill, score=40.0, generation=1)
        
        # Garante SAMe suficiente
        engine.state.sam_e_level = 80.0
        
        with patch.object(engine.opportunity_detector, 'calculate_opportunity_cost',
                         return_value={"is_parasite": False}):
            with patch.object(engine.transsulfuration_cycle, 'run', return_value=False):
                with patch.object(engine.methylation_cycle, 'run', return_value=False):
                    with patch.object(engine.epigenetic_registry, 'record_failure'):
                        decision = engine.process_candidate(candidate)
        
        assert decision.decision == "rejected"
        assert "Score" in decision.reason
    
    def test_consume_resources_updates_state(self, engine):
        """Consumo de recursos atualiza estado corretamente."""
        initial_sam = engine.state.sam_e_level
        initial_homocysteine = engine.state.homocysteine_level
        initial_cycles = engine.state.cycles_completed
        
        engine._consume_resources(success=True)
        
        assert engine.state.sam_e_level == initial_sam - 5.0
        assert engine.state.homocysteine_level == initial_homocysteine + 1.0
        assert engine.state.cycles_completed == initial_cycles + 1
    
    def test_homocysteine_elevated_triggers_debt(self, engine):
        """Homocisteína elevada aumenta technical debt."""
        engine.state.homocysteine_level = 60.0  # Acima do threshold
        initial_debt = engine.state.technical_debt_score
        
        engine._consume_resources(success=True)
        
        assert engine.state.technical_debt_score > initial_debt
    
    def test_reset_homocysteine(self, engine):
        """Reset de homocisteína funciona quando elevada."""
        engine.state.homocysteine_level = 75.0
        engine.state.technical_debt_score = 0.8
        
        result = engine.reset_homocysteine()
        
        assert result is True
        assert engine.state.homocysteine_level == 0.0
        assert engine.state.technical_debt_score < 0.8
    
    def test_reset_homocysteine_not_elevated(self, engine):
        """Reset não faz nada quando homocisteína normal."""
        engine.state.homocysteine_level = 20.0
        
        result = engine.reset_homocysteine()
        
        assert result is False
        assert engine.state.homocysteine_level == 20.0
    
    def test_replenish_sam_e(self, engine):
        """Reabastecimento de SAMe funciona."""
        initial_sam = engine.state.sam_e_level
        engine.state.sam_e_level = 30.0
        
        engine.replenish_sam_e(amount=40.0)
        
        assert engine.state.sam_e_level == 70.0
    
    def test_replenish_sam_e_caps_at_100(self, engine):
        """SAMe não ultrapassa 100."""
        engine.state.sam_e_level = 80.0
        
        engine.replenish_sam_e(amount=50.0)
        
        assert engine.state.sam_e_level == 100.0
    
    def test_get_health_report_healthy(self, engine):
        """Health report retorna status saudável."""
        engine.state.sam_e_level = 80.0
        engine.state.homocysteine_level = 10.0
        engine.state.technical_debt_score = 0.2
        engine.state.successful_methylations = 90
        engine.state.failed_methylations = 10
        
        report = engine.get_health_report()
        
        assert report["status"] == "healthy"
        assert len(report["recommendations"]) == 0
    
    def test_get_health_report_critical_low_sam(self, engine):
        """Health report detecta SAMe crítico."""
        engine.state.sam_e_level = 15.0  # Abaixo do mínimo
        
        report = engine.get_health_report()
        
        assert report["status"] == "critical"
        assert any("SAMe" in rec for rec in report["recommendations"])
    
    def test_get_health_report_critical_homocysteine(self, engine):
        """Health report detecta homocisteína crítica."""
        engine.state.homocysteine_level = 60.0  # Acima do threshold
        
        report = engine.get_health_report()
        
        assert report["status"] == "critical"
        assert any("Homocisteína" in rec for rec in report["recommendations"])
    
    def test_get_health_report_critical_debt(self, engine):
        """Health report detecta technical debt crítico."""
        engine.state.technical_debt_score = 0.75  # Acima do threshold
        
        report = engine.get_health_report()
        
        assert report["status"] == "critical"
        assert any("Technical debt" in rec for rec in report["recommendations"])
    
    def test_get_health_report_warning_low_efficiency(self, engine):
        """Health report detecta eficiência baixa."""
        engine.state.sam_e_level = 80.0
        engine.state.homocysteine_level = 10.0
        engine.state.technical_debt_score = 0.2
        engine.state.successful_methylations = 30
        engine.state.failed_methylations = 70  # Eficiência = 30%
        
        report = engine.get_health_report()
        
        assert report["status"] == "warning"
        assert any("Eficiência" in rec for rec in report["recommendations"])
    
    def test_get_recent_decisions(self, engine):
        """Retorna decisões recentes."""
        skill = Skill(name="test_skill", version="1.0.0", description="Test")
        
        # Adiciona decisões manualmente
        for i in range(10):
            candidate = CandidateSkill(skill=skill, score=80.0 + i, generation=1)
            decision = MethylationDecision(
                candidate=candidate,
                decision="production",
                reason=f"Decision {i}",
            )
            engine._record_decision(decision)
        
        recent = engine.get_recent_decisions(limit=5)
        assert len(recent) == 5
        assert recent[-1].reason == "Decision 9"
    
    def test_decisions_history_capped(self, engine):
        """Histórico de decisões é limitado a 1000."""
        skill = Skill(name="test_skill", version="1.0.0", description="Test")
        
        # Adiciona 1005 decisões
        for i in range(1005):
            candidate = CandidateSkill(skill=skill, score=80.0, generation=1)
            decision = MethylationDecision(
                candidate=candidate,
                decision="production",
                reason=f"Decision {i}",
            )
            engine._record_decision(decision)
        
        assert len(engine._decisions) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
