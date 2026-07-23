# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PipelineCoverageReport — gera relatório de cobertura de execução do DAG.

Consome:
  - execution_report (dict de ExecutionReport.finish())
  - skip_reasons (dict do ExecutionGraph)
  - topology.PHASES para classificação

Produz:
  - Per-phase execution counts
  - Skip reason breakdown
  - Overall coverage ratio
  - Mermaid timeline diagram
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from iaglobal.graphs.topology import PHASES, get_node_phase
from iaglobal.graphs.skip_reason import REASON_LABELS


def build_coverage_report(
    execution_report: Optional[Dict[str, Any]] = None,
    skip_reasons: Optional[Dict[str, str]] = None,
    all_nodes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Cross-references execution report + skip reasons + topology to produce
    a structured coverage report.

    Args:
        execution_report: dict from ExecutionReport.finish()
        skip_reasons: dict mapping node_name -> skip_reason constant
        all_nodes: complete list of expected node names (e.g. from RUN_NODE_NAMES)

    Returns:
        Coverage report dict with phases, skips, mermaid, and summary.
    """
    phase_nodes: Dict[str, set[str]] = {}
    for phase, nodes in PHASES.items():
        phase_nodes[phase] = set(nodes)

    all_expected: set[str] = set()
    for nodes in phase_nodes.values():
        all_expected.update(nodes)
    if all_nodes:
        all_expected.update(all_nodes)

    executed: set[str] = set()
    node_details: Dict[str, Dict[str, Any]] = {}

    if execution_report:
        for rec in execution_report.get("nodes", []):
            nid = rec.get("node", "")
            node_details[nid] = rec
            if rec.get("status") in ("success", "failed"):
                executed.add(nid)

    phase_counts: Dict[str, Dict[str, int]] = {}
    for phase in sorted(phase_nodes, key=_phase_order):
        phase_nodes_set = phase_nodes[phase]
        phase_total = len(phase_nodes_set & all_expected)
        phase_executed = len(phase_nodes_set & executed)
        phase_skipped = phase_total - phase_executed
        phase_counts[phase] = {
            "total": phase_total,
            "executed": phase_executed,
            "skipped": phase_skipped,
        }

    skip_breakdown: Dict[str, int] = {}
    if skip_reasons:
        for reason in skip_reasons.values():
            skip_breakdown[reason] = skip_breakdown.get(reason, 0) + 1

    labeled_skips: Dict[str, str] = {
        REASON_LABELS.get(k, k): v for k, v in skip_breakdown.items()
    }

    total_expected = len(all_expected)
    total_executed = len(executed)
    coverage_pct = (
        round((total_executed / total_expected) * 100, 1) if total_expected > 0 else 0.0
    )

    skipped_detail: List[Dict[str, str]] = []
    if skip_reasons:
        skipped_detail = [
            {
                "node": n,
                "reason": skip_reasons[n],
                "reason_label": REASON_LABELS.get(skip_reasons[n], skip_reasons[n]),
                "phase": get_node_phase(n),
            }
            for n in sorted(skip_reasons)
        ]

    mermaid_diagram = _build_mermaid(phase_nodes, executed, skip_reasons)

    return {
        "summary": {
            "total_expected": total_expected,
            "total_executed": total_executed,
            "coverage_pct": coverage_pct,
        },
        "phases": phase_counts,
        "skip_breakdown_raw": skip_breakdown,
        "skip_breakdown": labeled_skips,
        "skipped_nodes": skipped_detail,
        "mermaid": mermaid_diagram,
    }


def _phase_order(phase: str) -> int:
    """Sort key for pipeline phases."""
    order = [
        "definicao",
        "planejamento",
        "construcao",
        "qualidade",
        "entrega",
        "metacognicao",
    ]
    return order.index(phase) if phase in order else 99


def _build_mermaid(
    phase_nodes: Dict[str, set[str]],
    executed: set[str],
    skip_reasons: Optional[Dict[str, str]],
) -> str:
    """Generate a Mermaid Gantt / flowchart diagram of execution coverage."""
    if not phase_nodes:
        return ""

    lines = [
        "```mermaid",
        "gantt",
        "    title Pipeline Execution Coverage",
        "    dateFormat  YYYY-MM-DD",
        "    axisFormat  %H:%M",
    ]

    for phase in sorted(phase_nodes, key=_phase_order):
        nodes_sorted = sorted(phase_nodes[phase])
        if not nodes_sorted:
            continue
        lines.append(f"    section {phase}")
        for i, node_name in enumerate(nodes_sorted):
            status = "done" if node_name in executed else "crit"
            label = node_name
            if skip_reasons and node_name in skip_reasons:
                reason_label = REASON_LABELS.get(
                    skip_reasons[node_name], skip_reasons[node_name]
                )
                label = f"{node_name} ({reason_label})"
            lines.append(f"    {label} :{status}, 2024-01-01, 1d")

    lines.append("```")
    return "\n".join(lines)


__all__ = ["build_coverage_report"]
