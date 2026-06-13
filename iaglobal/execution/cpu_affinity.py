# iaglobal/execution/cpu_affinity.py

import os
import sys
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class CpuAffinityManager:
    """
    Gerenciador de distribuição aleatória de agentes entre núcleos de CPU.

    Estratégia:
    - Seleção puramente aleatória via secrets
    - Sem fixação permanente
    - Sem métricas de limitação ou balanceamento
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cores: List[int] = self._detect_cores()
        self._last_agent_map: Dict[str, int] = {}

    # ==========================================================
    # DETECÇÃO DE NÚCLEOS
    # ==========================================================

    def _detect_cores(self) -> List[int]:
        count = os.cpu_count() or 1
        return list(range(count))

    def refresh_topology(self) -> None:
        with self._lock:
            self._cores = self._detect_cores()
        logger.info("[CPU] Topologia atualizada: %d cores detectados", len(self._cores))

    # ==========================================================
    # ATRIBUIÇÃO ALEATÓRIA
    # ==========================================================

    def assign_core_deterministic(self, agent_id: str) -> int:
        """
        Atribui núcleo baseado no hash do agente.
        Isso garante que o mesmo agente sempre rode no mesmo núcleo (melhoria de cache).
        """
        # Converte o hash (ID) para um inteiro e usa o módulo dos cores
        # Se agent_id for o seu hash SHA3-512, isso é perfeito.
        core_index = int(agent_id[:8], 16) % len(self._cores)
        core = self._cores[core_index]
        
        with self._lock:
            self._last_agent_map[agent_id] = core
            
        return core

    def pin_for_agent(self, agent: str) -> int:
        """Atribui e fixa um núcleo para o agente (alias para assign_core)."""
        return self.assign_core(agent)

    def pin_to_hash(self, agent_id: str) -> int:
        """
        Fixa o processo ao núcleo baseado no hash do ID (afinidade determinística).
        Esta é a fonte de verdade para afinidade no sistema.
        """
        core_index = int(agent_id[:8], 16) % len(self._cores)
        core = self._cores[core_index]
        
        if sys.platform == "linux":
            try:
                os.sched_setaffinity(0, {core})
            except Exception as e:
                logger.error("[CPU] Falha ao fixar afinidade: %s", e)
        
        return core

    # Agora, pin_current torna-se apenas um wrapper elegante
    def pin_current(self, agent_id: str) -> None:
        """Fixa o processo atual ao núcleo correspondente ao DNA do agente."""
        self.pin_to_hash(agent_id)

    def get_last_mapping(self, agent: str, default: int = 0) -> int:
        """Retorna o último núcleo atribuído a um agente."""
        return self._last_agent_map.get(agent, default)

    def random_core(self) -> int:
        """Retorna um núcleo aleatório sem atribuição."""
        return secrets.choice(self._cores)

    def map_balanced(self, agents: List[str]) -> Dict[str, int]:
        """Distribui lista de agentes de forma balanceada entre núcleos."""
        assignment = {}
        for i, agent in enumerate(agents):
            core = self._cores[i % len(self._cores)]
            assignment[agent] = core
        with self._lock:
            self._last_agent_map.update(assignment)
        logger.info("[CPU] Distribuição balanceada concluída para %d agentes em %d cores",
                     len(agents), len(self._cores))
        return assignment

    def dispersion_report(self) -> dict:
        """Relatório de dispersão dos agentes pelos núcleos."""
        with self._lock:
            counts = {core: 0 for core in self._cores}
            for core in self._last_agent_map.values():
                if core in counts:
                    counts[core] += 1
        total = sum(counts.values()) or 1
        max_count = max(counts.values()) if counts else 1
        imbalance = (max_count - total / len(self._cores)) / (total / len(self._cores)) if total else 0
        return {
            "total_cores": len(self._cores),
            "distribution": counts,
            "efficiency": 1.0 - imbalance * 0.1,
            "imbalance": round(imbalance, 2),
        }

    def rotate(self) -> None:
        """Alterna o núcleo do processo atual para o próximo disponível."""
        if not self._cores:
            return
        current = self._cores[0]
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            current = libc.sched_getcpu()
        except Exception:
            pass
        next_core = self._cores[(current + 1) % len(self._cores)]
        if sys.platform == "linux":
            try:
                os.sched_setaffinity(0, {next_core})
            except Exception:
                pass

    def get_thread_pool(self) -> ThreadPoolExecutor:
        """Retorna um ThreadPoolExecutor para o gerenciador de CPU."""
        return ThreadPoolExecutor(max_workers=len(self._cores))

    def rebalance_if_needed(self, *args, **kwargs):

        """Verifica e rebalanceia se a distribuição estiver muito desigual."""
        with self._lock:
            counts = {core: 0 for core in self._cores}
            for core in self._last_agent_map.values():
                if core in counts:
                    counts[core] += 1
        if not counts:
            return False
        max_count = max(counts.values())
        min_count = min(counts.values())
        if max_count - min_count > 2 and len(self._last_agent_map) > len(self._cores):
            agents = list(self._last_agent_map.keys())
            self.map_balanced(agents)
            return True
        return False

    def map_agents(self, agents: List[str]) -> Dict[str, int]:
        """Distribui lista de agentes em núcleos aleatórios."""
        assignment = {agent: secrets.choice(self._cores) for agent in agents}
        with self._lock:
            self._last_agent_map.update(assignment)

        logger.info("[CPU] Distribuição aleatória concluída para %d agentes", len(agents))
        return assignment


# Instância global
cpu_affinity = CpuAffinityManager()

