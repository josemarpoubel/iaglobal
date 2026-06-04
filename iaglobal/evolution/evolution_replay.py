"""
Evolution Replay — reproduce and inspect evolutionary runs.

Reconstructs per-generation population snapshots from node lineage data,
enabling step-through replay, fitness curve extraction, ancestry trees,
and generation diffs.
"""

import copy
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from iaglobal.utils.logger import logger


# =========================================================================
# 1. ReplayNode — reconstructed node state at a generation
# =========================================================================

@dataclass
class ReplayNode:
    name: str
    strategy: str
    fitness: float
    event_type: str          # "seed", "mutation", "crossover", "core"
    parents: List[str]       # direct ancestors from lineage
    created_at: int          # generation when this node first appeared
    node_type: str = "general"
    seed_id: str = ""


# =========================================================================
# 2. ReplaySnapshot — full population state at one generation
# =========================================================================

@dataclass
class ReplaySnapshot:
    generation: int
    nodes: Dict[str, ReplayNode] = field(default_factory=dict)
    evo_count: int = 0
    core_count: int = 0
    mean_fitness: float = 0.0
    strategy_diversity: float = 0.0
    strategy_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def node_names(self) -> List[str]:
        return sorted(self.nodes.keys())


# =========================================================================
# 3. ReplayDiff — what changed between two snapshots
# =========================================================================

