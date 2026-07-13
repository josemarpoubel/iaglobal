# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/memory/vault_unifier.py
====================================
VaultUnifier — camada de unificação entre o vault Obsidian e o vault JSON canônico
para artefatos de linhagem (vaccines, failure_patterns, lineage_proofs).

Modelo biológico:
  - O vault JSON é o "DNA nuclear" — armazenamento canônico, estruturado,
    thread-safe, fonte única da verdade para o sistema computacional.
  - O vault Obsidian é o "RNA de expressão" — legível por humanos,
    editável, indexado por tags/links, mas derivado do JSON.

Write-through:
  Toda escrita no JSON é refletida no Obsidian em background. Se o Obsidian
  falhar, o JSON canônico persiste e a operação não é revertida (não causa
  perda de dados imunológicos).

Thread-safety:
  I/O de arquivo serializado por lineage_marker via threading.Lock(). Isso
  garante que duas apoptoses concorrentes da mesma linhagem não corrompam
  o arquivo JSON.

Async-first:
  Toda operação de I/O é encapsulada em asyncio.to_thread para não bloquear
  o event loop.
"""

import asyncio
import json
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

logger = get_logger("iaglobal.memory.vault_unifier")

# Diretórios canônicos
JSON_VAULT_DIR = Path(__file__).resolve().parent / "data" / "json"
JSON_VAULT_DIR.mkdir(parents=True, exist_ok=True)


class VaultUnifier:
    """
    Unifica persistência de artefatos de linhagem entre JSON canônico e Obsidian.

    Mantém interface compatível com `SubconsciousAPI.escrever_vacina` /
    `ler_vacina` para permitir drop-in replacement no VaccineLedger e
    ImmuneMemoryExchange sem alterar callers existentes.
    """

    def __init__(
        self, json_dir: Optional[Path] = None, vault_path: Optional[Path] = None
    ):
        self.json_dir = Path(json_dir or JSON_VAULT_DIR)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self._obsidian = SubconsciousAPI(vault_path=vault_path)
        # Lock por lineage_marker para write parallelism entre linhagens
        # distintas, mas serialização dentro da mesma linhagem.
        self._locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._global_lock = threading.Lock()  # protege dict de locks

    # ── Helpers de arquivo JSON (síncronos, rodam em thread pool) ──────

    def _json_path(self, marker: str) -> Path:
        return self.json_dir / f"linhagem_{marker}.json"

    def _read_json(self, marker: str) -> Optional[Dict[str, Any]]:
        path = self._json_path(marker)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(
                "[VAULT-UNIFIER] JSON corrompido %s (tratado como vazio): %s", path, e
            )
            return None

    def _write_json(self, marker: str, data: Dict[str, Any]) -> None:
        path = self._json_path(marker)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Helpers Obsidian (write-through best-effort) ───────────────────

    async def _write_obsidian(self, marker: str, conteudo_md: str) -> None:
        try:
            await self._obsidian.escrever_vacina(marker, conteudo_md)
        except Exception as e:
            logger.debug(
                "[VAULT-UNIFIER] write-through Obsidian falhou (não-bloqueante): %s", e
            )

    # ── API pública (compatível com SubconsciousAPI) ────────────────────

    async def ler_vacina(self, marker: str) -> Optional[str]:
        """
        Lê o ledger de vacinas.

        Fonte canônica: JSON local.
        Fallback: Obsidian (caso JSON ainda não tenha sido migrado).
        Retorna Markdown compatível com o parser legado do VaccineLedger.
        """

        def _read() -> Optional[str]:
            with self._lock_for(marker):
                data = self._read_json(marker)
            if data:
                return self._serialize_md(data.get("vacinas", []), marker)
            return None

        md = await asyncio.to_thread(_read)
        if md is not None:
            return md

        # Fallback final: tenta ler do Obsidian e retorna como está
        try:
            return await self._obsidian.ler_vacina(marker)
        except Exception as e:
            logger.debug("[VAULT-UNIFIER] fallback Obsidian falhou: %s", e)
        return None

    async def escrever_vacina(self, marker: str, conteudo: Any) -> Path:
        """
        Persiste vacinas no JSON canônico + write-through para Obsidian.

        Aceita tanto:
          - `List[Dict[str, Any]]`: patterns desestruturados (nova interface),
          - `str`: Markdown legado (compatibilidade com VaccineLedger._serialize).

        Returns:
            Path do arquivo JSON canônico.
        """
        from datetime import datetime, UTC

        if isinstance(conteudo, list):
            patterns = conteudo
            md = self._serialize_md(patterns, marker)
        else:
            # Legado: Markdown string — extrai patterns para JSON canônico
            patterns = self._parse_md(str(conteudo)) or []
            md = str(conteudo)

        def _write():
            path = self._json_path(marker)
            with self._lock_for(marker):
                data = {
                    "id": f"linhagem_{marker}",
                    "tipo": "VaccineLedger",
                    "lineage_marker": marker,
                    "timestamp": datetime.now(UTC).isoformat() + "Z",
                    "vacinas": sorted(patterns, key=lambda p: p.get("pattern", "")),
                }
                self._write_json(marker, data)
            return path

        path = await asyncio.to_thread(_write)

        # Write-through não-bloqueante para Obsidian
        await self._write_obsidian(marker, md)

        return path

    # ── Serialização / Parsing compatíveis com VaccineLedger ───────────

    @staticmethod
    def _parse_md(conteudo: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """Extrai lista de vacinas do Markdown do Obsidian (formato legado)."""
        if not conteudo:
            return []
        try:
            corpo = conteudo.split("---", 2)[-1]
            for linha in corpo.splitlines():
                if linha.strip().startswith("vacinas:"):
                    bloco = linha.split("vacinas:", 1)[1].strip()
                    if bloco:
                        return json.loads(bloco)
        except Exception as e:
            logger.warning("[VAULT-UNIFIER] parse MD falhou: %s", e)
        return None

    @staticmethod
    def _serialize_md(patterns: List[Dict[str, Any]], marker: str) -> str:
        """Monta Markdown legado para write-through no Obsidian."""
        from datetime import datetime, UTC

        ts = datetime.now(UTC).isoformat()
        vacinas = json.dumps(
            sorted(patterns, key=lambda p: p.get("pattern", "")),
            ensure_ascii=False,
        )
        return (
            f"---\n"
            f'id: "linhagem_{marker}"\n'
            f'tipo: "VaccineLedger"\n'
            f'lineage_marker: "{marker}"\n'
            f'timestamp: "{ts}Z"\n'
            f'tags: ["#vacina", "#imunidade"]\n'
            f"---\n\n"
            f"# Vacinas da Linhagem {marker}\n\n"
            f"vacinas: {vacinas}\n"
        )

    # ── Lock factory ───────────────────────────────────────────────────

    def _lock_for(self, marker: str) -> threading.Lock:
        with self._global_lock:
            if marker not in self._locks:
                self._locks[marker] = threading.Lock()
            return self._locks[marker]

    # ── Métodos auxiliares para migração ───────────────────────────────

    def migrate_obsidian_to_json(self, marker: str) -> bool:
        """
        Migra vacinas do Obsidian para JSON canônico (operação síncrona,
        deve ser chamada dentro de um executor de thread).
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            md = loop.run_until_complete(self._obsidian.ler_vacina(marker))
        except RuntimeError:
            md = asyncio.run(self._obsidian.ler_vacina(marker))

        if not md:
            return False

        patterns = self._parse_md(md)
        if not patterns:
            return False

        self._write_json(
            marker,
            {
                "id": f"linhagem_{marker}",
                "tipo": "VaccineLedger",
                "lineage_marker": marker,
                "migrated_from_obsidian": True,
                "vacinas": patterns,
            },
        )
        logger.info(
            "[VAULT-UNIFIER] Migrated %d vaccines for %s", len(patterns), marker
        )
        return True

    def vacuum_orphans(self, known_markers: List[str]) -> int:
        """
        Remove arquivos JSON de linhagens inexistentes.
        Retorna número de arquivos removidos.
        """
        removed = 0
        for path in self.json_dir.glob("linhagem_*.json"):
            marker = path.stem.replace("linhagem_", "")
            if marker not in known_markers:
                try:
                    path.unlink()
                    removed += 1
                except Exception as e:
                    logger.debug("[VAULT-UNIFIER] vacuum falhou %s: %s", path, e)
        return removed


# Singleton — substitui SubconsciousAPI como backend de vacinas
vault_unifier = VaultUnifier()
