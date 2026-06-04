from secrets import SystemRandom
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set


# =========================================================================
# 0. TaskInfo — structured task with metadata
# =========================================================================

@dataclass
class TaskInfo:
    prompt: str
    generation: int
    constraints: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

    @property
    def has_adversarial(self) -> bool:
        return len(self.constraints) > 0


# =========================================================================
# 1. Multi-criteria output evaluator
# =========================================================================

def evaluate_output(output: str, expected: str) -> Dict[str, float]:
    scores = {}

    correctness = 0.0
    exp_tokens = set(expected.lower().split())
    out_tokens = set(output.lower().split())
    if exp_tokens:
        intersection = exp_tokens & out_tokens
        correctness = len(intersection) / len(exp_tokens)
    scores["correctness"] = correctness

    security = 1.0
    security_bad = {"sql injection", "eval(", "exec(", "password plaintext",
                    "select * from", "drop table", "union select"}
    out_lower = output.lower()
    matches = sum(1 for pat in security_bad if pat in out_lower)
    security = max(0.0, 1.0 - (matches * 0.25))
    scores["security"] = security

    performance = 1.0
    perf_bad = {"for", "while", "recursion", "n+1", "n+1 query", "select n+1"}
    matches = sum(1 for pat in perf_bad if pat in out_lower)
    performance = max(0.0, 1.0 - (matches * 0.20))
    scores["performance"] = performance

    structure = 0.0
    for keyword in ["def ", "class ", "return", "import", "from "]:
        if keyword in output:
            structure += 0.2
    scores["structure"] = min(structure, 1.0)

    mean_score = sum(scores.values()) / len(scores)
    return {**scores, "mean": mean_score}


# =========================================================================
# 2. Dynamic Adversarial Environment
# =========================================================================

ERROR_TYPES = [
    "security_owasp",
    "performance_issue",
    "sql_injection",
    "race_condition",
    "insecure_design",
    "bad_practice",
    "memory_leak",
    "xss_vulnerability",
]

TASK_TEMPLATES = [
    "criar funcao de autenticacao segura",
    "implementar consulta ao banco de dados",
    "criar rota REST para listar usuarios",
    "implementar funcao de login com validacao",
    "criar funcao de cache para consultas frequentes",
    "implementar validacao de entrada de usuario",
    "criar middleware de logging e monitoramento",
    "implementar funcao de busca com filtros",
]


class DynamicAdversarialEnvironment:
    def __init__(self, seed: int = 0):
        self.generation = 0
        self.active_errors: List[str] = []
        self.rng = SystemRandom()

    def next_generation(self) -> TaskInfo:
        self.generation += 1
        if self.generation % 2 == 0 and len(self.active_errors) < len(ERROR_TYPES):
            new_error = ERROR_TYPES[len(self.active_errors)]
            self.active_errors.append(new_error)

        prompt = self.rng.choice(TASK_TEMPLATES)
        return TaskInfo(
            prompt=prompt,
            generation=self.generation,
            constraints=list(self.active_errors),
            tags={"adversarial"} if self.active_errors else {"neutral"},
        )

    @property
    def adversarial_pressure(self) -> float:
        return len(self.active_errors) / len(ERROR_TYPES)


# =========================================================================
# 3. Evolution Metrics
# =========================================================================

@dataclass
class GenerationSnapshot:
    gen: int
    fitness_values: List[float]
    population_size: int
    diversity: float
    error_count: int

    @property
    def mean_fitness(self) -> float:
        return sum(self.fitness_values) / len(self.fitness_values) if self.fitness_values else 0.0

    @property
    def variance(self) -> float:
        if len(self.fitness_values) < 2:
            return 0.0
        mean = self.mean_fitness
        return sum((f - mean) ** 2 for f in self.fitness_values) / len(self.fitness_values)


