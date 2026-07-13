# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""⚖️ GenesisTribunal — Valida DNA de agentes + genesis file no boot.

Duas camadas de verificacao:
  1. Genesis File (CBOR): verifica se o arquivo evolutivo corresponde ao hash oficial
  2. Agentes Python: verifica LINEAGE_MARKER em todos os .py de agents/ e nodes/

Se qualquer camada falhar, o sistema se recusa a nascer.
Agentes validados ganham nome fonetico derivado do DNA congelado.
"""

import hashlib
from pathlib import Path
from dataclasses import dataclass

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.security.pysecurity1024 import Pysecurity1024
from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

logger = get_logger("iaglobal.genesis.tribunal")

AGENTS_DIR = PACKAGE_DIR / "agents"
NODES_DIR = PACKAGE_DIR / "graphs" / "nodes"
SKIP_DIRS = {"__pycache__", ".mypy_cache", ".git", "venv", "node_modules"}


@dataclass
class Veredito:
    arquivo: str
    dna_valido: bool
    phonetic_name: str = ""
    razao: str = ""


class GenesisTribunal:
    """⚖️ Tribunal de Genesis — duas camadas de verificacao.

    1a camada (genesis file):  verify_genesis_integrity() do identity.py
    2a camada (agentes):       LINEAGE_MARKER em agents/ e nodes/

    Ambas precisam passar para o sistema nascer.
    """

    def __init__(self, block_on_failure: bool = True):
        self.block_on_failure = block_on_failure

    # ── helpers ────────────────────────────────────────────────────────

    def _first_line(self, file: Path) -> str:
        try:
            with file.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        return stripped
        except Exception:
            pass
        return ""

    def _phonetic_from_file(self, file: Path) -> str:
        rel = file.relative_to(PACKAGE_DIR)
        seed = f"{GENESIS_HASH_OFFICIAL}:{rel}"
        raw = hashlib.sha3_512(seed.encode()).digest()[:16]
        return Pysecurity1024.bytes_para_frase(raw)

    def _coletar_arquivos(self) -> list[Path]:
        arquivos: list[Path] = []
        for diretorio in [AGENTS_DIR, NODES_DIR]:
            if not diretorio.exists():
                continue
            for pyfile in sorted(diretorio.rglob("*.py")):
                rel = pyfile.relative_to(PACKAGE_DIR)
                if any(p.name in SKIP_DIRS for p in rel.parents):
                    continue
                if pyfile.name == "__init__.py":
                    continue
                arquivos.append(pyfile)
        return arquivos

    # ── 1a camada: genesis file ────────────────────────────────────────

    async def _verificar_genesis_file(self) -> Veredito:
        """Verifica se o arquivo genesis no disco corresponde ao DNA oficial."""
        try:
            from iaglobal.genesis.identity import verify_genesis_integrity as _verify

            resultado = await _verify()
            if resultado.get("match"):
                return Veredito(
                    arquivo="genesis/webhidden_genesis_evolutive.cbor",
                    dna_valido=True,
                    phonetic_name="DNA-ANCESTRAL",
                    razao="OK",
                )
            return Veredito(
                arquivo="genesis/webhidden_genesis_evolutive.cbor",
                dna_valido=False,
                razao=resultado.get("status", "Genesis file nao confere"),
            )
        except Exception as e:
            return Veredito(
                arquivo="genesis/webhidden_genesis_evolutive.cbor",
                dna_valido=False,
                razao=f"Erro na verificacao: {e}",
            )

    # ── 2a camada: agentes ─────────────────────────────────────────────

    def _verificar_agente(self, pyfile: Path) -> Veredito:
        rel = pyfile.relative_to(PACKAGE_DIR)
        first = self._first_line(pyfile)
        if GENESIS_HASH_OFFICIAL not in first:
            razao = "LINEAGE_MARKER ausente ou hash divergente"
            if first and "LINEAGE_MARKER" in first:
                razao = "Hash diverge do DNA oficial"
            return Veredito(arquivo=str(rel), dna_valido=False, razao=razao)
        return Veredito(
            arquivo=str(rel),
            dna_valido=True,
            phonetic_name=self._phonetic_from_file(pyfile),
            razao="OK",
        )

    # ── execucao ───────────────────────────────────────────────────────

    async def julgar(self) -> list[Veredito]:
        """Executa ambas as camadas do tribunal."""
        resultados: list[Veredito] = []

        # 1a camada: genesis file
        v = await self._verificar_genesis_file()
        resultados.append(v)

        # 2a camada: agentes
        for pyfile in self._coletar_arquivos():
            v = self._verificar_agente(pyfile)
            resultados.append(v)

        return resultados

    async def executar(self) -> list[Veredito]:
        """Executa o tribunal e bloqueia se houver qualquer violacao."""
        resultados = await self.julgar()
        invalidos = [v for v in resultados if not v.dna_valido]
        total = len(resultados)
        validos = total - len(invalidos)

        linha = "=" * 60
        print(f"\n{linha}")
        print(f"  ⚖️  TRIBUNAL DE GENESIS")
        print(f"  DNA Ancestral: {GENESIS_HASH_OFFICIAL[:24]}...")
        print(f"{linha}")

        # Mostra genesis file primeiro
        for v in resultados[:1]:
            s = "✅" if v.dna_valido else "❌"
            print(f"  {s} {v.arquivo:<50} {v.phonetic_name or v.razao}")

        print(f"{'─' * 60}")
        print(f"  Agentes ({total - 1} arquivos):")

        # Mostra agentes
        inv_mostrados = 0
        for v in resultados[1:]:
            s = "✅" if v.dna_valido else "❌"
            print(
                f"  {s} {v.arquivo:<50} {v.phonetic_name if v.dna_valido else v.razao}"
            )
            if not v.dna_valido:
                inv_mostrados += 1

        print(f"{linha}")
        print(
            f"  Genesis File: {'✅ CONFORME' if resultados[0].dna_valido else '❌ VIOLADO'}"
        )
        print(
            f"  Agentes: {total - 1} total | {validos - (1 if resultados[0].dna_valido else 0)} validos | {inv_mostrados} invalidados"
        )
        print(f"{linha}")

        if invalidos:
            print(f"\n  🛑 SISTEMA BLOQUEADO: {len(invalidos)} violacao(oes) de DNA.")
            if self.block_on_failure:
                raise SystemExit(
                    f"[TRIBUNAL] {len(invalidos)} violacao(oes) de DNA detectadas. "
                    f"Boot abortado para proteger a integridade do ecossistema."
                )

        return resultados
