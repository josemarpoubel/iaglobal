# ============================================================
# ARQUIVO: iaglobal/evolution/metabolic_rhythm.py
# RITMO METABÓLICO: "Todo desequilíbrio deve gerar ação corretiva..."
# ============================================================
"""MetabolicRhythm — Sincronia Metabólica Profunda (Deep Sleep + Burst Mode).

A Lei da Homeostase estabelece que todo desequilíbrio deve gerar uma ação
corretiva proporcional. Este módulo implementa dois modos metabólicos:

1. **Deep Sleep** — Ciclo de repouso para monitoramento de baixa energia
2. **Burst Mode (Adrenalina)** — Quebra temporária do teto de 25% em emergências

Operação:
- Monitora carga do sistema e energia disponível (ATP)
- Detecta quando entrar em Deep Sleep (baixa demanda)
- Detecta quando ativar Burst Mode (emergência/alta demanda)
- Gerencia transições entre modos metabolicamente
- Preserva homeostase energética

Padrão Singleton — existe um único MetabolicRhythm para todo o ecossistema.

Exemplo de uso assíncrono:
    ```python
    from iaglobal.evolution.metabolic_rhythm import metabolic_rhythm

    # Verificar estado metabólico atual
    state = await metabolic_rhythm.get_metabolic_state_async()

    if state["mode"] == "deep_sleep":
        # Sistema em repouso - reduzir atividade
        await metabolic_rhythm.enter_deep_sleep_async()

    elif state["emergency"] and state["mode"] == "normal":
        # Emergência detectada - ativar burst mode
        await metabolic_rhythm.activate_burst_mode_async(
            duration_seconds=60,
            cpu_override=0.5,  # 50% em vez de 25%
        )
    ```
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolic_rhythm")


class MetabolicMode(Enum):
    """Modos metabólicos do sistema."""

    DEEP_SLEEP = "deep_sleep"
    NORMAL = "normal"
    BURST_MODE = "burst_mode"
    RECOVERY = "recovery"


@dataclass
class MetabolicState:
    """Estado metabólico atual do sistema."""

    mode: MetabolicMode
    cpu_budget: float  # 0.0 → 1.0 (orçamento de CPU atual)
    atp_level: float  # 0.0 → 1.0 (nível de energia disponível)
    load_average: float  # 0.0 → 1.0 (carga média do sistema)
    burst_mode_active: bool
    burst_mode_remaining: float  # Segundos restantes do burst mode
    deep_sleep_entered_at: Optional[float]
    last_mode_transition: float
    homeostasis_score: float  # 0.0 (desequilibrado) → 1.0 (equilibrado)


@dataclass
class ModeTransition:
    """Registro de uma transição de modo metabólico."""

    from_mode: MetabolicMode
    to_mode: MetabolicMode
    timestamp: float
    reason: str
    trigger: str  # "automatic" ou "manual"
    duration_previous_mode: float  # Quanto tempo durou o modo anterior


class MetabolicRhythm:
    """Ritmo Metabólico — Gerenciamento de Deep Sleep e Burst Mode.

    A Lei da Homeostase exige que o sistema mantenha equilíbrio energético.
    Este módulo:

    1. Monitora carga e energia (ATP) do sistema
    2. Detecta quando entrar em Deep Sleep (baixa demanda)
    3. Detecta quando ativar Burst Mode (emergência)
    4. Gerencia transições entre modos
    5. Preserva homeostase energética

    Limiares de Transição:

    **Deep Sleep** (economia de energia):
    - load_average < 0.2 por > 60 segundos
    - atp_level < 0.3 (energia baixa)
    - cpu_budget reduzido para 0.1 (10%)

    **Burst Mode** (adrenalina para emergências):
    - load_average > 0.8 por > 10 segundos
    - atp_level > 0.7 (energia suficiente)
    - cpu_budget aumentado para 0.5-0.8 (50-80%)
    - Duração máxima: 60 segundos

    **Recovery** (pós-burst mode):
    - Ativado automaticamente após burst mode
    - Duração: 2x duração do burst mode
    - cpu_budget reduzido para 0.3 (30%)

    Padrão Singleton — existe um único MetabolicRhythm para todo o ecossistema.
    """

    _instance: Optional["MetabolicRhythm"] = None
    _lock = threading.Lock()

    # Limiares configuráveis (epigenéticos)
    _DEEP_SLEEP_LOAD_THRESHOLD = 0.2  # < 20% de carga
    _DEEP_SLEEP_DURATION_SECONDS = 60  # Por quanto tempo manter carga baixa
    _DEEP_SLEEP_CPU_BUDGET = 0.1  # 10% de CPU em deep sleep

    _BURST_MODE_LOAD_THRESHOLD = 0.8  # > 80% de carga
    _BURST_MODE_DURATION_SECONDS = 10  # Por quanto tempo manter carga alta
    _BURST_MODE_MAX_DURATION = 60  # Duração máxima do burst mode
    _BURST_MODE_CPU_BUDGET = 0.5  # 50% de CPU em burst mode (pode chegar a 80%)
    _BURST_MODE_ATP_MIN = 0.7  # ATP mínimo necessário

    _RECOVERY_MULTIPLIER = 2.0  # Recovery dura 2x o burst mode
    _RECOVERY_CPU_BUDGET = 0.3  # 30% de CPU em recovery

    _HOMEOSTASIS_TARGET = 0.8  # Target de homeostase

    def __new__(cls, *args, **kwargs) -> "MetabolicRhythm":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._state = MetabolicState(
            mode=MetabolicMode.NORMAL,
            cpu_budget=0.25,  # 25% default (padrão iaglobal)
            atp_level=1.0,
            load_average=0.0,
            burst_mode_active=False,
            burst_mode_remaining=0.0,
            deep_sleep_entered_at=None,
            last_mode_transition=time.time(),
            homeostasis_score=1.0,
        )
        self._rlock = threading.RLock()
        self._transition_history: List[ModeTransition] = []
        self._load_history: List[Tuple[float, float]] = []  # (timestamp, load)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._callbacks_on_transition: List[Callable] = []

        logger.info(
            "[MetabolicRhythm] Ritmo Metabólico initialized | "
            "deep_sleep_threshold=%.2f | burst_mode_threshold=%.2f | cpu_budget_default=%.2f",
            self._DEEP_SLEEP_LOAD_THRESHOLD,
            self._BURST_MODE_LOAD_THRESHOLD,
            self._state.cpu_budget,
        )

    def _record_load(self, load: float) -> None:
        """Registra carga atual no histórico."""
        now = time.time()
        with self._rlock:
            self._load_history.append((now, load))
            # Manter últimos 120 segundos de histórico
            cutoff = now - 120
            self._load_history = [(t, l) for t, l in self._load_history if t > cutoff]

    def _calculate_average_load(self, window_seconds: float) -> float:
        """Calcula carga média em uma janela de tempo."""
        now = time.time()
        cutoff = now - window_seconds

        with self._rlock:
            recent_loads = [
                load for timestamp, load in self._load_history if timestamp > cutoff
            ]

        if not recent_loads:
            return 0.0

        return sum(recent_loads) / len(recent_loads)

    def _should_enter_deep_sleep(self) -> bool:
        """Verifica se deve entrar em Deep Sleep."""
        if self._state.mode != MetabolicMode.NORMAL:
            return False

        avg_load = self._calculate_average_load(self._DEEP_SLEEP_DURATION_SECONDS)

        return (
            avg_load < self._DEEP_SLEEP_LOAD_THRESHOLD
            and self._state.atp_level < 0.5  # Energia moderada-baixa
        )

    def _should_enter_burst_mode(self) -> bool:
        """Verifica se deve ativar Burst Mode."""
        if self._state.mode not in [MetabolicMode.NORMAL, MetabolicMode.RECOVERY]:
            return False

        avg_load = self._calculate_average_load(self._BURST_MODE_DURATION_SECONDS)

        return (
            avg_load > self._BURST_MODE_LOAD_THRESHOLD
            and self._state.atp_level > self._BURST_MODE_ATP_MIN
        )

    def _should_exit_burst_mode(self) -> bool:
        """Verifica se deve sair do Burst Mode."""
        if self._state.mode != MetabolicMode.BURST_MODE:
            return False

        with self._rlock:
            # Verificar se tempo máximo foi atingido
            if self._state.burst_mode_remaining <= 0:
                return True

            # Verificar se carga diminuiu
            avg_load = self._calculate_average_load(5)  # Últimos 5 segundos
            if avg_load < self._BURST_MODE_LOAD_THRESHOLD * 0.7:  # 70% do threshold
                return True

        return False

    def _transition_to(
        self, new_mode: MetabolicMode, reason: str, trigger: str = "automatic"
    ) -> None:
        """Executa transição para novo modo metabólico."""
        with self._rlock:
            old_mode = self._state.mode
            duration_previous = time.time() - self._state.last_mode_transition

            # Registrar transição
            transition = ModeTransition(
                from_mode=old_mode,
                to_mode=new_mode,
                timestamp=time.time(),
                reason=reason,
                trigger=trigger,
                duration_previous_mode=duration_previous,
            )
            self._transition_history.append(transition)

            # Limitar histórico
            if len(self._transition_history) > 100:
                self._transition_history = self._transition_history[-100:]

            # Atualizar estado
            self._state.mode = new_mode
            self._state.last_mode_transition = time.time()

            # Ajustar CPU budget baseado no modo
            if new_mode == MetabolicMode.DEEP_SLEEP:
                self._state.cpu_budget = self._DEEP_SLEEP_CPU_BUDGET
                self._state.deep_sleep_entered_at = time.time()
                logger.info(
                    "[MetabolicRhythm] 💤 Deep Sleep ativado | cpu_budget=%.2f | reason=%s",
                    self._state.cpu_budget,
                    reason,
                )

            elif new_mode == MetabolicMode.BURST_MODE:
                self._state.cpu_budget = self._BURST_MODE_CPU_BUDGET
                self._state.burst_mode_active = True
                self._state.burst_mode_remaining = self._BURST_MODE_MAX_DURATION
                logger.warning(
                    "[MetabolicRhythm] ⚡ BURST MODE ATIVADO | cpu_budget=%.2f | duration_max=%ds | reason=%s",
                    self._state.cpu_budget,
                    self._BURST_MODE_MAX_DURATION,
                    reason,
                )

            elif new_mode == MetabolicMode.RECOVERY:
                self._state.cpu_budget = self._RECOVERY_CPU_BUDGET
                self._state.burst_mode_active = False
                logger.info(
                    "[MetabolicRhythm] 🔄 Recovery mode | cpu_budget=%.2f | reason=%s",
                    self._state.cpu_budget,
                    reason,
                )

            elif new_mode == MetabolicMode.NORMAL:
                self._state.cpu_budget = 0.25  # Default 25%
                self._state.deep_sleep_entered_at = None
                logger.info(
                    "[MetabolicRhythm] ✅ Normal mode | cpu_budget=%.2f | reason=%s",
                    self._state.cpu_budget,
                    reason,
                )

            # Atualizar homeostasis score
            self._update_homeostasis_score()

            # Chamar callbacks
            for callback in self._callbacks_on_transition:
                try:
                    callback(old_mode, new_mode, reason)
                except Exception as e:
                    logger.error(
                        "[MetabolicRhythm] Erro no callback de transição: %s", e
                    )

    def _update_homeostasis_score(self) -> None:
        """Atualiza score de homeostase baseado no equilíbrio energético.

        NOTA: Esta função usa pesos 0.4/0.4/0.2 para CPU/ATP/estabilidade,
        que são coincidentemente iguais aos pesos base do IVM (P/E/C).
        Isto NÃO é o IVM canônico — é um cálculo de homeostase de ritmo
        metabólico com métricas diferentes (cpu_score, atp_score, stability_score).
        """
        # Pesos específicos de homeostase (não confundir com IVM)
        PESO_CPU = 0.4
        PESO_ATP = 0.4
        PESO_ESTABILIDADE = 0.2

        with self._rlock:
            # Fatores de homeostase:
            # 1. Proximidade do target de CPU budget
            cpu_target = 0.25  # Target ideal
            cpu_distance = abs(self._state.cpu_budget - cpu_target)
            cpu_score = max(0.0, 1.0 - cpu_distance)

            # 2. Nível de ATP
            atp_score = self._state.atp_level

            # 3. Estabilidade do modo (tempo desde última transição)
            time_since_transition = time.time() - self._state.last_mode_transition
            stability_score = min(1.0, time_since_transition / 60)  # 60s para máximo

            # Homeostasis = média ponderada
            homeostasis = (
                (cpu_score * PESO_CPU) + (atp_score * PESO_ATP) + (stability_score * PESO_ESTABILIDADE)
            )

            self._state.homeostasis_score = homeostasis

    async def start_monitoring_async(self, update_interval: float = 5.0) -> None:
        """
        Inicia monitoramento contínuo do ritmo metabólico.

        Args:
            update_interval: Intervalo entre verificações (segundos)
        """

        async def _monitor_loop():
            while True:
                try:
                    await self._monitoring_cycle_async()
                    await asyncio.sleep(update_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("[MetabolicRhythm] Erro no monitoring cycle: %s", e)
                    await asyncio.sleep(update_interval)

        self._monitoring_task = asyncio.create_task(_monitor_loop())
        logger.info(
            "[MetabolicRhythm] 🔄 Monitoring iniciado | interval=%.1fs", update_interval
        )

    async def stop_monitoring_async(self) -> None:
        """Para monitoramento contínuo."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("[MetabolicRhythm] 🛑 Monitoring parado")

    async def _monitoring_cycle_async(self) -> None:
        """Ciclo único de monitoramento."""
        # Simular leitura de carga do sistema (em produção, viria de métricas reais)
        current_load = await self._read_system_load_async()
        current_atp = await self._read_atp_level_async()

        # Atualizar estado
        with self._rlock:
            self._state.load_average = current_load
            self._state.atp_level = current_atp

        # Registrar no histórico
        self._record_load(current_load)

        # Verificar transições
        if self._should_enter_burst_mode():
            self._transition_to(
                MetabolicMode.BURST_MODE,
                f"Alta carga detectada (load={current_load:.2f})",
            )

        elif self._should_exit_burst_mode():
            # Sair do burst mode → entrar em recovery
            burst_duration = time.time() - self._state.last_mode_transition
            recovery_duration = burst_duration * self._RECOVERY_MULTIPLIER

            self._transition_to(
                MetabolicMode.RECOVERY,
                f"Burst mode completado → Recovery por {recovery_duration:.0f}s",
            )

            # Agendar retorno ao normal após recovery
            asyncio.create_task(self._schedule_recovery_exit_async(recovery_duration))

        elif self._should_enter_deep_sleep():
            self._transition_to(
                MetabolicMode.DEEP_SLEEP,
                f"Baixa carga prolongada (load={current_load:.2f})",
            )

        elif self._state.mode == MetabolicMode.DEEP_SLEEP:
            # Verificar se deve sair do deep sleep
            avg_load = self._calculate_average_load(10)
            if avg_load > self._DEEP_SLEEP_LOAD_THRESHOLD * 2:  # Dobrou a carga
                self._transition_to(
                    MetabolicMode.NORMAL,
                    f"Carga aumentou (load={avg_load:.2f})",
                )

    async def _read_system_load_async(self) -> float:
        """Lê carga atual do sistema (0.0 → 1.0)."""
        # Em produção, isso viria de métricas reais do sistema
        # Por enquanto, simulação baseada em tempo
        import random

        return random.uniform(0.1, 0.9)

    async def _read_atp_level_async(self) -> float:
        """Lê nível de ATP disponível (0.0 → 1.0)."""
        # Em produção, isso viria de métricas de energia/compute
        import random

        return random.uniform(0.5, 1.0)

    async def _schedule_recovery_exit_async(self, recovery_duration: float) -> None:
        """Agenda saída do recovery mode."""
        await asyncio.sleep(recovery_duration)

        with self._rlock:
            if self._state.mode == MetabolicMode.RECOVERY:
                self._transition_to(
                    MetabolicMode.NORMAL,
                    f"Recovery completado ({recovery_duration:.0f}s)",
                )

    async def activate_burst_mode_async(
        self,
        duration_seconds: float = 60.0,
        cpu_override: float = 0.5,
        reason: str = "manual_override",
    ) -> bool:
        """
        Ativa Burst Mode manualmente.

        Args:
            duration_seconds: Duração do burst mode
            cpu_override: Override do CPU budget (0.0 → 1.0)
            reason: Motivo da ativação manual

        Returns:
            bool: True se ativado com sucesso
        """
        with self._rlock:
            if self._state.mode in [MetabolicMode.BURST_MODE, MetabolicMode.DEEP_SLEEP]:
                logger.warning(
                    "[MetabolicRhythm] Não é possível ativar burst mode: modo atual=%s",
                    self._state.mode.value,
                )
                return False

        # Validar CPU override
        cpu_override = max(0.3, min(0.8, cpu_override))  # Limitar entre 30-80%

        with self._rlock:
            self._BURST_MODE_MAX_DURATION = duration_seconds
            self._BURST_MODE_CPU_BUDGET = cpu_override

            self._transition_to(
                MetabolicMode.BURST_MODE,
                reason,
                trigger="manual",
            )

        return True

    async def enter_deep_sleep_async(self, reason: str = "manual_override") -> bool:
        """
        Entra em Deep Sleep manualmente.

        Args:
            reason: Motivo da entrada manual

        Returns:
            bool: True se entrou com sucesso
        """
        with self._rlock:
            if self._state.mode in [MetabolicMode.BURST_MODE, MetabolicMode.RECOVERY]:
                logger.warning(
                    "[MetabolicRhythm] Não é possível entrar em deep sleep: modo atual=%s",
                    self._state.mode.value,
                )
                return False

            self._transition_to(
                MetabolicMode.DEEP_SLEEP,
                reason,
                trigger="manual",
            )

        return True

    async def wake_up_async(self, reason: str = "manual_wake") -> bool:
        """
        Sai do Deep Sleep manualmente.

        Args:
            reason: Motivo do despertar manual

        Returns:
            bool: True se despertou com sucesso
        """
        with self._rlock:
            if self._state.mode != MetabolicMode.DEEP_SLEEP:
                logger.warning(
                    "[MetabolicRhythm] Não é possível wake up: modo atual=%s",
                    self._state.mode.value,
                )
                return False

            self._transition_to(
                MetabolicMode.NORMAL,
                reason,
                trigger="manual",
            )

        return True

    def get_metabolic_state(self) -> Dict[str, Any]:
        """Retorna estado metabólico atual."""
        with self._rlock:
            return {
                "mode": self._state.mode.value,
                "cpu_budget": round(self._state.cpu_budget, 3),
                "atp_level": round(self._state.atp_level, 3),
                "load_average": round(self._state.load_average, 3),
                "burst_mode_active": self._state.burst_mode_active,
                "burst_mode_remaining": round(self._state.burst_mode_remaining, 1),
                "deep_sleep_entered_at": (
                    datetime.fromtimestamp(
                        self._state.deep_sleep_entered_at, timezone.utc
                    ).isoformat()
                    if self._state.deep_sleep_entered_at
                    else None
                ),
                "last_mode_transition": datetime.fromtimestamp(
                    self._state.last_mode_transition, timezone.utc
                ).isoformat(),
                "homeostasis_score": round(self._state.homeostasis_score, 3),
            }

    def get_transition_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna histórico de transições."""
        with self._rlock:
            recent = self._transition_history[-limit:]
            return [
                {
                    "from_mode": t.from_mode.value,
                    "to_mode": t.to_mode.value,
                    "timestamp": datetime.fromtimestamp(
                        t.timestamp, timezone.utc
                    ).isoformat(),
                    "reason": t.reason,
                    "trigger": t.trigger,
                    "duration_previous_mode": round(t.duration_previous_mode, 1),
                }
                for t in recent
            ]

    def on_transition(self, callback: Callable) -> None:
        """
        Registra callback para ser chamado em transições de modo.

        Args:
            callback: Função(old_mode, new_mode, reason)
        """
        with self._rlock:
            self._callbacks_on_transition.append(callback)

    def reset(self) -> None:
        """Reseta estado (para testes)."""
        with self._rlock:
            self._state = MetabolicState(
                mode=MetabolicMode.NORMAL,
                cpu_budget=0.25,
                atp_level=1.0,
                load_average=0.0,
                burst_mode_active=False,
                burst_mode_remaining=0.0,
                deep_sleep_entered_at=None,
                last_mode_transition=time.time(),
                homeostasis_score=1.0,
            )
            self._transition_history.clear()
            self._load_history.clear()
            self._callbacks_on_transition.clear()
            logger.info("[MetabolicRhythm] ✅ Estado resetado")


# Singleton global
metabolic_rhythm = MetabolicRhythm()
