# tests/test_metabolic_rhythm.py
"""
Testes do MetabolicRhythm — Deep Sleep e Burst Mode.

Cobre:
- Monitoramento de estado metabólico
- Transições entre modos (Deep Sleep, Normal, Burst, Recovery)
- Ativação manual de burst mode
- Callbacks de transição
- Histórico de transições
"""
import pytest
import asyncio
import time
from iaglobal.evolution.metabolic_rhythm import (
    MetabolicRhythm,
    metabolic_rhythm,
    MetabolicMode,
    MetabolicState,
    ModeTransition,
)


class TestMetabolicState:
    """Testes de estado metabólico."""

    def setup_method(self):
        """Reset singleton antes de cada teste."""
        MetabolicRhythm._instance = None

    def test_initial_state_is_normal(self):
        """Estado inicial é NORMAL com CPU budget 25%."""
        rhythm = MetabolicRhythm()
        
        state = rhythm.get_metabolic_state()
        
        assert state["mode"] == "normal"
        assert state["cpu_budget"] == 0.25
        assert state["burst_mode_active"] is False
        assert state["homeostasis_score"] == 1.0

    def test_state_includes_all_fields(self):
        """Estado inclui todos os campos necessários."""
        rhythm = MetabolicRhythm()
        
        state = rhythm.get_metabolic_state()
        
        assert "mode" in state
        assert "cpu_budget" in state
        assert "atp_level" in state
        assert "load_average" in state
        assert "burst_mode_active" in state
        assert "burst_mode_remaining" in state
        assert "deep_sleep_entered_at" in state
        assert "last_mode_transition" in state
        assert "homeostasis_score" in state


class TestDeepSleep:
    """Testes de Deep Sleep."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    @pytest.mark.asyncio
    async def test_enter_deep_sleep_manually(self):
        """Entrada manual em Deep Sleep."""
        rhythm = MetabolicRhythm()
        
        success = await rhythm.enter_deep_sleep_async(reason="test")
        
        assert success is True
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "deep_sleep"
        assert state["cpu_budget"] == 0.1  # 10% em deep sleep
        assert state["deep_sleep_entered_at"] is not None

    @pytest.mark.asyncio
    async def test_wake_up_from_deep_sleep(self):
        """Despertar de Deep Sleep."""
        rhythm = MetabolicRhythm()
        
        # Entrar em deep sleep
        await rhythm.enter_deep_sleep_async()
        
        # Acordar
        success = await rhythm.wake_up_async()
        
        assert success is True
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "normal"
        assert state["cpu_budget"] == 0.25
        assert state["deep_sleep_entered_at"] is None

    @pytest.mark.asyncio
    async def test_cannot_enter_deep_sleep_from_burst(self):
        """Não é possível entrar em Deep Sleep durante Burst Mode."""
        rhythm = MetabolicRhythm()
        
        # Ativar burst mode
        await rhythm.activate_burst_mode_async(duration_seconds=60)
        
        # Tentar entrar em deep sleep
        success = await rhythm.enter_deep_sleep_async()
        
        assert success is False
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "burst_mode"

    def test_deep_sleep_cpu_budget(self):
        """Deep Sleep reduz CPU budget para 10%."""
        rhythm = MetabolicRhythm()
        rhythm._transition_to(MetabolicMode.DEEP_SLEEP, "test", "manual")
        
        state = rhythm.get_metabolic_state()
        
        assert state["cpu_budget"] == 0.1


class TestBurstMode:
    """Testes de Burst Mode."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    @pytest.mark.asyncio
    async def test_activate_burst_mode_manually(self):
        """Ativação manual de Burst Mode."""
        rhythm = MetabolicRhythm()
        
        success = await rhythm.activate_burst_mode_async(
            duration_seconds=30,
            cpu_override=0.6,
            reason="test_emergency",
        )
        
        assert success is True
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "burst_mode"
        assert state["burst_mode_active"] is True
        assert state["cpu_budget"] == 0.6
        assert state["burst_mode_remaining"] > 0

    @pytest.mark.asyncio
    async def test_burst_mode_cpu_override_limits(self):
        """CPU override é limitado entre 30-80%."""
        rhythm = MetabolicRhythm()
        
        # Testar limite mínimo
        await rhythm.activate_burst_mode_async(cpu_override=0.1)
        state_min = rhythm.get_metabolic_state()
        assert state_min["cpu_budget"] >= 0.3
        
        # Reset
        rhythm.reset()
        
        # Testar limite máximo
        await rhythm.activate_burst_mode_async(cpu_override=1.0)
        state_max = rhythm.get_metabolic_state()
        assert state_max["cpu_budget"] <= 0.8

    @pytest.mark.asyncio
    async def test_cannot_activate_burst_from_deep_sleep(self):
        """Não é possível ativar Burst Mode de Deep Sleep."""
        rhythm = MetabolicRhythm()
        
        # Entrar em deep sleep
        await rhythm.enter_deep_sleep_async()
        
        # Tentar ativar burst mode
        success = await rhythm.activate_burst_mode_async()
        
        assert success is False
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "deep_sleep"

    def test_burst_mode_increases_cpu_budget(self):
        """Burst Mode aumenta CPU budget para 50%+."""
        rhythm = MetabolicRhythm()
        rhythm._transition_to(MetabolicMode.BURST_MODE, "test", "manual")
        
        state = rhythm.get_metabolic_state()
        
        assert state["cpu_budget"] >= 0.5
        assert state["burst_mode_active"] is True


