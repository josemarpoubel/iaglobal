# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ExecutionTimeline — timeline cronológica da execução + DAG Mermaid colorido.

Consome:
  - execution_report (dict de ExecutionReport.finish())
  - semaphore_tracker (SemaphoreTracker.health_report())
  - skip_reasons (dict do ExecutionGraph)
  - topology.PHASES para classificação

Produz:
  - timeline.md: cronologia com timestamps relativos
  - graph.mmd: Mermaid DAG colorido por estado
  - metrics.json: métricas consolidadas
"""

from __future__ import annotations

import json
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.graphs.topology import PHASES, NODE_DEPENDENCIES, get_node_phase
from iaglobal.graphs.skip_reason import REASON_LABELS

NODE_COLORS = {
    "success": "#22c55e",
    "failed": "#ef4444",
    "running": "#3b82f6",
    "pending": "#94a3b8",
    "aborted": "#f97316",
    "dependency_not_met": "#94a3b8",
    "already_executed": "#a1a1aa",
    "aborted_by_sanity_barrier": "#f97316",
    "aborted_by_recovery": "#f97316",
    "timeout": "#eab308",
    "no_input_candidates": "#a1a1aa",
    "default": "#64748b",
}


def _node_color(status: str, skip_reason: Optional[str] = None) -> str:
    if skip_reason and skip_reason in NODE_COLORS:
        return NODE_COLORS[skip_reason]
    return NODE_COLORS.get(status, NODE_COLORS["default"])


def _status_label(status: str, skip_reason: Optional[str] = None) -> str:
    if skip_reason and skip_reason in REASON_LABELS:
        return REASON_LABELS[skip_reason]
    return status


def build_execution_timeline(
    execution_report: Optional[Dict[str, Any]] = None,
    semaphore_health: Optional[Dict[str, Dict[str, float]]] = None,
    skip_reasons: Optional[Dict[str, str]] = None,
    total_nodes: int = 0,
    pipeline_duration_ms: float = 0.0,
) -> Dict[str, Any]:
    """
    Gera os três artefatos de observabilidade:
      - timeline_text: cronologia textual
      - mermaid_dag: diagrama DAG colorido
      - consolidated_metrics: métricas consolidadas

    Returns:
        dict com chaves: timeline_text, mermaid_dag, consolidated_metrics
    """
    nodes_data: List[Dict[str, Any]] = []

    if execution_report:
        nodes_data = list(execution_report.get("nodes", []))

    # ── 1. Timeline cronológica ──
    reported_count = len(nodes_data)
    timeline_lines: List[str] = [
        "# Execution Timeline",
        "",
        f"Pipeline: {total_nodes} nós | "
        f"Duração: {pipeline_duration_ms:.0f}ms | "
        f"Reportados: {reported_count} | "
        f"Ignorados: {len(skip_reasons or {})}",
        "",
    ]

    # Ordenar eventos por start_time
    sorted_nodes = sorted(
        nodes_data,
        key=lambda n: n.get("start_time", ""),
    )

    # Calcular offset relativo ao primeiro start
    first_start: Optional[float] = None
    parsed_starts: Dict[str, float] = {}

    for nd in sorted_nodes:
        st = nd.get("start_time", "")
        if st and isinstance(st, str):
            try:
                parsed = _time.strptime(st, "%Y-%m-%dT%H:%M:%S")
                parsed_starts[nd["node"]] = _time.mktime(parsed)
                if first_start is None or parsed_starts[nd["node"]] < first_start:
                    first_start = parsed_starts[nd["node"]]
            except Exception:
                pass

    # Nós reportados (executados ou falhos)
    for nd in sorted_nodes:
        node_name = nd.get("node", "?")
        status = nd.get("status", "pending")
        latency_ms = nd.get("latency_ms", 0.0)
        exception = nd.get("exception")
        provider = nd.get("provider", "")
        model = nd.get("model", "")

        skip_reason = skip_reasons.get(node_name) if skip_reasons else None
        label = _status_label(status, skip_reason)

        rel_ms = 0.0
        if node_name in parsed_starts and first_start is not None:
            rel_ms = (parsed_starts[node_name] - first_start) * 1000

        provider_str = f" [{provider}/{model}]" if (provider or model) else ""
        err_str = f" ! {exception}" if exception else ""
        timeline_lines.append(
            f"t={rel_ms:8.0f}ms {node_name:30s} {label:25s} "
            f"({latency_ms:.0f}ms){provider_str}{err_str}"
        )

    # Nós ignorados (skip_reasons) que não estão no report
    if skip_reasons:
        reported_nodes = {nd.get("node", "") for nd in nodes_data}
        unreported_skips = {
            n: r for n, r in skip_reasons.items() if n not in reported_nodes
        }
        if unreported_skips:
            timeline_lines.append("")
            timeline_lines.append("### Skipped Nodes (not reported)")
            for node_name in sorted(unreported_skips):
                reason = unreported_skips[node_name]
                label = REASON_LABELS.get(reason, reason)
                timeline_lines.append(f"  {node_name:30s} {label}")

    # Adicionar eventos de semáforo
    if semaphore_health:
        timeline_lines.extend(["", "## Semaphore Health", ""])
        for model_name, metrics in sorted(semaphore_health.items()):
            timeline_lines.append(
                f"  {model_name:40s} "
                f"A:{metrics['acquires']:3d} R:{metrics['releases']:3d} "
                f"T:{metrics['timeouts']:2d} G:{metrics['gate_rejections']:2d} "
                f"avg_wait:{metrics['avg_wait_ms']:6.1f}ms "
                f"timeout_rate:{metrics['timeout_rate']:.2f} "
                f"leak:{metrics['leak_ratio']:.4f}"
            )

    timeline_text = "\n".join(timeline_lines)

    # ── 2. Mermaid DAG colorido ──
    mermaid_lines = [
        "```mermaid",
        "flowchart TD",
        "    classDef success fill:#22c55e,stroke:#16a34a,color:#fff",
        "    classDef failed fill:#ef4444,stroke:#dc2626,color:#fff",
        "    classDef skipped fill:#94a3b8,stroke:#64748b,color:#fff",
        "    classDef aborted fill:#f97316,stroke:#ea580c,color:#fff",
        "    classDef timeout fill:#eab308,stroke:#ca8a04,color:#000",
        "    classDef pending fill:#64748b,stroke:#475569,color:#fff",
    ]

    # Classificar nós por estado
    success_nodes: List[str] = []
    failed_nodes: List[str] = []
    skipped_nodes: List[str] = []
    aborted_nodes: List[str] = []
    timeout_nodes: List[str] = []
    pending_nodes: List[str] = []

    # Nós do execution_report
    for nd in nodes_data:
        n = nd.get("node", "")
        s = nd.get("status", "pending")
        if s == "success":
            success_nodes.append(n)
        elif s == "failed":
            failed_nodes.append(n)
        else:
            pending_nodes.append(n)

    # Nós com skip_reason
    if skip_reasons:
        for node_name, reason in skip_reasons.items():
            if reason in ("aborted_by_sanity_barrier", "aborted_by_recovery"):
                if node_name in success_nodes:
                    success_nodes.remove(node_name)
                aborted_nodes.append(node_name)
            elif reason in ("timeout",):
                if node_name in success_nodes:
                    success_nodes.remove(node_name)
                timeout_nodes.append(node_name)
            elif node_name not in success_nodes and node_name not in failed_nodes:
                if node_name not in aborted_nodes and node_name not in timeout_nodes:
                    skipped_nodes.append(node_name)

    # Nós pendentes (não reportados)
    all_phases_nodes: set[str] = set()
    for nodes in PHASES.values():
        all_phases_nodes.update(nodes)
    reported = {nd.get("node", "") for nd in nodes_data}
    unreported = all_phases_nodes - reported
    for n in unreported:
        if n not in skipped_nodes and n not in aborted_nodes:
            skipped_nodes.append(n)

    # Renderizar arcos do DAG
    rendered_edges: set[tuple[str, str]] = set()
    for node_name, deps in NODE_DEPENDENCIES.items():
        for dep in deps:
            if dep not in all_phases_nodes and dep not in reported:
                continue
            edge = (dep, node_name)
            if edge not in rendered_edges:
                mermaid_lines.append(f"    {dep} --> {node_name}")
                rendered_edges.add(edge)

    # Declarações de classe
    all_nodes_display = all_phases_nodes | reported
    style_map: Dict[str, str] = {}
    for n in all_nodes_display:
        if n in success_nodes:
            style_map[n] = "success"
        elif n in failed_nodes:
            style_map[n] = "failed"
        elif n in timeout_nodes:
            style_map[n] = "timeout"
        elif n in aborted_nodes:
            style_map[n] = "aborted"
        elif n in skipped_nodes:
            style_map[n] = "skipped"
        elif n in pending_nodes:
            style_map[n] = "pending"
        else:
            style_map[n] = "skipped"

    # Agrupar por classe
    for cls_name in ("success", "failed", "timeout", "aborted", "skipped", "pending"):
        members = [n for n, c in style_map.items() if c == cls_name]
        if members:
            joined = ",".join(members)
            mermaid_lines.append(f"    class {joined} {cls_name}")

    mermaid_lines.append("```")
    mermaid_dag = "\n".join(mermaid_lines)

    # ── 3. Métricas consolidadas ──
    by_phase: Dict[str, Dict[str, int]] = {}
    for phase, nodes_in_phase in PHASES.items():
        total = len(nodes_in_phase)
        executed = sum(
            1 for n in nodes_in_phase if n in success_nodes or n in failed_nodes
        )
        failed = sum(1 for n in nodes_in_phase if n in failed_nodes)
        skipped = total - executed
        by_phase[phase] = {
            "total": total,
            "executed": executed,
            "failed": failed,
            "skipped": skipped,
        }

    consolidated_metrics = {
        "total_nodes_in_topology": len(all_phases_nodes),
        "nodes_reported": len(nodes_data),
        "success": len(success_nodes),
        "failed": len(failed_nodes),
        "skipped": len(skipped_nodes),
        "aborted": len(aborted_nodes),
        "timeout": len(timeout_nodes),
        "pipeline_duration_ms": round(pipeline_duration_ms, 1),
        "by_phase": by_phase,
        "semaphore_health": semaphore_health or {},
    }

    return {
        "timeline_text": timeline_text,
        "mermaid_dag": mermaid_dag,
        "consolidated_metrics": consolidated_metrics,
    }


def export_to_obsidian(
    timeline_data: Dict[str, Any],
    execution_id: str,
    vault_path: Optional[Path] = None,
) -> Dict[str, Path]:
    """
    Escreve os três artefatos de observabilidade no vault Obsidian.

    Args:
        timeline_data: output de build_execution_timeline()
        execution_id: identificador único da execução
        vault_path: caminho do vault Obsidian (default: PACKAGE_DIR/obsidian)

    Returns:
        dict com caminhos dos arquivos gerados: timeline, mermaid, metrics
    """
    if vault_path is None:
        from iaglobal._paths import PACKAGE_DIR

        vault_path = PACKAGE_DIR / "obsidian"

    # 04_Synapses é o diretório de padrões de execução
    out_dir = vault_path / "04_Synapses" / "executions"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = _time.strftime("%Y%m%d_%H%M%S")

    # Timeline
    timeline_path = out_dir / f"execution_timeline_{execution_id[:8]}_{ts}.md"
    content = timeline_data.get("timeline_text", "")
    content += "\n\n## Semaphore Health\n\n"
    sm = timeline_data.get("consolidated_metrics", {}).get("semaphore_health", {})
    for model, m in sorted(sm.items()):
        content += (
            f"- `{model}`: A={m.get('acquires', 0)} R={m.get('releases', 0)} "
            f"T={m.get('timeouts', 0)} avg_wait={m.get('avg_wait_ms', 0)}ms "
            f"timeout_rate={m.get('timeout_rate', 0)} leak={m.get('leak_ratio', 0)}\n"
        )
    timeline_path.write_text(content)

    # Mermaid DAG
    mermaid_path = out_dir / f"execution_graph_{execution_id[:8]}_{ts}.mmd"
    mermaid_path.write_text(timeline_data.get("mermaid_dag", ""))

    # Metrics JSON
    metrics_path = out_dir / f"execution_metrics_{execution_id[:8]}_{ts}.json"
    metrics_path.write_text(
        json.dumps(
            timeline_data.get("consolidated_metrics", {}), indent=2, ensure_ascii=False
        )
    )

    return {
        "timeline": timeline_path,
        "mermaid": mermaid_path,
        "metrics": metrics_path,
    }


__all__ = ["build_execution_timeline", "export_to_obsidian", "NODE_COLORS"]
