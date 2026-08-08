# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/graphs/state_store.py — Buffer de estado do pipeline em memória.

Guarda o estado de execução por fingerprint de tarefa (running/success/failed),
comprime entradas antigas e dispara snapshots periódicos via Snapshotter.
"""

import threading
from typing import Any, Dict, Optional

from iaglobal.graphs.task import SUCCESS, FAILED

__all__ = ["SystemStateBuffer", "SUCCESS", "FAILED"]


class SystemStateBuffer:
    """Buffer de estado em memória com compressão e trigger de snapshot.

    Contrato consumido por CognitiveProxy e Snapshotter:
      - ``set``/``size``/``compress_old_entries``
      - ``should_snapshot``/``get_snapshot_data``/``mark_snapshot_done``
      - ``get_compressed_context``/``load_snapshot``
    """

    def __init__(self, max_size: int = 500, snapshot_interval_ops: int = 50):
        self.max_size = max_size
        self.snapshot_interval_ops = snapshot_interval_ops
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._compressed: Dict[str, Dict[str, Any]] = {}
        self._ops_since_snapshot = 0
        self._lock = threading.Lock()

    def set(
        self,
        key: str,
        status: str,
        output: Any = None,
        attempt: int = 0,
    ) -> None:
        """Registra/atualiza o estado de uma tarefa."""
        with self._lock:
            self._nodes[key] = {
                "key": key,
                "status": status,
                "output": output,
                "attempt": attempt,
            }
            self._ops_since_snapshot += 1

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retorna o estado atual de uma tarefa."""
        with self._lock:
            return self._nodes.get(key)

    def size(self) -> int:
        """Número de entradas ativas no buffer."""
        with self._lock:
            return len(self._nodes)

    def compress_old_entries(self, keep_last: int = 100) -> None:
        """Move as entradas mais antigas para o índice comprimido."""
        with self._lock:
            if len(self._nodes) <= keep_last:
                return
            excess = sorted(
                self._nodes.keys(),
                key=lambda k: self._nodes[k].get("ts", 0.0),
            )[: len(self._nodes) - keep_last]
            for key in excess:
                self._compressed[key] = self._nodes.pop(key)

    def should_snapshot(self) -> bool:
        """True quando o número de operações desde o último snapshot excede o limite."""
        with self._lock:
            return self._ops_since_snapshot >= self.snapshot_interval_ops

    def get_snapshot_data(self) -> Dict[str, Any]:
        """Retorna os dados serializáveis para o Snapshotter."""
        with self._lock:
            return {"nodes": dict(self._nodes), "compressed": dict(self._compressed)}

    def mark_snapshot_done(self) -> None:
        """Zera o contador de operações pós-snapshot."""
        with self._lock:
            self._ops_since_snapshot = 0

    def get_compressed_context(self) -> str:
        """Constrói um resumo textual das entradas para injeção no prompt."""
        with self._lock:
            if not self._nodes:
                return ""
            lines = ["[ESTADO DE EXECUÇÃO DO SISTEMA]"]
            for key, node in list(self._nodes.items())[-20:]:
                lines.append(
                    f"- {key}: {node.get('status', 'unknown')}"
                    f" (attempt={node.get('attempt', 0)})"
                )
            if self._compressed:
                lines.append(f"- ... +{len(self._compressed)} entradas comprimidas")
            return "\n".join(lines)

    def load_snapshot(self, state_data: Dict[str, Any]) -> None:
        """Restaura o buffer a partir dos dados de snapshot."""
        if not isinstance(state_data, dict):
            return
        with self._lock:
            self._nodes = dict(state_data.get("nodes", {}) or {})
            self._compressed = dict(state_data.get("compressed", {}) or {})
            self._ops_since_snapshot = 0
