# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
JointOptimizationLoop — Ribossomo do Ciclo Metabólico.

Fecha o loop: execution_metrics → CreditAssignmentEngine (com decay) →
BanditPolicy (ajuste contínuo de pesos) → IVM tracking →
gatilhos de apoptose/mitose na colônia.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.joint_optimization")


@dataclass
class ExecutionSnapshot:
    node: str
    model: str
    success: bool
    latency: float
    cost: float
    timestamp: float = field(default_factory=time.time)


IVM_APOPTOSE_THRESHOLD = 0.3
IVM_MITOSE_THRESHOLD = 0.7
DECAY_FACTOR = 0.95
WINDOW_SIZE = 1000


class JointOptimizationLoop:
    """
    Coleta execution_metrics de todos os nós, recalibra o BanditPolicy
    com aprendizado contínuo, e decide apoptose/mitose na colônia.
    """

    def __init__(self):
        self._snapshots: list[ExecutionSnapshot] = []
        self._node_stats: dict[str, dict] = defaultdict(
            lambda: {
                "success": 0,
                "fail": 0,
                "latency_sum": 0.0,
                "cost_sum": 0.0,
                "count": 0,
                "ivm_history": [],
            }
        )
        self._lock = asyncio.Lock()
        self._last_decay = time.time()
        self._last_sync = 0.0
        self._sync_interval = 60.0
        self._global_ivm = 0.5
        self._colony = None

    def bind_colony(self, colony) -> None:
        self._colony = colony

    async def ingest(
        self,
        node: str,
        success: bool,
        latency: float,
        cost: float = 0.0,
        model: str = "unknown",
    ) -> None:
        snapshot = ExecutionSnapshot(
            node=node,
            model=model,
            success=success,
            latency=latency,
            cost=cost,
        )
        async with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > WINDOW_SIZE:
                self._snapshots.pop(0)

            stats = self._node_stats[node]
            stats["count"] += 1
            if success:
                stats["success"] += 1
            else:
                stats["fail"] += 1
            stats["latency_sum"] += latency
            stats["cost_sum"] += cost

    async def ingest_metrics(self, metrics: dict) -> None:
        node = metrics.get("node") or metrics.get("agente_utilizado", "unknown")
        success = metrics.get("success", False)
        latency = metrics.get("latency", 0.0) or 0.0
        cost = metrics.get("cost", 0.0) or 0.0
        model = metrics.get("model", "unknown") or "unknown"
        await self.ingest(node, success, latency, cost, model)

    @staticmethod
    def _calc_node_ivm_from_stats(stats: dict) -> float:
        total = stats["success"] + stats["fail"]
        if total == 0:
            return 0.5
        productivity = stats["success"] / total
        avg_latency = (
            stats["latency_sum"] / stats["count"] if stats["count"] > 0 else 500.0
        )
        efficiency = max(0.0, 1.0 - min(avg_latency / 10.0, 1.0))
        cooperation = 0.5  # default neutro — stats não têm métricas de cooperação
        return round(
            productivity * 0.4 + efficiency * 0.4 + cooperation * 0.2, 4
        )

    async def get_node_ivm(self, node: str) -> float:
        async with self._lock:
            stats = self._node_stats.get(node)
        if not stats or stats["count"] == 0:
            return 0.5
        return self._calc_node_ivm_from_stats(stats)

    async def get_global_ivm(self) -> float:
        async with self._lock:
            if not self._node_stats:
                return 0.5
            ivms = [
                self._calc_node_ivm_from_stats(stats)
                for stats in self._node_stats.values()
                if stats["count"] > 0
            ]
        if not ivms:
            return 0.5
        return round(sum(ivms) / len(ivms), 4)

    async def sync_bandit_weights(self, bandit, candidates: list[str]) -> None:
        now = time.time()
        if now - self._last_sync < self._sync_interval:
            return
        self._last_sync = now

        if not bandit.credit_engine:
            logger.debug("[JOL] credit_engine ausente — sync ignorado")
            return

        for model in candidates:
            total_success = 0
            total_fail = 0
            total_reward = 0.0
            reward_count = 0

            for (node, mdl, strategy), stats in bandit.credit_engine.stats.items():
                if (
                    mdl == model or model.endswith(mdl.split("/")[-1])
                    if "/" in mdl
                    else mdl == model
                ):
                    total_success += stats["success"]
                    total_fail += stats["fail"]
                    if stats["reward_count"] > 0:
                        total_reward += stats["reward_total"]
                        reward_count += stats["reward_count"]

            total = total_success + total_fail
            if total > 0:
                success_rate = total_success / total
                avg_reward = total_reward / reward_count if reward_count > 0 else 0.0
                new_weight = (success_rate * 0.7) + (avg_reward * 0.3)

                current = bandit.weights.get(model, 0.0)
                smoothed = current * 0.7 + new_weight * 0.3
                old_weight = bandit.weights.get(model, 0.0)
                bandit.weights[model] = smoothed
                if abs(smoothed - old_weight) > 0.01:
                    logger.info(
                        "[JOL] Peso %s: %.4f → %.4f (success=%.2f, reward=%.2f)",
                        model,
                        old_weight,
                        smoothed,
                        success_rate,
                        avg_reward,
                    )

    async def apply_decay(self, credit_engine) -> None:
        now = time.time()
        if now - self._last_decay < 300.0:
            return
        self._last_decay = now

        if not credit_engine:
            return

        for key in list(credit_engine.stats.keys()):
            stats = credit_engine.stats[key]
            total = stats["success"] + stats["fail"]
            if total == 0:
                continue
            stats["success"] = max(1, int(stats["success"] * DECAY_FACTOR))
            stats["fail"] = max(1, int(stats["fail"] * DECAY_FACTOR))
            stats["latency"] *= DECAY_FACTOR
            stats["reward_total"] *= DECAY_FACTOR
            stats["reward_count"] = max(1, int(stats["reward_count"] * DECAY_FACTOR))

        logger.debug(
            "[JOL] Decay aplicado a %d entradas do credit_engine",
            len(credit_engine.stats),
        )

    async def evaluate_colony(self) -> list[dict]:
        decisions = []
        if not self._colony:
            return decisions

        async with self._lock:
            for especializacao, registro in list(self._colony._agentes.items()):
                total = registro.execucoes
                if total < 3:
                    continue
                success_rate = 1.0 - (registro.falhas / total) if total > 0 else 0.0
                ivm = (
                    success_rate * 0.4
                    + max(0.0, 1.0 - min(registro.latencia_media / 10.0, 1.0)) * 0.4
                    + 0.2
                )

                if ivm < IVM_APOPTOSE_THRESHOLD:
                    decisions.append(
                        {
                            "action": "apoptose",
                            "especializacao": especializacao,
                            "ivm": round(ivm, 4),
                            "success_rate": round(success_rate, 4),
                            "execucoes": total,
                        }
                    )
                elif ivm >= IVM_MITOSE_THRESHOLD and total >= 5:
                    decisions.append(
                        {
                            "action": "mitose",
                            "especializacao": especializacao,
                            "ivm": round(ivm, 4),
                            "success_rate": round(success_rate, 4),
                            "execucoes": total,
                        }
                    )

        return decisions

    async def get_colony_report(self) -> dict:
        async with self._lock:
            stats_snapshot = dict(self._node_stats)
            snapshots_copy = list(self._snapshots)

        ranked = sorted(
            [
                {
                    "node": node,
                    "ivm": self._calc_node_ivm_from_stats(stats),
                    "total": stats["count"],
                    "success": stats["success"],
                    "fail": stats["fail"],
                    "avg_latency": round(stats["latency_sum"] / stats["count"], 2)
                    if stats["count"]
                    else 0,
                    "avg_cost": round(stats["cost_sum"] / stats["count"], 4)
                    if stats["count"]
                    else 0,
                }
                for node, stats in stats_snapshot.items()
            ],
            key=lambda x: x["ivm"],
            reverse=True,
        )

        total_snapshots = len(snapshots_copy)
        total_success = sum(1 for s in snapshots_copy if s.success)
        total_fail = total_snapshots - total_success

        return {
            "global_ivm": await self.get_global_ivm(),
            "total_executions": total_snapshots,
            "total_success": total_success,
            "total_fail": total_fail,
            "success_rate": round(total_success / total_snapshots, 4)
            if total_snapshots
            else 0.0,
            "nodes": ranked,
            "avg_latency": round(
                sum(s.latency for s in snapshots_copy) / total_snapshots, 2
            )
            if total_snapshots
            else 0.0,
        }


joint_optimization_loop = JointOptimizationLoop()
