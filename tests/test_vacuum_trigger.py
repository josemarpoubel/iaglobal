# tests/test_vacuum_trigger.py
"""
Testes do VacuumTrigger — Lei do Vácuo.

Cobre:
- Registro de padrões
- Detecção de necessidade de vácuo
- Execução de vácuo (remoção de stale)
- Forçar diversidade
- Monitoramento de apoptose
- Estado e relatórios
"""
import pytest
import time
import asyncio
from iaglobal.immunity.vacuum_trigger import VacuumTrigger, vacuum_trigger, VacuumState


class TestVacuumTriggerRegistration:
    """Testes de registro de padrões."""

    def setup_method(self):
        """Reset singleton antes de cada teste."""
        VacuumTrigger._instance = None

    def test_register_pattern_creates_record(self):
        """Registro cria padrão com metadados."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent", {"quality": 0.9})
        
        assert "pattern_001" in trigger._patterns
        pattern = trigger._patterns["pattern_001"]
        assert pattern.agent_type == "coder_agent"
        assert pattern.execution_count == 1
        assert pattern.metadata["quality"] == 0.9

    def test_register_pattern_updates_existing(self):
        """Registro de padrão existente atualiza contagem."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent")
        trigger.register_pattern("pattern_001", "coder_agent")
        trigger.register_pattern("pattern_001", "coder_agent")
        
        pattern = trigger._patterns["pattern_001"]
        assert pattern.execution_count == 3
        assert pattern.is_stale is False

    def test_register_pattern_updates_last_seen(self):
        """Registro atualiza last_seen."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent")
        first_seen = trigger._patterns["pattern_001"].last_seen
        
        time.sleep(0.1)
        trigger.register_pattern("pattern_001", "coder_agent")
        second_seen = trigger._patterns["pattern_001"].last_seen
        
        assert second_seen > first_seen


class TestVacuumDetection:
    """Testes de detecção de necessidade de vácuo."""

    def setup_method(self):
        VacuumTrigger._instance = None

    def test_check_vacuum_not_needed(self):
        """Vácuo não é necessário com baixa densidade."""
        trigger = VacuumTrigger()
        
        # Poucos padrões
        for i in range(5):
            trigger.register_pattern(f"pattern_{i}", "coder_agent")
        
        needs_vacuum, reason = trigger.check_vacuum_needed()
        
        assert needs_vacuum is False
        assert reason["urgency"] == "none"

    def test_check_vacuum_density_high(self):
        """Vácuo necessário quando densidade > 80%."""
        trigger = VacuumTrigger()
        
        # Encher até > 80% da capacidade (100 max)
        for i in range(85):
            trigger.register_pattern(f"pattern_{i}", "coder_agent")
        
        needs_vacuum, reason = trigger.check_vacuum_needed()
        
        assert needs_vacuum is True
        assert "density" in ", ".join(reason["reasons"])

    def test_check_vacuum_diversity_critical(self):
        """Vácuo necessário quando diversidade < 30%."""
        trigger = VacuumTrigger()
        
        # Um padrão domina (baixa diversidade)
        for _ in range(50):
            trigger.register_pattern("dominant_pattern", "coder_agent")
        
        for i in range(3):
            trigger.register_pattern(f"rare_{i}", "critic_agent")
        
        needs_vacuum, reason = trigger.check_vacuum_needed()
        
        assert needs_vacuum is True
        assert reason["urgency"] == "critical"

    def test_check_vacuum_stale_emergency(self):
        """Vácuo emergencial quando > 50% stale."""
        trigger = VacuumTrigger()
        
        # Criar padrões
        for i in range(10):
            trigger.register_pattern(f"pattern_{i}", "coder_agent")
        
        # Simular tempo passando (padrões ficam stale)
        for pattern in trigger._patterns.values():
            pattern.last_seen = time.time() - 600  # 10 minutos atrás
        
        trigger._update_state()
        
        needs_vacuum, reason = trigger.check_vacuum_needed()
        
        assert needs_vacuum is True
        assert reason["urgency"] == "emergency"


class TestVacuumExecution:
    """Testes de execução do vácuo."""

    def setup_method(self):
        VacuumTrigger._instance = None

    @pytest.mark.asyncio
    async def test_trigger_vacuum_removes_stale(self):
        """Vácuo remove padrões stale."""
        trigger = VacuumTrigger()
        
        # Criar padrões
        trigger.register_pattern("fresh_pattern", "coder_agent")
        
        # Criar padrão stale manualmente
        trigger.register_pattern("stale_pattern", "critic_agent")
        trigger._patterns["stale_pattern"].last_seen = time.time() - 600
        trigger._patterns["stale_pattern"].is_stale = True
        
        trigger._update_state()
        assert trigger._state.stale_patterns == 1
        
        # Executar vácuo
        result = await trigger.trigger_vacuum_async(
            force_diversity=False,
            remove_stale_patterns=True,
        )
        
        assert result["vacuum_executed"] is True
        assert result["patterns_removed"] == 1
        assert "stale_pattern" not in trigger._patterns
        assert "fresh_pattern" in trigger._patterns

    @pytest.mark.asyncio
    async def test_trigger_vacuum_enforces_diversity(self):
        """Vácuo força diversidade quando solicitado."""
        trigger = VacuumTrigger()
        
        # Criar padrão dominante
        for _ in range(20):
            trigger.register_pattern("dominant", "coder_agent")
        
        for i in range(5):
            trigger.register_pattern(f"minor_{i}", "critic_agent")
        
        before_diversity = trigger._state.diversity_score
        
        # Executar vácuo com diversidade
        await trigger.trigger_vacuum_async(
            force_diversity=True,
            remove_stale_patterns=False,
        )
        
        after_diversity = trigger._state.diversity_score
        
        # Diversidade deveria aumentar
        assert after_diversity >= before_diversity

    @pytest.mark.asyncio
    async def test_trigger_vacuum_updates_state(self):
        """Vácuo atualiza estado corretamente."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent")
        
        result = await trigger.trigger_vacuum_async()
        
        assert result["timestamp"] is not None
        assert trigger._state.vacuum_count >= 1
        assert trigger._state.last_vacuum > 0