@dataclass
class EvolutionMetrics:
    snapshots: List[GenerationSnapshot] = field(default_factory=list)

    def record(self, snapshot: GenerationSnapshot) -> None:
        self.snapshots.append(snapshot)

    @property
    def generations(self) -> int:
        return len(self.snapshots)

    def mean_fitness_trend(self) -> List[float]:
        return [s.mean_fitness for s in self.snapshots]

    def is_strictly_improving(self, window: int = 2) -> bool:
        if len(self.snapshots) < window + 1:
            return True
        recent = self.mean_fitness_trend()[-window-1:]
        return all(recent[i] <= recent[i+1] + 1e-6 for i in range(len(recent) - 1))

    def cumulative_gain(self) -> float:
        if len(self.snapshots) < 2:
            return 0.0
        first = self.snapshots[0].mean_fitness
        last = self.snapshots[-1].mean_fitness
        return (last - first) / (first + 1e-10)

    def diversity_trend(self) -> List[float]:
        return [s.diversity for s in self.snapshots]

    def diversity_collapsed(self, threshold: float = 0.01) -> bool:
        return any(d < threshold for d in self.diversity_trend())

    def convergence_rate(self) -> float:
        if len(self.snapshots) < 3:
            return 0.0
        variances = [s.variance for s in self.snapshots]
        first, last = variances[0], variances[-1]
        return (first - last) / (first + 1e-10)


# =========================================================================
# 4. Adversarial task generator
# =========================================================================

def generate_adversarial_task(difficulty: float = 0.5) -> str:
    tasks = [
        "implementar sistema de auth com requisitos contraditorios: nao pode usar banco nem token JWT",
        "criar funcao que le e escreve no mesmo arquivo simultaneamente sem lock",
        "implementar busca que retorne todos os resultados mas nunca use mais que 1KB de memoria",
        "criar rota REST que aceite qualquer input mas seja 100% imune a SQL injection e XSS",
        "implementar cache que nunca expire mas sempre retorne dados atualizados",
        "criar funcao de validacao que aceite tudo mas rejeite tudo",
    ]
    idx = min(int(difficulty * len(tasks)), len(tasks) - 1)
    return tasks[idx]


# =========================================================================
# 5. Invariant validators
# =========================================================================

def check_survivor_fitness_invariant(engine, survivors: list, eliminated: list) -> bool:
    if not survivors or not eliminated:
        return True
    avg_survivor = sum(n.fitness() for n in survivors) / len(survivors)
    avg_eliminated = sum(n.fitness() for n in eliminated) / len(eliminated)
    return avg_survivor >= avg_eliminated - 1e-6


def check_diversity_invariant(graph_or_nodes, threshold: float = 0.05) -> bool:
    nodes = graph_or_nodes
    if hasattr(nodes, "nodes"):
        nodes = list(nodes.nodes.values())
    elif hasattr(nodes, "values"):
        nodes = list(nodes.values())
    strategies = {}
    for node in nodes:
        s = node.strategy
        strategies[s] = strategies.get(s, 0) + 1
    if len(strategies) <= 1:
        return False
    max_strat = max(strategies.values())
    total = sum(strategies.values())
    return (max_strat / total) < (1.0 - threshold)


def check_crossover_invariant(graph) -> Tuple[bool, List[str]]:
    invalids = []
    for name, node in graph.nodes.items():
        if "_x_" in name:
            if not node.depends_on:
                continue
            for dep in node.depends_on:
                if dep not in graph.nodes:
                    invalids.append(f"{name}: depends_on {dep} not found")
    return (len(invalids) == 0, invalids)


# =========================================================================
# 6. Simulation Recorder
# =========================================================================

@dataclass
class SimulationRecord:
    generation: int
    evo_count: int
    mutant_count: int
    hybrid_count: int
    core_count: int
    mean_fitness: float
    strategy_diversity: float
    node_names: List[str]


