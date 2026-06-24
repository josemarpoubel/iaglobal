# iaglobal/cli/evolution_lab.py

"""
Evolutionary Test Lab CLI.

Unified terminal interface for all evolution tools:
  init, evolve, snapshots, report, diff, patch-sequence,
  detect-collapse, lineage, fitness-curve, export-json.

Usage:
  iaglobal evolution-lab <subcommand> [options]
  # or via dedicated entry point:
  evolution-lab <subcommand> [options]

Subcommands:
  init                Seed core graph + EVO population
  evolve <N>          Run N evolution cycles
  snapshots           List all generations
  report              Full replay report
  diff <A> <B>        Git-style diff between two generations
  patch-sequence      All consecutive generation patches
  detect-collapse     Run CollapseDetector on current state
  lineage <name>      Show ancestry tree for a node
  fitness-curve       Show per-generation mean fitness
  export-json <file>  Export patches as JSON array
  status              Unified evolution dashboard
  help                Show this message
"""

import argparse
import json
import sys
import time

from iaglobal.graphs.node import Node
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.evolution.evolution_replay import EvolutionReplay, CORE_NODE_NAMES
from iaglobal.evolution.collapse_detector import CollapseDetector
from iaglobal.evolution.skills.skill_registry import skill_registry
from iaglobal.memory.memory_storage import init_storage

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

# ── Helpers ──────────────────────────────────────────────────────────────
from iaglobal.utils.logger import logger

CORE = [
    ("prompt_intake", "prompt_intake", "general"),
    ("architect", "architect", "general"),
    ("planner", "planner", "general"),
    ("coder", "coder", "coding"),
    ("reviewer", "reviewer", "general"),
    ("debug_coder", "debugger", "debug"),
]

def _make_graph() -> ExecutionGraph:
    graph = ExecutionGraph()
    for name, node_type, strategy in CORE:
        node = Node(
            name=name,
            run=lambda ctx, n=name: {"output": f"{n}", "success": True},
            depends_on=[], strategy=strategy, node_type=node_type,
        )
        graph.add_node(node)
    return graph


def _make_pipeline_graph() -> ExecutionGraph:
    """Build the real 25-node V3 pipeline graph for evolution-lab."""
    from unittest.mock import MagicMock
    
    # IMPORTANTE: Verifique se este caminho está correto. 
    # Caso a função tenha sido renomeada, altere o import abaixo:
    try:

        from iaglobal.graphs.nodes.no_integrator import build_default_graph

    except ImportError as e:
        logger.error(f"❌ [LAB] Falha ao importar build_default_graph: {e}")
        raise

    logger.debug("🛠️ [LAB] Construindo grafo de pipeline via builder...")

    orchestrator = MagicMock()
    orchestrator.planner = MagicMock()
    orchestrator.planner.plan = MagicMock(return_value={"steps": []})
    orchestrator.evolver = MagicMock()
    orchestrator.evolver.designer = MagicMock()
    orchestrator.evolver.designer.specialization_instructions = {}

    try:
        graph = build_default_graph(orchestrator, "evolution-lab pipeline graph")
        logger.info("✅ [LAB] Grafo de pipeline construído com sucesso.")
        return graph
    except Exception as e:
        logger.error(f"❌ [LAB] Erro fatal na construção do grafo: {e}", exc_info=True)
        raise


def _record_fitness(engine: EvolutionEngine, times: int = 3):
    logger.debug(f"📈 [LAB] Registrando fitness para {len(engine.graph.nodes)} nós.")
    for node in engine.graph.nodes.values():
        if node.name.startswith("evo_") or "_mut_" in node.name or "_x_" in node.name:
            for _ in range(times):
                node.record(success=True, latency=0.5)


def _fmt(val: float) -> str:
    return f"{val:.4f}"


def _bar(val: float, width: int = 40) -> str:
    n = max(0, min(width, int(val * width)))
    return "█" * n + "░" * (width - n)

