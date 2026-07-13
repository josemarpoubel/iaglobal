# iaglobal/graphs/communication/membrane_key.py
"""
MembraneKey — Chave de criptografia de membrana para sinalização celular segura.

Permite simbiose com sistemas externos autorizados.
"""

import hashlib
import secrets
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any

from iaglobal.immunity.entropy_sentinel import entropy_sentinel
from iaglobal.security.pysecurity1024 import gerar_node_id_soberano

logger = logging.getLogger(__name__)


class MembraneKey:
    """
    Chave de membrana para agentes externos.

    Operação:
    1. Gera chave derivada do genesis hash
    2. Assina agentes externos com permissão
    3. Permite sinalização via AcetylcholineBus
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._keys: Dict[str, Dict[str, Any]] = {}
        try:
            from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

            self._genesis_hash = GENESIS_HASH_OFFICIAL
        except Exception:
            self._genesis_hash = (
                entropy_sentinel._genesis_hash
                if hasattr(entropy_sentinel, "_genesis_hash")
                else "default"
            )

    def generate_key(self, system_name: str, permissions: list = None) -> str:
        """
        Gera chave de membrana para sistema externo.

        Returns:
            Chave fonética soberana (não falsificável)
        """
        if permissions is None:
            permissions = ["signal"]

        # Derivar chave do genesis + nome do sistema
        combined = f"{self._genesis_hash}:{system_name}:{secrets.token_hex(8)}".encode()
        key_bytes = hashlib.sha3_512(combined).digest()[:32]

        # Renderizar como ID fonético
        membrane_key = gerar_node_id_soberano(key_bytes)

        self._keys[system_name] = {
            "key": membrane_key,
            "permissions": permissions,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,  # Permanente até revogação
            "validated": True,
        }

        logger.info(
            f"[MEMBRANE-KEY] Generated for {system_name}: {membrane_key[:15]}..."
        )
        return membrane_key

    def validate_key(self, system_name: str, key: str) -> bool:
        """
        Valida chave de membrana.

        Returns:
            True se chave é válida e não revogada
        """
        if system_name in self._keys:
            key_data = self._keys[system_name]
            if key_data.get("key") == key and key_data.get("validated", False):
                return True

        # Buscar por chave específica (para simbiontes externos)
        for sys, data in self._keys.items():
            if data.get("key") == key and data.get("validated", False):
                return True

        logger.warning(f"[MEMBRANE] Key invalid or not found")
        return False

    def grant_permission(self, system_name: str, permission: str) -> bool:
        """Adiciona permissão à chave existente."""
        key_data = self._keys.get(system_name)
        if not key_data:
            return False

        if permission not in key_data["permissions"]:
            key_data["permissions"].append(permission)
            logger.info(f"[MEMBRANE] Granted {permission} to {system_name}")

        return True

    def revoke_key(self, system_name: str) -> bool:
        """Revoga chave de membrana (simbiose terminada)."""
        if system_name in self._keys:
            del self._keys[system_name]
            logger.warning(f"[MEMBRANE] Key revogada para {system_name}")
            return True
        return False


# Singleton
membrane_key = MembraneKey()
