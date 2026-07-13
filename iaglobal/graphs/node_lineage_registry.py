# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/node_lineage_registry.py

"""
NodeLineageRegistry — Registro soberano de identidades de nós em memória.

Cada entrada no registry representa um nó soberano do pipeline,
derivado via Proof-of-Lineage: SHA3-512(G0 + node_uid).

Princípios:
- RAM-Only: nenhum hash ou uid é persistido em disco
- Thread-safe: acesso concorrente protegido por asyncio.Lock
- Imutável: uma vez registrado, o hash não é alterado (não modifica G0)
- Epifenômeno: se G0 mudar, todos os hashes ficam inválidos atomicamente

Fluxo:
    nascimento → generate_node_lineage(uid) → registry.register(node_name, uid, lineage_hash)
    runtime   → registry.validate(node_name) → True/False
    heartbeat → registry.validate_all() → {valid, total, valid_count, rejected}
    apoptose  → registry.unregister(node_name) → remove silenciosamente
"""

import hashlib
import logging
import asyncio
import time
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class NodeLineageRegistry:
    """
    Registry soberano em memória para Lineage_Hash de nós.

    Equivalente biológico: núcleo celular — mantém o DNA de cada
    componente do organismo e governa sua expressão (validação).
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[str, Dict[str, str]] = {}
            cls._instance._created_at = time.time()
            cls._instance._heartbeat_task = None
        return cls._instance

    async def register(
        self,
        node_name: str,
        node_uid: str,
        lineage_hash: str,
    ) -> None:
        """
        Registra um nó soberano no registry.

        Args:
            node_name: Nome do nó no pipeline (ex: "coder", "debug_unificado").
            node_uid: Identificador único efêmero do nó.
            lineage_hash: Hash derivado SHA3-512(G0 + node_uid).
        """
        async with self._lock:
            self._registry[node_name] = {
                "uid": node_uid,
                "lineage_hash": lineage_hash,
                "registered_at": time.time(),
            }
            logger.debug(
                "[LINEAGE_REGISTRY] Nó registrado — name=%s uid=%s",
                node_name,
                node_uid,
            )

    async def unregister(self, node_name: str) -> None:
        """
        Remove um nó do registry (apoptose silenciosa).

        Args:
            node_name: Nome do nó a remover.
        """
        async with self._lock:
            if node_name in self._registry:
                del self._registry[node_name]
                logger.debug(
                    "[LINEAGE_REGISTRY] Nó removido — name=%s",
                    node_name,
                )

    async def validate(self, node_name: str) -> bool:
        """
        Valida se um nó é soberano.

        A validação é feita por re-derivação: recalcula SHA3-512(G0 + uid)
        e compara com o hash armazenado no registry.

        Args:
            node_name: Nome do nó a validar.

        Returns:
            bool: True se o nó for soberano, False se não estiver registrado ou hash divergir.
        """
        async with self._lock:
            entry = self._registry.get(node_name)
            if not entry:
                logger.warning(
                    "[LINEAGE_REGISTRY] Nó não registrado — name=%s",
                    node_name,
                )
                return False

            expected_hash = self._derive_hash(entry["uid"])
            is_valid = entry["lineage_hash"] == expected_hash

            if not is_valid:
                logger.warning(
                    "[LINEAGE_REGISTRY] Soberania violada — name=%s uid=%s",
                    node_name,
                    entry["uid"],
                )

            return is_valid

    async def validate_all(self) -> Dict[str, Any]:
        """
        Valida todos os nós registrados (heartbeat).

        Equivalente biológico: vigilância imunológica periódica —
        verifica se alguma célula foi corrompida ou infectada.

        Returns:
            Dict com:
                - valid (bool): True se todos passarem.
                - total (int): Total de nós registrados.
                - valid_count (int): Nós válidos.
                - rejected (list): Lista de nós inválidos.
        """
        async with self._lock:
            rejected = []
            for node_name, entry in self._registry.items():
                expected_hash = self._derive_hash(entry["uid"])
                if entry["lineage_hash"] != expected_hash:
                    rejected.append(
                        {
                            "node_name": node_name,
                            "uid": entry["uid"],
                            "reason": "lineage_hash divergente",
                        }
                    )

            total = len(self._registry)
            valid_count = total - len(rejected)
            valid = len(rejected) == 0

            if valid:
                logger.info(
                    "[LINEAGE_REGISTRY] Heartbeat OK — %d/%d nós soberanos",
                    valid_count,
                    total,
                )
            else:
                logger.error(
                    "[LINEAGE_REGISTRY] Heartbeat FALHOU — %d/%d rejeitados",
                    len(rejected),
                    total,
                )

            return {
                "valid": valid,
                "total": total,
                "valid_count": valid_count,
                "rejected": rejected,
            }

    async def get_node_info(self, node_name: str) -> Optional[Dict[str, str]]:
        """
        Retorna informações de um nó sem expor o hash completo.

        Args:
            node_name: Nome do nó.

        Returns:
            Dict com uid e lineage_hash, ou None se não existir.
        """
        async with self._lock:
            return self._registry.get(node_name)

    async def list_nodes(self) -> list[str]:
        """Lista todos os nomes de nós registrados."""
        async with self._lock:
            return list(self._registry.keys())

    async def start_heartbeat(self, interval: float = 60.0):
        """
        Inicia heartbeat periódico em background.

        Args:
            interval: Intervalo em segundos entre validações.
        """
        if self._heartbeat_task is not None:
            return

        async def _heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.validate_all()
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.error("[LINEAGE_REGISTRY] Erro no heartbeat: %s", exc)

        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())
        logger.info("[LINEAGE_REGISTRY] Heartbeat iniciado — intervalo=%.1fs", interval)

    async def stop_heartbeat(self):
        """Interrompe heartbeat periódico."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            logger.info("[LINEAGE_REGISTRY] Heartbeat parado")

    def _derive_hash(self, node_uid: str) -> str:
        """
        Re-deriva Lineage_Hash via SHA3-512(G0 + node_uid).

        Importação lazy de genesis/identity.py para evitar ciclos.
        """
        from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

        g0 = bytes.fromhex(GENESIS_HASH_OFFICIAL)
        return hashlib.sha3_512(g0 + node_uid.encode()).hexdigest()
