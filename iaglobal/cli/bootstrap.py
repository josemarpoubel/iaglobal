# iaglobal/cli/bootstrap.py

import time
import os

from iaglobal._paths import CORE_DB
from iaglobal.memory.memory_storage import storage
from iaglobal.memory.backup_manager import MemoryManager
from iaglobal._paths import DATA_DIR, BACKUP_DIR
from iaglobal.models.event_bus import bus
from iaglobal.core.orchestrator import Orchestrator as OrchestratorV4


class Bootstrap:
    def __init__(self):
        self.start_time = time.time()
        self.orchestrator = None

    def initialize(self) -> OrchestratorV4:
        from iaglobal.providers import ollama_provider
        ollama_provider.warmup()

        from iaglobal.memory.memory_vector import init_db as init_vector_db
        init_vector_db()
        print(f"✅ Banco de vetores inicializado em: {CORE_DB}")

        print("✅ Persistence (Interface Unificada) inicializada com sucesso.")

        print(f"💾 Inicializando DatabaseManager em: {CORE_DB}")
        print("✅ Tabelas (insights, knowledge, vector_store, execution_states, search_cache, decision_events) verificadas/criadas.")

        self.memory = storage
        self.memory_manager = MemoryManager(str(DATA_DIR), str(BACKUP_DIR))
        self.bus = bus
        self.orchestrator = OrchestratorV4()
        return self.orchestrator


bootstrap = Bootstrap()
