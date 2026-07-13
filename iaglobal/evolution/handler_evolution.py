# iaglobal/evolution/handler_evolution.py (HandlerEvolver — evolução dos handlers via mutation e crossover no nível de AST)

import ast
import hashlib
import logging
import re
import secrets
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from iaglobal.evolution.skills.utils.dynamic_registry import dynamic_registry
from iaglobal.evolution.skills.native.skill import ExecutionPolicy, Skill
from iaglobal.graphs.node import Node

HANDLERS_DIR = Path(__file__).parent.parent / "graphs" / "nodes"
MAX_MUTATIONS_PER_HANDLER = 2
MAX_HYBRIDS_PER_CYCLE = 7

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mutation operators — each is an ast.NodeTransformer subclass
# ---------------------------------------------------------------------------


class _BaseMutator(ast.NodeTransformer):
    """Base class for mutation operators with common helpers."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = secrets.SystemRandom()
        self._mutated = False

    def _maybe(self, prob: float = 0.5) -> bool:
        return self._rng.random() < prob

    def _jitter(self, value: int, fraction: float = 0.3) -> int:
        delta = max(1, int(value * fraction))
        return value + self._rng.choice([-delta, delta])


class _ScoreThresholdMutator(_BaseMutator):
    """Shifts numeric comparison thresholds by ±20%."""

    COMPARE_OPS = {ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq}

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        node = self.generic_visit(node)
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return node
        op = node.ops[0]
        if type(op) not in self.COMPARE_OPS:
            return node
        right = node.comparators[0]
        if not isinstance(right, ast.Constant) or not isinstance(
            right.value, (int, float)
        ):
            return node
        if isinstance(right.value, int) and right.value > 1000:
            return node
        if self._maybe(0.6):
            jittered = self._jitter(int(right.value), fraction=0.2)
            if jittered != right.value:
                node.comparators[0] = ast.Constant(value=jittered)
                self._mutated = True
        return node


class _SourceTupleMutator(_BaseMutator):
    """Adds/removes/reorders source-name tuples in for-loops."""

    ALL_SOURCES = [
        "multi_coder",
        "coder",
        "debug_coder",
        "backend_builder",
        "frontend_builder",
        "api_builder",
        "database_builder",
        "test_generator",
        "search",
        "knowledge",
        "architect",
    ]

    def visit_Tuple(self, node: ast.Tuple) -> ast.AST:
        node = self.generic_visit(node)
        elts = node.elts
        if not elts:
            return node
        if not all(
            isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts
        ):
            return node
        values: List[str] = [e.value for e in elts]

        # Only mutate source-looking tuples (all elements are short source names)
        if not all(v.isidentifier() for v in values):
            return node
        if not any(v in self.ALL_SOURCES for v in values):
            return node

        action = self._rng.choice(["add", "remove", "reorder", "replace"])
        if action == "add" and self._maybe(0.4):
            candidate = self._rng.choice(self.ALL_SOURCES)
            if candidate not in values:
                pos = self._rng.randint(0, len(values))
                values.insert(pos, candidate)
                self._mutated = True
        elif action == "remove" and len(values) > 2 and self._maybe(0.3):
            idx = self._rng.randint(0, len(values) - 1)
            values.pop(idx)
            self._mutated = True
        elif action == "reorder" and len(values) > 2 and self._maybe(0.3):
            self._rng.shuffle(values)
            self._mutated = True
        elif action == "replace" and self._maybe(0.3):
            idx = self._rng.randint(0, len(values) - 1)
            candidates = [s for s in self.ALL_SOURCES if s not in values]
            if candidates:
                values[idx] = self._rng.choice(candidates)
                self._mutated = True

        node.elts = [ast.Constant(value=v) for v in values]
        return node


class _LogLevelMutator(_BaseMutator):
    """Bumps log level up/down: info ↔ warning ↔ exception ↔ debug."""

    LEVELS = ["debug", "info", "warning", "error", "exception"]

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node = self.generic_visit(node)
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "logger"
            and node.attr in self.LEVELS
        ):
            if self._maybe(0.25):
                idx = self.LEVELS.index(node.attr)
                shift = self._rng.choice([-1, 1])
                new_idx = max(0, min(len(self.LEVELS) - 1, idx + shift))
                if new_idx != idx:
                    node.attr = self.LEVELS[new_idx]
                    self._mutated = True
        return node


class _IntParamMutator(_BaseMutator):
    """Tweaks int literals used as function arguments (max_*, limit, etc.)."""

    INT_PARAM_NAMES = re.compile(r"(max_|limit|timeout|count|size|attempts|retries)")

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        for kw in node.keywords:
            if kw.arg and self.INT_PARAM_NAMES.search(kw.arg):
                if isinstance(kw.value, ast.Constant) and isinstance(
                    kw.value.value, int
                ):
                    if self._maybe(0.3):
                        kw.value = ast.Constant(
                            value=self._jitter(kw.value.value, fraction=0.3)
                        )
                        self._mutated = True
        return node


class _BoolFlagMutator(_BaseMutator):
    """Flips boolean constants."""

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool) and self._maybe(0.1):
            node.value = not node.value
            self._mutated = True
        return node


# ---------------------------------------------------------------------------
# Crossover operators
# ---------------------------------------------------------------------------


class _SourceCrossover:
    """Combines source tuples from two parents — union of both."""

    @staticmethod
    def apply(parent_a_source: str, parent_b_source: str) -> str:
        def extract_sources(source: str) -> Set[str]:
            matches = re.findall(r'"([a-z_]+)"', source)
            return set(matches)

        sources_a = extract_sources(parent_a_source)
        sources_b = extract_sources(parent_b_source)
        combined = sources_a | sources_b
        if not combined:
            return parent_a_source
        sources_str = ", ".join(f'"{s}"' for s in sorted(combined))
        return f"({sources_str})"


class _ThresholdCrossover:
    """Swaps threshold values between two handlers."""

    @staticmethod
    def extract_thresholds(source: str) -> List[Tuple[int, ast.Compare]]:
        thresholds: List[Tuple[int, Any]] = []
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for comp in node.comparators:
                    if isinstance(comp, ast.Constant) and isinstance(
                        comp.value, (int, float)
                    ):
                        thresholds.append((comp.lineno, comp.value))
        return thresholds

    @staticmethod
    def apply(source: str, other_source: str) -> str:
        """Replace thresholds in source with thresholds from other_source at same position."""
        thresholds_other = _ThresholdCrossover.extract_thresholds(other_source)
        if not thresholds_other:
            return source
        lines = source.splitlines()
        replacements = 0
        for lineno, val in thresholds_other:
            idx = lineno - 1
            if idx >= len(lines):
                continue
            old_line = lines[idx]
            new_line = re.sub(r"\b\d{2,3}\b", str(int(val)), old_line, count=1)
            if new_line != old_line:
                lines[idx] = new_line
                replacements += 1
            if replacements >= 3:
                break
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Handler loader / writer
# ---------------------------------------------------------------------------


def _load_handler_source(name: str) -> Optional[str]:
    path = HANDLERS_DIR / f"no_{name}.py"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _is_stub(source: str) -> bool:
    """Heuristic: stubs just return ctx and are < 10 lines."""
    lines = [
        l
        for l in source.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    return len(lines) <= 8 and "return ctx" in source


def _extract_run_fn_name(source: str) -> Optional[str]:
    m = re.search(r"^async def (run_\w+)", source, re.MULTILINE)
    return m.group(1) if m else None


def _write_handler(name: str, source: str) -> Optional[Path]:
    path = HANDLERS_DIR / f"no_{name}.py"
    if path.exists():
        _log.warning("[HANDLER-EVO] %s já existe, pulando", path.name)
        return None
    path.write_text(source.strip() + "\n", encoding="utf-8")
    _log.info("[HANDLER-EVO] Escrito: %s (%d chars)", path.name, len(source))
    return path


def _validate_import(name: str) -> bool:
    """Try importing the new handler to verify it's valid Python."""
    import importlib

    try:
        importlib.import_module(f"iaglobal.graphs.nodes.no_{name}")
        return True
    except Exception:
        _log.warning(
            "[HANDLER-EVO] Falha ao importar no_%s:\n%s", name, traceback.format_exc()
        )
        return False


