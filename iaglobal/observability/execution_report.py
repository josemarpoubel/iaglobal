# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ExecutionReport — coletor de métricas via eventos.

Consome eventos do ExecutionEventBus e agrega com provider_metrics.buffer
para gerar relatório estruturado por execução.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.core.agent_roles import AgentRole
from iaglobal.core.role_resolver import RoleResolver
from iaglobal.providers.provider_metrics import metrics as provider_metrics
from iaglobal.observability.execution_events import (
    ExecutionEvent,
    NODE_STARTED,
    NODE_FINISHED,
    PROVIDER_SELECTED,
    FALLBACK,
    RETRY,
    get_event_bus,
)


@dataclass
class NodeRecord:
    node: str
    role: str
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: float = 0.0
    fallback_count: int = 0
    retry_count: int = 0
    status: str = "pending"
    exception: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    provider_attempts: List[Dict[str, Any]] = field(default_factory=list)


class ExecutionReport:
    def __init__(self, execution_id: str, output_path: Optional[Path] = None) -> None:
        self.execution_id = execution_id
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.nodes: Dict[str, NodeRecord] = {}
        self._output_path = output_path or Path("/tmp/iaglobal_execution_report.json")

        # Subscribe to events
        bus = get_event_bus()
        bus.subscribe(NODE_STARTED, self._on_node_started)
        bus.subscribe(NODE_FINISHED, self._on_node_finished)
        bus.subscribe(PROVIDER_SELECTED, self._on_provider_selected)
        bus.subscribe(FALLBACK, self._on_fallback)
        bus.subscribe(RETRY, self._on_retry)

    def _on_node_started(self, event: ExecutionEvent) -> None:
        role = RoleResolver.resolve(event.node_id)
        self.nodes[event.node_id] = NodeRecord(
            node=event.node_id,
            role=role.value,
            start_time=event.timestamp,
            status="running",
        )

    def _on_node_finished(self, event: ExecutionEvent) -> None:
        rec = self.nodes.get(event.node_id)
        if not rec:
            return
        rec.end_time = event.timestamp
        rec.latency_ms = (rec.end_time - rec.start_time) * 1000
        rec.status = "success" if event.payload.get("success", False) else "failed"
        rec.exception = event.payload.get("error")

    def _on_provider_selected(self, event: ExecutionEvent) -> None:
        rec = self.nodes.get(event.node_id)
        if rec:
            rec.provider = event.payload.get("provider")
            rec.model = event.payload.get("model")
            if "attempt" in event.payload:
                rec.provider_attempts.append(event.payload["attempt"])

    def _on_fallback(self, event: ExecutionEvent) -> None:
        rec = self.nodes.get(event.node_id)
        if rec:
            rec.fallback_count += 1
            if "attempt" in event.payload:
                rec.provider_attempts.append(event.payload["attempt"])

    def _on_retry(self, event: ExecutionEvent) -> None:
        rec = self.nodes.get(event.node_id)
        if rec:
            rec.retry_count += 1

    def finish(self) -> Dict[str, Any]:
        self.finished_at = time.time()
        total_duration = (self.finished_at - self.started_at) * 1000

        by_role: Dict[str, int] = {}
        by_provider: Dict[str, int] = {}
        llm_calls = 0
        local_only = 0
        fallbacks = 0
        retries = 0
        failures = 0

        for rec in self.nodes.values():
            by_role[rec.role] = by_role.get(rec.role, 0) + 1
            if rec.provider:
                by_provider[rec.provider] = by_provider.get(rec.provider, 0) + 1
            if rec.provider and rec.provider != "ollama":
                llm_calls += 1
            else:
                local_only += 1
            fallbacks += rec.fallback_count
            retries += rec.retry_count
            if rec.status == "failed":
                failures += 1

        report = {
            "execution_id": self.execution_id,
            "started_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(self.started_at)
            ),
            "finished_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(self.finished_at)
            ),
            "total_duration_ms": round(total_duration, 1),
            "summary": {
                "total_nodes": len(self.nodes),
                "executed": sum(
                    1 for r in self.nodes.values() if r.status != "pending"
                ),
                "llm_calls": llm_calls,
                "local_only": local_only,
                "fallbacks": fallbacks,
                "retries": retries,
                "failures": failures,
                "by_role": by_role,
                "by_provider": by_provider,
            },
            "provider_metrics_raw": provider_metrics.buffer,
            "nodes": [
                {
                    "node": rec.node,
                    "role": rec.role,
                    "provider": rec.provider,
                    "model": rec.model,
                    "latency_ms": round(rec.latency_ms, 1),
                    "fallback_count": rec.fallback_count,
                    "retry_count": rec.retry_count,
                    "status": rec.status,
                    "exception": rec.exception,
                    "provider_attempts": rec.provider_attempts,
                    "start_time": time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.gmtime(rec.start_time)
                    ),
                    "end_time": time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.gmtime(rec.end_time)
                    )
                    if rec.end_time
                    else None,
                }
                for rec in self.nodes.values()
            ],
        }

        try:
            self._output_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False)
            )
        except Exception:
            pass

        return report


_execution_report: Optional[ExecutionReport] = None


def init_execution_report(
    execution_id: str, output_path: Optional[Path] = None
) -> ExecutionReport:
    global _execution_report
    _execution_report = ExecutionReport(execution_id, output_path)
    return _execution_report


def get_execution_report() -> Optional[ExecutionReport]:
    return _execution_report
