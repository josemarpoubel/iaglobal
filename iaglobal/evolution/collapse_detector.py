"""
Formal Collapse Detector for evolutionary populations.

Monitors multiple indicators simultaneously and produces a structured
CollapseReport with per-indicator scores, overall verdict, and actionable
warnings.

Indicators:
  - Strategy entropy (Shannon): low entropy = strategy collapse
  - Fitness variance: low variance = population homogeneity
  - Fitness stagnation: generations without mean fitness improvement
  - Population size: below minimum viable threshold
  - Genetic diversity: ratio of unique node_ids / total evo nodes
  - Premature convergence: variance drops too fast in early generations
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from iaglobal.utils.logger import logger


# =========================================================================
# 1. CollapseIndicator — single indicator result
# =========================================================================


@dataclass
class CollapseIndicator:
    name: str
    score: float  # 0.0 (collapsed) to 1.0 (healthy)
    threshold: float  # minimum acceptable score
    value: float  # raw measured value
    message: str = ""  # human-readable explanation

    @property
    def collapsed(self) -> bool:
        return self.score < self.threshold


# =========================================================================
# 2. CollapseReport — full diagnostic
# =========================================================================


@dataclass
class CollapseReport:
    generation: int
    evo_count: int
    overall_score: float  # weighted average of all indicators
    indicators: List[CollapseIndicator] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def collapsed(self) -> bool:
        return self.overall_score < 0.5

    @property
    def collapsed_indicators(self) -> List[CollapseIndicator]:
        return [i for i in self.indicators if i.collapsed]

    def summary(self) -> str:
        lines = [f"=== Collapse Report (gen {self.generation}) ==="]
        lines.append(f"  Population: {self.evo_count} EVO nodes")
        lines.append(
            f"  Overall: {'⚠️  COLLAPSED' if self.collapsed else '✅  Healthy'} (score={self.overall_score:.3f})"
        )
        lines.append("")
        for ind in self.indicators:
            icon = "❌" if ind.collapsed else "✅"
            lines.append(
                f"  {icon} {ind.name:25s} score={ind.score:.3f} (threshold={ind.threshold}) | {ind.message}"
            )
        if self.warnings:
            lines.append("")
            for w in self.warnings:
                lines.append(f"  ⚠️  {w}")
        return "\n".join(lines)


# =========================================================================
# 3. CollapseDetector — main detector
# =========================================================================

DEFAULT_THRESHOLDS = {
    "strategy_entropy": 0.40,  # Shannon entropy / log2(n_strategies)
    "fitness_variance": 0.01,  # minimum acceptable variance
    "fitness_stagnation": 5,  # generations without improvement
    "population_size": 2,  # minimum EVO nodes
    "genetic_diversity": 0.15,  # unique node_id ratio
    "premature_convergence": 3,  # early generations to check
}


class CollapseDetector:
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, graph, engine, metrics=None) -> CollapseReport:
        evo_nodes = [
            n for n in graph.nodes.values() if n.name not in engine.CORE_NODE_NAMES
        ]
        evo_count = len(evo_nodes)
        generation = engine.generation

        indicators: List[CollapseIndicator] = []
        warnings: List[str] = []

        # --- 1. Strategy entropy ---
        indicators.append(self._check_strategy_entropy(evo_nodes))

        # --- 2. Fitness variance ---
        indicators.append(self._check_fitness_variance(evo_nodes))

        # --- 3. Fitness stagnation ---
        if metrics is not None and len(metrics.snapshots) >= 2:
            indicators.append(self._check_fitness_stagnation(metrics))
        else:
            indicators.append(
                CollapseIndicator(
                    name="fitness_stagnation",
                    score=1.0,
                    threshold=self.thresholds["fitness_stagnation"],
                    value=0,
                    message="not enough data",
                )
            )

        # --- 4. Population size ---
        indicators.append(self._check_population_size(evo_count))

        # --- 5. Genetic diversity ---
        indicators.append(self._check_genetic_diversity(evo_nodes))

        # --- 6. Premature convergence ---
        if metrics is not None and len(metrics.snapshots) >= 2:
            ind, warn = self._check_premature_convergence(metrics, evo_count)
            indicators.append(ind)
            if warn:
                warnings.append(warn)
        else:
            indicators.append(
                CollapseIndicator(
                    name="premature_convergence",
                    score=1.0,
                    threshold=self.thresholds["premature_convergence"],
                    value=0,
                    message="not enough data",
                )
            )

        # --- Weighted overall score ---
        weights = {
            "strategy_entropy": 0.25,
            "fitness_variance": 0.20,
            "fitness_stagnation": 0.15,
            "population_size": 0.15,
            "genetic_diversity": 0.15,
            "premature_convergence": 0.10,
        }
        overall = sum(ind.score * weights.get(ind.name, 0.15) for ind in indicators)

        report = CollapseReport(
            generation=generation,
            evo_count=evo_count,
            overall_score=overall,
            indicators=indicators,
            warnings=warnings,
        )

        if report.collapsed:
            logger.warning("💥 [COLLAPSE] Populacao colapsou! score=%.3f", overall)
            for ind in report.collapsed_indicators:
                logger.warning(
                    "  ❌ %s: score=%.3f (threshold=%.3f)",
                    ind.name,
                    ind.score,
                    ind.threshold,
                )

        return report

    # ----------------------------------------------------------
    # Individual indicator checks
    # ----------------------------------------------------------

    def _check_strategy_entropy(self, evo_nodes: list) -> CollapseIndicator:
        if not evo_nodes:
            return CollapseIndicator(
                name="strategy_entropy",
                score=0.0,
                threshold=self.thresholds["strategy_entropy"],
                value=0,
                message="no evo nodes",
            )
        counts: Dict[str, int] = {}
        for n in evo_nodes:
            counts[n.strategy] = counts.get(n.strategy, 0) + 1
        total = len(evo_nodes)
        # Shannon entropy
        entropy = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                entropy -= p * math.log2(p)
        # Normalize by log2(number of strategies)
        n_strats = len(counts)
        max_entropy = math.log2(n_strats) if n_strats > 1 else 1.0
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0

        msg = f"{n_strats} strategies, H={entropy:.3f}/{max_entropy:.3f}"
        return CollapseIndicator(
            name="strategy_entropy",
            score=normalized,
            threshold=self.thresholds["strategy_entropy"],
            value=entropy,
            message=msg,
        )

    def _check_fitness_variance(self, evo_nodes: list) -> CollapseIndicator:
        if len(evo_nodes) < 2:
            return CollapseIndicator(
                name="fitness_variance",
                score=1.0,
                threshold=self.thresholds["fitness_variance"],
                value=0,
                message="too few nodes",
            )
        fvals = [n.fitness() for n in evo_nodes]
        mean = sum(fvals) / len(fvals)
        variance = sum((f - mean) ** 2 for f in fvals) / len(fvals)
        # Score: 1.0 at variance=0.1+, scales down linearly
        score = min(1.0, variance / 0.1)
        msg = f"var={variance:.5f}"
        return CollapseIndicator(
            name="fitness_variance",
            score=score,
            threshold=self.thresholds["fitness_variance"],
            value=variance,
            message=msg,
        )

    def _check_fitness_stagnation(self, metrics) -> CollapseIndicator:
        trend = metrics.mean_fitness_trend()
        if len(trend) < 2:
            return CollapseIndicator(
                name="fitness_stagnation",
                score=1.0,
                threshold=self.thresholds["fitness_stagnation"],
                value=0,
                message="not enough data",
            )
        # Count consecutive generations without improvement
        stagnant = 0
        for i in range(len(trend) - 1, 0, -1):
            if trend[i] <= trend[i - 1] + 1e-6:
                stagnant += 1
            else:
                break

        max_stagnant = self.thresholds["fitness_stagnation"]
        score = max(0.0, 1.0 - (stagnant / (max_stagnant * 2)))
        msg = f"{stagnant} gen sem melhoria"
        return CollapseIndicator(
            name="fitness_stagnation",
            score=score,
            threshold=1.0 / (max_stagnant + 1),
            value=stagnant,
            message=msg,
        )

    def _check_population_size(self, evo_count: int) -> CollapseIndicator:
        min_size = self.thresholds["population_size"]
        score = min(1.0, evo_count / (min_size * 3))
        msg = f"{evo_count} EVO nodes (min={min_size})"
        return CollapseIndicator(
            name="population_size",
            score=score,
            threshold=0.3,  # below 30% of ideal = collapsed
            value=evo_count,
            message=msg,
        )

    def _check_genetic_diversity(self, evo_nodes: list) -> CollapseIndicator:
        if not evo_nodes:
            return CollapseIndicator(
                name="genetic_diversity",
                score=0.0,
                threshold=self.thresholds["genetic_diversity"],
                value=0,
                message="no evo nodes",
            )
        unique_ids = len(set(n.node_id for n in evo_nodes))
        ratio = unique_ids / len(evo_nodes) if evo_nodes else 0.0
        msg = f"{unique_ids}/{len(evo_nodes)} unique node_ids"
        return CollapseIndicator(
            name="genetic_diversity",
            score=ratio,
            threshold=self.thresholds["genetic_diversity"],
            value=ratio,
            message=msg,
        )

    def _check_premature_convergence(
        self, metrics, evo_count: int
    ) -> Tuple[CollapseIndicator, Optional[str]]:
        if len(metrics.snapshots) < 3:
            return (
                CollapseIndicator(
                    name="premature_convergence",
                    score=1.0,
                    threshold=self.thresholds["premature_convergence"],
                    value=0,
                    message="not enough data",
                ),
                None,
            )
        # Check first N generations for variance cliff
        early_windows = self.thresholds["premature_convergence"]
        early_snaps = metrics.snapshots[: early_windows + 1]
        if len(early_snaps) < 2:
            return (
                CollapseIndicator(
                    name="premature_convergence",
                    score=1.0,
                    threshold=self.thresholds["premature_convergence"],
                    value=0,
                    message="not enough data",
                ),
                None,
            )
        variances = [s.variance for s in early_snaps]
        first_var = variances[0] if variances else 0.0
        last_var = variances[-1] if variances else 0.0
        if first_var > 0:
            drop_ratio = (first_var - last_var) / first_var
        else:
            drop_ratio = 0.0

        # Healthy convergence: drop between 20-80%. Too fast (< 20% drop or > 80% drop) is bad
        if drop_ratio > 0.8:
            score = max(0.0, 1.0 - drop_ratio)
            warn = f"Variance dropped {drop_ratio * 100:.0f}% in first {early_windows} gens — premature convergence"
        elif drop_ratio < 0.2:
            score = max(0.0, drop_ratio / 0.2)
            warn = None
        else:
            score = 1.0
            warn = None

        msg = f"var drop={drop_ratio * 100:.0f}% in first {early_windows} gens"
        return (
            CollapseIndicator(
                name="premature_convergence",
                score=score,
                threshold=0.5,
                value=drop_ratio,
                message=msg,
            ),
            warn,
        )
