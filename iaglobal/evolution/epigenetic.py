# iaglobal/evolution/evolution/epigenetic.py

import json
from pathlib import Path
from typing import Any, Dict, Optional
from iaglobal.utils.logger import get_logger
from iaglobal.utils.atomic_io import AtomicJSONStore

logger = get_logger("iaglobal.evolution.epigenetic")

# ── Flags Epigenéticas Globais ──────────────────────────────────────────────
DEFAULT_FLAGS = {
    "use_advanced_sampling": True,
    "enable_reflexion_loop": True,
    "strict_homeostasis": False,
    "evolution_deep_mode": False,
    # Integração EvoAgent ↔ AgentBase (ver agent_base.py)
    "evo_self_critique": True,  # auto-crítica heurística pós-LLM (barata, sem LLM)
    "evo_reflexion_enabled": False,  # ReflexionEngine (consome ATP/LLM) — off por padrão
    "evo_learning_enabled": False,  # LearningLoop automático — off por padrão
    "evo_vaccine_persist": True,  # persistir failure_patterns no Obsidian + vacinas
    "immune_cycle": True,  # Fase 3: FailureAnalyzer + code_executor + VaccineLedger + JOL no handle()
    # Membrana seletiva: só o agente crítico (critic) tem direito a modelo externo
    # (cloud). Demais agentes usam Ollama local, forçando-os a evoluir com o
    # próprio substrato. Env EXTERNAL_ACCESS_ONLY_CRITIC=false desativa.
    "external_access_only_critic": True,
}

_flags = DEFAULT_FLAGS.copy()


def get_flag(name: str) -> bool:
    return _flags.get(name, DEFAULT_FLAGS.get(name, False))


def is_flag_enabled(name: str) -> bool:
    return get_flag(name)


def set_flag(name: str, value: bool):
    _flags[name] = value


def all_memory_flags() -> dict:
    return _flags.copy()


def get_max_iterations(strategy: str = "default") -> int:
    return 10 if strategy == "deep" else 5


def adapt_bandit_policy() -> dict:
    """
    Função de adaptação epigenética para o BanditPolicy.
    Analisa o estado global para sugerir ajustes de epsilon.
    """
    return {"epsilon": 0.2}


class EpigeneticMemory:
    """
    Sistema de Memória Epigenética do iaglobal.

    Permite que o organismo grave 'cicatrizes' (estresses metabólicos)
    ou 'vantagens' (sucessos recorrentes) no genome.json sem alterar
    o DNA base.

    Cada agente tem seu próprio arquivo genoma; o AtomicJSONStore é
    criado sob demanda por agent_id e cacheado em self._stores.
    """

    def __init__(self):
        self._cache = {}
        self._stores: Dict[str, AtomicJSONStore] = {}

    def _resolve_genome_path(self, agent_id: str) -> Optional[Path]:
        try:
            from iaglobal._paths import JSON_DIR

            return JSON_DIR / f"genome_{agent_id}.json"
        except Exception:
            return None

    def _get_store(self, agent_id: str) -> Optional[AtomicJSONStore]:
        path = self._resolve_genome_path(agent_id)
        if not path:
            return None
        key = str(path.resolve())
        if key not in self._stores:
            self._stores[key] = AtomicJSONStore(path, default={})
        return self._stores[key]

    @staticmethod
    def _apply_cicatriz(data: Any, trauma: str, severidade: float) -> Any:
        if not isinstance(data, dict):
            data = {}
        epigenetics = data.get("epigenetics", {})
        if not isinstance(epigenetics, dict):
            epigenetics = {}
        markers = epigenetics.get("markers", {})
        if not isinstance(markers, dict):
            markers = {}
        markers[trauma] = markers.get(trauma, 0.0) + severidade
        epigenetics["markers"] = markers
        data["epigenetics"] = epigenetics
        return data

    def gravar_cicatriz(self, agent_id: str, trauma: str, severidade: float):
        """
        Grava uma marca epigenética de falha ou estresse.

        Trauma: Ex: 'baixa_viabilidade_metabolica', 'violacao_lei_pensamento'
        Severidade: 0.0 a 1.0

        Usa AtomicJSONStore.mutate_sync() para garantir atomicidade
        (torn write + lost update) sob concorrência inter-processo.
        """
        store = self._get_store(agent_id)
        if not store:
            return

        try:
            store.mutate_sync(
                lambda data: self._apply_cicatriz(data, trauma, severidade)
            )
            logger.info(
                "[EPIGENÉTICA] Cicatriz gravada para %s: %s (+%.2f)",
                agent_id,
                trauma,
                severidade,
            )
        except Exception as e:
            logger.error("💥 Erro ao gravar marca epigenética: %s", e)

    def obter_expressao(self, agent_id: str) -> dict:
        """Retorna as marcações epigenéticas ativas para o agente."""
        path = self._resolve_genome_path(agent_id)
        if not path or not path.exists():
            return {"markers": {}}

        try:
            data = json.loads(path.read_text())
            return data.get("epigenetics", {"markers": {}})
        except Exception:
            return {"markers": {}}


epigenetic_memory = EpigeneticMemory()
