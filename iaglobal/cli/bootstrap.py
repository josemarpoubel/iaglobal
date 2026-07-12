# iaglobal/cli/bootstrap.py

import os
import sys
from dotenv import load_dotenv

# Carrega .env IMEDIATAMENTE, antes de qualquer importação do iaglobal
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

import asyncio
import logging
from iaglobal.core.orchestrator import Orchestrator
from iaglobal.observability.health import HealthCheck
from iaglobal.observability.metrics_collector import MetricsCollector
from iaglobal._paths import CORE_DB

logger = logging.getLogger("ia-global")

class Bootstrap:
    _instance = None

    def __init__(self):
        self.orchestrator = None
        self.initialized = False

    def reset(self) -> None:
        """Reseta o estado do bootstrap para permitir reinicialização."""
        self.orchestrator = None
        self.initialized = False

    async def initialize(self) -> 'Orchestrator':
        """
        Inicializa todos os serviços core do sistema de forma segura.
        """
        if self.initialized and self.orchestrator:
            return self.orchestrator

        # 1. Garantia de Estrutura
        try:
            from iaglobal.core.structure import ensure_structure
            ensure_structure()
            logger.info("✅ Estrutura de diretórios verificada.")
        except Exception as e:
            logger.critical("Falha ao preparar diretórios: %s", e)
            raise SystemExit("Sistema não pode continuar sem permissões de pasta.")

        # 1.1 Life Signal Collector (instala cedo para capturar logs de inicialização)
        try:
            from iaglobal.utils.life_signal_collector import collector as life_collector
            from iaglobal import _paths
            life_signal_file = _paths.DATA_DIR / "life_signals.json"
            life_collector.install(life_signal_file)
            logger.info("[BOOTSTRAP] LifeSignalCollector ativo — %s", life_signal_file)
        except Exception as e:
            logger.debug("[BOOTSTRAP] LifeSignalCollector skip: %s", e)

        # 1.2 ErrorPersistence — persiste erros reais em errors.json + error/
        # instalado cedo para que a métrica '0 erros' reflita a verdade
        # (antes o app.log registrava dezenas de erros nunca persistidos).
        try:
            from iaglobal.immunity.error_persistence import install as install_error_persistence
            install_error_persistence()
            logger.info("[BOOTSTRAP] ErrorPersistence ativo — erros reais serão persistidos.")
        except Exception as e:
            logger.debug("[BOOTSTRAP] ErrorPersistence skip: %s", e)

        # 2. ⚖️ TRIBUNAL DE GENESIS — Valida DNA ancestral + agentes antes de nascer
        try:
            from iaglobal.genesis.tribunal import GenesisTribunal
            tribunal = GenesisTribunal(block_on_failure=True)
            await tribunal.executar()
            logger.info("⚖️ [TRIBUNAL] DNA ancestral e agentes verificados e aprovados.")
        except SystemExit:
            raise
        except Exception as e:
            logger.critical("[TRIBUNAL] Falha ao executar tribunal: %s", e)
            raise SystemExit(f"Tribunal de Genesis falhou: {e}")

        logger.info("🛠️ [BOOTSTRAP] Iniciando inicialização do Orchestrator...")
        
        try:
            # 3. Lazy Imports (Evita carregamento circular)
            from iaglobal.core.orchestrator import Orchestrator
            from iaglobal.memory.memory_storage import storage
            from iaglobal.memory.backup_manager import MemoryManager
            from iaglobal.models.event_bus import bus
            from iaglobal.memory.memory_vector import init_db
            from iaglobal.core.config import DATA_DIR, BACKUP_DIR
            
            # 3. Inicialização da Persistência
            init_db()
            
            # 4. Instanciação dos Core Services
            self.memory = storage
            self.memory_manager = MemoryManager(str(DATA_DIR), str(BACKUP_DIR))
            self.bus = bus
            
            # Inicializa Orchestrator (gerencia suas próprias dependências internas)
            self.orchestrator = Orchestrator()
            
            # Inicializar componentes do Orchestrator (async)
            await self.orchestrator.initialize()
            logger.info("[BOOTSTRAP] Orchestrator async init completo")

            # 5. Chappie — Núcleo da Autonomia Computacional
            _set_chappie = None  # Initialize as None in case import fails
            try:
                from iaglobal.chappie import VacuumDaemon, ErrorEnricher, LineageGuardian, _set_chappie
                from iaglobal.chappie.ivm_axiom import init_ivm_axiom_com_persistencia
                from iaglobal._paths import MEMORY_SWAP_DIR
                self.chappie_ivm = init_ivm_axiom_com_persistencia(db_path=MEMORY_SWAP_DIR / "ivm.db")
                self.chappie_vacuum = VacuumDaemon(interval_hours=1.0)
                self.chappie_error = ErrorEnricher()
                self.chappie_lineage = LineageGuardian()
                _set_chappie(ivm=self.chappie_ivm, vacuum=self.chappie_vacuum,
                            error=self.chappie_error, lineage=self.chappie_lineage)
                asyncio.create_task(self.chappie_vacuum.start(), name="vacuum-daemon")
                logger.info("🧬 [CHAPPIE] 4/4 módulos ativos: IVM | Vacuum | ErrorEnricher | LineageGuardian")
            except Exception as e:
                logger.warning("[CHAPPIE] Bootstrap parcial: %s", e)
                self.chappie_ivm = None
                self.chappie_vacuum = None
                self.chappie_error = None
                self.chappie_lineage = None
                if _set_chappie is not None:
                    _set_chappie()

            # 6. Observabilidade (Fail-safe)
            try:
                from iaglobal.observability.health import HealthCheck
                logger.debug("📊 Health: %s", HealthCheck.summary())
            except Exception as e:
                logger.warning("Erro ao inicializar observabilidade: %s", e)

            # 6. Runtime e Configurações Dinâmicas
            if os.environ.get("EVOLUTION_AUTO") == "1":
                self.orchestrator.evolution_runtime.start()

            # Configura CPU affinity (Fail-safe)
            try:
                core = await self.orchestrator.cpu_affinity.pin_current("bootstrap") or 0
                logger.info("[CPU] Affinity configurado: core %d", core)
            except Exception as e:
                logger.debug("[CPU] Affinity skip: %s", e)

            # 7. Serviços assíncronos
            from iaglobal.storage.batch_writer import batch_writer
            batch_writer.start()
            
            self.initialized = True
            logger.info("✅ [BOOTSTRAP] Orchestrator e serviços prontos.")
            return self.orchestrator

        except Exception as e:
            logger.exception("💥 [BOOTSTRAP] Falha fatal na inicialização: %s", e)
            raise RuntimeError(f"Falha na inicialização do sistema: {e}")

# Instância global única
bootstrap = Bootstrap()
