# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from iaglobal._paths import PROJECT_ROOT
from iaglobal.core.orchestrator import Orchestrator
from iaglobal.utils.logger import get_logger

load_dotenv(PROJECT_ROOT / ".env")

logger = get_logger("iaglobal.cli.bootstrap")


def _discover_pipeline_agents() -> list:
    """Descobre os agentes do pipeline a partir dos módulos `iaglobal.graphs.nodes.no_*`.

    Cada arquivo `no_<agent>.py` exporta `run_<agent>` (AGENTS.md §1). O nome
    do agente (sem o prefixo `no_`) é o que cpu_affinity usa como agent_id —
    assim bandit.begin_generation("critic") encontra o agent_id já registrado
    com budget e core atribuído.
    """
    import os as _os

    nodes_dir = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "..", "graphs", "nodes"
    )
    nodes_dir = _os.path.abspath(nodes_dir)
    agents: list = []
    if not _os.path.isdir(nodes_dir):
        return agents
    for fname in sorted(_os.listdir(nodes_dir)):
        if (
            fname.startswith("no_")
            and fname.endswith(".py")
            and fname != "__init__.py"
            and not fname.startswith("_")
        ):
            agents.append(fname[3:-3])
    return agents


def datetime_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Bootstrap:
    _instance = None

    PHASE2_STEPS = (
        "orchestrator_init",
        "chappie",
        "observability",
        "evolution_runtime",
        "cpu_affinity",
        "batch_writer",
        "mitochondrial_probe",
        "warmup",
    )

    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.initialized = False
        self._phase1_done = False
        self._phase2_done = False
        self._phase2_task: Optional[asyncio.Task] = None
        self._phase2_started_at: Optional[float] = None
        self._phase2_progress: Dict[str, str] = {}
        self._phase1_started_at: Optional[float] = None
        self._phase1_completed_at: Optional[float] = None
        self._phase2_completed_at: Optional[float] = None
        self._phase1_invocation_count: int = 0
        self._phase2_schedule_count: int = 0
        self._ready_at_iso: Optional[str] = None
        self._fast_path_count: int = 0

    def reset(self) -> None:
        self.orchestrator = None
        self.initialized = False
        self._phase1_done = False
        self._phase2_done = False
        if self._phase2_task and not self._phase2_task.done():
            self._phase2_task.cancel()
        self._phase2_task = None
        self._phase2_started_at = None
        self._phase2_progress = {}

    def metrics(self) -> Dict[str, Any]:
        time.time()
        phase1_duration = (
            round(self._phase1_completed_at - self._phase1_started_at, 3)
            if self._phase1_started_at is not None
            and self._phase1_completed_at is not None
            else None
        )
        phase2_duration = (
            round(self._phase2_completed_at - self._phase2_started_at, 3)
            if self._phase2_started_at is not None
            and self._phase2_completed_at is not None
            else None
        )
        time_to_ready = (
            round(self._phase2_completed_at - self._phase1_started_at, 3)
            if self._phase1_started_at is not None
            and self._phase2_completed_at is not None
            else None
        )
        return {
            "phase1_invocation_count": self._phase1_invocation_count,
            "phase2_schedule_count": self._phase2_schedule_count,
            "fast_path_count": self._fast_path_count,
            "phase1_duration_seconds": phase1_duration,
            "phase2_duration_seconds": phase2_duration,
            "phase2_task_count": 0 if self._phase2_task is None else 1,
            "time_to_ready_seconds": time_to_ready,
            "ready_at_iso": self._ready_at_iso,
        }

    def snapshot(self) -> Dict[str, Any]:
        complete: list[str] = []
        if self._phase1_done:
            complete.append("phase1")
        if self._phase2_done:
            complete.append("phase2")
        current = None
        if not self._phase1_done:
            current = "phase1"
        elif self._phase2_task is not None and not self._phase2_task.done():
            current = "phase2"
        elapsed = 0.0
        if (
            self._phase2_started_at
            and self._phase2_task is not None
            and not self._phase2_task.done()
        ):
            elapsed = time.time() - self._phase2_started_at
        snap = {
            "phase1_done": self._phase1_done,
            "phase2_done": self._phase2_done,
            "phase2_running": bool(
                self._phase2_task is not None and not self._phase2_task.done()
            ),
            "current_phase": current,
            "phase2_steps": dict(self._phase2_progress),
            "phase2_elapsed_seconds": round(elapsed, 2),
            "complete": complete,
            "metrics": self.metrics(),
        }
        return snap

    async def ensure_phase1(self) -> None:
        self._phase1_invocation_count += 1
        if self._phase1_done:
            self._fast_path_count += 1
            if self._phase2_task is None:
                self._schedule_phase2()
            return

        self._phase1_started_at = time.time()
        try:
            try:
                from iaglobal.core.structure import ensure_structure

                ensure_structure()
                logger.info("✅ [BOOTSTRAP] Estrutura de diretórios verificada.")
            except Exception as e:
                logger.critical("Falha ao preparar diretórios: %s", e)
                raise SystemExit("Sistema não pode continuar sem permissões de pasta.")

            try:
                from iaglobal.utils.life_signal_collector import (
                    collector as life_collector,
                )
                from iaglobal import _paths

                life_signal_file = _paths.DATA_DIR / "life_signals.json"
                life_collector.install(life_signal_file)
                logger.info(
                    "[BOOTSTRAP] LifeSignalCollector ativo — %s", life_signal_file
                )
            except Exception as e:
                logger.debug("[BOOTSTRAP] LifeSignalCollector skip: %s", e)

            try:
                from iaglobal.immunity.error_persistence import (
                    install as install_error_persistence,
                )

                install_error_persistence()
                logger.info("[BOOTSTRAP] ErrorPersistence ativo.")
            except Exception as e:
                logger.debug("[BOOTSTRAP] ErrorPersistence skip: %s", e)

            try:
                from iaglobal.genesis.tribunal import GenesisTribunal

                tribunal = GenesisTribunal(block_on_failure=True)
                await tribunal.executar()
                logger.info("⚖️ [TRIBUNAL] DNA ancestral e agentes aprovados.")
            except SystemExit:
                raise
            except Exception as e:
                logger.critical("[TRIBUNAL] Falha: %s", e)
                raise SystemExit(f"Tribunal de Genesis falhou: {e}")

            try:
                from iaglobal.memory.memory_storage import storage
                from iaglobal.memory.backup_manager import MemoryManager
                from iaglobal.models.event_bus import bus
                from iaglobal.memory.memory_vector import init_db
                from iaglobal.core.config import DATA_DIR, BACKUP_DIR

                init_db()
                self.memory = storage
                self.memory_manager = MemoryManager(str(DATA_DIR), str(BACKUP_DIR))
                self.bus = bus
            except Exception as e:
                logger.exception("💥 [BOOTSTRAP] Falha em phase1/persistência: %s", e)
                raise

            try:
                self.orchestrator = Orchestrator()
                logger.info("🛠️ [BOOTSTRAP] Orchestrator instanciado (Phase1).")
            except Exception as e:
                logger.exception(
                    "💥 [BOOTSTRAP] Falha ao instanciar Orchestrator: %s", e
                )
                raise

        finally:
            self._phase1_completed_at = time.time()
        self._phase1_done = True
        logger.info("⚡ [BOOTSTRAP] Phase1 completo — MCP pode responder.")
        self._schedule_phase2()

    def _schedule_phase2(self) -> None:
        if self._phase2_task is not None:
            return
        self._phase2_schedule_count += 1
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._phase2_started_at = time.time()
        self.phase2_progress_reset()
        self._phase2_task = loop.create_task(
            self._run_phase2(), name="bootstrap-phase2"
        )
        logger.info("🛌 [BOOTSTRAP] Phase2 agendada em background.")

    def phase2_progress_reset(self) -> None:
        self._phase2_progress = {step: "pending" for step in self.PHASE2_STEPS}

    async def _run_phase2(self) -> None:
        try:
            await self._phase2()
            self._phase2_done = True
            self._phase2_completed_at = time.time()
            self.initialized = True
            self._ready_at_iso = datetime_iso_now()
            logger.info("✅ [BOOTSTRAP] Phase2 completa — sistema operacional.")
        except Exception as e:
            logger.exception("💥 [BOOTSTRAP] Phase2 falhou: %s", e)
            self._phase2_progress["__error__"] = str(e)

    async def _phase2_step(self, name: str, coro_factory) -> None:
        self._phase2_progress[name] = "running"
        try:
            await coro_factory()
            self._phase2_progress[name] = "ok"
        except Exception as e:
            self._phase2_progress[name] = f"error: {e}"
            logger.warning("[BOOTSTRAP] %s falhou: %s", name, e)

    async def _phase2(self) -> None:
        assert self.orchestrator is not None

        async def _orch_init() -> None:
            await self.orchestrator.initialize()
            logger.info("[BOOTSTRAP] Orchestrator async init completo")

        await self._phase2_step("orchestrator_init", _orch_init)

        async def _chappie() -> None:
            from iaglobal.chappie import (
                VacuumDaemon,
                ErrorEnricher,
                LineageGuardian,
                _set_chappie,
            )
            from iaglobal.chappie.ivm_axiom import init_ivm_axiom_com_persistencia
            from iaglobal._paths import MEMORY_SWAP_DIR

            self.chappie_ivm = init_ivm_axiom_com_persistencia(
                db_path=MEMORY_SWAP_DIR / "ivm.db"
            )
            self.chappie_vacuum = VacuumDaemon(interval_hours=1.0)
            self.chappie_error = ErrorEnricher()
            self.chappie_lineage = LineageGuardian()
            _set_chappie(
                ivm=self.chappie_ivm,
                vacuum=self.chappie_vacuum,
                error=self.chappie_error,
                lineage=self.chappie_lineage,
            )
            asyncio.create_task(self.chappie_vacuum.start(), name="vacuum-daemon")
            logger.info("🧬 [CHAPPIE] 4/4 módulos ativos")

        await self._phase2_step("chappie", _chappie)

        async def _observability() -> None:
            try:
                from iaglobal.observability.health import HealthCheck

                logger.debug("Health: %s", HealthCheck.summary())
            except Exception as e:
                logger.debug("Observability skip: %s", e)

        await self._phase2_step("observability", _observability)

        async def _evolution() -> None:
            if (
                os.environ.get("EVOLUTION_AUTO") == "1"
                and self.orchestrator is not None
                and self.orchestrator.evolution_runtime is not None
            ):
                self.orchestrator.evolution_runtime.start()

        await self._phase2_step("evolution_runtime", _evolution)

        async def _cpu_affinity() -> None:
            try:
                if (
                    self.orchestrator is not None
                    and self.orchestrator.cpu_affinity is not None
                ):
                    # Enforcement real: pina o processo a 25% da capacidade
                    # total de núcleos (dinâmico por máquina). Antes, o
                    # scheduler distribuía budgets simbólicos mas nunca
                    # impunha limite no SO — o processo usava 100% de um
                    # núcleo (ou de todos) livremente.
                    result = await asyncio.to_thread(
                        self.orchestrator.cpu_affinity.apply_process_affinity
                    )
                    if result.get("enforced"):
                        logger.info(
                            "[CPU] Enforcement aplicado: %d núcleos de %d "
                            "(%.0f%% da capacidade, regra de 25%%/núcleo)",
                            result["target_cores"],
                            result["total_cores"],
                            result["fraction"] * 100,
                        )
                    else:
                        logger.info(
                            "[CPU] Enforcement não aplicado (%s) — processo "
                            "sem teto de CPU no SO",
                            result.get("reason", "desconhecido"),
                        )
                    core = (
                        await self.orchestrator.cpu_affinity.pin_current("bootstrap")
                        or 0
                    )
                    logger.info("[CPU] Affinity core %d", core)
            except Exception as e:
                logger.debug("[CPU] Affinity skip: %s", e)

        await self._phase2_step("cpu_affinity", _cpu_affinity)

        async def _cpu_affinity_register_agents() -> None:
            """Registra os agentes do pipeline no cpu_affinity (map_balanced).

            Sem isto, o budget permanece como regra morta: os agentes so existem
            no manager depois que bandit.begin_generation() os cria lazily, sem
            entrada em _budgets e sem distribuicao per-core. Aqui descobrimos os
            `no_*.py` agents e aplicamos map_balanced() para que:
              - cada agente receba um core logico via hash deterministico;
              - o teto de geracoes LLM (gate) saiba o orcamento agregado;
              - dispersion_report / rebalance / boost operem sobre os agentes reais.
            """
            try:
                from iaglobal.execution.cpu_affinity import cpu_affinity

                agents = _discover_pipeline_agents()
                if not agents:
                    logger.debug("[CPU] Nenhum agente de pipeline descoberto")
                    return
                await cpu_affinity.map_balanced(agents)
                cores = cpu_affinity._total_cores
                logger.info(
                    "[CPU] %d agentes registrados em %d cores (ate %d geracoes "
                    "locais concorrentes: 25%%/agente x %d cores)",
                    len(agents),
                    cores,
                    cores * 4,
                    cores,
                )
                await cpu_affinity.set_priority_boost(["critic"], boost_percent=50)
            except Exception as e:
                logger.debug("[CPU] register_agents skip: %s", e)

        await self._phase2_step("cpu_affinity_register", _cpu_affinity_register_agents)

        async def _batch_writer() -> None:
            from iaglobal.storage.batch_writer import batch_writer

            batch_writer.start()

        await self._phase2_step("batch_writer", _batch_writer)

        async def _mito_probe() -> None:
            from iaglobal.core.mitochondrial_probe import mitochondrial_probe

            mitochondrial_probe.start_background_task()

        await self._phase2_step("mitochondrial_probe", _mito_probe)

        async def _warmup() -> None:
            from iaglobal.providers.contract import registry as _provider_registry

            results = await _provider_registry.warmup_all(timeout=120)
            ok = sum(1 for v in results.values() if v)
            total = len(results)
            if total == 0:
                logger.info("[WARMUP] Nenhum provider com warmup")
            elif ok == total:
                logger.info("[WARMUP] %d/%d providers aquecidos", ok, total)
            else:
                logger.warning(
                    "[WARMUP] %d/%d providers (%d falharam)",
                    ok,
                    total,
                    total - ok,
                )

        await self._phase2_step("warmup", _warmup)

    async def initialize(self) -> "Orchestrator":
        await self.ensure_phase1()
        if self._phase2_task is not None and not self._phase2_task.done():
            await self._phase2_task
        if self._phase2_task is not None and self._phase2_task.exception():
            exc = self._phase2_task.exception()
            raise RuntimeError(f"Phase2 falhou: {exc}") from exc
        return self.orchestrator

    async def wait_full(self) -> "Orchestrator":
        return await self.initialize()


bootstrap = Bootstrap()
