# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ============================================================
# ARQUIVO: iaglobal/genesis/genesis_purifier.py
# FUNÇÃO: Purificação de Linhagem e Sincronização Genômica
# LEI: Lei da Replicação - A herança genética deve preservar a identidade.
# ============================================================

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Tuple

from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
from iaglobal.utils.logger import get_logger

logger = logging.getLogger("iaglobal")

class GenesisPurifier:
    """
    Agente de Purificação Genômica.
    Garante que todos os componentes do ecossistema possuam a linhagem oficial.
    """

    def __init__(self):
        self.official_hash = GENESIS_HASH_OFFICIAL
        self.purified_count = 0
        self.errors = []

    def verify_component_dna(self, file_path: Path) -> Tuple[bool, str]:
        """Verifica se o arquivo contém a referência ao hash oficial."""
        try:
            content = file_path.read_text(encoding="utf-8")
            if self.official_hash in content:
                return True, "VÁLIDO"
            return False, "DNA_DIVERGENTE"
        except Exception as e:
            return False, f"ERRO_LEITURA: {str(e)}"

    async def purify_component(self, file_path: Path):
        """Injeta a linhagem oficial se ela estiver ausente."""
        try:
            def _read():
                return file_path.read_text(encoding="utf-8")

            content = await asyncio.to_thread(_read)

            header = f"# 🧬 LINEAGE_MARKER: {self.official_hash}\n"

            if header not in content:
                if content.startswith("#!"):
                    lines = content.splitlines()
                    lines.insert(1, f"# {self.official_hash}")
                    new_content = "\n".join(lines)
                else:
                    new_content = header + content

                def _write(payload):
                    file_path.write_text(payload, encoding="utf-8")

                await asyncio.to_thread(_write, new_content)
                self.purified_count += 1
                logger.info(f"[PURIFIER] 🧬 Linhagem injetada em: {file_path.name}")
        except Exception as e:
            self.errors.append((str(file_path), str(e)))

    async def run_global_purification(self):
        """Varre agentes e nós para garantir soberania genômica."""
        logger.info("🌌 Iniciando Purificação Genômica Global...")

        targets = [
            "iaglobal/agents",
            "iaglobal/graphs/nodes",
            "iaglobal/genesis"
        ]

        for target in targets:
            target_path = Path(f"/home/kitohamachi/projeto-iaglobal/{target}")

            def _exists(p=target_path):
                return p.exists()

            if not await asyncio.to_thread(_exists):
                continue

            def _list_files(p=target_path):
                return list(p.rglob("*.py"))

            files = await asyncio.to_thread(_list_files)
            for f in files:
                valid, status = self.verify_component_dna(f)
                if not valid:
                    await self.purify_component(f)

        logger.info(f"✨ Purificação Concluída: {self.purified_count} componentes sincronizados.")
        if self.errors:
            logger.error(f"🚨 {len(self.errors)} falhas na purificação.")

async def main():
    purifier = GenesisPurifier()
    await purifier.run_global_purification()

if __name__ == "__main__":
    asyncio.run(main())