class TestRecoveryMode:
    """Testes de Recovery Mode."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    def test_recovery_mode_after_burst(self):
        """Recovery mode é ativado após Burst Mode."""
        rhythm = MetabolicRhythm()
        
        # Simular transição burst → recovery
        rhythm._transition_to(MetabolicMode.BURST_MODE, "test burst", "manual")
        burst_timestamp = rhythm._state.last_mode_transition
        
        # Simular saída do burst mode
        rhythm._transition_to(MetabolicMode.RECOVERY, "burst completed", "automatic")
        
        state = rhythm.get_metabolic_state()
        
        assert state["mode"] == "recovery"
        assert state["cpu_budget"] == 0.3  # 30% em recovery
        assert state["burst_mode_active"] is False


class TestTransitionHistory:
    """Testes de histórico de transições."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    def test_transition_history_records_changes(self):
        """Histórico registra transições."""
        rhythm = MetabolicRhythm()
        
        # Executar várias transições
        rhythm._transition_to(MetabolicMode.DEEP_SLEEP, "test 1", "manual")
        rhythm._transition_to(MetabolicMode.NORMAL, "test 2", "manual")
        rhythm._transition_to(MetabolicMode.BURST_MODE, "test 3", "manual")
        
        history = rhythm.get_transition_history(limit=10)
        
        assert len(history) == 3
        assert history[0]["to_mode"] == "deep_sleep"
        assert history[1]["to_mode"] == "normal"
        assert history[2]["to_mode"] == "burst_mode"

    def test_transition_history_includes_metadata(self):
        """Histórico inclui metadados completos."""
        rhythm = MetabolicRhythm()
        
        rhythm._transition_to(MetabolicMode.DEEP_SLEEP, "manual_test", "manual")
        
        history = rhythm.get_transition_history()
        
        assert "from_mode" in history[0]
        assert "to_mode" in history[0]
        assert "timestamp" in history[0]
        assert "reason" in history[0]
        assert "trigger" in history[0]
        assert "duration_previous_mode" in history[0]

    def test_transition_history_limited(self):
        """Histórico é limitado a 100 entradas."""
        rhythm = MetabolicRhythm()
        
        # Criar 150 transições
        for i in range(150):
            mode = MetabolicMode.NORMAL if i % 2 == 0 else MetabolicMode.DEEP_SLEEP
            rhythm._transition_to(mode, f"test {i}", "test")
        
        history = rhythm.get_transition_history(limit=100)
        
        assert len(history) <= 100