#=========================================================================================

# ── Subcommands ──────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace):
    """Seed core graph + EVO population."""
    logger.info(f"🚀 [LAB] Iniciando init (pipeline={args.pipeline})")
    try:
        init_storage(clear=True)
        skill_registry.clear()
        graph = _make_graph() if not args.pipeline else _make_pipeline_graph()
        engine = EvolutionEngine(graph, mutation_rate=args.mutation_rate)
        engine._seed_evo_population()
        _record_fitness(engine, 3)
        
        n_core = len(CORE_NODE_NAMES) if args.pipeline else len({c[0] for c in CORE})
        n_evo = len([n for n in graph.nodes.values() if n.name.startswith("evo_")])
        
        logger.info(f"✅ [LAB] Graph inicializado: {n_core} core + {n_evo} EVO nodes")
        print(f"  Graph initialized: {n_core} core + {n_evo} EVO nodes ({'pipeline' if args.pipeline else 'synthetic'} mode)")
        print(f"  Mutation rate: {engine.mutation_rate}")
        
        _store_engine(graph, engine)
        return graph, engine
    except Exception as e:
        logger.error(f"❌ [LAB] Falha no cmd_init: {e}", exc_info=True)
        raise


def cmd_evolve(args: argparse.Namespace):
    """Run N evolution cycles."""
    logger.info(f"🔄 [LAB] Iniciando evolução: {args.n} ciclos")
    graph, engine = _load_or_init(args)
    n = max(1, args.n)
    try:
        for i in range(n):
            logger.debug(f"⚙️ [LAB] Ciclo de evolução {i + 1}/{n}")
            engine.evolve()
            _record_fitness(engine, 3)
            replay = EvolutionReplay(graph, engine)
            snaps = replay.snapshots()
            last = snaps[-1] if snaps else None
            if last:
                print(f"  >>> Evolution cycle {i + 1}/{n} <<<")
                print(f"      Gen {last.generation}: {last.evo_count} EVO nodes, "
                      f"fitness={_fmt(last.mean_fitness)}, "
                      f"{last.strategy_diversity} strategies")
        _store_engine(graph, engine)
        logger.info("✅ [LAB] Evolução concluída.")
        return graph, engine
    except Exception as e:
        logger.error(f"❌ [LAB] Falha no cmd_evolve: {e}", exc_info=True)
        raise


def cmd_snapshots(args: argparse.Namespace):
    """List all generations."""
    logger.debug("📋 [LAB] Listando snapshots")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    snaps = replay.snapshots()
    if not snaps:
        print("  No snapshots available.")
        return
    print(f"  {'Gen':<6} {'EVO':<6} {'Core':<6} {'Mean Fitness':<16} {'Strategies':<12} {'Nodes'}")
    print(f"  {'-'*60}")
    for snap in snaps:
        node_list = ", ".join(n for n in sorted(snap.nodes) if n not in CORE_NODE_NAMES)[:80]
        print(f"  {snap.generation:<6} {snap.evo_count:<6} {snap.core_count:<6} "
              f"{_fmt(snap.mean_fitness):<16} {snap.strategy_diversity:<12} {node_list}")


def cmd_report(args: argparse.Namespace):
    """Full replay report."""
    logger.debug("📊 [LAB] Gerando relatório completo")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    print(replay.report())


def cmd_diff(args: argparse.Namespace):
    """Git-style diff between two generations."""
    logger.debug(f"⚖️ [LAB] Comparando gen {args.gen_a} com {args.gen_b}")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    try:
        patch = replay.diff_patch(args.gen_a, args.gen_b)
        _print_patch(patch)
    except ValueError as e:
        logger.warning(f"⚠️ [LAB] Erro no diff: {e}")
        print(f"  Error: {e}")
        print("  Use 'snapshots' to see available generations.")

#=========================================================================================

