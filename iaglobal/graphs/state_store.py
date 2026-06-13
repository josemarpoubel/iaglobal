import time
import json
from collections import OrderedDict
from typing import Any, Dict, Optional, List, Tuple

from iaglobal.utils.logger import logger


PENDING = "PENDING"
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"


class SystemStateBuffer:
    """Buffer de estado volátil com LRU eviction e compressão semântica.

    Gerencia estado de execução dos nós com:

    - LRU eviction: remove entradas menos acessadas quando atinge max_size
    - Compressão semântica: sumariza entradas antigas para reduzir tokens
    - Snapshot trigger: sinaliza quando deve persistir (a cada N operações ou T segundos)
    """

    def __init__(self, max_size: int = 500, snapshot_interval_ops: int = 50,
                 snapshot_interval_sec: int = 30):
        self._data: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._snapshot_interval_ops = snapshot_interval_ops
        self._snapshot_interval_sec = snapshot_interval_sec
        self._ops_since_snapshot = 0
        self._last_snapshot_time = time.time()
        self._compressed: Dict[str, str] = {}

    # -----------------------------------------------------------------
    # Core API
    # -----------------------------------------------------------------

    def set(self, node: str, status: str, output: Optional[Any] = None,
            error: Optional[str] = None, attempt: int = 0) -> None:
        entry = {
            "status": status,
            "output": output,
            "error": error,
            "attempt": attempt,
            "updated_at": time.time(),
        }
        if node in self._data:
            self._data.move_to_end(node)
        self._data[node] = entry
        self._ops_since_snapshot += 1
        self._evict_if_needed()

    def get(self, node: str) -> Dict[str, Any]:
        entry = self._data.get(node)
        if entry is None:
            return {"status": PENDING, "output": None, "error": None, "attempt": 0}
        self._data.move_to_end(node)
        return entry

    def is_ready(self, node: str, depends_on: list) -> bool:
        entry = self.get(node)
        if entry["status"] in (SUCCESS, FAILED):
            return False
        for dep in depends_on:
            dep_status = self.get(dep)["status"]
            if dep_status != SUCCESS:
                return False
        return True

    def all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._data)

    def keys(self) -> List[str]:
        return list(self._data.keys())

    def size(self) -> int:
        return len(self._data)

    def clear(self):
        self._data.clear()
        self._compressed.clear()
        self._ops_since_snapshot = 0
        self._last_snapshot_time = time.time()

    # -----------------------------------------------------------------
    # LRU Eviction
    # -----------------------------------------------------------------

    def _evict_if_needed(self):
        while len(self._data) > self._max_size:
            evicted_node, evicted_entry = self._data.popitem(last=False)
            logger.debug(f"[STATE_BUFFER] LRU evict: {evicted_node} "
                         f"(size={len(self._data)})")

    # -----------------------------------------------------------------
    # Compressão Semântica
    # -----------------------------------------------------------------

    def compress_old_entries(self, keep_last: int = 100):
        """Sumariza entradas antigas (não acessadas recentemente).

        Mantém as `keep_last` entradas mais recentes intactas e
        substitui as anteriores por um resumo compacto.
        """
        if len(self._data) <= keep_last:
            return

        items = list(self._data.items())
        old_items = items[:-keep_last]
        recent_items = items[-keep_last:]

        summaries = []
        for node, entry in old_items:
            if entry["status"] == SUCCESS and entry.get("output"):
                summary = self._summarize_entry(node, entry)
                summaries.append(summary)

        if summaries:
            self._compressed["_old_summary"] = "\n".join(summaries)
            logger.info(f"[STATE_BUFFER] Comprimidas {len(old_items)} entradas antigas "
                        f"em {len(summaries)} linhas de resumo")

        self._data = OrderedDict(recent_items)

    def get_compressed_context(self) -> str:
        """Retorna contexto comprimido para incluir no prompt."""
        if self._compressed:
            parts = ["[CONTEXTO COMPRIMIDO]", self._compressed.get("_old_summary", "")]
            return "\n".join(parts)
        return ""

    def _summarize_entry(self, node: str, entry: Dict[str, Any]) -> str:
        """Sumariza uma entrada em uma linha compacta."""
        output = entry.get("output", "")
        if isinstance(output, str) and len(output) > 80:
            output = output[:80] + "..."
        status = entry["status"]
        return f"[{node}] {status}: {output}"

    # -----------------------------------------------------------------
    # Snapshot Triggers
    # -----------------------------------------------------------------

    def should_snapshot(self) -> bool:
        """Retorna True se deve criar um snapshot.

        Critérios (qualquer um dispara):
        - Número de operações desde último snapshot >= intervalo
        - Tempo desde último snapshot >= intervalo
        """
        ops_ok = self._ops_since_snapshot >= self._snapshot_interval_ops
        time_ok = (time.time() - self._last_snapshot_time) >= self._snapshot_interval_sec
        return ops_ok or time_ok

    def mark_snapshot_done(self):
        """Marca que um snapshot foi criado."""
        self._ops_since_snapshot = 0
        self._last_snapshot_time = time.time()

    def get_snapshot_data(self) -> Dict[str, Any]:
        """Retorna dados serializáveis para snapshot."""
        return {
            "nodes": dict(self._data),
            "compressed": dict(self._compressed),
            "ops_since_snapshot": self._ops_since_snapshot,
            "last_snapshot_time": self._last_snapshot_time,
        }

    def load_snapshot(self, data: Dict[str, Any]):
        """Restaura estado a partir de dados de snapshot."""
        self._data = OrderedDict(data.get("nodes", {}))
        self._compressed = dict(data.get("compressed", {}))
        self._ops_since_snapshot = data.get("ops_since_snapshot", 0)
        self._last_snapshot_time = data.get("last_snapshot_time", time.time())
        logger.info(f"[STATE_BUFFER] Snapshot restaurado: {len(self._data)} nós")


# Alias para compatibilidade com código existente
StateStore = SystemStateBuffer

