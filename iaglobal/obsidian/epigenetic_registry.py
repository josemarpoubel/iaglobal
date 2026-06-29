import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("iaglobal")


class EpigeneticRegistry:
    """Registra e recupera configurações epigenéticas via Obsidian Vault."""

    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path(
            "/home/kitohamachi/projeto-iaglobal/obsidian/epigenetic"
        )
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _epigenetic_id(self, agent_id: str, task_hash: str, error_type: str) -> str:
        return hashlib.sha3_512(
            f"{agent_id}:{task_hash}:{error_type}".encode()
        ).hexdigest()[:16]

    async def record_failure(
        self, agent_id: str, task_hash: str, error_type: str, context: Dict[str, Any]
    ) -> str:
        """Registra uma falha como 'marca epigenética' no Obsidian Vault."""
        metadata = {
            "agent_id": agent_id,
            "task_hash": task_hash,
            "error_type": error_type,
            "timestamp": time.time(),
            "context": context,
        }
        epigenetic_id = self._epigenetic_id(agent_id, task_hash, error_type)
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.info("🧬 [EPIGENETIC] Falha registrada: %s | %s", epigenetic_id, error_type)
        return epigenetic_id

    async def record_success(self, agent_id: str, task_hash: str) -> str:
        """Registra uma tentativa bem-sucedida como 'epigenética positiva'."""
        metadata = {
            "agent_id": agent_id,
            "task_hash": task_hash,
            "error_type": "success",
            "timestamp": time.time(),
            "context": {"status": "success"},
        }
        epigenetic_id = self._epigenetic_id(agent_id, task_hash, "success")
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.info("✅ [EPIGENETIC] Sucesso registrado: %s", epigenetic_id)
        return epigenetic_id

    async def get_adaptive_weights(
        self, agent_id: str, task_hash: str
    ) -> Dict[str, float]:
        """Recupera pesos epigenéticos para ajustar o comportamento do agente."""
        weights = {"retry_delay": 1.0, "model_priority": 1.0, "fallback_enabled": True}

        def _read_all() -> Dict[str, float]:
            import cbor2
            result = weights.copy()
            for file in self.base_path.glob("*.cbor"):
                try:
                    with open(file, "rb") as f:
                        data = cbor2.load(f)
                    if data.get("agent_id") == agent_id and data.get("task_hash") == task_hash:
                        error_type = data.get("error_type")
                        if error_type == "timeout":
                            result["retry_delay"] *= 1.5
                            result["model_priority"] *= 0.8
                        elif error_type == "invalid_output":
                            result["fallback_enabled"] = False
                        elif error_type == "security_rejection":
                            result["model_priority"] *= 0.5
                        elif error_type == "success":
                            result["retry_delay"] = min(result["retry_delay"] * 0.9, 1.0)
                except Exception as exc:
                    logger.warning("[EPIGENETIC] Falha ao ler %s: %s", file.name, exc)

            return result

        return await asyncio.to_thread(_read_all)

    async def registrar_violação_lei(
        self, agente_id: str, lei: str, contexto: Dict[str, Any]
    ) -> str:
        """Armazena violações de lei como marca epigenética para aprendizado dinâmico."""
        metadata = {
            "agent_id": agente_id,
            "task_hash": "lei_violation",
            "error_type": f"violation_{lei.lower().replace(' ', '_')}",
            "timestamp": time.time(),
            "context": contexto,
        }
        epigenetic_id = self._epigenetic_id(agente_id, "lei_violation", lei)
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.warning(
            "🧬 [EPIGENETIC] Violação de lei registrada: %s | Lei: '%s'",
            epigenetic_id, lei,
        )
        return epigenetic_id

    async def salvar_marca_epigenetica(
        self, chave: str, valor: Any, metadata: Dict[str, Any]
    ) -> str:
        """Salva uma marca epigenética no vault."""
        metadata.update({
            "chave": chave,
            "valor": valor,
            "timestamp": time.time(),
        })
        epigenetic_id = self._epigenetic_id(chave, "metadata", "marca")
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.info("🧬 [EPIGENETIC] Marca epigenética salva: %s", chave)
        return epigenetic_id


# Instância global
epigenetic_registry = EpigeneticRegistry()
