# iaglobal/evolution/evolutionruntime.py

# iaglobal/evolution/evolutionruntime.py

import threading
import time
import traceback
from typing import Optional, Protocol

from iaglobal.utils.logger import logger

# ------------------------------------------------------
# Evolver Protocol (type hint leve para segurança)
# ------------------------------------------------------
class Evolver(Protocol):
    def evolve(self) -> None:
        ...


class EvolutionRuntime:
    """
    Runtime resiliente de evolução contínua.

    Responsável por:
    - executar ciclos autônomos
    - evitar múltiplas threads duplicadas
    - recovery automático
    - métricas de saúde
    - graceful shutdown
    - heartbeat de execução
    """

    def __init__(
        self,
        evolver: Evolver,
        interval: int = 60,
        auto_restart: bool = True,
        daemon: bool = True
    ):

        self.evolver = evolver
        self.interval = max(5, interval)
        self.base_interval = self.interval
        self.auto_restart = auto_restart
        self.daemon = daemon

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # métricas internas
        self.cycles = 0
        self.failures = 0
        self.last_execution: Optional[float] = None
        self.last_error: Optional[str] = None
        self._consecutive_stable = 0

    # =====================================================
    # PUBLIC API
    # =====================================================

    def start(self):
        """Inicia runtime de evolução (singleton)."""
        if self._running:
            logger.warning("⚠️ EvolutionRuntime já está ativo.")
            return

        logger.info("🧠 Iniciando Evolution Runtime...")
        self._running = True

        self._thread = threading.Thread(
            target=self._background_loop,
            daemon=self.daemon,
            name="IAGlobal-EvolutionRuntime"
        )
        self._thread.start()
        logger.info("✅ Evolution Runtime iniciado.")

    def stop(self):
        """Shutdown graceful."""
        logger.info("🛑 Encerrando Evolution Runtime...")
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("✅ Evolution Runtime encerrado.")

    def status(self) -> dict:
        """Estado operacional do runtime."""
        return {
            "running": self._running,
            "cycles": self.cycles,
            "failures": self.failures,
            "last_execution": self.last_execution,
            "last_error": self.last_error,
            "thread_alive": self._thread.is_alive() if self._thread else False
        }

    # =====================================================
    # INTERNAL LOOP
    # =====================================================

    def _background_loop(self):
        """Loop cognitivo contínuo."""
        logger.info("♾️ Background evolution loop ativo.")
        logger.info("📊 Config: interval=%ds | auto_restart=%s | daemon=%s", self.interval, self.auto_restart, self.daemon)

        while self._running:
            started_at = time.time()
            try:
                gen_before = getattr(self.evolver, "generation", 0)
                logger.info("🧬 [CICLO %d] Iniciando ciclo evolutivo...", self.cycles + 1)
                self.evolver.evolve()
                self.cycles += 1
                gen_after = getattr(self.evolver, "generation", 0)
                if gen_after > gen_before:
                    self._consecutive_stable = 0
                    self.interval = min(self.interval, self.base_interval)
                else:
                    self._consecutive_stable += 1
                    if self._consecutive_stable >= 3:
                        self.interval = min(self.interval * 2, 600)
                        self._consecutive_stable = 0
                self.last_execution = time.time()
                duration = round(time.time() - started_at, 3)
                logger.info("🧠 [CICLO %d] Ciclo completo em %.3fs | total_cycles=%d | failures=%d | stable=%d interval=%ds",
                            self.cycles, duration, self.cycles, self.failures, self._consecutive_stable, self.interval)

            except Exception as e:
                self.failures += 1
                self.last_error = str(e)
                logger.error("💥 [CICLO] Evolution loop failure #%d: %s", self.failures, e)
                logger.error(traceback.format_exc())

                if not self.auto_restart:
                    logger.critical("🛑 [CICLO] Auto-restart desabilitado — encerrando runtime.")
                    self._running = False
                    break

                logger.warning("🔄 [CICLO] Runtime continuará ativo após falha #%d. Próxima tentativa em %ds...",
                               self.failures, max(1, self.interval))

            finally:
                elapsed = time.time() - started_at
                sleep_time = max(1, self.interval - elapsed)
                logger.info("😴 [CICLO] Aguardando %.1fs até próximo ciclo (interval=%ds, elapsed=%.1fs)",
                            sleep_time, self.interval, elapsed)
                time.sleep(sleep_time)
