# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""MetabolicDataAdapter — Ponte entre armazenamento interno (CBOR2/SQLite/JSON) e LLMs.

Lê dados metabólicos reais do disco e monta um contexto JSON limpo que o LLM
pode consumir. Substitui templates genéricos do Obsidian por dados vivos.

Fontes (controladas por METABOLIC_STORAGE_TYPE no .env):
  - auto (padrão): todas as fontes abaixo
  - cbor2: apenas epigenetic markers CBOR2
  - json: apenas pools + methylation + knowledge + omnimind
  - sqlite: apenas STM/LTM via SQLite BLOBs

Fontes individuais:
  - Epigenetic markers (CBOR2, ~100+ arquivos em obsidian/epigenetic/)
  - Metabolic pools (JSON: same, homocysteine, glutathione)
  - Methylation engine (JSON)
  - OmniMind collective memory (JSON)
  - Knowledge (JSON)
  - Short-term / Long-term memory (SQLite BLOBs via cbor2.loads)
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.storage.metabolic_adapter")


class MetabolicDataAdapter:
    """Agrega dados metabólicos de múltiplas fontes em contexto JSON para LLM."""

    def __init__(self):
        self._epigenetic_dir: Optional[Path] = None
        self._omnimind_path: Optional[Path] = None

    # ── Fontes Individuais ─────────────────────────────────────────────────

    async def _read_json_file(self, path: Path) -> Any:
        """Lê arquivo JSON de forma assíncrona (thread pool)."""
        if not path or not path.exists():
            return None
        try:
            return await asyncio.to_thread(
                lambda: json.loads(path.read_text(encoding="utf-8"))
            )
        except Exception as e:
            logger.debug("[METABOLIC] Falha ao ler %s: %s", path.name, e)
            return None

    async def _read_cbor_dir(self, directory: Path, limit: int = 50) -> List[Dict]:
        """Lê até `limit` arquivos .cbor de um diretório."""
        if not directory or not directory.exists():
            return []
        try:
            import cbor2

            files = sorted(
                directory.glob("*.cbor"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:limit]

            def _read_all():
                result = []
                for f in files:
                    try:
                        with open(f, "rb") as fh:
                            data = cbor2.load(fh)
                        if isinstance(data, dict):
                            data["_file"] = f.name
                            result.append(data)
                    except Exception:
                        continue
                return result

            return await asyncio.to_thread(_read_all)
        except Exception as e:
            logger.debug("[METABOLIC] Falha ao ler CBOR de %s: %s", directory, e)
            return []

    async def _read_sqlite_blobs(self) -> List[Dict]:
        """Lê registros recentes do SQLite via cbor2 BLOBs (STM + LTM)."""
        results = []
        try:
            from iaglobal._paths import CORE_DB
            import sqlite3
            import cbor2

            def _read_stm():
                out = []
                if not CORE_DB.exists():
                    return out
                try:
                    conn = sqlite3.connect(str(CORE_DB), timeout=2)
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT data FROM stm_entries ORDER BY rowid DESC LIMIT 10"
                    ).fetchall()
                    for r in rows:
                        try:
                            out.append(cbor2.loads(r["data"]))
                        except Exception:
                            continue
                    conn.close()
                except Exception:
                    pass
                return out

            results.extend(await asyncio.to_thread(_read_stm))
        except Exception as e:
            logger.debug("[METABOLIC] Falha ao ler SQLite BLOBs: %s", e)
        return results

    # ── Montagem do Contexto ───────────────────────────────────────────────

    async def build_context(self, task: str, max_epigenetic: int = 30) -> str:
        """Monta contexto metabólico completo como string JSON.

        Args:
            task: Prompt/tarefa do agente (usado para filtrar relevância)
            max_epigenetic: Máximo de marcadores epigenéticos a incluir

        Returns:
            String JSON com dados metabólicos, ou string vazia se nada encontrado
        """
        from iaglobal._paths import (
            DATA_DIR,
            SAME_POOL_FILE,
            HOMOCYSTEINE_POOL_FILE,
            GLUTATHIONE_POOL_FILE,
            METHYLATION_ENGINE_FILE,
            KNOWLEDGE_FILE,
            METABOLIC_STORAGE_TYPE,
        )

        storage_type = METABOLIC_STORAGE_TYPE
        epigenetic_dir = Path(__file__).parent.parent / "obsidian" / "epigenetic"
        omnimind_path = DATA_DIR / "omnimind_state.json"

        # Lê fontes conforme storage_type
        fetch_cbor = storage_type in ("auto", "cbor2")
        fetch_json = storage_type in ("auto", "json")
        fetch_sql = storage_type in ("auto", "sqlite")

        epigenetic = same_pool = homocysteine_pool = None
        glutathione_pool = methylation = knowledge = None
        omnimind = sqlite_records = None

        gather_tasks = []
        if fetch_cbor:
            gather_tasks.append(self._read_cbor_dir(epigenetic_dir, max_epigenetic))
        if fetch_json:
            gather_tasks.extend(
                [
                    self._read_json_file(SAME_POOL_FILE),
                    self._read_json_file(HOMOCYSTEINE_POOL_FILE),
                    self._read_json_file(GLUTATHIONE_POOL_FILE),
                    self._read_json_file(METHYLATION_ENGINE_FILE),
                    self._read_json_file(KNOWLEDGE_FILE),
                    self._read_json_file(omnimind_path),
                ]
            )
        if fetch_sql:
            gather_tasks.append(self._read_sqlite_blobs())

        if gather_tasks:
            results = await asyncio.gather(*gather_tasks, return_exceptions=True)
            it = iter(results)
            if fetch_cbor:
                epigenetic = next(it)
            if fetch_json:
                same_pool = next(it)
                homocysteine_pool = next(it)
                glutathione_pool = next(it)
                methylation = next(it)
                knowledge = next(it)
                omnimind = next(it)
            if fetch_sql:
                sqlite_records = next(it)

        # Substitui exceções por None nas variáveis
        for v in [
            epigenetic,
            same_pool,
            homocysteine_pool,
            glutathione_pool,
            methylation,
            knowledge,
            omnimind,
            sqlite_records,
        ]:
            if isinstance(v, Exception):
                pass  # Serão ignoradas na montagem do JSON

        # Monta estrutura
        context = {
            "_adapter": "metabolic_data_adapter/v1",
            "_generated_for": task[:200],
            "epigenetic_recent": epigenetic or [],
            "metabolic_pools": {
                "same": same_pool if isinstance(same_pool, (list, dict)) else [],
                "homocysteine": homocysteine_pool
                if isinstance(homocysteine_pool, (list, dict))
                else [],
                "glutathione": glutathione_pool
                if isinstance(glutathione_pool, (list, dict))
                else [],
            },
            "methylation_engine": methylation if isinstance(methylation, dict) else {},
            "omnimind_collective": omnimind if isinstance(omnimind, list) else [],
            "knowledge": knowledge if isinstance(knowledge, (list, dict)) else [],
            "memory_recent": sqlite_records or [],
        }

        # Remove fontes vazias para não poluir o prompt
        compact = {k: v for k, v in context.items() if v}
        if compact.get("metabolic_pools"):
            compact["metabolic_pools"] = {
                k: v for k, v in compact["metabolic_pools"].items() if v
            }
            if not compact["metabolic_pools"]:
                del compact["metabolic_pools"]

        if not compact or compact == {
            "_adapter": "metabolic_data_adapter/v1",
            "_generated_for": task[:200],
        }:
            return ""

        return json.dumps(compact, indent=2, ensure_ascii=False, default=str)

    # ── Interface Pública ─────────────────────────────────────────────────

    async def get_epigenetic_summary(self, agent_id: Optional[str] = None) -> str:
        """Retorna apenas marcadores epigenéticos como JSON (para debugging)."""
        epigenetic_dir = Path(__file__).parent.parent / "obsidian" / "epigenetic"
        markers = await self._read_cbor_dir(epigenetic_dir, 100)
        if agent_id:
            markers = [m for m in markers if m.get("agent_id") == agent_id]
        return json.dumps(markers, indent=2, ensure_ascii=False, default=str)

    async def get_pool_summary(self) -> str:
        """Retorna apenas pools metabólicos como JSON."""
        from iaglobal._paths import (
            SAME_POOL_FILE,
            HOMOCYSTEINE_POOL_FILE,
            GLUTATHIONE_POOL_FILE,
        )

        same, homo, gluta = await asyncio.gather(
            self._read_json_file(SAME_POOL_FILE),
            self._read_json_file(HOMOCYSTEINE_POOL_FILE),
            self._read_json_file(GLUTATHIONE_POOL_FILE),
            return_exceptions=True,
        )
        pools = {
            "same": same
            if not isinstance(same, Exception) and isinstance(same, (list, dict))
            else [],
            "homocysteine": homo
            if not isinstance(homo, Exception) and isinstance(homo, (list, dict))
            else [],
            "glutathione": gluta
            if not isinstance(gluta, Exception) and isinstance(gluta, (list, dict))
            else [],
        }
        return json.dumps(pools, indent=2, ensure_ascii=False, default=str)


# Singleton
metabolic_adapter = MetabolicDataAdapter()
