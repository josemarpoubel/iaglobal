import os
import time
from typing import Dict, Any, List
from collections import Counter

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node
from iaglobal.evolution.evolutionruntime import EvolutionRuntime
from iaglobal.memory.db_manager import db as insights_db
from iaglobal.memory.memory_error import load_errors
from iaglobal.memory.memory_storage import storage
from iaglobal.security.sandbox_rules import SandboxRules
from iaglobal.utils.logger import logger


def _format_pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def _format_ts(ts: float) -> str:
    if not ts:
        return "never"
    dt = time.strftime("%H:%M:%S", time.localtime(ts))
    return dt


def _bar(value: float, width: int = 10) -> str:
    filled = max(0, min(width, int(value * width)))
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"


class Dashboard:

    def __init__(self, monitor=None): # Adicione o monitor aqui
        self.monitor = monitor

    @staticmethod
    def show_status(orch) -> None:
        """Exibe o painel completo de status no terminal."""
        graph = getattr(orch, "graph", None)
        evo_runtime = getattr(orch, "evolution_runtime", None)
        evo_engine = getattr(orch, "evolver", None)

        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("  IAGlobal System Status")
        lines.append("=" * 60)
        lines.append("")

        Dashboard._show_header(lines, graph)
        Dashboard._show_cpu_status(lines)
        Dashboard._show_dag_summary(lines, graph)
        Dashboard._show_node_health(lines, graph)
        Dashboard._show_evolution_status(lines, evo_runtime, evo_engine, graph)
        Dashboard._show_memory_status(lines)
        Dashboard._show_security_status(lines)
        Dashboard._show_immune_status(lines)

        print("\n".join(lines))
        logger.info("Status dashboard rendered")

    @staticmethod
    def _show_header(lines: list, graph: ExecutionGraph) -> None:
        lines.append(f"  Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Python    : {os.sys.version.split()[0]}")
        if graph:
            lines.append(f"  Graph gen : {graph.generation}")
        lines.append("")

    @staticmethod
    def _show_cpu_status(lines: list) -> None:
        lines.append("  ── CPU Affinity ──")
        try:
            from iaglobal.execution.cpu_affinity import cpu_affinity
            import asyncio
            report = asyncio.run(cpu_affinity.dispersion_report())
            lines.append(f"  Cores       : {report['total_cores']}")
            lines.append(f"  Agents map  : {report['agents_mapped']}")
            lines.append(f"  Max/core    : {report['max_load']}")
            lines.append(f"  Min/core    : {report['min_load']}")
            lines.append(f"  Imbalance   : {report['imbalance']}")
            lines.append(f"  Efficiency  : {_format_pct(report['efficiency'])}")
            cores_str = ", ".join(
                f"c{k}: {len(v)}" for k, v in sorted(report['per_core'].items())
            )
            lines.append(f"  Dist        : {cores_str}")
        except Exception as e:
            lines.append(f"  (erro: {e})")
        lines.append("")

    @staticmethod
    def _show_dag_summary(lines: list, graph: ExecutionGraph) -> None:
        lines.append("  ── DAG Summary ──")
        if not graph:
            lines.append("  (no graph)")
            return

        nodes = graph.nodes
        total = len(nodes)
        core_count = 0
        evo_count = 0
        strategy_counts: Counter = Counter()
        for node in nodes.values():
            if node.name.startswith("evo_"):
                evo_count += 1
            else:
                core_count += 1
            strategy_counts[node.strategy] += 1

        lines.append(f"  Total nodes  : {total}")
        lines.append(f"  Core nodes   : {core_count}")
        lines.append(f"  EVO nodes    : {evo_count}")
        lines.append(f"  Strategies   : {dict(strategy_counts)}")
        lines.append("")

    @staticmethod
    def _show_node_health(lines: list, graph: ExecutionGraph) -> None:
        lines.append("  ── Node Health ──")
        if not graph or not graph.nodes:
            lines.append("  (no data)")
            return

        header = f"  {'Node':<35} {'Type':<18} {'Execs':<6} {'Succ':<6} {'Fail':<6} {'Latency':<9} {'Fitness':<8}"
        sep = "  " + "-" * (35 + 18 + 6 + 6 + 6 + 9 + 8 + 1)

        lines.append(header)
        lines.append(sep)

        sorted_nodes = sorted(graph.nodes.values(), key=lambda n: n.executions, reverse=True)

        for node in sorted_nodes:
            name = node.name[:34]
            ntype = (node.node_type or "general")[:17]
            execs = str(node.executions)
            succ = str(node.success_count)
            fail = str(node.fail_count)
            lat = f"{node.avg_latency:.4f}s" if node.executions > 0 else "-"
            fit = f"{node.fitness():.4f}" if node.executions > 0 else "-"

            bar = _bar(node.success_rate if node.executions > 0 else 0.5, 8)
            lines.append(f"  {name:<35} {ntype:<18} {execs:<6} {succ:<6} {fail:<6} {lat:<9} {fit:<8}")
            if node.last_error:
                lines.append(f"  {'':>2} last error: {node.last_error[:80]}")

        lines.append("")

    @staticmethod
    def _show_evolution_status(lines: list, runtime: EvolutionRuntime, engine, graph: ExecutionGraph) -> None:
        lines.append("  ── Evolution ──")
        if runtime:
            st = runtime.status()
            lines.append(f"  Running     : {'yes' if st.get('running') else 'no'}")
            lines.append(f"  Cycles      : {st.get('cycles', 0)}")
            lines.append(f"  Failures    : {st.get('failures', 0)}")
            lines.append(f"  Last cycle  : {_format_ts(st.get('last_execution', 0))}")
            if st.get("last_error"):
                lines.append(f"  Last error  : {st['last_error'][:80]}")
        else:
            lines.append("  (runtime not available)")

        if engine:
            strategies = getattr(engine, "strategies", [])
            mut_rates = getattr(engine, "strategy_mutation_rates", {})
            lines.append(f"  Strategies  : {strategies}")
            lines.append(f"  Mut rates   : {mut_rates}")

        if graph:
            # Top 3 by fitness
            evo_nodes = [n for n in graph.nodes.values() if n.name.startswith("evo_") and n.executions > 0]
            if evo_nodes:
                top = sorted(evo_nodes, key=lambda n: n.fitness(), reverse=True)[:3]
                lines.append(f"  Top EVO     :")
                for n in top:
                    lines.append(f"    {n.name:<40} fitness={n.fitness():.4f} sr={n.success_rate:.2f} lat={n.avg_latency:.4f}s")
        lines.append("")

    @staticmethod
    def _show_memory_status(lines: list) -> None:
        lines.append("  ── Memory ──")
        try:
            total = insights_db.count_insights()
            lines.append(f"  Insights    : {total}")
        except Exception:
            lines.append("  Insights    : (erro ao consultar)")

        try:
            errors = load_errors()
            lines.append(f"  Errors      : {len(errors)}")
            if errors:
                types: Counter = Counter(e.get("error_type", "Unknown") for e in errors)
                lines.append(f"  Error types : {dict(types)}")
        except Exception:
            lines.append("  Errors      : (erro ao consultar)")

        try:
            success_count = 0
            if storage and hasattr(storage, "get_all"):
                success_count = len(storage.get_all())
            lines.append(f"  Successes   : {success_count}")
        except Exception:
            pass

        lines.append("")

    @staticmethod
    def _show_audit_status(lines: list, orch=None) -> None:
        lines.append("  ── Audit Trail ──")
        try:
            from iaglobal.events import store as decision_store
            decision_store.start()
            total = decision_store.count()
            lines.append(f"  DecisionEvents : {total}")
            if total > 0:
                steps = {}
                for s in ["memory_lookup", "candidate_selection", "model_selection",
                          "lock", "execution_metrics", "memory_store", "evolution_check",
                          "task_normalization"]:
                    c = decision_store.count(step=s)
                    if c:
                        steps[s] = c
                lines.append(f"  By step        : {steps}")

                # Count unique executions
                from iaglobal.memory.db_manager import db
                conn = db._get_conn()
                try:
                    cursor = conn.execute(
                        "SELECT COUNT(DISTINCT execution_id) FROM decision_events"
                    )
                    row = cursor.fetchone()
                    unique = row[0] if row else 0
                    lines.append(f"  Executions     : {unique}")

                    # Last 3 execution IDs
                    cursor2 = conn.execute(
                        "SELECT execution_id, MAX(created_at) FROM decision_events "
                        "GROUP BY execution_id ORDER BY MAX(created_at) DESC LIMIT 3"
                    )
                    recent = []
                    for r in cursor2.fetchall():
                        ts = r[1] or ""
                        recent.append(f"{r[0][:20]}...")
                    if recent:
                        lines.append(f"  Recent         : {', '.join(recent)}")
                finally:
                    conn.close()

            # Bandit info from orchestrator
            credit = getattr(orch, "credit", None) if orch else None
            if credit:
                lines.append(f"  Bandit keys    : {len(credit.stats)}")
                if credit.stats:
                    best_node = max(credit.stats.items(),
                                    key=lambda kv: kv[1]["success"] / max(1, kv[1]["success"] + kv[1]["fail"]))
                    lines.append(f"  Best combo     : {best_node[0]} ({best_node[1]['success']}/{best_node[1]['success'] + best_node[1]['fail']} ok)")

            evo_graph = getattr(orch, 'graph', None)
            if evo_graph and hasattr(evo_graph, 'nodes'):
                evo_nodes = [n for n in evo_graph.nodes.values()
                            if isinstance(n, Node) and n.name.startswith("evo_")]
                if evo_nodes:
                    lines.append(f"  EVO alive      : {len(evo_nodes)}")
        except Exception:
            lines.append("  (erro ao consultar)")
        lines.append("")

    @staticmethod
    def _show_security_status(lines: list) -> None:
        lines.append("  ── Security ──")
        try:
            rules = SandboxRules()
            lines.append(f"  Modules     : {len(rules.allowed_modules)} permitidos")
            lines.append(f"  Read paths  : {len(rules.allowed_read_paths)}")
            lines.append(f"  Write paths : {len(rules.allowed_write_paths)}")
            lines.append(f"  Blocked env : {len(rules.blocked_env_vars)} variaveis")
            stats = rules.get_stats()
            lines.append(f"  Checks      : {stats['modules_checked']} modulos, {stats['paths_checked']} paths")
        except Exception:
            lines.append("  (erro ao consultar)")
        lines.append("")

    @staticmethod
    def _show_immune_status(lines: list) -> None:
        lines.append("  ── Immune System ──")
        try:
            from iaglobal.observability.entropy_interceptor import get_immune_state
            
            state = get_immune_state()
            entropia = state.get("entropia", {})
            barreira = state.get("barreira", {})
            quarantine = state.get("quarantine", {})
            
            # Entropia
            total = entropia.get("total_profiles", 0)
            at_risk = entropia.get("agents_at_apoptosis_risk", 0)
            degrading = entropia.get("agents_degrading", 0)
            threshold = entropia.get("apoptosis_threshold", 0)
            min_exec = entropia.get("min_executions", 0)
            
            lines.append(f"  Entropy Profiles    : {total}")
            lines.append(f"  At Risk (Apoptose)  : {at_risk}")
            lines.append(f"  Degrading           : {degrading}")
            lines.append(f"  Threshold           : {threshold:.0%}")
            lines.append(f"  Min Executions      : {min_exec}")
            
            # Barreira
            events = barreira.get("events", {})
            lines.append(f"  Barreira Events     : cache_poison={events.get('cache_poison', 0)}, stale={events.get('stale_cache', 0)}")
            
            # Quarentena
            lines.append(f"  Quarantine Skills   : {quarantine.get('skills', 0)}")
            lines.append(f"  Active Detectors    : {quarantine.get('active_detectors', 0)}")
        except Exception as e:
            lines.append(f"  (erro ao consultar: {e})")
        lines.append("")
        lines.append("=" * 60)
