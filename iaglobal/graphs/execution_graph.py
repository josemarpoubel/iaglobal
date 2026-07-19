# iaglobal/graphs/execution_graph.py

import asyncio
import time
import uuid
import hashlib
import threading


from typing import Dict, Any, Optional, Set, Tuple

from iaglobal.utils.logger import logger
from iaglobal.utils.hash_utils import LineageID

from .node import Node

from .workdir import make_workdir

from iaglobal.memory.db_manager import db as checkpoint_db
from iaglobal.evolution.execution_registry import registry as exec_registry
from iaglobal.evolution.canonical_graph import canonicalize, compute_graph_hash
from iaglobal.evolution.skills.native.skill_executor import (
    skill_executor,
    SkillExecutionError,
)
from iaglobal.graphs.artifact import Artifact
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.instrumentation import trace_node_execution, trace_node_completed
from iaglobal.execution.cpu_affinity import cpu_affinity
from iaglobal.immunity.loop_detector import LoopDetector
from iaglobal.evolution.homeostasis_controller import homeostasis_controller
from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus,
    AgentMessage,
)
from iaglobal.sandbox.sandbox_expansion import sandbox_expansion
from iaglobal.graphs.contracts.node_contract import MissingContextError
from iaglobal.graphs.recovery import RecoveryPolicy, RecoveryDecision, RecoveryResult
from iaglobal.obsidian.omnimind import omni_mind