class SimulationRecorder:
    def __init__(self):
        self.records: List[SimulationRecord] = []

    def record(self, graph, engine, fitness_values: List[float]) -> SimulationRecord:
        rec = SimulationRecord(
            generation=engine.generation,
            evo_count=len([n for n in graph.nodes if n.startswith("evo_")]),
            mutant_count=len([n for n in graph.nodes if "_mut_" in n]),
            hybrid_count=len([n for n in graph.nodes if "_x_" in n]),
            core_count=len([n for n in graph.nodes if n in engine.CORE_NODE_NAMES]),
            mean_fitness=sum(fitness_values) / len(fitness_values) if fitness_values else 0.0,
            strategy_diversity=len(set(
                graph.nodes[n].strategy for n in graph.nodes if n.startswith("evo_")
            )),
            node_names=sorted(graph.nodes.keys()),
        )
        self.records.append(rec)
        return rec

    def snapshot(self) -> Dict:
        if not self.records:
            return {}
        last = self.records[-1]
        return {
            "generation": last.generation,
            "evo_count": last.evo_count,
            "mutants": last.mutant_count,
            "crossovers": last.hybrid_count,
            "core_count": last.core_count,
            "mean_fitness": round(last.mean_fitness, 4),
            "strategy_diversity": last.strategy_diversity,
        }

    def detect_regression(self, reference: Dict) -> List[str]:
        current = self.snapshot()
        issues = []
        for key in ("evo_count", "mutants", "crossovers", "core_count"):
            if current.get(key, 0) < reference.get(key, 0):
                issues.append(f"{key}: {reference.get(key)} -> {current.get(key)}")
        return issues


# =========================================================================
# 7. Graph snapshot and structural distance
# =========================================================================

def snapshot_graph(graph) -> Dict:
    return {
        "node_names": sorted(graph.nodes.keys()),
        "strategies": {n: graph.nodes[n].strategy for n in graph.nodes},
        "evo_count": len([n for n in graph.nodes if n.startswith("evo_")]),
        "mutant_count": len([n for n in graph.nodes if "_mut_" in n]),
        "hybrid_count": len([n for n in graph.nodes if "_x_" in n]),
        "core_count": len([n for n in graph.nodes if hasattr(graph.nodes[n], "node_type") and not n.startswith("evo_")]),
    }


def structural_distance(before: Dict, after: Dict) -> float:
    changes = 0.0
    if before.get("evo_count", 0) != after.get("evo_count", 0):
        changes += 1.0
    if before.get("mutant_count", 0) != after.get("mutant_count", 0):
        changes += 1.0
    if before.get("hybrid_count", 0) != after.get("hybrid_count", 0):
        changes += 1.0
    before_strats = set(before.get("strategies", {}).values())
    after_strats = set(after.get("strategies", {}).values())
    if before_strats != after_strats:
        changes += 0.5
    return changes


# =========================================================================
# 8. Trend analysis
# =========================================================================

def trend(scores: List[float]) -> float:
    if len(scores) < 2:
        return 0.0
    n = len(scores)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(scores) / n
    num = sum((xs[i] - mean_x) * (scores[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


# =========================================================================
# 9. Invariant classifiers
# =========================================================================

def check_hard_invariants(graph) -> List[str]:
    violations = []
    core_expected = {
        "prompt_intake", "enhancement", "orchestrator_agent",
        "pm", "requirements", "architect", "search", "knowledge",
        "dependency", "risk_analysis", "security_design",
        "performance_design", "planner", "coder", "reviewer",
        "semantic_validator", "security_audit", "performance_audit",
        "tester", "debug_coder", "documentation", "release",
        "metrics", "optimization", "result_agent",
    }
    for name in core_expected:
        if name not in graph.nodes:
            violations.append(f"core node '{name}' missing")
    return violations


def check_soft_invariants(graph, threshold: float = 0.05) -> List[str]:
    warnings = []
    evo_nodes = [n for n in graph.nodes.values() if n.name.startswith("evo_")]
    if len(evo_nodes) <= 1:
        warnings.append("population too small for diversity check")
    else:
        strategies = {}
        for n in evo_nodes:
            strategies[n.strategy] = strategies.get(n.strategy, 0) + 1
        max_strat = max(strategies.values())
        if (max_strat / len(evo_nodes)) > (1.0 - threshold):
            warnings.append("diversity below threshold")
    return warnings


def check_trend_invariant(scores: List[float]) -> bool:
    if len(scores) < 3:
        return True
    slope = trend(scores)
    return slope >= -0.01