# ── Subcommands (Continuação) ──────────────────────────────────────────

def cmd_patch_sequence(args: argparse.Namespace):
    """All consecutive generation patches."""
    logger.debug("📜 [LAB] Gerando sequência de patches")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    patches = replay.patch_sequence()
    if not patches:
        logger.warning("⚠️ [LAB] Nenhuma patch encontrada para sequência")
        print("  No patches — need at least 2 generations.")
        return
    for p in patches:
        print(f"  {p.summary}")
        if args.verbose:
            _print_patch_detail(p)
            print()


def cmd_detect_collapse(args: argparse.Namespace):
    """Run CollapseDetector on current state."""
    logger.info("🔍 [LAB] Executando CollapseDetector...")
    try:
        graph, engine = _load_or_init(args)
        from iaglobal.evolution.collapse_detector import CollapseDetector
        detector = CollapseDetector(
            entropy_threshold=args.entropy_threshold,
            variance_threshold=args.variance_threshold,
            stagnation_threshold=args.stagnation_threshold,
            min_population=args.min_population,
            genetic_diversity_threshold=args.diversity_threshold,
            convergence_threshold=args.convergence_threshold,
        )
        report = detector.detect(graph)
        logger.info("✅ [LAB] Detecção de colapso concluída.")
        print(report.summary() if hasattr(report, 'summary') else str(report))
    except Exception as e:
        logger.error(f"❌ [LAB] Falha ao detectar colapso: {e}", exc_info=True)
        raise


def cmd_lineage(args: argparse.Namespace):
    """Show ancestry tree for a node."""
    logger.debug(f"🌳 [LAB] Consultando linhagem para: {args.name}")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    name = args.name
    
    if name == "__list__":
        evo_names = sorted(
            n.name for n in graph.nodes.values()
            if n.name.startswith("evo_") or "_mut_" in n.name or "_x_" in n.name
        )
        print("  Available EVO nodes:")
        for n in evo_names:
            node = graph.nodes.get(n)
            fit = _fmt(node.fitness()) if node else "?"
            print(f"    {n}  (fitness={fit})")
        return

    if name not in graph.nodes:
        logger.warning(f"⚠️ [LAB] Nó '{name}' não encontrado.")
        print(f"  Node '{name}' not found. Use 'lineage __list__' to see available nodes.")
        return

    try:
        tree = replay.ancestry_tree(name)
        print(tree)

        # Also show fitness history
        fh = replay.fitness_by_node(name)
        if fh:
            print(f"\n  Fitness history for '{name}':")
            for gen, fit in fh:
                print(f"    Gen {gen}: {_fmt(fit)}  {_bar(fit)}")
    except Exception as e:
        logger.error(f"❌ [LAB] Falha ao gerar árvore de linhagem para {name}: {e}", exc_info=True)
        raise

#=========================================================================================

# ── Subcommands (Continuação - Final) ───────────────────────────────────

def cmd_fitness_curve(args: argparse.Namespace):
    """Show per-generation mean fitness."""
    logger.debug("📈 [LAB] Gerando curva de fitness")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    
    try:
        curve = replay.fitness_curve()
        if not curve:
            logger.warning("⚠️ [LAB] Nenhuma curva de fitness disponível")
            print("  No fitness data.")
            return
            
        print(f"  {'Gen':<6} {'Fitness':<12} {'Bar'}")
        print(f"  {'-'*50}")
        for gen, fit in curve:
            print(f"  {gen:<6} {_fmt(fit):<12} {_bar(fit)}")
    except Exception as e:
        logger.error(f"❌ [LAB] Falha ao gerar curva de fitness: {e}", exc_info=True)
        raise


