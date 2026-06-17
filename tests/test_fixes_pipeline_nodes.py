# test_fixes_pipeline_nodes.py

"""
test_fixes_pipeline_nodes.py — Geração 3
═══════════════════════════════════════════════════════════════════════════════
Fixes desta geração sobre a Geração 2:

  ✦ CRÍTICO: NodeScheduler com triplo fallback no claim()
      node_id → node_name → str(node_id)
      Resolve o falso deadlock com 8 nós raiz bloqueados
  ✦ CRÍTICO: init_execution_robust() registra AMBOS node_id e node_name
  ✦ DeadlockDetector distingue DEADLOCK_REAL de CLAIM_STARVATION
  ✦ Claim starvation tem retry com backoff antes de falhar
  ✦ Logs confirmam qual identificador o registry aceita (diagnóstico vivo)
  ✦ Todas as demais melhorias da Geração 2 mantidas
  
  Resultado:
  
    PipelineCLI (entrypoint + argparse + exit-code)
        └── DebugGraphRunner (orquestrador, substitui debug_async_run)
                ├── _AsyncBridge       (abstração sync/async unificada)
                ├── CheckpointRestorer (restaurar estado salvo)
                └── NodeScheduler      (ready-nodes + deadlock diagnosis)
                        └── _patched_graph (context-manager para monkey-patch seguro)
  
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("pipeline.debug")

NodeResults = Dict[str, Dict[str, Any]]


@dataclass
class RunConfig:
    task: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_timeout: float = 120.0
    claim_retries: int = 3
    claim_retry_delay: float = 0.5


@dataclass
class PipelineOutcome:
    nodes_executed: int
    nodes_failed: int
    final_output_len: int
    elapsed_seconds: float
    execution_id: str
    success: bool


# ──────────────────────────────────────────────────────────────────────────────
# _AsyncBridge
# ──────────────────────────────────────────────────────────────────────────────

class _AsyncBridge:
    @staticmethod
    async def call(func, *args, **kwargs) -> Any:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return await asyncio.to_thread(func, *args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# CheckpointRestorer
# ──────────────────────────────────────────────────────────────────────────────

class CheckpointRestorer:
    def __init__(self, checkpoint_db, exec_registry, bridge: _AsyncBridge):
        self._db = checkpoint_db
        self._registry = exec_registry
        self._bridge = bridge

    async def restore(self, execution_id: str, results: NodeResults, executed: Set[str]) -> None:
        checkpoint = await self._bridge.call(self._db.get_checkpoint, execution_id)
        if not checkpoint:
            log.debug("checkpoint.not_found", extra={"execution_id": execution_id})
            return

        log.info("checkpoint.restored", extra={"execution_id": execution_id, "nodes": len(checkpoint)})
        for node_name, state in checkpoint.items():
            results[node_name] = {
                "output": state.get("result_data"),
                "status": "COMPLETED",
                "success": True,
            }
            executed.add(node_name)
            await self._bridge.call(self._registry.complete_node, execution_id, node_name)


# ──────────────────────────────────────────────────────────────────────────────
# NodeScheduler com triplo fallback no claim()
# ──────────────────────────────────────────────────────────────────────────────

class NodeScheduler:
    """
    Versão corrigida: claim() com fallback node_id → node_name → str(node_id).

    O bug original: após canonicalize(), node.node_id pode divergir do
    identificador registrado em init_execution(). O fallback garante que
    pelo menos um dos identificadores seja aceito, e loga qual venceu
    para diagnóstico permanente.
    """

    @staticmethod
    def pending_blocked(nodes, executed: Set[str]) -> Dict[str, Set[str]]:
        return {
            name: set(node.depends_on) - executed
            for name, node in nodes.items()
            if name not in executed
        }

    @staticmethod
    def diagnose_deadlock(pending_blocked: Dict[str, Set[str]]) -> str:
        lines = ["Deadlock REAL. Nós com dependências insatisfeitas:"]
        for name, missing in pending_blocked.items():
            if missing:
                lines.append(f"  • {name} aguarda: {sorted(missing)}")
        return "\n".join(lines)

    @staticmethod
    async def ready_nodes(
        nodes,
        executed: Set[str],
        execution_id: str,
        exec_registry,
        bridge: _AsyncBridge,
    ) -> List[Tuple[str, Any]]:
        ready = []
        claim_failures = []

        for name, node in nodes.items():
            if name in executed:
                continue
            if not all(dep in executed for dep in node.depends_on):
                continue

            claimed, winning_id = await NodeScheduler._claim_with_fallback(
                exec_registry, bridge, execution_id, node, name
            )

            if claimed:
                log.debug("claim.ok", extra={"node": name, "via": winning_id})
                ready.append((name, node))
            else:
                claim_failures.append(name)

        if claim_failures:
            log.warning(
                "claim.starvation",
                extra={
                    "nodes": claim_failures,
                    "hint": "claim() retornou False para nós prontos — possível mismatch de node_id",
                },
            )

        return ready

    @staticmethod
    async def _claim_with_fallback(
        exec_registry,
        bridge: _AsyncBridge,
        execution_id: str,
        node,
        node_name: str,
    ) -> Tuple[bool, Optional[str]]:
        node_id = getattr(node, "node_id", None)

        # Monta candidatos sem duplicatas, mantendo ordem de preferência
        seen: Set[Any] = set()
        candidates: List[Tuple[str, Any]] = []

        for label, val in [
            ("node_id",      node_id),
            ("node_name",    node_name),
            ("str(node_id)", str(node_id) if node_id is not None else None),
        ]:
            if val is not None and val not in seen:
                candidates.append((label, val))
                seen.add(val)

        for label, identifier in candidates:
            try:
                result = await bridge.call(exec_registry.claim, execution_id, identifier)
                if result:
                    if label != "node_id":
                        log.warning(
                            "claim.id_mismatch_fixed",
                            extra={
                                "node": node_name,
                                "node_id": str(node_id)[:60],
                                "succeeded_via": label,
                                "winning_value": str(identifier)[:60],
                                "action": "Corrija init_execution para registrar com node_name",
                            },
                        )
                    return True, label
            except Exception as exc:
                log.debug("claim.attempt_exc", extra={"node": node_name, "via": label, "error": str(exc)})

        return False, None

    @staticmethod
    def classify_stall(nodes, executed: Set[str]) -> str:
        """
        COMPLETED          → todos executados
        DEADLOCK_REAL      → nós pendentes bloqueados por deps não-satisfeitas
        CLAIM_STARVATION   → nós prontos por deps mas claim() falha para todos
        """
        pending = {n: node for n, node in nodes.items() if n not in executed}
        if not pending:
            return "COMPLETED"

        ready_by_deps = [
            n for n, node in pending.items()
            if all(dep in executed for dep in node.depends_on)
        ]

        return "CLAIM_STARVATION" if ready_by_deps else "DEADLOCK_REAL"


# ──────────────────────────────────────────────────────────────────────────────
# init_execution robusto: registra node_id E node_name
# ──────────────────────────────────────────────────────────────────────────────

async def _init_execution_robust(
    bridge: _AsyncBridge,
    exec_registry,
    execution_id: str,
    nodes: dict,
) -> None:
    """
    Registra cada nó com todos os identificadores possíveis:
      node_id, node_name, str(node_id)

    Garante que claim() funcione independentemente de qual convenção
    o registry usa internamente.
    """
    seen: Set[Any] = set()
    all_ids: List[Any] = []

    for name, node in nodes.items():
        node_id = getattr(node, "node_id", None)
        for val in [node_id, name, str(node_id) if node_id is not None else None]:
            if val is not None and val not in seen:
                all_ids.append(val)
                seen.add(val)

    log.debug(
        "init_execution.ids_registered",
        extra={"execution_id": execution_id, "count": len(all_ids), "sample": all_ids[:8]},
    )

    try:
        await bridge.call(exec_registry.init_execution, execution_id, all_ids)
    except TypeError:
        # Fallback: registry só aceita node_ids originais
        log.warning("init_execution.fallback_node_ids_only", extra={"execution_id": execution_id})
        node_ids = [getattr(n, "node_id", name) for name, n in nodes.items()]
        await bridge.call(exec_registry.init_execution, execution_id, node_ids)


# ──────────────────────────────────────────────────────────────────────────────
# DebugGraphRunner — Geração 3
# ──────────────────────────────────────────────────────────────────────────────

class DebugGraphRunner:
    def __init__(self, checkpoint_db, exec_registry, node_timeout: float = 120.0,
                 claim_retries: int = 3, claim_retry_delay: float = 0.5):
        self._bridge = _AsyncBridge()
        self._restorer = CheckpointRestorer(checkpoint_db, exec_registry, self._bridge)
        self._registry = exec_registry
        self._timeout = node_timeout
        self._claim_retries = claim_retries
        self._claim_retry_delay = claim_retry_delay

    async def run(self, graph, input_data: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        from iaglobal.evolution.canonical_graph import canonicalize

        input_data.setdefault("metadata", {})["execution_id"] = execution_id
        graph.nodes = canonicalize(graph.nodes)
        total_nodes = len(graph.nodes)

        log.info("graph.start", extra={"execution_id": execution_id, "total_nodes": total_nodes})

        # CRÍTICO: usa init robusto com node_id + node_name
        await _init_execution_robust(self._bridge, self._registry, execution_id, graph.nodes)

        graph.results: NodeResults = {}
        executed: Set[str] = set()
        failed_count = 0

        await self._restorer.restore(execution_id, graph.results, executed)

        start_time = time.monotonic()
        iteration = 0
        consecutive_stalls = 0

        while len(executed) < total_nodes:
            iteration += 1

            ready = await NodeScheduler.ready_nodes(
                graph.nodes, executed, execution_id, self._registry, self._bridge
            )

            log.debug(
                "scheduler.tick",
                extra={
                    "iteration": iteration,
                    "executed": len(executed),
                    "total": total_nodes,
                    "ready": [n for n, _ in ready],
                },
            )

            if not ready:
                condition = NodeScheduler.classify_stall(graph.nodes, executed)

                if condition == "COMPLETED":
                    break

                if condition == "CLAIM_STARVATION":
                    consecutive_stalls += 1
                    if consecutive_stalls <= self._claim_retries:
                        delay = self._claim_retry_delay * consecutive_stalls
                        log.warning(
                            "starvation.retry",
                            extra={
                                "attempt": consecutive_stalls,
                                "max": self._claim_retries,
                                "delay_s": delay,
                                "execution_id": execution_id,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Starvation persistente após retries → falha informativa
                        stalled_nodes = [
                            name for name, node in graph.nodes.items()
                            if name not in executed
                            and all(dep in executed for dep in node.depends_on)
                        ]
                        raise RuntimeError(
                            f"Claim starvation persistente após {self._claim_retries} retries.\n"
                            f"execution_id={execution_id}\n"
                            f"Nós prontos mas não reclamados: {stalled_nodes}\n"
                            f"Verifique se exec_registry.init_execution() aceita node_name como identificador."
                        )

                if condition == "DEADLOCK_REAL":
                    blocked = NodeScheduler.pending_blocked(graph.nodes, executed)
                    # Filtra apenas os que têm deps realmente pendentes
                    truly_blocked = {k: v for k, v in blocked.items() if v}
                    msg = NodeScheduler.diagnose_deadlock(truly_blocked)
                    log.critical("deadlock.real", extra={"execution_id": execution_id, "detail": msg})
                    raise RuntimeError(f"Deadlock real — {execution_id}\n{msg}")

            consecutive_stalls = 0  # reset ao progredir

            tasks = [
                asyncio.wait_for(
                    graph._execute_node_async(node, input_data),
                    timeout=self._timeout,
                )
                for _, node in ready
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (name, node), result in zip(ready, results):
                if isinstance(result, asyncio.TimeoutError):
                    result = TimeoutError(f"Nó '{name}' excedeu {self._timeout}s")

                if isinstance(result, Exception):
                    failed_count += 1
                    error_msg = str(result)
                    log.error("node.failed", extra={"node": name, "error": error_msg[:200]})
                    await self._safe_checkpoint(execution_id, name, "FAILED", error_msg)
                    if getattr(node, "critical", False):
                        await graph._abort_dependent_nodes_async(execution_id, name, error_msg)
                else:
                    if result.get("success"):
                        graph.results[name] = result
                        log.info("node.completed", extra={"node": name})
                        await self._safe_checkpoint(execution_id, name, "COMPLETED")
                    else:
                        failed_count += 1
                        error_msg = str(result.get("error", "Execution Failed"))
                        log.error("node.failed", extra={"node": name, "error": error_msg[:200]})
                        await self._safe_checkpoint(execution_id, name, "FAILED", error_msg)
                        if getattr(node, "critical", False):
                            await graph._abort_dependent_nodes_async(execution_id, name, error_msg)

                executed.add(name)

        elapsed = time.monotonic() - start_time
        log.info(
            "graph.completed",
            extra={
                "execution_id": execution_id,
                "iterations": iteration,
                "executed": len(executed),
                "failed": failed_count,
                "elapsed_s": round(elapsed, 3),
            },
        )

        raw = graph._aggregate(elapsed, execution_id)
        raw["_meta"] = {
            "nodes_failed": failed_count,
            "elapsed_seconds": round(elapsed, 3),
            "iterations": iteration,
        }
        return raw

    async def _safe_checkpoint(self, execution_id, name, status, error_msg=None):
        try:
            from iaglobal.memory.db_manager import db as checkpoint_db
            kwargs = {"error_message": error_msg} if error_msg else {}
            await self._bridge.call(
                checkpoint_db.update_node_status, execution_id, name, status, **kwargs
            )
        except Exception as exc:
            log.warning("checkpoint.update_failed", extra={"node": name, "error": str(exc)})


# ──────────────────────────────────────────────────────────────────────────────
# Context manager para monkey-patch seguro
# ──────────────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def _patched_graph(runner: DebugGraphRunner):
    from iaglobal.graphs.execution_graph import ExecutionGraph

    original = ExecutionGraph.async_run

    async def _debug_run(self, input_data, execution_id=None):
        execution_id = execution_id or str(uuid.uuid4())
        return await runner.run(self, input_data, execution_id)

    ExecutionGraph.async_run = _debug_run
    try:
        yield
    finally:
        ExecutionGraph.async_run = original
        log.debug("monkey_patch.restored")


# ──────────────────────────────────────────────────────────────────────────────
# PipelineCLI
# ──────────────────────────────────────────────────────────────────────────────

class PipelineCLI:
    DEFAULT_TASK = "crie em php um blog com tema escuro para receitas de cozinha"

    @classmethod
    def parse_args(cls) -> RunConfig:
        parser = argparse.ArgumentParser(description="Debug runner iaglobal — Geração 3")
        parser.add_argument("--task", default=cls.DEFAULT_TASK)
        parser.add_argument("--execution-id", default=f"debug-gen3-{uuid.uuid4().hex[:8]}", dest="execution_id")
        parser.add_argument("--timeout", type=float, default=120.0)
        parser.add_argument("--claim-retries", type=int, default=3, dest="claim_retries")
        parser.add_argument("--claim-retry-delay", type=float, default=0.5, dest="claim_retry_delay")
        args = parser.parse_args()
        return RunConfig(
            task=args.task,
            execution_id=args.execution_id,
            node_timeout=args.timeout,
            claim_retries=args.claim_retries,
            claim_retry_delay=args.claim_retry_delay,
        )

    @classmethod
    async def run(cls, cfg: RunConfig) -> PipelineOutcome:
        from iaglobal.evolution.execution_registry import registry as exec_registry
        from iaglobal.graphs.builder import build_pipeline_from_nodes
        from iaglobal.memory.db_manager import db as checkpoint_db

        log.info("pipeline.start", extra={
            "task": cfg.task[:80],
            "execution_id": cfg.execution_id,
            "node_timeout": cfg.node_timeout,
            "claim_retries": cfg.claim_retries,
        })

        runner = DebugGraphRunner(
            checkpoint_db=checkpoint_db,
            exec_registry=exec_registry,
            node_timeout=cfg.node_timeout,
            claim_retries=cfg.claim_retries,
            claim_retry_delay=cfg.claim_retry_delay,
        )

        graph = build_pipeline_from_nodes(None)
        t0 = time.monotonic()

        with _patched_graph(runner):
            raw_result = await graph.async_run(
                {"task": cfg.task},
                execution_id=cfg.execution_id,
            )

        meta = raw_result.get("_meta", {})
        outcome = PipelineOutcome(
            nodes_executed=raw_result.get("nodes_executed", 0),
            nodes_failed=meta.get("nodes_failed", 0),
            final_output_len=len(raw_result.get("final_output", "")),
            elapsed_seconds=meta.get("elapsed_seconds", round(time.monotonic() - t0, 3)),
            execution_id=cfg.execution_id,
            success=meta.get("nodes_failed", 0) == 0,
        )

        log.info("pipeline.outcome", extra={
            "nodes_executed": outcome.nodes_executed,
            "nodes_failed": outcome.nodes_failed,
            "final_output_len": outcome.final_output_len,
            "elapsed_s": outcome.elapsed_seconds,
            "success": outcome.success,
        })
        return outcome


async def _main() -> int:
    cfg = PipelineCLI.parse_args()
    try:
        outcome = await PipelineCLI.run(cfg)
        return 0 if outcome.success else 1
    except Exception as exc:
        log.exception("pipeline.fatal_error", extra={"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
