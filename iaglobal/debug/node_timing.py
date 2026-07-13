"""Benchmark: latência por node e por fase do DAG de 55 nós."""

import asyncio
import logging
import time
from typing import Dict

logging.basicConfig(level=logging.WARNING)

from iaglobal.graphs.builder import build_pipeline_from_nodes
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node
import iaglobal.graphs.topology as topology


class TimedExecutionGraph(ExecutionGraph):
    """Wraps _execute_node_async to capture per-node timing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timings: Dict[str, dict] = {}

    async def _execute_node_async(self, node: Node, input_data: dict) -> dict:
        t0 = time.time()
        try:
            result = await super()._execute_node_async(node, input_data)
            elapsed = time.time() - t0
            self.timings[node.name] = {
                "elapsed": elapsed,
                "phase": topology.get_node_phase(node.name),
                "success": result.get("success", False),
                "error": result.get("error"),
            }
            return result
        except Exception as e:
            elapsed = time.time() - t0
            self.timings[node.name] = {
                "elapsed": elapsed,
                "phase": topology.get_node_phase(node.name),
                "success": False,
                "error": str(e),
            }
            raise


def report(timings: Dict[str, dict], total: float) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("BENCHMARK DE LATÊNCIA — DAG 55 NÓS")
    lines.append("=" * 60)

    phase_times: Dict[str, float] = {}
    phase_counts: Dict[str, int] = {}
    phase_fails: Dict[str, int] = {}

    for name, t in sorted(timings.items(), key=lambda x: x[1]["elapsed"], reverse=True):
        phase = t["phase"]
        phase_times[phase] = phase_times.get(phase, 0) + t["elapsed"]
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        if not t["success"]:
            phase_fails[phase] = phase_fails.get(phase, 0) + 1

    # Top 10 mais lentos
    lines.append(f"\n{'═' * 60}")
    lines.append("TOP 10 NÓS MAIS LENTOS")
    lines.append(f"{'═' * 60}")
    lines.append(f"{'#':>3} {'Node':<28} {'Fase':<16} {'Tempo':>8}")
    lines.append(f"{'─' * 58}")
    for i, (name, t) in enumerate(
        sorted(timings.items(), key=lambda x: x[1]["elapsed"], reverse=True)[:10], 1
    ):
        status = "✗" if not t["success"] else "✓"
        lines.append(
            f"{i:>3} {name:<28} {t['phase']:<16} {t['elapsed']:>7.2f}s {status}"
        )

    # Todas as fases
    lines.append(f"\n{'═' * 60}")
    lines.append("RESUMO POR FASE")
    lines.append(f"{'═' * 60}")
    lines.append(f"{'Fase':<18} {'Nós':>4} {'Falhas':>7} {'Tempo':>8} {'Média':>8}")
    lines.append(f"{'─' * 48}")
    phases_in_order = [
        "definicao",
        "planejamento",
        "construcao",
        "qualidade",
        "correcao",
        "entrega",
        "metacognicao",
    ]
    for phase in phases_in_order:
        tt = phase_times.get(phase, 0)
        n = phase_counts.get(phase, 0)
        f = phase_fails.get(phase, 0)
        avg = tt / n if n > 0 else 0
        lines.append(f"{phase:<18} {n:>4} {f:>7} {tt:>8.2f}s {avg:>7.2f}s")
    lines.append(f"{'─' * 48}")
    lines.append(f"{'TOTAL':<18} {len(timings):>4} {'':>7} {total:>8.2f}s")

    # Estatísticas
    all_times = [t["elapsed"] for t in timings.values()]
    successes = sum(1 for t in timings.values() if t["success"])
    failures = sum(1 for t in timings.values() if not t["success"])

    lines.append(f"\n{'═' * 60}")
    lines.append("ESTATÍSTICAS")
    lines.append(f"{'═' * 60}")
    lines.append(f"  Nós executados : {len(timings)}")
    lines.append(f"  Sucessos       : {successes}")
    lines.append(f"  Falhas         : {failures}")
    lines.append(f"  Tempo total    : {total:.2f}s")
    lines.append(
        f"  Mais rápido    : {min(all_times):.2f}s ({min(timings, key=lambda n: timings[n]['elapsed'])})"
    )
    lines.append(
        f"  Mais lento     : {max(all_times):.2f}s ({max(timings, key=lambda n: timings[n]['elapsed'])})"
    )
    lines.append(
        f"  Mediana        : {sorted(all_times)[len(all_times) // 2]:.2f}s"
        if all_times
        else "N/A"
    )
    lines.append("=" * 60)

    return "\n".join(lines)


async def main():
    graph = TimedExecutionGraph()
    graph.nodes = build_pipeline_from_nodes().nodes

    t0 = time.time()
    ctx = {"input": {"task": "gerar script python hello world"}, "output": ""}
    result = graph.run(ctx)
    total = time.time() - t0

    print(report(graph.timings, total))

    # Salvar raw data
    import json

    raw = {
        "total_seconds": total,
        "nodes": len(graph.timings),
        "per_node": graph.timings,
    }
    import os

    data_dir = os.path.join(os.path.dirname(__file__), "..", "memory", "data")
    target_path = os.path.join(data_dir, "benchmark_latency.json")

    def _save():
        with open(target_path, "w") as f:
            json.dump(raw, f, indent=2, default=str)

    await asyncio.to_thread(_save)
    print(f"\nDados brutos salvos em {data_dir}/benchmark_latency.json")


if __name__ == "__main__":
    asyncio.run(main())
