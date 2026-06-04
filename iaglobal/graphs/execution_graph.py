import asyncio
import time
import uuid
import hashlib
import ast
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Set, List, Tuple

from iaglobal.utils.logger import logger

from .node import Node
from .workdir import make_workdir, WorkDir

from iaglobal._paths import CACHE_DB, get_db_connection
from iaglobal.memory.db_manager import db as checkpoint_db
from iaglobal.models.event_bus import bus, EventType
from iaglobal.evolution.execution_registry import registry as exec_registry
from iaglobal.evolution.execution_context import make_context
from iaglobal.evolution.canonical_graph import canonicalize, compute_graph_hash
from iaglobal.evolution.skills.skill_executor import skill_executor, SkillExecutionError
from iaglobal.graphs.artifact import Artifact, SolutionArtifact


class ExecutionGraph:

    MAX_RETRY = 3
    MAX_WORKERS = 4

    def __init__(self, tool_router=None):
        self.tool_router = tool_router
        self.nodes = {}
        self.results = {}
        self._node_cache = {}
        self.generation = 0
        self._graph_hash = ""
        self._results_lock = threading.Lock()

    def add_node(self, node: Node):
        if node.name in self.nodes:
            raise ValueError(f"Node '{node.name}' já existe no grafo")
        # Verifica duplicação por node_id determinístico
        for existing_name, existing_node in self.nodes.items():
            if existing_node.node_id == node.node_id:
                raise ValueError(
                    f"Node '{node.name}' tem node_id duplicado com '{existing_name}' "
                    f"(node_id={node.node_id})"
                )
        self.nodes[node.name] = node
        logger.info(f"➕ Node registrado: {node.name} (node_id={node.node_id})")

    def _execute_node(self, node: Node, input_data: dict) -> dict:
        # 🔒 Node Lock (anti race condition)
        if not node.acquire():
            return {
                "output": None,
                "latency": 0.0,
                "success": False,
                "error": f"Node '{node.name}' já está em execução (lock)",
                "result_text": "",
            }

        start = time.time()

        raw_task = str(input_data.get("task", ""))
        exec_id = str(input_data.get("metadata", {}).get("execution_id", raw_task))

        workdir = make_workdir(node.name, exec_id, raw_task)

        ctx = {
            "input": input_data,
            "memory": self.results,
            "workdir": workdir,
        }

        skill_name = node.node_type if node.node_type != "general" else node.name
        result_text = ""
        result_raw = None
        success = False
        last_error = None
        extra_fields = {}

        try:
            contract_error = None
            executed = False
            node_run_failed = False
            if skill_executor.can_execute(skill_name):
                try:
                    result = skill_executor.execute_with_fallback(skill_name, ctx)
                    if asyncio.iscoroutine(result):
                        with asyncio.Runner() as _runner:
                            result = _runner.run(result)
                    executed = True
                except SkillExecutionError as e:
                    contract_error = str(e)
                    logger.debug("[GRAPH] Contrato da skill '%s' não satisfeito: %s — fallback node.run", skill_name, e)
                    workdir.append_log("contrato insatisfeito: %s — fallback" % str(e)[:80])

            if not executed and node.run:
                try:
                    if asyncio.iscoroutinefunction(node.run):
                        with asyncio.Runner() as _runner:
                            result = _runner.run(node.run(ctx))
                    else:
                        result = node.run(ctx)
                    executed = True
                except Exception:
                    node_run_failed = True
                    raise

            if executed:
                if isinstance(result, dict):
                    result_raw = result.get("output")
                    if hasattr(result_raw, "code"):
                        result_text = result_raw.code or ""
                        extra_fields = {
                            k: v for k, v in result.items() if k != "output"
                        }
                        if "artifact" not in result and result_text:
                            task = getattr(result_raw, "task", "") or str(input_data.get("task", ""))
                            score = getattr(result_raw, "score", 0)
                            extra_fields["artifact"] = Artifact(
                                content=result_text,
                                type="code",
                                metadata={"task": task, "score": score, "node": node.name, "evo": True},
                            )
                    else:
                        result_text = str(result_raw) if result_raw is not None else ""
                        extra_fields = {
                            k: v for k, v in result.items() if k != "output"
                        }
                    if isinstance(result, dict) and result.get("skipped"):
                        logger.info("[GRAPH] Nó '%s' pulado (single-run já executada)", node.name)
                else:
                    result_text = str(result)

            if not result_text and node_run_failed:
                last_error = last_error or "node.run falhou"

            if not result_text and not node_run_failed:
                from iaglobal.providers.provider_config import ProviderConfig
                _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
                model = node.model_hint or f"ollama/{_default_ollama}"
                if self.tool_router:
                    try:
                        task = self.tool_router.resolve(
                            model_type=getattr(node, "model_type", "local"),
                            task=raw_task
                        )
                    except Exception:
                        task = raw_task
                else:
                    task = raw_task

                cache_key = f"{node.name}:{hash(task)}"
                if cache_key in self._node_cache:
                    return {
                        "output": self._node_cache[cache_key],
                        "cached": True,
                        "latency": 0.0,
                        "success": True,
                        "error": None,
                    }

                from iaglobal.providers.provider_router import route_generate as _route
                result_text = _route(
                    model=model,
                    prompt=task,
                    task_type=node.strategy
                )

                if result_text:
                    self._node_cache[cache_key] = result_text

            if result_text:
                success = True
                workdir.write_code(result_text).append_log("executado com sucesso")
            elif contract_error:
                last_error = contract_error

        except Exception as e:
            last_error = str(e)
            result_text = ""
            workdir.append_log("erro: %s" % last_error)

        finally:
            node.release()

        latency = time.time() - start
        node.record(success, latency, last_error)

        return {
            "output": result_raw if result_raw is not None else result_text,
            "latency": latency,
            "success": success,
            "error": last_error,
            "result_text": result_text,
            **extra_fields,
        }

    async def _execute_node_async(self, node: Node, input_data: dict) -> dict:
        if not node.acquire():
            return {"output": None, "latency": 0.0, "success": False,
                    "error": f"Node '{node.name}' já está em execução (lock)", "result_text": ""}

        start = time.time()
        raw_task = str(input_data.get("task", ""))
        exec_id = str(input_data.get("metadata", {}).get("execution_id", raw_task))
        workdir = make_workdir(node.name, exec_id, raw_task)

        ctx = {"input": input_data, "memory": self.results, "workdir": workdir}
        skill_name = node.node_type if node.node_type != "general" else node.name
        result_text = ""
        result_raw = None
        success = False
        last_error = None
        extra_fields = {}

        try:
            contract_error = None
            executed = False
            node_run_failed = False
            if skill_executor.can_execute(skill_name):
                try:
                    result = skill_executor.execute_with_fallback(skill_name, ctx)
                    if asyncio.iscoroutine(result):
                        result = await result
                    executed = True
                except SkillExecutionError as e:
                    contract_error = str(e)
                    await workdir.async_append_log("contrato insatisfeito: %s — fallback" % str(e)[:80])

            if not executed and node.run:
                try:
                    if asyncio.iscoroutinefunction(node.run):
                        result = await node.run(ctx)
                    else:
                        result = await asyncio.to_thread(node.run, ctx)
                    executed = True
                except Exception:
                    node_run_failed = True
                    raise

            if executed:
                if isinstance(result, dict):
                    result_raw = result.get("output")
                    if hasattr(result_raw, "code"):
                        result_text = result_raw.code or ""
                        extra_fields = {k: v for k, v in result.items() if k != "output"}
                        if "artifact" not in result and result_text:
                            task = getattr(result_raw, "task", "") or str(input_data.get("task", ""))
                            score = getattr(result_raw, "score", 0)
                            extra_fields["artifact"] = Artifact(
                                content=result_text, type="code",
                                metadata={"task": task, "score": score, "node": node.name, "evo": True},
                            )
                    else:
                        result_text = str(result_raw) if result_raw is not None else ""
                        extra_fields = {k: v for k, v in result.items() if k != "output"}
                    if isinstance(result, dict) and result.get("skipped"):
                        logger.info("[GRAPH] No '%s' pulado (single-run já executada)", node.name)
                else:
                    result_text = str(result)

            if not result_text and node_run_failed:
                last_error = last_error or "node.run falhou"

            if not result_text and not node_run_failed:
                from iaglobal.providers.provider_config import ProviderConfig
                _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
                model = node.model_hint or f"ollama/{_default_ollama}"
                task = raw_task
                from iaglobal.providers.provider_router import async_route_generate as _async_route
                result_text = await _async_route(model=model, prompt=task, task_type=node.strategy)

            if result_text:
                success = True
                await workdir.async_write_code(result_text)
                await workdir.async_append_log("executado com sucesso")
            elif contract_error:
                last_error = contract_error

        except Exception as e:
            last_error = str(e)
            result_text = ""
            await workdir.async_append_log("erro: %s" % last_error)
        finally:
            node.release()

        latency = time.time() - start
        node.record(success, latency, last_error)

        return {"output": result_raw if result_raw is not None else result_text,
                "latency": latency, "success": success, "error": last_error,
                "result_text": result_text, **extra_fields}

    def _abort_dependent_nodes(
        self, execution_id: str, failed_node_name: str, reason: str
    ):
        dependents = set()
        def _find_dependents(node_name: str):
            for n_name, n_node in self.nodes.items():
                if failed_node_name in n_node.depends_on and n_name not in dependents:
                    dependents.add(n_name)
                    _find_dependents(n_name)
        _find_dependents(failed_node_name)

        for dep_name in dependents:
            logger.warning(f"🛡️ Sanity Barrier: abortando nó '{dep_name}' devido à falha crítica em '{failed_node_name}'")
            self.results[dep_name] = {
                "error": f"Abortado pela Sanity Barrier: nó crítico '{failed_node_name}' falhou",
                "node": dep_name,
                "status": "ABORTED",
                "success": False,
            }
            checkpoint_db.update_node_status(
                execution_id, dep_name, "ABORTED",
                error_message=f"Abortado pela Sanity Barrier: nó crítico '{failed_node_name}' falhou: {reason}"
            )

    def run(
        self,
        input_data: Dict[str, Any],
        execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        # Garante exec_id no metadata para workdir
        if "metadata" not in input_data:
            input_data["metadata"] = {}
        input_data["metadata"]["execution_id"] = execution_id

        task_text = str(input_data.get("task", input_data.get("input", {}).get("task", "")))
        input_data["_task_text"] = task_text

        logger.info(f"🧠 ativando agentes especialistas ...")

        # 🔒 DAG Canonicalization (remove duplicatas, consolida edges, ordena)
        original_count = len(self.nodes)
        self.nodes = canonicalize(self.nodes)

        current_hash = compute_graph_hash(self.nodes)
        if current_hash != self._graph_hash:
            logger.info(f"[GRAPH] Grafo alterado: {self._graph_hash} → {current_hash} ({original_count} → {len(self.nodes)} nós)")
            self._graph_hash = current_hash

        # 🔒 Execution Context (imutável)
        ctx = make_context(
            execution_id=execution_id,
            graph=self.snapshot(),
            seed_version=f"gen_{self.generation}",
            task=task_text,
            metadata=input_data.get("metadata", {}),
        )

        # 🔒 Execution Registry (idempotência)
        node_ids = [n.node_id for n in self.nodes.values()]
        exec_registry.init_execution(execution_id, node_ids)

        self.results = {}
        executed: Set[str] = set()

        checkpoint = checkpoint_db.get_checkpoint(execution_id)

        if not checkpoint and execution_id:
            checkpoint_db.init_execution(execution_id, list(self.nodes.keys()))
            logger.info(f"📝 Novos estados PENDING registrados para {execution_id}")
        elif checkpoint:
            logger.info(f"📦 Checkpoint encontrado: {len(checkpoint)} nós COMPLETED")

        for node_name, state in checkpoint.items():
            self.results[node_name] = {
                "output": state.get("result_data"),
                "status": "COMPLETED",
                "cached": True,
                "success": True,
                "error": None,
            }
            executed.add(node_name)
            exec_registry.complete(execution_id, node_name)
            logger.info(f"⏭️ Pulando nó já COMPLETED: {node_name}")

        start_time = time.time()

        while len(executed) < len(self.nodes):
            ready_nodes = []
            for name, node in self.nodes.items():
                if name in executed:
                    continue
                node_id = node.node_id
                if exec_registry.was_executed(execution_id, node_id):
                    logger.info(f"⏭️ [REGISTRY] Node '{name}' (id={node_id}) já executado — pulando")
                    executed.add(name)
                    continue
                if not all(dep in executed for dep in node.depends_on):
                    continue
                existing = self.results.get(name, {})
                if existing.get("status") == "ABORTED":
                    executed.add(name)
                    continue
                aborted = False
                for dep in node.depends_on:
                    dep_result = self.results.get(dep, {})
                    if dep_result.get("status") == "ABORTED" or (dep_result.get("status") == "FAILED" and self.nodes.get(dep) and self.nodes[dep].critical):
                        self.results[name] = {
                            "error": f"Abortado pela Sanity Barrier: dependência '{dep}' falhou criticamente",
                            "node": name, "status": "ABORTED", "success": False,
                        }
                        checkpoint_db.update_node_status(execution_id, name, "ABORTED",
                            error_message=f"Abortado pela Sanity Barrier: dependência '{dep}' falhou criticamente")
                        exec_registry.skip(execution_id, node_id)
                        executed.add(name)
                        aborted = True
                        break
                if aborted:
                    continue
                retry_count = checkpoint_db.get_node_retry_count(execution_id, name)
                if retry_count >= self.MAX_RETRY:
                    logger.error(f"🚫 Nó '{name}' excedeu limite de retry ({retry_count}). Abortando.")
                    bus.publish(EventType.EXECUTION_ABORTED, {
                        "execution_id": execution_id, "node_id": name,
                        "reason": f"retry_count={retry_count} >= MAX_RETRY={self.MAX_RETRY}"
                    }, source="execution_graph.run")
                    self.results[name] = {"error": f"Max retry ({self.MAX_RETRY}) exceeded", "node": name, "status": "ABORTED"}
                    exec_registry.skip(execution_id, node_id)
                    executed.add(name)
                    continue
                if not exec_registry.claim(execution_id, node_id):
                    logger.info(f"⏭️ [REGISTRY] Node '{name}' não pôde ser reivindicado — pulando")
                    executed.add(name)
                    continue
                ready_nodes.append((name, node, node_id, retry_count))

            if not ready_nodes:
                remaining = set(self.nodes.keys()) - executed
                if not remaining:
                    break
                raise RuntimeError(
                    f"💥 Deadlock no Graph: dependência circular ou node inválido | execution_id={execution_id} | pendentes={remaining}"
                )

            logger.info("🚀 executando %d agente(s) em paralelo ...", len(ready_nodes))
            batch_results = {}
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_map = {}
                for name, node, node_id, retry_count in ready_nodes:
                    logger.info(f"⚙️ Enviando node: {name} | retry={retry_count} | id={node_id}")
                    future = executor.submit(self._execute_node, node, input_data)
                    future_map[future] = (name, node, node_id, retry_count)

                for future in as_completed(future_map):
                    name, node, node_id, retry_count = future_map[future]
                    try:
                        result = future.result()
                        batch_results[name] = (result, node, node_id, retry_count)
                    except Exception as e:
                        logger.error(f"❌ Node '{name}' falhou com exceção: {e}")
                        batch_results[name] = (None, node, node_id, retry_count)

            for name, (result, node, node_id, retry_count) in batch_results.items():
                if result is None:
                    error_msg = f"Exceção na execução concorrente do nó '{name}'"
                    new_retry = retry_count + 1
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    if node.critical:
                        logger.warning(f"🛡️ Sanity Barrier acionada! Nó crítico '{name}' falhou. Abortando dependentes.")
                        self._abort_dependent_nodes(execution_id, name, error_msg)
                        bus.publish(EventType.CRITICAL_NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg, "retry_count": new_retry,
                            "aborted_dependents": [n for n in self.nodes.keys() if name in self.nodes[n].depends_on]
                        }, source="execution_graph.run")
                        bus.publish(EventType.SANITY_BARRIER_TRIGGERED, {
                            "execution_id": execution_id, "failed_node": name,
                            "error": error_msg,
                            "reason": f"Nó crítico '{name}' falhou após {new_retry} tentativa(s)"
                        }, source="execution_graph.run")
                    else:
                        bus.publish(EventType.NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg, "retry_count": new_retry
                        }, source="execution_graph.run")
                    with self._results_lock:
                        self.results[name] = {"error": error_msg, "node": name, "status": "FAILED", "success": False}
                    executed.add(name)
                    continue

                with self._results_lock:
                    self.results[name] = result
                executed.add(name)

                if result.get("success"):
                    checkpoint_db.update_node_status(execution_id, name, "COMPLETED",
                        result_data=str(result.get("output", "")).encode() if result.get("output") else None)
                    exec_registry.complete(execution_id, node_id, result.get("result_text", ""))
                else:
                    error_msg = result.get("error", "Unknown error")
                    new_retry = retry_count + 1
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    if node.critical:
                        logger.warning(f"🛡️ Sanity Barrier acionada! Nó crítico '{name}' falhou. Abortando dependentes.")
                        self._abort_dependent_nodes(execution_id, name, error_msg)
                        bus.publish(EventType.CRITICAL_NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg, "retry_count": new_retry,
                            "aborted_dependents": [n for n in self.nodes.keys() if name in self.nodes[n].depends_on]
                        }, source="execution_graph.run")
                        bus.publish(EventType.SANITY_BARRIER_TRIGGERED, {
                            "execution_id": execution_id, "failed_node": name,
                            "error": error_msg,
                            "reason": f"Nó crítico '{name}' falhou após {new_retry} tentativa(s)"
                        }, source="execution_graph.run")
                    else:
                        bus.publish(EventType.NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg, "retry_count": new_retry
                        }, source="execution_graph.run")

        return self._aggregate(time.time() - start_time, execution_id)

    async def async_run(
        self,
        input_data: Dict[str, Any],
        execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        if "metadata" not in input_data:
            input_data["metadata"] = {}
        input_data["metadata"]["execution_id"] = execution_id

        task_text = str(input_data.get("task", input_data.get("input", {}).get("task", "")))
        input_data["_task_text"] = task_text

        logger.info("🧠 [ASYNC] ativando agentes especialistas ...")

        original_count = len(self.nodes)
        self.nodes = canonicalize(self.nodes)

        current_hash = compute_graph_hash(self.nodes)
        if current_hash != self._graph_hash:
            logger.info("[GRAPH] Grafo alterado: %s -> %s (%d -> %d nos)",
                         self._graph_hash, current_hash, original_count, len(self.nodes))
            self._graph_hash = current_hash

        ctx = make_context(
            execution_id=execution_id,
            graph=self.snapshot(),
            seed_version=f"gen_{self.generation}",
            task=task_text,
            metadata=input_data.get("metadata", {}),
        )

        node_ids = [n.node_id for n in self.nodes.values()]
        exec_registry.init_execution(execution_id, node_ids)

        self.results = {}
        executed: Set[str] = set()

        checkpoint = checkpoint_db.get_checkpoint(execution_id)

        if not checkpoint and execution_id:
            checkpoint_db.init_execution(execution_id, list(self.nodes.keys()))
        elif checkpoint:
            logger.info("[ASYNC] Checkpoint encontrado: %d nos COMPLETED", len(checkpoint))

        for node_name, state in checkpoint.items():
            self.results[node_name] = {"output": state.get("result_data"), "status": "COMPLETED",
                                        "cached": True, "success": True, "error": None}
            executed.add(node_name)
            exec_registry.complete(execution_id, node_name)

        start_time = time.time()

        while len(executed) < len(self.nodes):
            ready_nodes = []
            for name, node in self.nodes.items():
                if name in executed:
                    continue
                node_id = node.node_id
                if exec_registry.was_executed(execution_id, node_id):
                    executed.add(name)
                    continue
                if not all(dep in executed for dep in node.depends_on):
                    continue
                existing = self.results.get(name, {})
                if existing.get("status") == "ABORTED":
                    executed.add(name)
                    continue
                aborted = False
                for dep in node.depends_on:
                    dep_result = self.results.get(dep, {})
                    if dep_result.get("status") == "ABORTED" or (dep_result.get("status") == "FAILED"
                       and self.nodes.get(dep) and self.nodes[dep].critical):
                        self.results[name] = {"error": f"Abortado: dependencia '{dep}' falhou",
                                               "node": name, "status": "ABORTED", "success": False}
                        checkpoint_db.update_node_status(execution_id, name, "ABORTED",
                            error_message=f"Abortado: dependencia '{dep}' falhou")
                        exec_registry.skip(execution_id, node_id)
                        executed.add(name)
                        aborted = True
                        break
                if aborted:
                    continue
                retry_count = checkpoint_db.get_node_retry_count(execution_id, name)
                if retry_count >= self.MAX_RETRY:
                    logger.error("[ASYNC] No '%s' excedeu limite de retry. Abortando.", name)
                    self.results[name] = {"error": "Max retry exceeded", "node": name, "status": "ABORTED"}
                    exec_registry.skip(execution_id, node_id)
                    executed.add(name)
                    continue
                if not exec_registry.claim(execution_id, node_id):
                    executed.add(name)
                    continue
                ready_nodes.append((name, node, node_id, retry_count))

            if not ready_nodes:
                remaining = set(self.nodes.keys()) - executed
                if not remaining:
                    break
                raise RuntimeError(f"Deadlock no Graph: execution_id={execution_id} | pendentes={remaining}")

            logger.info("🚀 [ASYNC] executando %d agente(s) em paralelo ...", len(ready_nodes))
            batch_results = {}

            async def _run_node(name, node, node_id, retry_count):
                try:
                    result = await self._execute_node_async(node, input_data)
                    return (name, result, node, node_id, retry_count)
                except Exception as e:
                    logger.error("[ASYNC] Node '%s' falhou: %s", name, e)
                    return (name, None, node, node_id, retry_count)

            tasks = [_run_node(name, node, node_id, retry_count) for name, node, node_id, retry_count in ready_nodes]
            for task_batch in [tasks[i:i+self.MAX_WORKERS] for i in range(0, len(tasks), self.MAX_WORKERS)]:
                for coro in asyncio.as_completed(task_batch):
                    name, result, node, node_id, retry_count = await coro
                    batch_results[name] = (result, node, node_id, retry_count)

            for name, (result, node, node_id, retry_count) in batch_results.items():
                if result is None:
                    error_msg = f"Excecao na execucao do no '{name}'"
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    if node.critical:
                        self._abort_dependent_nodes(execution_id, name, error_msg)
                    self.results[name] = {"error": error_msg, "node": name, "status": "FAILED"}
                    executed.add(name)
                    continue

                self.results[name] = result
                executed.add(name)

                if result.get("success"):
                    checkpoint_db.update_node_status(execution_id, name, "COMPLETED",
                        result_data=str(result.get("output", "")).encode() if result.get("output") else None)
                    exec_registry.complete(execution_id, node_id, result.get("result_text", ""))
                else:
                    error_msg = result.get("error", "Unknown error")
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    if node.critical:
                        self._abort_dependent_nodes(execution_id, name, error_msg)

        return self._aggregate(time.time() - start_time, execution_id)

    async def run_parallel(
        self,
        input_data: Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parallel DAG scheduling via streaming topological execution.

        Uses asyncio.gather() to execute ALL ready nodes concurrently at each
        scheduling step — no fixed batch sizes. Nodes become ready as soon as
        their dependencies complete, enabling maximum parallelism.

        Preserves: canonicalization, checkpoint, registry, Sanity Barrier,
        skill_executor, LLM fallback, workdir, node recording, _aggregate output.
        """
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        if "metadata" not in input_data:
            input_data["metadata"] = {}
        input_data["metadata"]["execution_id"] = execution_id

        task_text = str(input_data.get("task", input_data.get("input", {}).get("task", "")))
        input_data["_task_text"] = task_text

        logger.info("⚡ [PARALLEL] ativando agentes especialistas ...")

        # Canonicalize (dedup, edge consolidation, topological sort)
        original_count = len(self.nodes)
        self.nodes = canonicalize(self.nodes)
        current_hash = compute_graph_hash(self.nodes)
        if current_hash != self._graph_hash:
            logger.info("[PARALLEL] Grafo alterado: %s → %s (%d → %d nós)",
                         self._graph_hash, current_hash, original_count, len(self.nodes))
            self._graph_hash = current_hash

        # Execution context
        ctx = make_context(
            execution_id=execution_id,
            graph=self.snapshot(),
            seed_version=f"gen_{self.generation}",
            task=task_text,
            metadata=input_data.get("metadata", {}),
        )

        node_ids = [n.node_id for n in self.nodes.values()]
        exec_registry.init_execution(execution_id, node_ids)

        self.results = {}
        executed: Set[str] = set()

        # Restore checkpoint
        checkpoint = checkpoint_db.get_checkpoint(execution_id)
        if not checkpoint and execution_id:
            checkpoint_db.init_execution(execution_id, list(self.nodes.keys()))
        elif checkpoint:
            logger.info("[PARALLEL] Checkpoint encontrado: %d nós COMPLETED", len(checkpoint))

        for node_name, state in checkpoint.items():
            self.results[node_name] = {"output": state.get("result_data"), "status": "COMPLETED",
                                        "cached": True, "success": True, "error": None}
            executed.add(node_name)
            exec_registry.complete(execution_id, node_name)

        start_time = time.time()

        # Track node statuses for the scheduler
        node_status: Dict[str, str] = {n: "PENDING" for n in self.nodes}
        for n in executed:
            node_status[n] = "COMPLETED"

        def _find_dependents(node_name: str) -> Set[str]:
            """Find all transitive dependents of a node."""
            deps: Set[str] = set()
            def _walk(name: str):
                for n_name, n_node in self.nodes.items():
                    if name in n_node.depends_on and n_name not in deps:
                        deps.add(n_name)
                        _walk(n_name)
            _walk(node_name)
            return deps

        def _get_ready() -> List[str]:
            """Return names of nodes ready to execute."""
            ready = []
            for name, node in self.nodes.items():
                if node_status.get(name, "PENDING") != "PENDING":
                    continue
                if name in executed:
                    continue
                deps = node.depends_on or []
                all_done = True
                abort = False
                for dep in deps:
                    dep_status = node_status.get(dep)
                    if dep_status is None or dep_status == "PENDING":
                        all_done = False
                        break
                    if dep_status == "ABORTED":
                        abort = True
                        break
                    if dep_status == "FAILED" and self.nodes.get(dep) and self.nodes[dep].critical:
                        abort = True
                        break
                if abort:
                    logger.warning("🛡️ [PARALLEL] Sanity Barrier: '%s' abortado — dependência crítica '%s' falhou", name, dep)
                    error_msg = f"Abortado pela Sanity Barrier: dependência crítica '{dep}' falhou"
                    self.results[name] = {"error": error_msg, "node": name, "status": "ABORTED", "success": False}
                    checkpoint_db.update_node_status(execution_id, name, "ABORTED", error_message=error_msg)
                    exec_registry.skip(execution_id, node.node_id)
                    node_status[name] = "ABORTED"
                    executed.add(name)
                    continue
                if all_done:
                    ready.append(name)
            return ready

        while len(executed) < len(self.nodes):
            ready = _get_ready()
            if not ready:
                remaining = set(self.nodes.keys()) - executed
                if not remaining:
                    break
                raise RuntimeError(
                    f"💥 [PARALLEL] Deadlock no Grafo: execution_id={execution_id} | pendentes={remaining}"
                )

            logger.info("🚀 [PARALLEL] executando %d agente(s) concorrentemente ...", len(ready))

            # Execute all ready nodes via asyncio.gather (true concurrent parallelism)
            async def _run_one(name: str) -> tuple:
                node = self.nodes[name]
                node_id = node.node_id
                try:
                    result = await self._execute_node_async(node, input_data)
                    return (name, result, node, node_id)
                except Exception as e:
                    logger.error("[PARALLEL] Node '%s' falhou com exceção: %s", name, e)
                    return (name, None, node, node_id)

            coros = [_run_one(name) for name in ready]
            batch_results = await asyncio.gather(*coros)

            for name, result, node, node_id in batch_results:
                if result is None:
                    error_msg = f"Exceção na execução concorrente do nó '{name}'"
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    node_status[name] = "FAILED"
                    if node.critical:
                        logger.warning("🛡️ [PARALLEL] Sanity Barrier acionada! Nó crítico '%s' falhou. Abortando dependentes.", name)
                        for dep_name in _find_dependents(name):
                            self.results[dep_name] = {
                                "error": f"Abortado pela Sanity Barrier: nó crítico '{name}' falhou",
                                "node": dep_name, "status": "ABORTED", "success": False,
                            }
                            checkpoint_db.update_node_status(execution_id, dep_name, "ABORTED",
                                error_message=f"Abortado pela Sanity Barrier: nó crítico '{name}' falhou: {error_msg}")
                            node_status[dep_name] = "ABORTED"
                            executed.add(dep_name)
                        bus.publish(EventType.CRITICAL_NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg,
                            "aborted_dependents": list(_find_dependents(name)),
                        }, source="execution_graph.run_parallel")
                        bus.publish(EventType.SANITY_BARRIER_TRIGGERED, {
                            "execution_id": execution_id, "failed_node": name,
                            "error": error_msg,
                        }, source="execution_graph.run_parallel")
                    else:
                        bus.publish(EventType.NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg,
                        }, source="execution_graph.run_parallel")
                    self.results[name] = {"error": error_msg, "node": name, "status": "FAILED", "success": False}
                    executed.add(name)
                    continue

                self.results[name] = result
                executed.add(name)

                if result.get("success"):
                    node_status[name] = "COMPLETED"
                    checkpoint_db.update_node_status(execution_id, name, "COMPLETED",
                        result_data=str(result.get("output", "")).encode() if result.get("output") else None)
                    exec_registry.complete(execution_id, node_id, result.get("result_text", ""))
                else:
                    error_msg = result.get("error", "Unknown error")
                    node_status[name] = "FAILED"
                    checkpoint_db.update_node_status(execution_id, name, "FAILED", error_message=error_msg)
                    exec_registry.fail(execution_id, node_id, error_msg)
                    if node.critical:
                        logger.warning("🛡️ [PARALLEL] Sanity Barrier acionada! Nó crítico '%s' falhou. Abortando dependentes.", name)
                        for dep_name in _find_dependents(name):
                            self.results[dep_name] = {
                                "error": f"Abortado pela Sanity Barrier: nó crítico '{name}' falhou",
                                "node": dep_name, "status": "ABORTED", "success": False,
                            }
                            checkpoint_db.update_node_status(execution_id, dep_name, "ABORTED",
                                error_message=f"Abortado pela Sanity Barrier: nó crítico '{name}' falhou: {error_msg}")
                            node_status[dep_name] = "ABORTED"
                            executed.add(dep_name)
                        bus.publish(EventType.CRITICAL_NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg,
                            "aborted_dependents": list(_find_dependents(name)),
                        }, source="execution_graph.run_parallel")
                        bus.publish(EventType.SANITY_BARRIER_TRIGGERED, {
                            "execution_id": execution_id, "failed_node": name,
                            "error": error_msg,
                        }, source="execution_graph.run_parallel")
                    else:
                        bus.publish(EventType.NODE_FAILED, {
                            "execution_id": execution_id, "node_id": name,
                            "error": error_msg,
                        }, source="execution_graph.run_parallel")

        return self._aggregate(time.time() - start_time, execution_id)

    def restart_node(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        logger.info(f"🔄 Restart node: {node_id} | execution_id={execution_id}")

        if node_id not in self.nodes:
            raise ValueError(f"Node '{node_id}' não encontrado no grafo")

        checkpoint_db.reset_failed_node(execution_id, node_id)

        context = {"task": "", "metadata": {"ts": time.time(), "restart": True}}
        result = self.run(context, execution_id=execution_id)
        return result

    def _get_output_text(self, result: dict) -> str:
        output = result.get("output")
        if hasattr(output, "code"):
            return output.code or ""
        if isinstance(output, str):
            return output
        return result.get("result_text", str(output or ""))

    def _aggregate(self, duration: float, execution_id: Optional[str] = None) -> Dict[str, Any]:
        outputs = [
            r.get("output")
            for r in self.results.values()
            if isinstance(r, dict) and r.get("success")
        ]

        final = None
        final_text = None

        if outputs:
            scored = []
            for name, r in self.results.items():
                if not isinstance(r, dict) or not r.get("success"):
                    continue
                output_text = self._get_output_text(r)
                if not output_text:
                    continue

                score = self._compute_score(name, r)
                scored.append((output_text, score, name))

            if scored:
                scored.sort(key=lambda x: x[1], reverse=True)
                final_text = scored[0][0]
                logger.info(f"🏆 melhor resultado: {scored[0][2]} (score={scored[0][1]:.2f})")

        if not final_text and outputs:
            final_text = max((self._get_output_text(r) for r in self.results.values() if isinstance(r, dict)), key=len, default="")

        return {
            "success": True,
            "execution_time": duration,
            "nodes_executed": len(self.results),
            "final_output": final_text,
            "raw_results": self.results,
            "execution_id": execution_id or "",
        }

    def _compute_score(self, node_name: str, result: dict) -> float:
        base = 0.0

        tests_passed = int(result.get("tests_passed", 0))
        tests_total = int(result.get("tests_total", 0))
        if tests_total > 0:
            base += (tests_passed / tests_total) * 0.50
            if tests_passed == tests_total:
                base += 0.10

        critic_score = float(result.get("critic_score", 0))
        base += (critic_score / 100.0) * 0.20

        security_valid = result.get("security_valid", True)
        if security_valid:
            base += 0.15

        code_len = len(self._get_output_text(result))
        simplicity = max(0, 1.0 - min(code_len / 5000, 1.0))
        base += simplicity * 0.10

        latency = result.get("latency", 1.0)
        perf = max(0, 1.0 - min(latency / 30.0, 1.0))
        base += perf * 0.05

        return base

    def snapshot(self):
        return {
            "nodes": {
                name: {
                    "depends_on": list(node.depends_on),
                    "strategy": node.strategy,
                    "model_hint": node.model_hint,
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "seed_id": node.seed_id,
                    "mutation_id": node.mutation_id,
                    "version": node.version,
                    "success_rate": node.success_rate,
                    "avg_latency": node.avg_latency,
                    "executions": node.executions
                }
                for name, node in self.nodes.items()
            }
        }