class TestDiversityEnforcement:
    """Testes de forçar diversidade."""

    def setup_method(self):
        VacuumTrigger._instance = None

    @pytest.mark.asyncio
    async def test_enforce_diversity_after_apoptosis(self):
        """Diversidade forçada após apoptose."""
        trigger = VacuumTrigger()
        
        # Criar alguns padrões
        for i in range(5):
            trigger.register_pattern(f"pattern_{i}", "coder_agent")
        
        # Simular apoptose
        result = await trigger.enforce_diversity_async(
            after_apoptosis=["agent_x", "agent_y"]
        )
        
        assert result["diversity_enforced"] is True
        assert result["apoptosis_events"] == 2
        assert len(trigger._apoptosis_events) == 2

    def test_apoptosis_events_tracked(self):
        """Eventos de apoptose são rastreados com limite de 100."""
        trigger = VacuumTrigger()
        
        # Adicionar eventos diretamente (simulando uso interno)
        for i in range(5):
            trigger._apoptosis_events.append((f"agent_{i}", time.time()))
        
        # Adicionar mais 100 para testar limite
        for i in range(100):
            trigger._apoptosis_events.append((f"agent_{i}", time.time()))
        
        # Chamar trim manualmente (já que o teste não usa enforce_diversity_async)
        trigger._trim_apoptosis_events()
        
        # Deveria ter no máximo 100
        assert len(trigger._apoptosis_events) <= 100
        assert len(trigger._apoptosis_events) == 100  # Exatamente 100 após trim


class TestVacuumState:
    """Testes de estado do vácuo."""

    def setup_method(self):
        VacuumTrigger._instance = None

    def test_get_vacuum_state(self):
        """Estado retorna informações completas."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent")
        trigger.register_pattern("pattern_002", "critic_agent")
        
        state = trigger.get_vacuum_state()
        
        assert "total_patterns" in state
        assert "stale_patterns" in state
        assert "diversity_score" in state
        assert "density" in state
        assert "vacuum_count" in state
        
        assert state["total_patterns"] == 2
        assert state["density"] > 0.0

    def test_get_patterns(self):
        """Lista de padrões retorna detalhes."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent", {"key": "value"})
        
        patterns = trigger.get_patterns()
        
        assert len(patterns) == 1
        assert patterns[0]["pattern_id"] == "pattern_001"
        assert patterns[0]["agent_type"] == "coder_agent"
        assert patterns[0]["execution_count"] == 1
        assert patterns[0]["is_stale"] is False


class TestReset:
    """Testes de reset."""

    def setup_method(self):
        VacuumTrigger._instance = None

    def test_reset_clears_all(self):
        """Reset limpa todos os padrões e estado."""
        trigger = VacuumTrigger()
        
        trigger.register_pattern("pattern_001", "coder_agent")
        trigger._apoptosis_events.append(("agent_x", time.time()))
        trigger._state.vacuum_count = 5
        
        trigger.reset()
        
        assert len(trigger._patterns) == 0
        assert len(trigger._apoptosis_events) == 0
        assert trigger._state.vacuum_count == 0


class TestSingleton:
    """Testes de singleton."""

    def test_singleton_instance(self):
        """VacuumTrigger é singleton."""
        VacuumTrigger._instance = None
        
        t1 = VacuumTrigger()
        t2 = VacuumTrigger()
        
        assert t1 is t2

    def test_global_singleton(self):
        """vacuum_trigger global é instância válida."""
        assert isinstance(vacuum_trigger, VacuumTrigger)


class TestAsyncOperations:
    """Testes de operações assíncronas."""

    def setup_method(self):
        VacuumTrigger._instance = None

    @pytest.mark.asyncio
    async def test_async_vacuum_workflow(self):
        """Fluxo completo assíncrono de vácuo."""
        trigger = VacuumTrigger()
        
        # Registrar padrões
        for i in range(10):
            await asyncio.to_thread(
                trigger.register_pattern, f"pattern_{i}", "coder_agent"
            )
        
        # Verificar vácuo
        needs_vacuum, reason = await asyncio.to_thread(trigger.check_vacuum_needed)
        
        # Executar vácuo se necessário
        if needs_vacuum:
            result = await trigger.trigger_vacuum_async()
            assert result["vacuum_executed"] is True
        
        # Obter estado
        state = await asyncio.to_thread(trigger.get_vacuum_state)
        assert "total_patterns" in state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])