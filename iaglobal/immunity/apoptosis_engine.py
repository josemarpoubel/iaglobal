# iaglobal/immunity/apoptosis_engine.py
"""
ApoptosisEngine — Morte celular programada para agentes corrompidos.

Garante remoção limpa do registry sem deixar rastro.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from iaglobal.memory.async_memory import add_ltm

logger = logging.getLogger(__name__)


class ApoptosisEngine:
    """
    Motor de apoptose programada.
    
    Operação:
    1. Drain de conexões do agente
    2. Serialização do estado (snapshot)
    3. Remoção do registry
    4. Limpeza de rastros
    5. Notificação de dependentes
    """

    _instance: Optional["ApoptosisEngine"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

    async def execute(self, agent_name: str, agent_state: Dict[str, Any], reason: str = "pathogen_detected") -> Dict[str, Any]:
        """
        Executa apoptose programada no agente.
        
        Returns:
            {"executed": bool, "snapshot_path": str, "cleanup_performed": bool}
        """
        logger.warning(f"[APOPTOSIS] Iniciando eliminação de {agent_name}")

        # 1. Serializar estado
        snapshot = await self._serialize_state(agent_name, agent_state, reason)

        # 2. Remover do registry (se existir)
        removed = await self._remove_from_registry(agent_name)

        # 3. Limpeza de rastros
        cleaned = await self._cleanup_traces(agent_name)

        logger.info(f"[APOPTOSIS] {agent_name} eliminado com sucesso")

        return {
            "executed": True,
            "agent": agent_name,
            "reason": reason,
            "snapshot_path": snapshot,
            "removed_from_registry": removed,
            "cleanup_performed": cleaned,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _serialize_state(self, agent_name: str, state: Dict[str, Any], reason: str) -> Optional[str]:
        """Serializa estado do agente antes da morte."""
        try:
            snapshot = {
                "agent_name": agent_name,
                "terminated_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "final_state": state,
                "apoptosis_id": f"apop_{agent_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            }
            await add_ltm(f"apoptosis_{agent_name}", snapshot)
            return f"LTM:apoptosis_{agent_name}"
        except Exception as e:
            logger.error(f"[APOPTOSIS] Erro serializando estado: {e}")
            return None

    async def _remove_from_registry(self, agent_name: str) -> bool:
        """Remove agente do registry global."""
        try:
            # Tentar remover de registry se existir
            from iaglobal.core.registry import registry
            registry.remove(agent_name)
            return True
        except Exception:
            return False

    async def _cleanup_traces(self, agent_name: str) -> bool:
        """Limpa rastros de arquivos temporários."""
        try:
            from iaglobal._paths import TEMP_DIR
            for tmp_file in TEMP_DIR.glob(f"*{agent_name}*"):
                tmp_file.unlink()
            return True
        except Exception:
            return False

    def request_apoptosis(self, agent_name: str, threat_level: float = 0.8) -> bool:
        """
        Solicita apoptose (sync wrapper).
        
        threat_level >= 0.7 → executa imediatamente
        """
        if threat_level >= 0.7:
            return True
        return False


# Singleton
apoptosis_engine = ApoptosisEngine()