# ---------------------------------------------------------------------------
# HandlerEvolver
# ---------------------------------------------------------------------------


class HandlerEvolver:
    """Evolves handler implementations at the AST level."""

    MUTATORS: List[Callable[[], _BaseMutator]] = [
        _ScoreThresholdMutator,
        _SourceTupleMutator,
        _LogLevelMutator,
        _IntParamMutator,
        _BoolFlagMutator,
    ]

    def __init__(self, engine: Any, generation: int = 0):
        self.engine = engine
        self.graph = engine.graph if hasattr(engine, "graph") else engine
        self.generation = generation
        self._core_names = (
            getattr(engine, "CORE_NODE_NAMES", [])
            if hasattr(engine, "CORE_NODE_NAMES")
            else []
        )
        self._rng = secrets.SystemRandom()
        self._evo_nodes = self._collect_evo_nodes()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _collect_evo_nodes(self) -> List[Tuple[str, Any]]:
        """Return (handler_name, node) pairs eligible for evolution.

        A handler is eligible when:
        - Its node exists in the graph with executions > 0
        - Its handler file exists on disk and is not a stub
        - Its name doesn't already contain '_evo_' (prevents re-evolution)
        """
        candidates: List[Tuple[str, Any]] = []
        for node_name, node in self.graph.nodes.items():
            if node_name in self._core_names:
                continue
            if "_evo_" in node_name:
                continue
            if getattr(node, "executions", 0) == 0:
                continue
            source = _load_handler_source(node_name)
            if source is None or _is_stub(source):
                continue
            candidates.append((node_name, node))
        return candidates

    def _select_parents(self) -> List[Tuple[str, Any]]:
        """Select top 50% by fitness."""
        scored = [(n.name, n.fitness(), n) for _, n in self._evo_nodes]
        scored.sort(key=lambda t: t[1], reverse=True)
        cutoff = max(1, len(scored) // 2)
        return [(name, node) for name, _, node in scored[:cutoff]]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def _mutate_handler(self, name: str, source: str) -> Optional[str]:
        """Apply random mutation operators to handler source."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            _log.warning("[HANDLER-EVO] Erro de sintaxe em %s, pulando mutação", name)
            return None

        mutators = self._rng.sample(
            self.MUTATORS, min(MAX_MUTATIONS_PER_HANDLER, len(self.MUTATORS))
        )
        modified = tree
        applied: List[str] = []
        for mut_cls in mutators:
            mut = mut_cls()
            modified = mut.visit(modified)
            ast.fix_missing_locations(modified)
            if mut._mutated:
                applied.append(mut_cls.__name__.lstrip("_").removesuffix("Mutator"))

        if not applied:
            return None

        new_source = ast.unparse(modified)
        new_name = self._new_name(name, applied, "mut")
        _log.info(
            "[HANDLER-EVO] Mutado %s → %s [%s]", name, new_name, ",".join(applied)
        )

        # Replace the run function name
        old_fn = _extract_run_fn_name(new_source) or f"run_{name}"
        new_fn = f"run_{new_name}"
        new_source = new_source.replace(old_fn, new_fn)

        return new_name, new_source

    def _new_name(self, base: str, ops: List[str], mode: str) -> str:
        tag = hashlib.sha256("_".join(ops).encode()).hexdigest()[:6]
        return f"{base}_evo_{self.generation}_{tag}"

    # ------------------------------------------------------------------
    # Crossover
    # ------------------------------------------------------------------

    def _crossover_handlers(
        self, parent_a: Tuple[str, str], parent_b: Tuple[str, str]
    ) -> Optional[Tuple[str, str]]:
        name_a, src_a = parent_a
        name_b, src_b = parent_b
        try:
            ast.parse(src_a)
            ast.parse(src_b)
        except SyntaxError:
            return None

        operator = self._rng.choice(["sources", "thresholds", "both"])
        new_src = src_a

        if operator in ("sources", "both"):
            new_src = _SourceCrossover.apply(new_src, src_b)
        if operator in ("thresholds", "both"):
            new_src = _ThresholdCrossover.apply(new_src, src_b)

        new_name = self._new_name(name_a, [name_b[:6]], "cx")
        old_fn = _extract_run_fn_name(new_src) or f"run_{name_a}"
        new_fn = f"run_{new_name}"
        new_src = new_src.replace(old_fn, new_fn)

        _log.info(
            "[HANDLER-EVO] Crossover %s x %s → %s [%s]",
            name_a,
            name_b,
            new_name,
            operator,
        )
        return new_name, new_src

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_handler(self, name: str, source: str) -> bool:
        """Write, validate, register as Skill, add as Node."""
        path = _write_handler(name, source)
        if path is None:
            return False
        if not _validate_import(name):
            path.unlink()
            _log.warning("[HANDLER-EVO] Removido %s (falha na importação)", path.name)
            return False

        skill = Skill(
            name=name,
            version=f"v1_gen{self.generation}",
            description=f"Handler evoluído via {name.split('_evo_')[1] if '_evo_' in name else 'crossover'}",
            inputs=["memory", "task"],
            outputs=["output"],
            execution_policy=ExecutionPolicy.SINGLE_RUN,
            tags=["evolved", f"gen{self.generation}"],
        )
        dynamic_registry.register_dynamic(
            skill, template_type="evolved", template_prompt=""
        )

        node = Node(
            name=name,
            run=None,
            strategy="general",
            node_type="evolved_handler",
        )
        self.graph.nodes[name] = node
        _log.info("[HANDLER-EVO] Registrado: %s (gen=%d)", name, self.generation)
        return True

    # ------------------------------------------------------------------
    # Main evolve method
    # ------------------------------------------------------------------

    def evolve(self) -> Dict[str, Any]:
        """Main evolution cycle for handlers.

        Returns stats dict with counts of mutations, crossovers, and registrations.
        """
        parents = self._select_parents()
        stats: Dict[str, Any] = {
            "eligible": len(self._evo_nodes),
            "parents": len(parents),
            "mutations": 0,
            "crossovers": 0,
            "registered": 0,
            "errors": 0,
        }

        if not parents:
            _log.info("[HANDLER-EVO] Nenhum handler elegível para evolução")
            return stats

        # ── Mutation phase ──────────────────────────────────────────────
        for name, node in parents:
            source = _load_handler_source(name)
            if source is None:
                continue
            result = self._mutate_handler(name, source)
            if result is None:
                continue
            new_name, new_source = result
            stats["mutations"] += 1
            if self._register_handler(new_name, new_source):
                stats["registered"] += 1
            else:
                stats["errors"] += 1

        # ── Crossover phase ─────────────────────────────────────────────
        if len(parents) >= 2:
            shuffled = list(parents)
            self._rng.shuffle(shuffled)
            pairs = min(MAX_HYBRIDS_PER_CYCLE, len(shuffled) // 2)
            for i in range(pairs):
                a_name, _ = shuffled[i * 2]
                b_name, _ = shuffled[i * 2 + 1]
                src_a = _load_handler_source(a_name)
                src_b = _load_handler_source(b_name)
                if src_a is None or src_b is None:
                    continue
                result = self._crossover_handlers((a_name, src_a), (b_name, src_b))
                if result is None:
                    continue
                new_name, new_source = result
                stats["crossovers"] += 1
                if self._register_handler(new_name, new_source):
                    stats["registered"] += 1
                    stats["registered"] += 1
                else:
                    stats["errors"] += 1

        _log.info(
            "[HANDLER-EVO] Ciclo: eleg=%d pais=%d mut=%d cx=%d reg=%d err=%d",
            stats["eligible"],
            stats["parents"],
            stats["mutations"],
            stats["crossovers"],
            stats["registered"],
            stats["errors"],
        )
        return stats
