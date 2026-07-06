# iaglobal/immunity/epigenetic_masking.py
"""
EpigeneticMasking — Máscaras de execução para proteção de memória crítica.

Simula barreira hematoencefálica digital:
- Apenas agentes validados podem acessar memory/core.db
- Feature flags controlam acesso granular
- Máscaras são carregadas via genesis hash
"""
import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, Optional, Any

from iaglobal.security.entropy_sentinel import entropy_sentinel

logger = logging.getLogger(__name__)


class EpigeneticMask:
    """Máscara de acesso a recursos críticos."""
    def __init__(self, name: str, allowed_agents: Set[str], genesis_hash: str):
        self.name = name
        self.allowed_agents = allowed_agents
        self.genesis_hash = genesis_hash
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.mask_id = hashlib.sha3_512(
            f"{genesis_hash}:{name}:{len(allowed_agents)}".encode()
        ).hexdigest()[:32]


class EpigeneticMasking:
    """
    Motor de máscaras epigenéticas.
    
    Operação:
    1. Carrega máscara baseada no genesis hash
    2. Valida agente contra lista de permissões
    3. Ativa/desativa acesso via feature flags
    """

    _instance: Optional["EpigeneticMasking"] = None
    _lock = threading.RLock()

    # Máscaras padrão (derivadas do genesis)
    CRITICAL_RESOURCES = {
        "core_db": ["planner", "architect", "coder", "evaluator", "evolution_committee"],
        "memory_vector": ["knowledge", "knowledge_analyzer", "memory_writer"],
        "ltm_stm": ["retrospective", "evolution_knowledge", "immune_monitor"],
        "registry": ["orchestrator_agent", "pipeline_updater", "entropy_sentinel"],
    }

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._masks: Dict[str, EpigeneticMask] = {}
        self._load_masks_from_genesis()

    def _load_masks_from_genesis(self) -> None:
        """Carrega máscaras baseadas no genesis hash."""
        try:
            from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
            genesis_hash = GENESIS_HASH_OFFICIAL
        except Exception:
            genesis_hash = getattr(entropy_sentinel, '_genesis_hash', None) or "default"
        
        for resource, agents in self.CRITICAL_RESOURCES.items():
            mask = EpigeneticMask(
                name=resource,
                allowed_agents=set(agents),
                genesis_hash=genesis_hash,
            )
            self._masks[resource] = mask
            logger.info(f"[EPIGENETIC-MASK] Created mask for {resource}: {mask.mask_id[:16]}...")

    def can_access(self, agent_name: str, resource: str) -> bool:
        """
        Verifica se agente tem permissão para acessar recurso.
        
        Usa:
        1. Validação do ID soberano (agente pertence ao genesis)
        2. Lista de permissões na máscara
        """
        # Verificar se agente é derivado do genesis
        agent_id = entropy_sentinel.get_sober_agent_id(agent_name)
        if not agent_id:
            logger.warning(f"[EPIGENETIC] Agente {agent_name} sem ID soberano - negado")
            return False

        # Verificar máscara
        mask = self._masks.get(resource)
        if not mask:
            return True  # Sem máscara = acesso livre

        if agent_name not in mask.allowed_agents:
            logger.warning(f"[EPIGENETIC] {agent_name} negado a {resource}")
            return False

        return True

    def check_and_enforce(self, agent_name: str, resource: str) -> Dict[str, Any]:
        """
        Verifica e aplica máscara.
        
        Returns:
            {"allowed": bool, "mask_id": str, "reason": str}
        """
        allowed = self.can_access(agent_name, resource)
        
        mask = self._masks.get(resource)
        mask_id = mask.mask_id if mask else "no-mask"

        return {
            "allowed": allowed,
            "mask_id": mask_id,
            "resource": resource,
            "agent": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def add_agent_to_mask(self, resource: str, agent_name: str) -> bool:
        """Adiciona agente à máscara de recurso."""
        with self._lock:
            if resource not in self._masks:
                # Criar nova máscara
                genesis_hash = entropy_sentinel._genesis_hash or "default"
                self._masks[resource] = EpigeneticMask(
                    name=resource,
                    allowed_agents={agent_name},
                    genesis_hash=genesis_hash,
                )
                return True
            
            self._masks[resource].allowed_agents.add(agent_name)
            return True


# Singleton
epigenetic_masking = EpigeneticMasking()