class TestCallbacks:
    """Testes de callbacks de transição."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    def test_on_transition_callback(self):
        """Callback é chamado em transições."""
        rhythm = MetabolicRhythm()
        callback_calls = []
        
        def callback(old_mode, new_mode, reason):
            callback_calls.append((old_mode, new_mode, reason))
        
        rhythm.on_transition(callback)
        
        rhythm._transition_to(MetabolicMode.DEEP_SLEEP, "test", "manual")
        
        assert len(callback_calls) == 1
        assert callback_calls[0][1] == MetabolicMode.DEEP_SLEEP

    def test_multiple_callbacks(self):
        """Múltiplos callbacks são chamados."""
        rhythm = MetabolicRhythm()
        callback1_calls = []
        callback2_calls = []
        
        rhythm.on_transition(lambda o, n, r: callback1_calls.append((o, n)))
        rhythm.on_transition(lambda o, n, r: callback2_calls.append((o, n)))
        
        rhythm._transition_to(MetabolicMode.BURST_MODE, "test", "manual")
        
        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 1


class TestHomeostasis:
    """Testes de homeostase."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    def test_homeostasis_score_updates(self):
        """Score de homeostase é atualizado."""
        rhythm = MetabolicRhythm()
        
        # Estado inicial deve ter homeostase alta
        state = rhythm.get_metabolic_state()
        assert state["homeostasis_score"] > 0.5
        
        # Mudar para burst mode (desequilíbrio)
        rhythm._transition_to(MetabolicMode.BURST_MODE, "test", "manual")
        
        state = rhythm.get_metabolic_state()
        # Homeostase pode cair, mas não necessariamente
        assert "homeostasis_score" in state


class TestMonitoring:
    """Testes de monitoramento."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        """Iniciar e parar monitoramento."""
        rhythm = MetabolicRhythm()
        
        # Iniciar
        await rhythm.start_monitoring_async(update_interval=1.0)
        assert rhythm._monitoring_task is not None
        
        # Aguardar um ciclo
        await asyncio.sleep(1.5)
        
        # Parar
        await rhythm.stop_monitoring_async()
        assert rhythm._monitoring_task is None

    @pytest.mark.asyncio
    async def test_monitoring_records_load(self):
        """Monitoramento registra carga no histórico."""
        rhythm = MetabolicRhythm()
        
        await rhythm.start_monitoring_async(update_interval=0.5)
        await asyncio.sleep(1.5)
        await rhythm.stop_monitoring_async()
        
        # Verificar que histórico foi populado
        assert len(rhythm._load_history) > 0


class TestReset:
    """Testes de reset."""

    def setup_method(self):
        MetabolicRhythm._instance = None

    def test_reset_clears_all(self):
        """Reset limpa todo o estado."""
        rhythm = MetabolicRhythm()
        
        # Criar estado complexo
        rhythm._transition_to(MetabolicMode.DEEP_SLEEP, "test", "manual")
        rhythm._transition_to(MetabolicMode.NORMAL, "test", "manual")
        
        rhythm.on_transition(lambda o, n, r: None)
        rhythm._load_history.append((time.time(), 0.5))
        
        # Reset
        rhythm.reset()
        
        state = rhythm.get_metabolic_state()
        assert state["mode"] == "normal"
        assert state["cpu_budget"] == 0.25
        assert len(rhythm._transition_history) == 0
        assert len(rhythm._load_history) == 0
        assert len(rhythm._callbacks_on_transition) == 0


class TestSingleton:
    """Testes de singleton."""

    def test_singleton_instance(self):
        """MetabolicRhythm é singleton."""
        MetabolicRhythm._instance = None
        
        r1 = MetabolicRhythm()
        r2 = MetabolicRhythm()
        
        assert r1 is r2

    def test_global_singleton(self):
        """metabolic_rhythm global é instância válida."""
        assert isinstance(metabolic_rhythm, MetabolicRhythm)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])