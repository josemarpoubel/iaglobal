# iaglobal/cli/bootstrap.py

import os
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

    def initialize(self) -> 'Orchestrator':
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

        logger.info("🛠️ [BOOTSTRAP] Iniciando inicialização do Orchestrator...")
        
        try:
            # 2. Lazy Imports (Evita carregamento circular)
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

            # 5. Observabilidade (Fail-safe)
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
                core = self.orchestrator.cpu_affinity.pin_current("bootstrap") or 0
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
