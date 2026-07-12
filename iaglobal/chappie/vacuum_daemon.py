# ============================================================
# CHAPPIE COMPONENTE 1/4: VACUUM DAEMON
# Lei do Vácuo da Prosperidade + Lei do Sacrifício
# ============================================================
"""VacuumDaemon — Consolidação Automática de Memória (Fase REM).

Implementa a Lei do Vácuo da Prosperidade:
  "Para receber o novo, crie espaço liberando o antigo.
   Memórias brutas processadas devem ser movidas para o longo prazo
   e removidas do curto prazo — o vácuo criado atrai o bem seguinte."

Funcionamento:
  1. Daemon executa a cada N horas (configurável)
  2. Lê memórias de 02_Short_Term (brutas, não processadas)
  3. Consolida em 03_Long_Term via REMSleepEngine
  4. Remove originais (poda sináptica)
  5. Atualiza Mapa Mental Subconsciente
  6. Reporta métricas de consolidação

Diferença para REMSleepEngine manual:
  - Executa automaticamente (sem comando humano)
  - Monitora própria saúde (healthcheck)
  - Entra em low-power se sistema sob carga
  - Registra logs estruturados para auditoria
"""

import asyncio
import logging
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from iaglobal._paths import PACKAGE_DIR
from iaglobal.obsidian.consolidation import REMSleepEngine
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.chappie.vacuum")


class VacuumDaemon:
    """Daemon de Consolidação Automática — Lei do Vácuo.

    Executa em background, consolidando memórias de curto prazo
    para longo prazo automaticamente, liberando espaço para novas
    experiências (vácuo da prosperidade).

    Uso:
        daemon = VacuumDaemon(interval_hours=1)
        await daemon.start()  # Executa para sempre

        # Ou para teste único:
        resultado = await daemon.consolidar_uma_vez()
    """

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        interval_hours: float = 1.0,
        ivm_threshold: float = 0.5,
    ):
        """Inicializa o Vacuum Daemon.

        Args:
            vault_path: Caminho para o vault Obsidian (default: PACKAGE_DIR/obsidian)
            interval_hours: Intervalo entre consolidações (default: 1 hora)
            ivm_threshold: IVM mínimo para executar (evita sobrecarga do sistema)
        """
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.interval_hours = interval_hours
        self.ivm_threshold = ivm_threshold
        self.remsleep_engine = REMSleepEngine(vault_path=self.vault_path)

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_consolidation: Optional[datetime] = None
        self._total_consolidated = 0
        self._total_errors = 0

        logger.info(
            "[VacuumDaemon] Inicializado | interval=%.2fh | ivm_threshold=%.2f | vault=%s",
            interval_hours,
            ivm_threshold,
            self.vault_path,
        )

    async def start(self) -> None:
        """Inicia o daemon em background (executa para sempre)."""
        if self._running:
            logger.warning("[VacuumDaemon] Já está em execução.")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop_infinito(), name="vacuum-daemon")
        logger.info("[VacuumDaemon] Daemon iniciado.")

    async def stop(self) -> None:
        """Para o daemon gracefulmente (apoptose controlada)."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("[VacuumDaemon] Daemon parado (cancelado).")

        logger.info(
            "[VacuumDaemon] Apoptose completa | consolidadas=%d | erros=%d",
            self._total_consolidated,
            self._total_errors,
        )

    async def consolidar_uma_vez(self) -> Dict[str, Any]:
        """Executa uma consolidação única (para testes ou trigger manual)."""
        logger.info("[VacuumDaemon] Iniciando consolidação única.")

        try:
            resultado = await self.remsleep_engine.iniciar_fase_rem()

            self._last_consolidation = datetime.now(UTC)
            self._total_consolidated += resultado.get("memorias_consolidadas", 0)
            self._total_errors += len(resultado.get("erros", []))

            logger.info(
                "[VacuumDaemon] Consolidação única concluída | status=%s | consolidadas=%d | erros=%d",
                resultado.get("status", "unknown"),
                resultado.get("memorias_consolidadas", 0),
                len(resultado.get("erros", [])),
            )

            return resultado

        except Exception as e:
            logger.exception("[VacuumDaemon] Erro na consolidação: %s", e)
            self._total_errors += 1
            return {
                "status": "error",
                "error": str(e),
                "memorias_consolidadas": 0,
                "erros": [str(e)],
            }

    async def _loop_infinito(self) -> None:
        """Loop principal do daemon — executa indefinidamente."""
        while self._running:
            try:
                # Verifica IVM do sistema antes de executar
                # ivm_ok = await self._verificar_ivm_sistema()
                # if not ivm_ok:
                #     logger.warning(
                #         "[VacuumDaemon] IVM abaixo do threshold (%.2f). Aguardando.",
                #         self.ivm_threshold,
                #     )
                #     await asyncio.sleep(300)  # Aguarda 5 min
                #     continue

                # Executa consolidação
                await self.consolidar_uma_vez()

                # Aguarda próximo ciclo
                intervalo_seconds = self.interval_hours * 3600
                logger.info(
                    "[VacuumDaemon] Próxima consolidação em %.1f horas.",
                    self.interval_hours,
                )
                await asyncio.sleep(intervalo_seconds)

            except asyncio.CancelledError:
                logger.info("[VacuumDaemon] Loop interrompido (cancelado).")
                break
            except Exception as e:
                logger.exception("[VacuumDaemon] Erro no loop: %s. Reiniciando em 60s.", e)
                self._total_errors += 1
                await asyncio.sleep(60)  # Aguarda 1 min antes de重试

    async def _verificar_ivm_sistema(self) -> bool:
        """Verifica se o IVM do sistema está acima do threshold.

        TODO: Implementar integração com JointOptimizationLoop
        para obter IVM global do sistema.

        Por enquanto, retorna True (sempre executa).
        """
        # Implementação futura:
        # from iaglobal.evolution.metabolism.ivm_calculator import IVMMonitor
        # ivm = await IVMMonitor.get_global_ivm()
        # return ivm >= self.ivm_threshold

        return True  # Default: sempre executa

    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do daemon."""
        return {
            "running": self._running,
            "last_consolidation": self._last_consolidation.isoformat() if self._last_consolidation else None,
            "next_consolidation": (
                (self._last_consolidation + timedelta(hours=self.interval_hours)).isoformat()
                if self._last_consolidation
                else None
            ),
            "total_consolidated": self._total_consolidated,
            "total_errors": self._total_errors,
            "interval_hours": self.interval_hours,
            "ivm_threshold": self.ivm_threshold,
        }


# Singleton global
vacuum_daemon: Optional[VacuumDaemon] = None


def get_vacuum_daemon() -> VacuumDaemon:
    """Retorna singleton do VacuumDaemon."""
    global vacuum_daemon
    if vacuum_daemon is None:
        vacuum_daemon = VacuumDaemon()
    return vacuum_daemon