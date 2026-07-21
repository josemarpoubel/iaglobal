# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
MitochondrialProbe — Sonda de Potencial Mitocondrial do Event Loop.

Monitora continuamente o "lag" do event loop do asyncio para detectar
início de hipóxia sistêmica (bloqueio por I/O síncrono) antes do colapso.

Analogia Biológica:
- Event Loop = Gradiente eletroquímico (força próton-motriz)
- Tasks = Piruvato (substrato do Ciclo de Krebs)
- Lag = Acúmulo de lactato (hipóxia)
- Crash = Necrose celular

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Sensor endógeno do estado do gradiente
- AXIOMA 8 (Sinalização): Broadcast de saúde via logs e /health
"""

import asyncio
import time
from typing import Callable, List, Awaitable, Dict, Any
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.core.mitochondrial_probe")


class MitochondrialProbe:
    """Sonda de Potencial Mitocondrial — Guardião do Gradiente do Event Loop.

    Não é apenas um monitor passivo. É um regulador alostérico que:
    1. Mede o "lag" do event loop (tempo extra além do sleep esperado)
    2. Dispara alertas críticos se lag > 50ms (início de hipóxia)
    3. (Futuro) Inibe criação de tasks não-essenciais se gradiente < threshold

    Arquitetura:
    - Singleton global para estado compartilhado
    - Loop de monitoramento em background (baixa prioridade)
    - Proteção contra cancelamento (asyncio.shield)
    - Callbacks registráveis para futura inibição alostérica
    """

    # Thresholds de Hipóxia
    HYPOXIA_THRESHOLD_SECONDS = (
        0.25  # 250ms (hardware 4-core CPU, evita falso-positivo em startup spike)
    )
    MONITOR_INTERVAL_SECONDS = 1.0  # Monitora a cada 1 segundo
    PROBE_SLEEP_SECONDS = 0.01  # 10ms (yield mínimo ao loop)

    STARTUP_GRACE_SECONDS = 10.0  # Não alerta nos primeiros 10s (startup spike)

    def __init__(self):
        self.current_lag = 0.0
        self.hypoxia_detected = False
        self._alert_callbacks: List[Callable[[float], Awaitable[None]]] = []
        self._monitor_task: asyncio.Task = None
        self._startup_time = time.perf_counter()

    def register_alosteric_inhibitor(
        self, callback: Callable[[float], Awaitable[None]]
    ):
        """Registra callback para inibição alostérica quando hipóxia detectada.

        Args:
            callback: Função async que recebe lag (em segundos) como argumento
        """
        self._alert_callbacks.append(callback)
        logger.info(
            "[MITO-PROBE] Inibidor alostérico registrado | total=%d",
            len(self._alert_callbacks),
        )

    async def start_monitoring(self):
        """Loop de monitoramento contínuo (baixa prioridade).

        Este método deve ser executado como task de background no bootstrap.
        Protegido contra cancelamento por asyncio.shield.
        """
        logger.info(
            "[MITO-PROBE] Iniciando sonda | threshold=%.0fms | interval=%.0fs | probe_sleep=%.0fms",
            self.HYPOXIA_THRESHOLD_SECONDS * 1000,
            self.MONITOR_INTERVAL_SECONDS,
            self.PROBE_SLEEP_SECONDS * 1000,
        )

        while True:
            try:
                # Protege o ciclo de monitoramento contra cancelamento
                await asyncio.shield(self._monitor_cycle())
            except asyncio.CancelledError:
                logger.warning("[MITO-PROBE] Sonda cancelada (shutdown?)")
                raise
            except Exception as e:
                # Nunca deixa a sonda morrer silenciosamente
                logger.exception("[MITO-PROBE] Erro no ciclo de monitoramento: %s", e)
                # Aguarda 1s antes de tentar novamente (fallback)
                await asyncio.sleep(1.0)

    async def _monitor_cycle(self):
        """Ciclo único de monitoramento (mede lag, dispara alertas)."""
        start = time.perf_counter()

        # Yield mínimo ao event loop (a "sonda" que mede viscosidade)
        await asyncio.sleep(self.PROBE_SLEEP_SECONDS)

        # Calcula lag: tempo real - tempo esperado
        elapsed = time.perf_counter() - start
        expected = self.PROBE_SLEEP_SECONDS
        lag = elapsed - expected

        self.current_lag = lag

        # Detecta hipóxia (com graça de startup para evitar falso positivo)
        if lag > self.HYPOXIA_THRESHOLD_SECONDS:
            elapsed_startup = time.perf_counter() - self._startup_time
            if elapsed_startup < self.STARTUP_GRACE_SECONDS:
                if not self.hypoxia_detected:
                    logger.info(
                        "[MITO-PROBE] Lag elevado durante startup (%.0fms < %.0fs de gracejo) — ignorando",
                        lag * 1000,
                        self.STARTUP_GRACE_SECONDS,
                    )
            elif not self.hypoxia_detected:
                self.hypoxia_detected = True
                logger.critical(
                    "[MITO-PROBE] ⚠️ GRADIENTE EM COLAPSO: %.0fms de lag (threshold=%.0fms)",
                    lag * 1000,
                    self.HYPOXIA_THRESHOLD_SECONDS * 1000,
                )
                # Dispara inibição alostérica (callbacks)
                await self._trigger_alosteric_inhibitors(lag)
        else:
            if self.hypoxia_detected:
                # Recuperação
                self.hypoxia_detected = False
                logger.info(
                    "[MITO-PROBE] ✅ Gradiente restaurado: %.0fms de lag",
                    lag * 1000,
                )

        # Aguarda próximo ciclo (intervalo total)
        # Compensa tempo gasto no monitoramento
        sleep_time = max(0, self.MONITOR_INTERVAL_SECONDS - elapsed)
        await asyncio.sleep(sleep_time)

    async def _trigger_alosteric_inhibitors(self, lag: float):
        """Dispara todos os callbacks de inibição alostérica registrados."""
        if not self._alert_callbacks:
            return

        logger.warning(
            "[MITO-PROBE] Disparando %d inibidores alostéricos (lag=%.0fms)",
            len(self._alert_callbacks),
            lag * 1000,
        )

        for i, callback in enumerate(self._alert_callbacks):
            try:
                await callback(lag)
                logger.debug("[MITO-PROBE] Inibidor %d executado com sucesso", i + 1)
            except Exception as e:
                logger.exception(
                    "[MITO-PROBE] Falha em inibidor alostérico %d: %s", i + 1, e
                )

    def get_health_status(self) -> Dict[str, Any]:
        """Retorna status atual para /health endpoint.

        Returns:
            Dict com métricas de saúde do gradiente:
            - current_lag_ms: lag atual em milissegundos
            - hypoxia_detected: bool indicando hipóxia ativa
            - threshold_ms: threshold de hipóxia em ms
            - status: "healthy" ou "hypoxic"
        """
        return {
            "current_lag_ms": round(self.current_lag * 1000, 2),
            "hypoxia_detected": self.hypoxia_detected,
            "threshold_ms": self.HYPOXIA_THRESHOLD_SECONDS * 1000,
            "status": "hypoxic" if self.hypoxia_detected else "healthy",
        }

    def start_background_task(self, loop: asyncio.AbstractEventLoop = None):
        """Inicia task de background em um event loop específico.

        Conveniência para bootstrap. Se loop=None, usa o loop atual.

        Returns:
            asyncio.Task: Task de monitoramento
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        self._monitor_task = loop.create_task(self.start_monitoring())
        logger.info(
            "[MITO-PROBE] Task de monitoramento iniciada | task_id=%s",
            id(self._monitor_task),
        )
        return self._monitor_task


# Singleton global
mitochondrial_probe = MitochondrialProbe()
