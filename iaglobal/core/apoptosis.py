# iaglobal/core/apoptosis.py
import asyncio
import hashlib
import logging
import cbor2
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("iaglobal")


class ApoptosisEngine:
    """Mecanismo de morte programada com herança epigenética."""

    def __init__(self, epigenetic_path: Path | None = None):
        from iaglobal._paths import PACKAGE_DIR

        self.epigenetic_path = epigenetic_path or (
            PACKAGE_DIR / "obsidian" / "epigenetic"
        )
        self.backup_path = self.epigenetic_path / "apoptosis_archive"
        self.backup_path.mkdir(parents=True, exist_ok=True)

    async def trigger_apoptosis(
        self, agent_id: str, failure_count: int, max_retries: int = 3
    ) -> Optional[str]:
        """Dispara a apoptose se o agente falhar além do limite. Retorna o ID do clone evoluído."""
        if failure_count < max_retries:
            return None

        logger.critical(
            f"💀 [APOPTOSIS] Agente {agent_id[:8]}... excedeu {max_retries} falhas. Iniciando morte programada..."
        )

        # 1. Coleta todas as marcas epigenéticas do agente (async)
        agent_patterns = await asyncio.to_thread(
            lambda: list(self.epigenetic_path.glob("*.cbor"))
        )
        agent_memories = []

        for file in agent_patterns:
            data = await asyncio.to_thread(self._read_cbor, file)
            if data.get("agent_id") == agent_id:
                agent_memories.append(data)

        if not agent_memories:
            logger.warning(
                f"⚠️ [APOPTOSIS] Nenhuma memória encontrada para {agent_id}. Apoptose sem herança."
            )
            return None

        # 2. Cria um novo ID (clone) com DNA idêntico, mas geração incrementada
        new_agent_id = hashlib.sha3_512((agent_id + "_evolved").encode()).hexdigest()[
            :32
        ]
        logger.info(f"♻️ [APOPTOSIS] Nova geração gerada: {new_agent_id[:8]}...")

        # 3. Arquiva as memórias do agente antigo (async)
        archive_file = self.backup_path / f"{agent_id}_v{failure_count}.cbor"
        await asyncio.to_thread(
            self._write_cbor,
            archive_file,
            {
                "original_agent_id": agent_id,
                "new_agent_id": new_agent_id,
                "failures": failure_count,
                "epigenetic_memories": agent_memories,
                "timestamp": time.time(),
            },
        )

        logger.info(f"📁 [APOPTOSIS] Memórias arquivadas: {archive_file.name}")

        # 4. Registra as memórias como "herança" para o novo clone (async)
        for mem in agent_memories:
            mem["agent_id"] = new_agent_id
            new_file = (
                self.epigenetic_path
                / f"{hashlib.sha3_512(f'{new_agent_id}:{mem['task_hash']}:{mem['error_type']}'.encode()).hexdigest()[:16]}.cbor"
            )
            await asyncio.to_thread(self._write_cbor, new_file, mem)

        logger.info(
            f"🧬 [APOPTOSIS] {len(agent_memories)} memórias herdadas pelo clone {new_agent_id[:8]}..."
        )

        # 5. Remove as memórias originais do agente antigo (async)
        for file in agent_patterns:
            data = await asyncio.to_thread(self._read_cbor, file)
            if data.get("agent_id") == agent_id:
                await asyncio.to_thread(file.unlink)

        logger.info(f"🗑️ [APOPTOSIS] Memórias originais removidas. Apoptose completa.")
        return new_agent_id

    @staticmethod
    def _read_cbor(file: Path) -> Dict[str, Any]:
        with open(file, "rb") as f:
            return cbor2.load(f)

    @staticmethod
    def _write_cbor(file: Path, data: Dict[str, Any]) -> None:
        with open(file, "wb") as f:
            cbor2.dump(data, f)