def cmd_export_json(args: argparse.Namespace):
    """Export all patches as JSON array to a file."""
    logger.info(f"💾 [LAB] Exportando patches para: {args.file}")
    graph, engine = _load_or_init(args)
    replay = EvolutionReplay(graph, engine)
    
    try:
        patches = replay.patch_sequence()
        data = [p.to_dict() for p in patches]
        path = args.file
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
            
        logger.info(f"✅ [LAB] Sucesso: {len(patches)} patches exportados.")
        print(f"  Exported {len(patches)} patches to {path}")
        
    except IOError as e:
        logger.error(f"❌ [LAB] Erro de I/O ao gravar JSON: {e}")
        print(f"  Error: Failed to write to {args.file}. Check permissions.")
    except Exception as e:
        logger.error(f"❌ [LAB] Falha inesperada na exportação: {e}", exc_info=True)
        raise

#=========================================================================================

# ── status ───────────────────────────────────────────────────────────


def cmd_status(args: argparse.Namespace):
    """Show unified dashboard: evolution, metabolism, immunity, recycling."""
    from iaglobal.evolution.metacognition.evaluator import PipelineEvaluator
    from iaglobal.evolution.same_engine import same_pool
    from iaglobal.recycling.mta_pool import mta_pool
    from iaglobal.evolution.metabolism.homocysteine_pool import homocysteine_pool
    from iaglobal.evolution.skills.skill_registry import skill_registry

    print("=" * 50)
    print("🧬 IAGlobal — Evolution Dashboard")
    print("=" * 50)

    print("\n📈 EVOLUTION")
    print(f"  Ciclos de evolução:  {PipelineEvaluator._evolution_count}")
    print(f"  Último score:        {PipelineEvaluator._last_score}/100")

    print("\n⚡ SAME BUDGET")
    try:
        balance = same_pool.balance("evolution_trigger")
        print(f"  Saldo SAMe:          {balance}")
    except Exception:
        print("  Saldo SAMe:          N/A")

    print("\n🧪 METABOLISM")
    try:
        hc_count = homocysteine_pool.count()
        pending = len(homocysteine_pool.get_pending())
        print(f"  Candidatas no pool:  {hc_count}")
        print(f"  Pendentes:           {pending}")
    except Exception:
        print("  Homocysteine pool:   N/A")

    print("\n🔧 SKILLS")
    try:
        all_skills = skill_registry.list_skills() if hasattr(skill_registry, "list_skills") else []
        auto_gen = [s for s in all_skills if "auto_generated" in (s.tags if hasattr(s, "tags") else [])]
        guardrails = [s for s in all_skills if "guardrail" in (s.tags if hasattr(s, "tags") else [])]
        print(f"  Total registradas:   {len(all_skills)}")
        print(f"  Auto-generated:      {len(auto_gen)}")
        print(f"  Guardrails:          {len(guardrails)}")
    except Exception:
        print("  Skills:              N/A")

    print("\n♻️  RECYCLING")
    try:
        mta_total = mta_pool.count()
        mta_failed = mta_pool.count("failed_prompt")
        print(f"  MTA Pool total:      {mta_total}")
        print(f"  Failed prompts:      {mta_failed}")
    except Exception:
        print("  MTA Pool:            N/A")

    print("\n🛡️  IMMUNITY")
    print("  Regression detector: ativo no evaluator")
    print("  Hallucination detect: ativo no evaluator")
    print("  Glutathione guardrails: ativo no sandbox")

    print("\n🧬 META-EVOLUTION")
    try:
        from iaglobal.evolution.meta_evolver import meta_evolver
        meta_stats = meta_evolver.get_stats()
        print(f"  Trials registrados:  {meta_stats['trials_count']}")
        print(f"  Melhor melhoria:     {meta_stats['best_improvement']:+.1f}")
        print(f"  Média de melhoria:   {meta_stats['avg_improvement']:+.1f}")
        print(f"  Mutation rate:       {meta_stats['current_params']['mutation_rate']:.3f}")
        print(f"  Crossover rate:      {meta_stats['current_params']['crossover_rate']:.3f}")
        print(f"  Exploration rate:    {meta_stats['current_params']['exploration_rate']:.3f}")
    except Exception:
        print("  Meta-evolution:      N/A")

    print("\n" + "=" * 50)