@dataclass
class ReplayDiff:
    gen_a: int
    gen_b: int
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    fitness_changes: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [f"=== Diff gen {self.gen_a} → gen {self.gen_b} ==="]
        if self.added:
            lines.append(f"  ➕ Added ({len(self.added)}): {', '.join(self.added)}")
        if self.removed:
            lines.append(f"  ➖ Removed ({len(self.removed)}): {', '.join(self.removed)}")
        if self.fitness_changes:
            up = [(n, d) for n, d in self.fitness_changes.items() if d > 0]
            down = [(n, d) for n, d in self.fitness_changes.items() if d < 0]
            if up:
                lines.append(f"  📈 Fitness up: {', '.join(f'{n}={d:+.3f}' for n, d in up[:5])}")
            if down:
                lines.append(f"  📉 Fitness down: {', '.join(f'{n}={d:+.3f}' for n, d in down[:5])}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ReplayDiff":
        return ReplayDiff(**d)


# =========================================================================
# 3b. GenerationPatch — git-style structured diff for audit trail
# =========================================================================

@dataclass
class GenerationPatch:
    """Full structured diff between two generations, analogous to a git commit.

    Fields:
        from_gen:       source generation number
        to_gen:         target generation number
        author:         engine version / creator identifier
        timestamp:      when this patch was generated (epoch seconds)
        nodes_added:    ReplayNode metadata for every added node
        nodes_removed:  ReplayNode metadata for every removed node
        nodes_modified: (before_name, ReplayNode_before, ReplayNode_after) for changed nodes
        strategy_shifts:  {node_name: (old_strategy, new_strategy)}
        fitness_before: mean fitness of EVO nodes at from_gen
        fitness_after:  mean fitness of EVO nodes at to_gen
        fitness_delta:  fitness_after - fitness_before
        diversity_before: strategy diversity at from_gen
        diversity_after:  strategy diversity at to_gen
        diversity_delta:  diversity_after - diversity_before
        summary:        human-readable one-liner
    """
    from_gen: int
    to_gen: int
    author: str = "evolution_replay"
    timestamp: float = 0.0
    nodes_added: Dict[str, dict] = field(default_factory=dict)
    nodes_removed: Dict[str, dict] = field(default_factory=dict)
    nodes_modified: List[Tuple[str, dict, dict]] = field(default_factory=list)
    strategy_shifts: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    fitness_before: float = 0.0
    fitness_after: float = 0.0
    fitness_delta: float = 0.0
    diversity_before: int = 0
    diversity_after: int = 0
    diversity_delta: int = 0
    summary: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        self.fitness_delta = self.fitness_after - self.fitness_before
        self.diversity_delta = self.diversity_after - self.diversity_before
        if not self.summary:
            self.summary = (
                f"Gen {self.from_gen}→{self.to_gen}: "
                f"+{len(self.nodes_added)} -{len(self.nodes_removed)} "
                f"~{len(self.nodes_modified)} | "
                f"fitness Δ={self.fitness_delta:+.4f} | "
                f"diversity Δ={self.diversity_delta:+d}"
            )

    def to_dict(self) -> dict:
        return {
            "from_gen": self.from_gen,
            "to_gen": self.to_gen,
            "author": self.author,
            "timestamp": self.timestamp,
            "nodes_added": self.nodes_added,
            "nodes_removed": self.nodes_removed,
            "nodes_modified": [(n, b, a) for n, b, a in self.nodes_modified],
            "strategy_shifts": dict(self.strategy_shifts),
            "fitness_before": self.fitness_before,
            "fitness_after": self.fitness_after,
            "fitness_delta": self.fitness_delta,
            "diversity_before": self.diversity_before,
            "diversity_after": self.diversity_after,
            "diversity_delta": self.diversity_delta,
            "summary": self.summary,
        }

    @staticmethod
    def from_dict(d: dict) -> "GenerationPatch":
        obj = GenerationPatch(
            from_gen=d["from_gen"],
            to_gen=d["to_gen"],
        )
        obj.author = d.get("author", "evolution_replay")
        obj.timestamp = d.get("timestamp", time.time())
        obj.nodes_added = d.get("nodes_added", {})
        obj.nodes_removed = d.get("nodes_removed", {})
        obj.nodes_modified = [(n, b, a) for n, b, a in d.get("nodes_modified", [])]
        obj.strategy_shifts = dict(d.get("strategy_shifts", {}))
        obj.fitness_before = d.get("fitness_before", 0.0)
        obj.fitness_after = d.get("fitness_after", 0.0)
        obj.fitness_delta = d.get("fitness_delta", 0.0)
        obj.diversity_before = d.get("diversity_before", 0)
        obj.diversity_after = d.get("diversity_after", 0)
        obj.diversity_delta = d.get("diversity_delta", 0)
        obj.summary = d.get("summary", "")
        return obj

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string for audit persistence."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @staticmethod
    def from_json(data: str) -> "GenerationPatch":
        """Deserialize from JSON string."""
        return GenerationPatch.from_dict(json.loads(data))

    def apply_to(self, snapshot_a: "ReplaySnapshot") -> "ReplaySnapshot":
        """Apply this patch to a snapshot to reconstruct the next generation.

        Analogous to ``git apply`` — allows replaying evolution without
        re-running the engine.
        """
        new_nodes = dict(snapshot_a.nodes)

        # Remove deleted nodes
        for name in self.nodes_removed:
            new_nodes.pop(name, None)

        # Apply modifications
        for name, before, after in self.nodes_modified:
            new_nodes[name] = ReplayNode(**after)

        # Add new nodes
        for name, ndata in self.nodes_added.items():
            new_nodes[name] = ReplayNode(**ndata)

        # Apply strategy shifts
        for name, (old_s, new_s) in self.strategy_shifts.items():
            if name in new_nodes:
                new_nodes[name].strategy = new_s

        # Build the resulting snapshot
        evo_list = [n for n in new_nodes.values() if n.name not in CORE_NODE_NAMES]
        core_list = [n for n in new_nodes.values() if n.name in CORE_NODE_NAMES]
        fitness_values = [n.fitness for n in evo_list] if evo_list else [0.0]
        mean_fit = sum(fitness_values) / len(fitness_values)
        strategy_counts: Dict[str, int] = {}
        for n in evo_list:
            strategy_counts[n.strategy] = strategy_counts.get(n.strategy, 0) + 1

        return ReplaySnapshot(
            generation=self.to_gen,
            nodes=new_nodes,
            evo_count=len(evo_list),
            core_count=len(core_list),
            mean_fitness=mean_fit,
            strategy_diversity=len(strategy_counts),
            strategy_counts=strategy_counts,
        )


# =========================================================================
# 4. EvolutionReplay — main replay engine
# =========================================================================

CORE_NODE_NAMES = {
    "prompt_intake", "enhancement", "orchestrator_agent",
    "pm", "requirements", "architect", "search", "knowledge",
    "dependency", "risk_analysis",
    "security_design", "performance_design",
    "planner", "coder",
    "reviewer", "semantic_validator",
    "security_audit", "performance_audit",
    "tester", "debug_coder",
    "documentation", "release",
    "metrics", "optimization",
    "result_agent",
}


class EvolutionReplay:
    def __init__(self, graph, engine):
        self.graph = graph
        self.engine = engine
        self._snapshots: Optional[List[ReplaySnapshot]] = None

    # ----------------------------------------------------------
    # Reconstruct per-generation snapshots from lineage data
    # ----------------------------------------------------------

    def snapshots(self) -> List[ReplaySnapshot]:
        if self._snapshots is not None:
            return self._snapshots
        self._snapshots = self._build_snapshots()
        return self._snapshots

    def _build_snapshots(self) -> List[ReplaySnapshot]:
        """Reconstruct one ReplaySnapshot per generation from node lineage."""
        # Map: generation → {node_name → event_type}
        gen_nodes: Dict[int, Dict[str, str]] = {}
        gen_node_map: Dict[int, Dict[str, Node]] = {}

        # Collect all generations present in lineage data
        all_gens: set = set()
        for name, node in self.graph.nodes.items():
            if node.name in CORE_NODE_NAMES:
                continue  # core nodes exist in all generations
            for entry in node.lineage:
                gen = entry.generation
                all_gens.add(gen)
                if gen not in gen_nodes:
                    gen_nodes[gen] = {}
                    gen_node_map[gen] = {}
                gen_nodes[gen][node.name] = entry.event_type

        # Also infer survivor status: a node that was created at gen N
        # also exists in all subsequent generations (until potentially removed
        # by selection). We include it in subsequent snapshots.
        # First, find each node's creation generation
        node_created: Dict[str, int] = {}
        for name, node in self.graph.nodes.items():
            if node.name in CORE_NODE_NAMES:
                continue
            for entry in node.lineage:
                if entry.event_type == "seed":
                    node_created[name] = min(node_created.get(name, 999), entry.generation)
                elif entry.event_type in ("mutation", "crossover"):
                    node_created[name] = min(node_created.get(name, 999), entry.generation)

        # For each generation, include all nodes created at or before it
        max_gen = max(all_gens) if all_gens else 0
        # Ensure we have at least gen 0
        if 0 not in gen_nodes:
            gen_nodes[0] = {}
            gen_node_map[0] = {}

        for gen in range(max_gen + 1):
            if gen not in gen_nodes:
                gen_nodes[gen] = {}
                gen_node_map[gen] = {}

        for name, created_gen in node_created.items():
            node = self.graph.nodes.get(name)
            if not node:
                continue
            for gen in range(created_gen, max_gen + 1):
                if gen not in gen_nodes:
                    gen_nodes[gen] = {}
                    gen_node_map[gen] = {}
                if name not in gen_nodes[gen]:
                    gen_nodes[gen][name] = "survivor"

        # Build snapshots
        snapshots: List[ReplaySnapshot] = []
        for gen in sorted(gen_nodes.keys()):
            nodes_in_gen = gen_nodes[gen]
            replay_nodes: Dict[str, ReplayNode] = {}

            # Core nodes exist in all generations
            for core_name in sorted(CORE_NODE_NAMES):
                core_node = self.graph.nodes.get(core_name)
                if core_node:
                    replay_nodes[core_name] = ReplayNode(
                        name=core_name,
                        strategy=core_node.strategy,
                        fitness=core_node.fitness() if core_node else 0.0,
                        event_type="core",
                        parents=[],
                        created_at=0,
                        node_type=core_node.node_type if core_node else "general",
                    )

            for node_name, event_type in nodes_in_gen.items():
                node = self.graph.nodes.get(node_name)
                if not node:
                    continue
                parents = []
                for entry in node.lineage:
                    if entry.event_type == "crossover":
                        for p in entry.parent_name.split(" x "):
                            p = p.strip()
                            if p:
                                parents.append(p)
                    elif entry.parent_name:
                        parents.append(entry.parent_name)
                replay_nodes[node_name] = ReplayNode(
                    name=node_name,
                    strategy=node.strategy,
                    fitness=node.fitness(),
                    event_type=event_type if event_type != "survivor" else
                               (node.lineage[-1].event_type if node.lineage else "seed"),
                    parents=parents,
                    created_at=node_created.get(node_name, gen),
                    node_type=node.node_type,
                    seed_id=node.seed_id,
                )

            # Compute metrics
            evo_list = [n for n in replay_nodes.values() if n.name not in CORE_NODE_NAMES]
            core_list = [n for n in replay_nodes.values() if n.name in CORE_NODE_NAMES]
            fitness_values = [n.fitness for n in evo_list] if evo_list else [0.0]
            mean_fit = sum(fitness_values) / len(fitness_values)

            strategy_counts: Dict[str, int] = {}
            for n in evo_list:
                strategy_counts[n.strategy] = strategy_counts.get(n.strategy, 0) + 1
            strategy_div = len(strategy_counts)

            snapshots.append(ReplaySnapshot(
                generation=gen,
                nodes=replay_nodes,
                evo_count=len(evo_list),
                core_count=len(core_list),
                mean_fitness=mean_fit,
                strategy_diversity=strategy_div,
                strategy_counts=strategy_counts,
            ))

        return snapshots

    # ----------------------------------------------------------
    # Fitness curve
    # ----------------------------------------------------------

    def fitness_curve(self) -> List[Tuple[int, float]]:
        """Return (generation, mean_fitness) pairs."""
        return [(s.generation, s.mean_fitness) for s in self.snapshots()]

    def fitness_by_node(self, node_name: str) -> List[Tuple[int, float]]:
        """Return (generation, fitness) for a specific node."""
        result = []
        for snap in self.snapshots():
            node = snap.nodes.get(node_name)
            if node:
                result.append((snap.generation, node.fitness))
        return result

    # ----------------------------------------------------------
    # Ancestry
    # ----------------------------------------------------------

    def ancestry(self, node_name: str) -> List[str]:
        """Full ancestry chain from root seed to this node."""
        dag = self.engine.lineage_graph() if hasattr(self.engine, 'lineage_graph') else {}
        chain = []
        visited = set()
        def _walk(n: str):
            if n in visited:
                return
            visited.add(n)
            parents = dag.get(n, [])
            if parents:
                for p in parents:
                    _walk(p)
            chain.append(n)
        _walk(node_name)
        return chain

    def ancestry_tree(self, node_name: str) -> str:
        """ASCII tree of the full ancestry."""
        dag = self.engine.lineage_graph() if hasattr(self.engine, 'lineage_graph') else {}
        lines = []
        def _draw(n: str, prefix: str = "", is_last: bool = True):
            connector = "└── " if is_last else "├── "
            node = self.graph.nodes.get(n)
            fitness = f"{node.fitness():.3f}" if node else "?"
            strategy = node.strategy if node else "?"
            lines.append(f"{prefix}{connector}{n}  (f={fitness}, s={strategy})")
            children = [c for c, p in dag.items() if n in p]
            if not children:
                return
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(sorted(children)):
                _draw(child, child_prefix, i == len(children) - 1)
        _draw(node_name)
        return "\n".join(lines)

    # ----------------------------------------------------------
    # Generation diff
    # ----------------------------------------------------------

    def _snapshot_to_dict(self, snap: ReplaySnapshot) -> dict:
        """Serialize a ReplaySnapshot to a plain dict (JSON-friendly)."""
        return {
            "generation": snap.generation,
            "evo_count": snap.evo_count,
            "core_count": snap.core_count,
            "mean_fitness": snap.mean_fitness,
            "strategy_diversity": snap.strategy_diversity,
            "strategy_counts": dict(snap.strategy_counts),
            "nodes": {n: asdict(rn) for n, rn in snap.nodes.items()},
        }

    def diff(self, gen_a: int, gen_b: int) -> ReplayDiff:
        snaps = self.snapshots()
        snap_map = {s.generation: s for s in snaps}
        sa = snap_map.get(gen_a)
        sb = snap_map.get(gen_b)
        if not sa or not sb:
            raise ValueError(f"Generation {gen_a} or {gen_b} not found")

        evo_a = set(n for n in sa.nodes if n not in CORE_NODE_NAMES)
        evo_b = set(n for n in sb.nodes if n not in CORE_NODE_NAMES)
        added = sorted(evo_b - evo_a)
        removed = sorted(evo_a - evo_b)

        fitness_changes = {}
        for name in evo_a & evo_b:
            na = sa.nodes[name]
            nb = sb.nodes[name]
            if abs(nb.fitness - na.fitness) > 1e-6:
                fitness_changes[name] = nb.fitness - na.fitness

        return ReplayDiff(
            gen_a=gen_a,
            gen_b=gen_b,
            added=added,
            removed=removed,
            fitness_changes=fitness_changes,
        )

    def diff_patch(self, gen_a: int, gen_b: int,
                   author: str = "evolution_replay") -> GenerationPatch:
        """Produce a GenerationPatch (git-style diff) between two generations.

        Includes full node metadata, strategy shifts, and aggregate stats.
        """
        snaps = self.snapshots()
        snap_map = {s.generation: s for s in snaps}
        sa = snap_map.get(gen_a)
        sb = snap_map.get(gen_b)
        if not sa or not sb:
            raise ValueError(f"Generation {gen_a} or {gen_b} not found")

        evo_a = {n: sa.nodes[n] for n in sa.nodes if n not in CORE_NODE_NAMES}
        evo_b = {n: sb.nodes[n] for n in sb.nodes if n not in CORE_NODE_NAMES}
        set_a = set(evo_a)
        set_b = set(evo_b)

        added_names = set_b - set_a
        removed_names = set_a - set_b
        common = set_a & set_b

        nodes_added = {}
        for n in added_names:
            rn = evo_b[n]
            nodes_added[n] = asdict(rn)

        nodes_removed = {}
        for n in removed_names:
            rn = evo_a[n]
            nodes_removed[n] = asdict(rn)

        nodes_modified = []
        strategy_shifts = {}
        for n in sorted(common):
            before = evo_a[n]
            after = evo_b[n]
            if abs(before.fitness - after.fitness) > 1e-6 or before.strategy != after.strategy:
                nodes_modified.append((n, asdict(before), asdict(after)))
            if before.strategy != after.strategy:
                strategy_shifts[n] = (before.strategy, after.strategy)

        fitness_before = sa.mean_fitness
        fitness_after = sb.mean_fitness
        div_before = sa.strategy_diversity
        div_after = sb.strategy_diversity

        return GenerationPatch(
            from_gen=gen_a,
            to_gen=gen_b,
            author=author,
            nodes_added=nodes_added,
            nodes_removed=nodes_removed,
            nodes_modified=nodes_modified,
            strategy_shifts=strategy_shifts,
            fitness_before=fitness_before,
            fitness_after=fitness_after,
            fitness_delta=fitness_after - fitness_before,
            diversity_before=div_before,
            diversity_after=div_after,
            diversity_delta=div_after - div_before,
        )

    def patch_sequence(self, author: str = "evolution_replay") -> List[GenerationPatch]:
        """Return a list of GenerationPatches for all consecutive generations."""
        snaps = self.snapshots()
        patches = []
        for i in range(len(snaps) - 1):
            patch = self.diff_patch(snaps[i].generation, snaps[i + 1].generation,
                                    author=author)
            patches.append(patch)
        return patches

    def diff_to_json(self, gen_a: int, gen_b: int, indent: int = 2) -> str:
        """Serialize diff between two generations as JSON."""
        return self.diff_patch(gen_a, gen_b).to_json(indent=indent)

    @staticmethod
    def diff_from_json(data: str) -> GenerationPatch:
        """Deserialize a GenerationPatch from JSON."""
        return GenerationPatch.from_json(data)

    # ----------------------------------------------------------
    # Step-through generator
    # ----------------------------------------------------------

    def stepper(self):
        """Generator yielding one ReplaySnapshot at a time in order."""
        for snap in self.snapshots():
            yield snap

    # ----------------------------------------------------------
    # Human-readable report
    # ----------------------------------------------------------

    def report(self) -> str:
        snaps = self.snapshots()
        if not snaps:
            return "No replay data available."

        lines = ["=" * 60]
        lines.append("  EVOLUTION REPLAY REPORT")
        lines.append("=" * 60)

        curve = self.fitness_curve()
        lines.append("")
        lines.append("  Fitness Curve:")
        for gen, fit in curve:
            bar = "█" * max(0, min(50, int(fit * 50)))
            lines.append(f"    Gen {gen}: {fit:.4f}  {bar}")

        lines.append("")
        lines.append("  Per-Generation Summary:")
        for snap in snaps:
            lines.append(f"    Gen {snap.generation}: "
                         f"{snap.evo_count} EVO nodes, "
                         f"{snap.strategy_diversity} strategies, "
                         f"fitness={snap.mean_fitness:.4f}")

        lines.append("")
        lines.append("  Diffs:")
        for i in range(len(snaps) - 1):
            d = self.diff(snaps[i].generation, snaps[i + 1].generation)
            delta = snaps[i + 1].mean_fitness - snaps[i].mean_fitness
            dir_str = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
            lines.append(f"    Gen {d.gen_a}→{d.gen_b}: "
                         f"{dir_str} fitness Δ={delta:+.4f} | "
                         f"+{len(d.added)} -{len(d.removed)} nodes")

        lines.append("")
        lines.append("  Ancestry Roots:")
        dag = self.engine.lineage_graph() if hasattr(self.engine, 'lineage_graph') else {}
        roots = sorted(n for n, p in dag.items() if not p)
        for root in roots[:10]:
            node = self.graph.nodes.get(root)
            fit = f"{node.fitness():.3f}" if node else "?"
            lines.append(f"    🌱 {root}  (f={fit})")
        if len(roots) > 10:
            lines.append(f"    ... and {len(roots) - 10} more")

        return "\n".join(lines)