class ExecutionGraph:
    MAX_RETRY = 4
    MAX_WORKERS = 32

    def __init__(self, tool_router=None):
        self.tool_router = tool_router
        self.nodes = {}
        self.results = {}
        self._node_cache = {}
        self.generation = 0
        self._graph_hash = ""
        self._results_lock = threading.Lock()
        self.credit = CreditAssignmentEngine()
        self._loop_detector = LoopDetector()
        self.bus = AcetylcholineBus()
        self._homeostasis = homeostasis_controller
        self._recovery = RecoveryPolicy()
        self._recovery_in_flight: Set[Tuple[str, str]] = set()
        self._background_tasks: Set["asyncio.Task"] = set()
        self._bus_handlers_registered = False
        try:
            from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
            self._epigenetic = EpigeneticRegistry()
        except Exception:
            self._epigenetic = None
        self._init_agent_bus()
        try:
            from iaglobal.reflection.reflexion_engine import reflexion_callback_for_loop

            self._loop_detector.set_reflexion_fn(reflexion_callback_for_loop)
        except ImportError:
            logger.warning(
                "[IMMUNITY] ReflexionEngine não disponível - loop repair desativado"
            )

    def _init_agent_bus(self):
        """Registra handlers padrão para agentes no AcetylcholineBus."""
        try:
            from iaglobal.graphs.comms.agent_mailbox import MailboxManager

            self.mailbox_manager = MailboxManager()
            # Handlers genéricos para debug (registrados de forma lazy)
            self._bus_handlers_registered = False
            logger.debug("[EXECUTION_GRAPH] AcetylcholineBus pronto para handlers")
        except Exception as e:
            logger.warning("[EXECUTION_GRAPH] Falha ao inicializar agent bus: %s", e)

    def _register_bus_handlers(self):
        """Registra handlers no bus se ainda não registrado (precisa de event loop)."""
        if self._bus_handlers_registered:
            return
        try:

            async def _log_message(msg):
                logger.info(
                    "[BUS] %s → %s | type=%s", msg.sender, msg.receiver, msg.type
                )

            self.bus.subscribe("*:*", _log_message)
            self._bus_handlers_registered = True
        except Exception:
            pass

    @staticmethod
    def generate_node_id(strategy: str, code_payload: str, generation: int = 0) -> str:
        """Cria a identidade única SHA3-512 baseada em DNA (conteúdo + geração)."""
        if not isinstance(code_payload, str):
            code_payload = str(code_payload)
        return LineageID.compute(
            entity_type="dna_node",
            name=f"{strategy}:{hashlib.sha3_256(code_payload.encode()).hexdigest()[:16]}",
            generation=generation,
        )[0]

    def add_node(self, node):
        """
        Adiciona um nó ao grafo.
        Usa o nome do nó como chave (para DAG pipeline) ou chama add_node_by_dna
        se o nó possuir atributos 'strategy' e 'payload' (sistema evolutivo legado).
        """
        node_name = getattr(node, "name", None)
        if node_name and node_name not in self.nodes:
            self.nodes[node_name] = node
            self._update_graph_hash()
            return node
        strategy = getattr(node, "strategy", "default")
        payload = getattr(node, "payload", getattr(node, "run", str(node)))
        return self.add_node_by_dna(strategy, payload)

    def add_node_by_dna(self, strategy: str, payload: str, generation: int = 0):
        """Adiciona ou recupera um nó baseado no seu DNA (hash SHA3-512)."""
        node_id = self.generate_node_id(strategy, payload, generation=generation)

        if node_id in self.nodes:
            return self.nodes[node_id]

        new_node = Node(name=node_id, strategy=strategy, run=payload)
        self.nodes[node_id] = new_node
        self._update_graph_hash()

        logger.info(f"🧬 DNA Evolutivo: Nó inédito criado com ID {node_id[:16]}...")
        return new_node

    def _update_graph_hash(self):
        """Calcula um hash baseado no estado atual dos nós."""
        import hashlib

        # Concatena os nomes dos nós ordenados para garantir consistência
        node_ids = sorted(self.nodes.keys())
        content = "|".join(node_ids)
        self._graph_hash = hashlib.sha256(content.encode()).hexdigest()

    async def _execute_node_async(self, node: Node, input_data: dict) -> dict:
        # 1. Afinidade Determinística baseada no DNA (Hash) do nó
        await cpu_affinity.pin_to_hash(node.name)

        # Registra handlers no bus (lazy)
        self._register_bus_handlers()

        await self.bus.publish(
            AgentMessage(
                sender="execution_graph",
                receiver=node.name,
                type="node_start",
                payload={"node": node.name, "time": time.time()},
            )
        )

        # 2. Lock via thread (Node.acquire é síncrono)
        if not await asyncio.to_thread(node.acquire):
            return {
                "output": None,
                "latency": 0.0,
                "success": False,
                "error": f"Node '{node.name}' já está em execução (lock)",
                "result_text": "",
            }

        start = time.time()
        raw_task = str(
            input_data.get("task", "")
            or (
                input_data.get("input", {}).get("task", "")
                if isinstance(input_data.get("input"), dict)
                else ""
            )
        )
        exec_id = str(input_data.get("metadata", {}).get("execution_id", raw_task))
        workdir = make_workdir(node.name, exec_id, raw_task)

        ctx = {"input": input_data, "memory": self.results, "workdir": workdir}
        if raw_task:
            ctx["task"] = raw_task
        trace = trace_node_execution(node.name, ctx)
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

            # Execução de Skills
            if skill_executor.can_execute(skill_name):
                try:
                    result = skill_executor.execute_with_fallback(skill_name, ctx)
                    if asyncio.iscoroutine(result):
                        result = await result
                    executed = True
                except SkillExecutionError as e:
                    contract_error = str(e)
                    await workdir.async_append_log(
                        f"contrato insatisfeito: {str(e)[:80]} — fallback"
                    )

            # Fallback para node.run
            if not executed and node.run:
                try:
                    result = node.run(ctx)
                    if asyncio.iscoroutine(result):
                        result = await result
                    executed = True
                except Exception as e:
                    node_run_failed = True
                    logger.debug(
                        "[GRAPH] Nó '%s' node.run falhou: %s — continuando para fallback Bandit",
                        node.name,
                        str(e)[:80],
                    )

            # ====================================================================================================

            if executed:
                # 1. Parsing do resultado (independente se veio de Skill ou Node.run)
                if isinstance(result, dict):
                    result_raw = result.get("output")
                    extra_fields = {k: v for k, v in result.items() if k != "output"}

                    if hasattr(result_raw, "code"):
                        result_text = result_raw.code or ""
                        # Criação de artefato se necessário
                        if "artifact" not in result and result_text:
                            task_ref = getattr(result_raw, "task", "") or raw_task
                            extra_fields["artifact"] = Artifact(
                                content=result_text,
                                type="code",
                                metadata={
                                    "task": task_ref,
                                    "score": getattr(result_raw, "score", 0),
                                    "node": node.name,
                                    "evo": True,
                                },
                            )
                    else:
                        result_text = str(result_raw) if result_raw is not None else ""
                else:
                    result_raw = result if hasattr(result, "code") else None
                    result_text = (
                        result.code if hasattr(result, "code") else str(result)
                    )

                if isinstance(result, dict) and result.get("skipped"):
                    logger.info(
                        "[GRAPH] Nó '%s' pulado (single-run já executada)", node.name
                    )

            # 2. Caso o nó não tenha retornado nada útil, dispara o Bandit Policy
            # Também dispara se o output for muito curto ou genérico (modelo local fraco)
            _weak_output = result_text and (
                len(result_text.strip()) < 80
                or result_text.strip().lower()
                in [
                    "olá! como posso te ajudar hoje?",
                    "olá, tudo bem?",
                    "hello",
                    "olá",
                ]
            )
            if not result_text or _weak_output:
                from iaglobal.agents.critic_agent import _get_critic

                result_text = await _get_critic().arbitrar_geracao(
                    node_id=node.name,
                    prompt=raw_task,
                    task_type=node.strategy,
                )

            # 3. Validação final do sucesso
            if result_text:
                success = True
                await workdir.async_write_code(result_text)
                await workdir.async_append_log("executado com sucesso")
            elif contract_error:
                last_error = contract_error

        except MissingContextError:
            raise
        except ImportError as e:
            last_error = str(e)
            result_text = ""
            await workdir.async_append_log(f"import_error: {last_error}")
            missing_lib = sandbox_expansion.extract_missing_lib(e)

            # Evita loop infinito: não tenta instalar módulos do projeto local
            # nem libs que já falharam nesta execução
            if missing_lib and not missing_lib.startswith("iaglobal"):
                if not hasattr(self, "_pec_retried"):
                    self._pec_retried = set()
                retry_key = (node.name, missing_lib)
                if retry_key not in self._pec_retried:
                    self._pec_retried.add(retry_key)
                    logger.warning(
                        "[PEC] ImportError detectado no no '%s': lib=%s | instalando...",
                        node.name,
                        missing_lib,
                    )
                    installed = sandbox_expansion.request_install(missing_lib)
                    if installed:
                        logger.info(
                            "[PEC] Lib '%s' instalada. Re-executando no '%s'...",
                            missing_lib,
                            node.name,
                        )
                        await asyncio.to_thread(node.release)
                        return await self._execute_node_async(node, input_data)
        except Exception as e:
            last_error = str(e)
            result_text = ""
            await workdir.async_append_log(f"erro: {last_error}")
        finally:
            # Liberação via thread (Node.release é síncrono)
            await asyncio.to_thread(node.release)
            # Rotação removida pois agora usamos pin_to_hash (afinidade determinística)
            latency = time.time() - start

        # --- ATUALIZAÇÃO DA POLÍTICA PÓS EXECUÇÃO ---
        # Se 'bandit' e 'chosen_model' foram definidos no escopo anterior
        if "bandit" in locals() and "chosen_model" in locals() and result_text:
            try:
                reward = 1.0 if success else 0.0
                ivm = getattr(self._homeostasis, "current_ivm", 0.5)
                await asyncio.to_thread(
                    bandit.update_reward,
                    chosen_model,
                    reward,
                    ivm,
                )
            except Exception as e_train:
                logger.warning(f"[GRAPH-ASYNC] Falha ao atualizar bandit: {e_train}")

        # Gravação de métricas do nó (Node.record é síncrono)
        await asyncio.to_thread(node.record, success, latency, last_error)

        # Publicação no barramento de eventos (AcetylcholineBus.publish é async)
        await self.bus.publish(
            AgentMessage(
                sender=node.name,
                receiver="execution_graph",
                type="node_complete",
                payload={"node": node.name, "success": success, "latency": latency},
            )
        )

        # Check de imunidade (LoopDetector.check_and_repair é síncrono)
        loop_check = await asyncio.to_thread(
            self._loop_detector.check_and_repair, node.name, success, ctx
        )
        if loop_check.get("in_loop"):
            logger.warning(
                "🛡️ [IMMUNITY-ASYNC] Loop detectado no nó '%s' (%d execuções)",
                node.name,
                loop_check.get("executions", 0),
            )
            if loop_check.get("repair_triggered"):
                logger.info(
                    "🛡️ [IMMUNITY-ASYNC] Reparação auto-triggered: %s",
                    loop_check.get("repair_result", {}).get("status", "unknown"),
                )

        # Tracing final
        trace = trace_node_completed(
            trace,
            {
                "output": result_raw if result_raw is not None else result_text,
                "latency": latency,
                "success": success,
            },
            ctx,
        )

        # Registro de homeostase (SLA metrics)
        cost_usd = extra_fields.get("cost", 0.0)
        self._homeostasis.record_execution(success, latency * 1000, cost_usd)

        logger.debug(
            "[TRACE] node=%s duration=%.1fms", node.name, trace.get("duration_ms", 0)
        )

        return {
            "output": result_raw if result_raw is not None else result_text,
            "latency": latency,
            "success": success,
            "error": last_error,
            "result_text": result_text,
            **extra_fields,
        }

    def _find_dependents(
        self, node_name: str, visited: Optional[Set[str]] = None
    ) -> Set[str]:
        """Encontra recursivamente todos os dependentes (transitivos) de um nó."""
        if visited is None:
            visited = set()
        for n_name, n_node in self.nodes.items():
            if node_name in n_node.depends_on and n_name not in visited:
                visited.add(n_name)
                self._find_dependents(n_name, visited)
        return visited

    async def _abort_dependent_nodes_async(
        self, execution_id: str, failed_node_name: str, reason: str
    ):
        """Abortamento assíncrono em cascata (Sanity Barrier)."""
        dependents = self._find_dependents(failed_node_name)

        if not dependents:
            return

        # Execução paralela dos abortos para não bloquear o loop
        tasks = []
        for dep_name in dependents:
            logger.warning(
                "🛡️ [SANITY BARRIER] Abortando nó '%s' por falha em '%s'",
                dep_name,
                failed_node_name,
            )

            # Atualização em memória
            self.results[dep_name] = {
                "error": f"Abortado pela Sanity Barrier: falha em '{failed_node_name}'",
                "node": dep_name,
                "status": "ABORTED",
                "success": False,
            }

            # Atualização assíncrona no DB
            tasks.append(
                checkpoint_db.update_node_status_async(
                    execution_id,
                    dep_name,
                    "ABORTED",
                    error_message=f"Abortado pela Sanity Barrier: nó crítico '{failed_node_name}' falhou: {reason}",
                )
            )

        # Aguarda todas as atualizações de status no banco de dados em paralelo
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _invalidate_sibling_consumers(
        self,
        upstream_id: str,
        execution_id: str,
        executed: Set[str],
        skip_node: str,
    ) -> None:
        """Invalida TODOS os consumidores (transitivo) de `upstream_id`
        exceto `skip_node`.

        Percorre o DAG em BFS a partir do upstream, invalidando cada
        nó downstream que já executou com resultado obsoleto (FIX-1 + FIX-4).

        Ex: A→B→C. Se A resetar, B é invalidado como consumidor direto,
        e C também (consumidor transitivo de A via B). `skip_node` é
        atravessado mas não invalidado (já está sendo tratado pelo
        handler principal), permitindo alcançar seus dependentes.
        """
        visited: Set[str] = {upstream_id}
        queue: list[str] = [upstream_id]
        while queue:
            current = queue.pop(0)
            for sib_name, sib_node in self.nodes.items():
                if sib_name in visited:
                    continue
                if current not in (sib_node.depends_on or []):
                    continue
                visited.add(sib_name)
                if sib_name != skip_node and sib_name in executed:
                    sib_node.release()
                    self.results.pop(sib_name, None)
                    executed.discard(sib_name)
                    await asyncio.to_thread(
                        exec_registry.reset_node, execution_id, sib_name
                    )
                queue.append(sib_name)

    async def _record_recovery_decision(
        self,
        node_id: str,
        missing: list[str],
        decision: RecoveryDecision,
        attempt: int,
        reason: str,
    ) -> None:
        """Registra decisões do RecoveryPolicy como memória imunológica (FIX-3).

        RESCHEDULE  → EpigeneticRegistry.record_failure (fire-and-forget)
        ABORT       → OmniMind.emitir_gatilho_apoptose
        """
        if decision is RecoveryDecision.ABORT:
            try:
                # emitir_gatilho_apoptose faz I/O síncrono (_salvar_estado
                # escreve JSON em disco). Executar em thread para não bloquear
                # o event loop (FIX-3 blocking I/O).
                await asyncio.to_thread(
                    omni_mind.emitir_gatilho_apoptose,
                    agent_id=node_id,
                    motivo=f"RecoveryPolicy ABORT após {attempt}x MissingContextError: {reason}",
                    violation_type="recovery_abort",
                )
            except Exception:
                logger.exception("[RECOVERY] Falha ao registrar apoptose no OmniMind")
        elif self._epigenetic is not None:
            try:
                import hashlib
                task_hash = hashlib.sha256(
                    f"{node_id}:{missing}".encode()
                ).hexdigest()[:16]
                loop = asyncio.get_running_loop()
                # Guarda referência + done_callback para evitar que a task
                # seja coletada pelo GC antes de completar (FIX-2).
                task = loop.create_task(
                    self._epigenetic.record_failure(
                        agent_id=node_id,
                        task_hash=task_hash,
                        error_type="missing_context_reschedule",
                        context={
                            "missing": missing,
                            "attempt": attempt,
                            "reason": reason,
                        },
                    )
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._on_recovery_task_done)
            except Exception:
                logger.exception("[RECOVERY] Falha ao registrar falha epigenética")

    def _on_recovery_task_done(self, task: "asyncio.Task") -> None:
        """Callback de background task — remove da set E loga exceção
        no logger do iaglobal (não no logger padrão do asyncio)."""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception(
                "[RECOVERY] record_failure falhou (não-fatal)", exc_info=exc
            )

    async def drain_background_tasks(self, timeout: Optional[float] = None) -> None:
        """Aguarda conclusão das background tasks pendentes (FIX-2 shutdown).

        Usado no encerramento do pipeline para garantir que memória
        imunológica (record_failure) seja gravada antes do processo terminar.

        Args:
            timeout: Se None, espera indefinidamente (default). Se float,
                     espera até timeout segundos — tasks não completadas
                     NÃO são canceladas (continuam rodando em background).
        """
        if not self._background_tasks:
            return
        pending = list(self._background_tasks)
        if pending:
            logger.info(
                "[RECOVERY] Drenando %d background tasks antes do shutdown...",
                len(pending),
            )
            if timeout is not None:
                # asyncio.wait com timeout NÃO cancela tasks restantes
                done, remaining = await asyncio.wait(
                    pending, timeout=timeout, return_when=asyncio.ALL_COMPLETED
                )
                if remaining:
                    logger.warning(
                        "[RECOVERY] %d tasks não completaram em %.1fs — continuam rodando",
                        len(remaining),
                        timeout,
                    )
                # Agrega exceções das tasks completadas
                for task in done:
                    exc = task.exception()
                    if exc is not None:
                        logger.exception(
                            "[RECOVERY] Task falhou durante drain", exc_info=exc
                        )
            else:
                # Espera indefinidamente
                await asyncio.gather(*pending, return_exceptions=True)
            logger.info("[RECOVERY] Background tasks drenadas.")

    async def async_run(
        self, input_data: Dict[str, Any], execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        execution_id = execution_id or str(uuid.uuid4())
        input_data.setdefault("metadata", {})["execution_id"] = execution_id
        task_text = str(
            input_data.get("task", input_data.get("input", {}).get("task", ""))
        )
        input_data["_task_text"] = task_text

        logger.info("🚀 [ASYNC] Iniciando execução orquestrada: %s", execution_id)

        # Canonicalização e Hash do Grafo
        self.nodes = canonicalize(self.nodes)
        self._graph_hash = compute_graph_hash(self.nodes)

        # Inicialização do Registro
        await asyncio.to_thread(
            exec_registry.init_execution,
            execution_id,
            [n.node_id for n in self.nodes.values()],
        )

        self.results = {}
        executed: Set[str] = set()

        # Carregamento de checkpoint assíncrono
        checkpoint = await asyncio.to_thread(checkpoint_db.get_checkpoint, execution_id)
        if checkpoint:
            for node_name, state in checkpoint.items():
                self.results[node_name] = {
                    "output": state.get("result_data"),
                    "status": "COMPLETED",
                    "success": True,
                }
                executed.add(node_name)
                await asyncio.to_thread(
                    exec_registry.complete_node, execution_id, node_name
                )

        start_time = time.time()

        while len(executed) < len(self.nodes):
            ready_nodes = []
            for name, node in self.nodes.items():
                if name in executed or name in self.results:
                    continue
                if not all(
                    dep in executed or dep in self.results for dep in node.depends_on
                ):
                    continue

                # Checagem de status assíncrona
                if await asyncio.to_thread(
                    exec_registry.was_executed, execution_id, node.node_id
                ):
                    executed.add(name)
                    continue

                # Lógica de ABORT (usando métodos assíncronos)
                # ... (manter lógica de checagem de dependência) ...

                if await asyncio.to_thread(
                    exec_registry.claim, execution_id, node.node_id
                ):
                    ready_nodes.append((name, node, node.node_id))

            if not ready_nodes:
                processed = executed | set(self.results.keys())
                if len(processed) >= len(self.nodes):
                    logger.info(
                        "[ASYNC] Grafo finalizado: %d nós processados (%d executados, %d em results)",
                        len(processed),
                        len(executed),
                        len(self.results),
                    )
                    break
                logger.warning(
                    "[ASYNC] DEADLOCK SUSPEITO — pendentes: %s | executados: %d/%d",
                    [n for n in self.nodes if n not in processed],
                    len(executed),
                    len(self.nodes),
                )
                raise RuntimeError(f"Deadlock detectado: {execution_id}")

            # Execução em batch assíncrono
            node_names_batch = [name for name, _, _ in ready_nodes]
            logger.warning("[ASYNC] BATCH EXECUTANDO: %s", node_names_batch)
            tasks = [
                self._execute_node_async(node, input_data)
                for name, node, node_id in ready_nodes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (name, node, node_id), result in zip(ready_nodes, results):
                is_exception = isinstance(result, Exception)
                is_failed = is_exception or (
                    isinstance(result, dict) and not result.get("success")
                )

                if is_failed:
                    error_msg = (
                        str(result.get("error", "Execution Failed"))
                        if isinstance(result, dict)
                        else str(result)
                    )
                    logger.warning("[GRAPH] Nó '%s' falhou: %s", name, error_msg)

                    if isinstance(result, MissingContextError):
                        recovery = await self._recovery.handle_missing_context(
                            node_id=name,
                            missing=result.missing,
                        )

                        await self._record_recovery_decision(
                            node_id=name,
                            missing=result.missing,
                            decision=recovery.decision,
                            attempt=recovery.attempt_number,
                            reason=recovery.reason,
                        )

                        if recovery.decision is RecoveryDecision.RESCHEDULE:
                            reset_uids: list[str] = []
                            try:
                                for uid in recovery.upstream_ids:
                                    # Guard anti-corrida (FIX-2): só adiciona
                                    # ao _recovery_in_flight QUEM esta
                                    # chamada realmente resetou. O finally
                                    # só descarta reset_uids, nao todo o
                                    # recovery.upstream_ids — assim um irmão
                                    # que fez continue não remove o guard
                                    # de quem está no meio do reset.
                                    uid_flight = (execution_id, uid)
                                    if uid_flight in self._recovery_in_flight:
                                        continue
                                    self._recovery_in_flight.add(uid_flight)
                                    reset_uids.append(uid)
                                    upstream_node = self.nodes.get(uid)
                                    if upstream_node:
                                        upstream_node.release()
                                    self.results.pop(uid, None)
                                    executed.discard(uid)
                                    await asyncio.to_thread(
                                        exec_registry.reset_node, execution_id, uid
                                    )
                                    # Invalida TODOS os consumidores
                                    # (transitivo) do upstream (FIX-1 + FIX-4)
                                    await self._invalidate_sibling_consumers(
                                        uid, execution_id, executed, skip_node=name
                                    )
                                node.release()
                                self.results.pop(name, None)
                                await asyncio.to_thread(
                                    exec_registry.reset_node, execution_id, name
                                )
                                await asyncio.to_thread(
                                    checkpoint_db.update_node_status,
                                    execution_id,
                                    name,
                                    "PENDING",
                                )
                            finally:
                                for uid in reset_uids:
                                    self._recovery_in_flight.discard(
                                        (execution_id, uid)
                                    )
                            continue
                        else:
                            await self._abort_dependent_nodes_async(
                                execution_id, name, error_msg
                            )
                    elif is_exception and node.critical:
                        await self._abort_dependent_nodes_async(
                            execution_id, name, error_msg
                        )

                    await asyncio.to_thread(
                        checkpoint_db.update_node_status,
                        execution_id,
                        name,
                        "FAILED",
                        error_message=error_msg,
                    )
                else:
                    self.results[name] = result
                    await asyncio.to_thread(
                        checkpoint_db.update_node_status,
                        execution_id,
                        name,
                        "COMPLETED",
                    )

                executed.add(name)

        return self._aggregate(time.time() - start_time, execution_id)

    async def run_parallel(
        self, input_data: Dict[str, Any], execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        execution_id = execution_id or str(uuid.uuid4())
        input_data.setdefault("metadata", {})["execution_id"] = execution_id
        task_text = str(
            input_data.get("task", input_data.get("input", {}).get("task", ""))
        )
        input_data["_task_text"] = task_text

        logger.info("⚡ [PARALLEL] Iniciando fluxo concorrente: %s", execution_id)

        self.nodes = canonicalize(self.nodes)
        self._graph_hash = compute_graph_hash(self.nodes)

        await asyncio.to_thread(
            exec_registry.init_execution,
            execution_id,
            [n.node_id for n in self.nodes.values()],
        )

        self.results = {}
        node_status: Dict[str, str] = {n: "PENDING" for n in self.nodes}
        executed: Set[str] = set()

        checkpoint = await asyncio.to_thread(checkpoint_db.get_checkpoint, execution_id)
        if checkpoint:
            for name, state in checkpoint.items():
                self.results[name] = {
                    "output": state.get("result_data"),
                    "status": "COMPLETED",
                    "success": True,
                }
                node_status[name] = "COMPLETED"
                executed.add(name)
                await asyncio.to_thread(exec_registry.complete, execution_id, name)

        start_time = time.time()

        while len(executed) < len(self.nodes):
            # Escalonamento: Filtra nós prontos
            ready = [
                name
                for name, node in self.nodes.items()
                if node_status.get(name) == "PENDING"
                and all(
                    node_status.get(d) == "COMPLETED" for d in (node.depends_on or [])
                )
            ]

            if not ready:
                if len(executed) == len(self.nodes):
                    break
                raise RuntimeError(f"Deadlock detectado: {execution_id}")

            # Execução Concorrente Máxima
            tasks = {
                name: self._execute_node_async(self.nodes[name], input_data)
                for name in ready
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            for name, result in zip(tasks.keys(), results):
                node = self.nodes[name]
                executed.add(name)

                # Tratamento de Erro e Sanity Barrier
                if isinstance(result, Exception) or not (
                    isinstance(result, dict) and result.get("success")
                ):
                    error_msg = (
                        str(result.get("error", "Failed"))
                        if isinstance(result, dict)
                        else str(result)
                    )
                    node_status[name] = "FAILED"
                    await asyncio.to_thread(
                        checkpoint_db.update_node_status,
                        execution_id,
                        name,
                        "FAILED",
                        error_message=error_msg,
                    )

                    if node.critical:
                        logger.warning(
                            "🛡️ [PARALLEL] Sanity Barrier: abortando dependentes de '%s'",
                            name,
                        )
                        await self._abort_dependent_nodes_async(
                            execution_id, name, error_msg
                        )
                        # Atualiza status local dos dependentes abortados
                        for dep in self._find_dependents(name):
                            node_status[dep] = "ABORTED"
                            executed.add(dep)
                else:
                    self.results[name] = result
                    node_status[name] = "COMPLETED"
                    await asyncio.to_thread(
                        checkpoint_db.update_node_status,
                        execution_id,
                        name,
                        "COMPLETED",
                    )
                    await asyncio.to_thread(
                        exec_registry.complete_node,
                        execution_id,
                        node.node_id,
                        result.get("result_text", ""),
                    )

        return self._aggregate(time.time() - start_time, execution_id)

    async def restart_node_async(
        self, execution_id: str, node_id: str
    ) -> Dict[str, Any]:
        """Reinicia um nó específico de forma assíncrona."""
        logger.info(
            "🔄 [ASYNC] Restart node: %s | execution_id=%s", node_id, execution_id
        )

        if node_id not in self.nodes:
            raise ValueError(f"Node '{node_id}' não encontrado no grafo")

        # Reset via thread para não bloquear o loop
        await asyncio.to_thread(checkpoint_db.reset_failed_node, execution_id, node_id)

        # Re-executa o fluxo (aqui você pode chamar run_parallel ou async_run)
        context = {"task": "", "metadata": {"ts": time.time(), "restart": True}}
        return await self.run_parallel(context, execution_id=execution_id)

    def _get_output_text(self, result: dict) -> str:
        """Extração robusta de texto com suporte a artefatos."""
        output = result.get("output")
        if hasattr(output, "code"):
            texts = [output.code or ""]
            if hasattr(output, "files") and output.files:
                texts.extend(output.files.values())
            return "\n\n".join(t for t in texts if t)

        if isinstance(output, str):
            return output

        return result.get("result_text") or str(output or "")

    def _aggregate(
        self, duration: float, execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Agregação final com seleção baseada em pontuação (score)."""
        scored = []
        any_success = False
        for name, r in self.results.items():
            if isinstance(r, dict) and r.get("success"):
                any_success = True
                output_text = self._get_output_text(r)
                if output_text:
                    score = self._compute_score(name, r)
                    scored.append((output_text, score, name))

        import re as _re

        _parece_codigo = lambda t: bool(
            t
            and (
                _re.search(r"<!DOCTYPE\s+html", t)
                or _re.search(r"<html[\s>]", t)
                or _re.search(r"<head[\s>]", t)
                or _re.search(r"<body[\s>]", t)
                or _re.search(r"<script[\s>]", t)
                or _re.search(r"<style[\s>]", t)
                or _re.search(r"^import\s+\w+", t, _re.MULTILINE)
                or _re.search(r"^from\s+\w+\s+import", t, _re.MULTILINE)
                or _re.search(r"^def\s+\w+\s*\(", t, _re.MULTILINE)
                or _re.search(r"^class\s+\w+", t, _re.MULTILINE)
                or _re.search(r"^async\s+def\s+\w+", t, _re.MULTILINE)
                or _re.search(r"^function\s+\w+\s*\(", t, _re.MULTILINE)
                or _re.search(r"^const\s+\w+\s*=", t, _re.MULTILINE)
                or _re.search(r"^let\s+\w+\s*=", t, _re.MULTILINE)
                or _re.search(r"^var\s+\w+\s*=", t, _re.MULTILINE)
            )
        )

        final_text = ""
        if scored:
            # Filtra: só output que pareça código executável
            code_scored = [(t, s, n) for t, s, n in scored if _parece_codigo(t)]
            if code_scored:
                code_scored.sort(key=lambda x: x[1], reverse=True)
                final_text = code_scored[0][0]
                logger.info(
                    "🏆 Melhor codigo: %s (score=%.2f)",
                    code_scored[0][2],
                    code_scored[0][1],
                )
            else:
                scored.sort(key=lambda x: x[1], reverse=True)
                final_text = scored[0][0]
                logger.info(
                    "🏆 Melhor resultado (fallback sem codigo): %s (score=%.2f)",
                    scored[0][2],
                    scored[0][1],
                )
        elif self.results:
            fallback_candidates = []
            for name, r in self.results.items():
                if not isinstance(r, dict):
                    continue
                text = self._get_output_text(r)
                if not _parece_codigo(text):
                    continue
                priority = 3 if name in self._CODE_NODE_PRIORITY else 1
                fallback_candidates.append((priority, len(text), text, name))
            fallback_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            final_text = fallback_candidates[0][2] if fallback_candidates else ""
            logger.info(
                "[DEBUG-AGG] fallback winner: %s (p=%d, len=%d)",
                fallback_candidates[0][3] if fallback_candidates else "NONE",
                fallback_candidates[0][0] if fallback_candidates else 0,
                fallback_candidates[0][1] if fallback_candidates else 0,
            )

        return {
            "success": any_success,
            "execution_time": duration,
            "nodes_executed": len(self.results),
            "final_output": final_text,
            "raw_results": self.results,
            "execution_id": execution_id or "",
        }

    _CODE_NODE_PRIORITY = {
        "integrator",
        "coder",
        "debug_coder",
        "api_builder",
        "backend_builder",
        "frontend_builder",
        "database_builder",
        "multi_coder",
        "artifact_writer",
    }

    def _compute_score(self, node_name: str, result: dict) -> float:
        score = 0.0
        output_text = self._get_output_text(result)
        code_len = len(output_text)

        # 1. Bônus para nós que produzem código substancial (50%)
        if code_len >= 200:
            code_quality = min(1.0, code_len / 3000.0)
            score += code_quality * 0.40
        if node_name in self._CODE_NODE_PRIORITY:
            score += 0.10

        # 2. Qualidade Funcional (Testes: 20%)
        tests_passed = max(0, int(result.get("tests_passed", 0)))
        tests_total = max(0, int(result.get("tests_total", 0)))
        if tests_total > 0:
            score += (tests_passed / tests_total) * 0.20

        # 3. Avaliação de Critic (15%)
        critic_score = max(0.0, min(100.0, float(result.get("critic_score", 0))))
        score += (critic_score / 100.0) * 0.15

        # 4. Validação de Segurança (10%)
        if result.get("security_valid", True):
            score += 0.10

        # 5. Performance/Latência (5%)
        latency = max(0.001, float(result.get("latency", 1.0)))
        perf = max(0.0, 1.0 - min(latency / 30.0, 1.0))
        score += perf * 0.05

        return round(score, 4)

    def snapshot(self) -> Dict[str, Any]:
        """
        Retorna uma representação serializável do estado atual do grafo.
        Ideal para persistência de checkpoint ou auditoria de evolução (evo).
        """
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
                    # Métricas dinâmicas garantidas como tipos primitivos
                    "success_rate": float(node.success_rate),
                    "avg_latency": float(node.avg_latency),
                    "executions": int(node.executions),
                    "critical": getattr(
                        node, "critical", False
                    ),  # Incluído para consistência com a Sanity Barrier
                }
                for name, node in self.nodes.items()
            },
            "timestamp": time.time(),  # Útil para controle de versão do snapshot
        }