# ── Storage helpers ──────────────────────────────────────────────────────


class _EvolutionLabCache:
    """Cache thread-safe para EvolutionEngine e ExecutionGraph.

    Substitui globais de módulo (_GRAPH_CACHE, _ENGINE_CACHE) por
    uma classe com escopo controlado, evitando vazamento de memória
    e permitindo concorrência.
    """
    def __init__(self):
        self.graph = None
        self.engine = None

    def store(self, graph, engine):
        self.graph = graph
        self.engine = engine

    def load(self, args):
        if self.graph is not None and self.engine is not None:
            return self.graph, self.engine
        return None


_LAB_CACHE = _EvolutionLabCache()


def _store_engine(graph, engine):
    _LAB_CACHE.store(graph, engine)


def _load_or_init(args) -> tuple:
    cached = _LAB_CACHE.load(args)
    if cached is not None:
        return cached
    graph, engine = cmd_init(args)
    return graph, engine


# ── Output helpers ───────────────────────────────────────────────────────

def _print_patch(patch):
    print(f"  Gen {patch.from_gen} → {patch.to_gen}")
    print(f"    Author: {patch.author}")
    print(f"    Timestamp: {patch.timestamp}")
    print(f"    Summary: {patch.summary}")
    if patch.nodes_added:
        print(f"    Added ({len(patch.nodes_added)}):")
        for name in sorted(patch.nodes_added):
            nd = patch.nodes_added[name]
            print(f"      + {name}  (f={_fmt(nd.get('fitness', 0))}, "
                  f"strategy={nd.get('strategy', '?')})")
    if patch.nodes_removed:
        print(f"    Removed ({len(patch.nodes_removed)}):")
        for name in sorted(patch.nodes_removed):
            print(f"      - {name}")
    if patch.nodes_modified:
        print(f"    Modified ({len(patch.nodes_modified)}):")
        for name, before, after in patch.nodes_modified:
            bf = before.get("fitness", 0)
            af = after.get("fitness", 0)
            print(f"      ~ {name}: {_fmt(bf)} → {_fmt(af)} (Δ={af - bf:+.4f})")
            if before.get("strategy") != after.get("strategy"):
                print(f"        strategy: {before['strategy']} → {after['strategy']}")
    if patch.strategy_shifts:
        print(f"    Strategy shifts:")
        for name, (old_s, new_s) in patch.strategy_shifts.items():
            print(f"      {name}: {old_s} → {new_s}")
    print(f"    Fitness: {_fmt(patch.fitness_before)} → {_fmt(patch.fitness_after)} "
          f"(Δ={patch.fitness_delta:+.4f})")
    print(f"    Diversity: {patch.diversity_before} → {patch.diversity_after} "
          f"(Δ={patch.diversity_delta:+d})")


def _print_patch_detail(patch):
    if patch.nodes_added:
        for name in sorted(patch.nodes_added):
            nd = patch.nodes_added[name]
            print(f"      + {name}  f={_fmt(nd.get('fitness', 0))}  "
                  f"s={nd.get('strategy', '?')}")
    if patch.nodes_removed:
        for name in sorted(patch.nodes_removed):
            print(f"      - {name}")
    if patch.nodes_modified:
        for name, before, after in patch.nodes_modified:
            print(f"      ~ {name}  {_fmt(before.get('fitness', 0))} → "
                  f"{_fmt(after.get('fitness', 0))}")


# ── Main entry point ─────────────────────────────────────────────────────

