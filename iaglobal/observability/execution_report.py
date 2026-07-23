# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ExecutionReport — coletor de métricas via eventos.

Consome eventos do ExecutionEventBus e agrega com provider_metrics.buffer
para gerar relatório estruturado por execução.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from iaglobal.observability.execution_events import (
    ExecutionEvent,
    NODE_STARTED,
    NODE_FINISHED,
    get_event_bus,
)

# Optional import for semaphore health
try:
    from iaglobal.observability.semaphore_tracker import get_semaphore_tracker
except Exception:  # pragma: no cover - optional
    get_semaphore_tracker = None  # type: ignore

# Global holder for current execution report
_execution_report: Optional["ExecutionReport"] = None


@dataclass
class _NodeRecord:
    node: str
    start_time: float = 0.0
    status: str = "pending"  # pending, success, failed
    latency: float = 0.0
    exception: Optional[str] = None


class ExecutionReport:
    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self.nodes: Dict[str, _NodeRecord] = {}
        self._bus = get_event_bus()
        self._bus.subscribe(NODE_STARTED, self._on_node_started)
        self._bus.subscribe(NODE_FINISHED, self._on_node_finished)

    def _on_node_started(self, event: ExecutionEvent) -> None:
        if event.execution_id != self.execution_id:
            return
        rec = self.nodes.get(event.node_id)
        if rec is None:
            rec = _NodeRecord(node=event.node_id)
            self.nodes[event.node_id] = rec
        rec.start_time = event.timestamp

    def _on_node_finished(self, event: ExecutionEvent) -> None:
        if event.execution_id != self.execution_id:
            return
        rec = self.nodes.get(event.node_id)
        if rec is None:
            rec = _NodeRecord(node=event.node_id)
            self.nodes[event.node_id] = rec
        rec.status = "success" if event.payload.get("success") else "failed"
        rec.latency = float(event.payload.get("latency", 0.0))
        rec.exception = event.payload.get("error")

    def finish(self) -> Dict[str, Any]:
        # Build summary
        total = len(self.nodes)
        executed = sum(
            1 for n in self.nodes.values() if n.status in ("success", "failed")
        )
        failures = sum(1 for n in self.nodes.values() if n.status == "failed")
        nodes_out = []
        for rec in self.nodes.values():
            nodes_out.append(
                {
                    "node": rec.node,
                    "status": rec.status,
                    "latency": rec.latency,
                    "exception": rec.exception,
                }
            )

        # Timeline text with node info
        lines = ["Execution Timeline:"]
        for rec in self.nodes.values():
            lines.append(
                f"  {rec.node}: {rec.status} ({rec.latency:.2f}s)"
                + (f" - {rec.exception}" if rec.exception else "")
            )

        # Semaphore health if tracker available
        if get_semaphore_tracker is not None:
            tracker = get_semaphore_tracker()
            health = tracker.health_report()
            if health:
                lines.append("\nSemaphore Health:")
                for model, metrics in health.items():
                    lines.append(
                        f"  {model}: timeouts={metrics['timeouts']} "
                        f"avg_wait={metrics['avg_wait_ms']}ms "
                        f"timeout_rate={metrics['timeout_rate']}"
                    )

        timeline_text = "\n".join(lines)

        # Simple mermaid DAG representation
        mermaid_lines = ["graph TD"]
        for rec in self.nodes.values():
            mermaid_lines.append(f'    {rec.node}["{rec.node}"]')
        # add dummy edges to show order based on start_time
        sorted_nodes = sorted(self.nodes.values(), key=lambda r: r.start_time)
        for i in range(len(sorted_nodes) - 1):
            mermaid_lines.append(
                f"    {sorted_nodes[i].node} --> {sorted_nodes[i + 1].node}"
            )
        mermaid_dag = "\n".join(mermaid_lines)

        return {
            "summary": {
                "total_nodes": total,
                "executed": executed,
                "failures": failures,
            },
            "nodes": nodes_out,
            "timeline_text": timeline_text,
            "mermaid_dag": mermaid_dag,
        }


def init_execution_report(execution_id: str) -> ExecutionReport:
    global _execution_report
    _execution_report = ExecutionReport(execution_id)
    return _execution_report


def get_execution_report() -> Optional[ExecutionReport]:
    return _execution_report