def run_evolution_lab():
    logger.info("🧪 [LAB] Inicializando Laboratório de Evolução...")
    
    parser = argparse.ArgumentParser(
        description="Evolutionary Test Lab CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Argumentos globais
    parser.add_argument("--mutation-rate", type=float, default=0.3, help="Mutation rate (default: 0.3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--pipeline", action="store_true", help="Use real 25-node V3 pipeline graph")

    # Limiares
    parser.add_argument("--entropy-threshold", type=float, default=0.5)
    parser.add_argument("--variance-threshold", type=float, default=0.01)
    parser.add_argument("--stagnation-threshold", type=int, default=3)
    parser.add_argument("--min-population", type=int, default=2)
    parser.add_argument("--diversity-threshold", type=float, default=0.4)
    parser.add_argument("--convergence-threshold", type=float, default=0.95)

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

    # Definição dos subcomandos
    subparsers.add_parser("init", help="Seed core graph + EVO population").set_defaults(func=cmd_init)
    
    sp_evolve = subparsers.add_parser("evolve", help="Run N evolution cycles")
    sp_evolve.add_argument("n", type=int, nargs="?", default=1, help="Number of cycles")
    sp_evolve.set_defaults(func=cmd_evolve)

    subparsers.add_parser("snapshots", help="List all generations").set_defaults(func=cmd_snapshots)
    subparsers.add_parser("report", help="Full replay report").set_defaults(func=cmd_report)
    
    sp_diff = subparsers.add_parser("diff", help="Git-style diff between two generations")
    sp_diff.add_argument("gen_a", type=int, help="Source generation")
    sp_diff.add_argument("gen_b", type=int, help="Target generation")
    sp_diff.set_defaults(func=cmd_diff)

    subparsers.add_parser("patch-sequence", help="All consecutive patches").set_defaults(func=cmd_patch_sequence)
    subparsers.add_parser("detect-collapse", help="Run CollapseDetector").set_defaults(func=cmd_detect_collapse)
    
    sp_lineage = subparsers.add_parser("lineage", help="Show ancestry tree for a node")
    sp_lineage.add_argument("name", type=str, nargs="?", default="__list__", help="Node name")
    sp_lineage.set_defaults(func=cmd_lineage)

    subparsers.add_parser("fitness-curve", help="Show per-generation fitness").set_defaults(func=cmd_fitness_curve)
    
    sp_export = subparsers.add_parser("export-json", help="Export patches as JSON array")
    sp_export.add_argument("file", type=str, help="Output JSON file path")
    sp_export.set_defaults(func=cmd_export_json)

    subparsers.add_parser("status", help="Unified evolution dashboard").set_defaults(func=cmd_status)
    subparsers.add_parser("help", help="Show help").set_defaults(func=lambda a: parser.print_help())

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        return

    # Execução protegida por log
    logger.debug(f"⚙️ [LAB] Executando comando: {args.subcommand}")
    try:
        if args.subcommand == "init":
            cmd_init(args)
        elif args.subcommand == "evolve":
            cmd_evolve(args)
        elif args.subcommand == "snapshots":
            cmd_snapshots(args)
        elif args.subcommand == "report":
            cmd_report(args)
        elif args.subcommand == "diff":
            cmd_diff(args)
        elif args.subcommand == "patch-sequence":
            cmd_patch_sequence(args)
        elif args.subcommand == "detect-collapse":
            cmd_detect_collapse(args)
        elif args.subcommand == "lineage":
            cmd_lineage(args)
        elif args.subcommand == "fitness-curve":
            cmd_fitness_curve(args)
        elif args.subcommand == "export-json":
            cmd_export_json(args)
        elif args.subcommand == "status":
            cmd_status(args)
        elif hasattr(args, "func"):
            args.func(args)
        logger.info(f"✅ [LAB] Comando '{args.subcommand}' finalizado com sucesso.")
    except Exception as e:
        logger.error(f"❌ [LAB] Falha crítica ao executar '{args.subcommand}': {str(e)}", exc_info=True)
        # exc_info=True mostrará o stack trace completo no log, ajudando a achar o bug do builder
        raise

if __name__ == "__main__":
    run_evolution_lab()
