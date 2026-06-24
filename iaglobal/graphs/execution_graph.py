# iaglobal/graphs/execution_graph.py

import asyncio
import time
import uuid
import hashlib
import ast
import threading


from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Set, List, Tuple

from iaglobal.utils.logger import logger
from iaglobal.utils.hash_utils import LineageID

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
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.instrumentation import trace_node_execution, trace_node_completed
from iaglobal.execution.cpu_affinity import cpu_affinity
from iaglobal.immunity.loop_detector import LoopDetector
from iaglobal.evolution.homeostasis_controller import homeostasis_controller
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage


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
        self._homeostasis = homeostasis_controller  # Import singleton
        # Inject reflexion function into loop detector for auto-repair
        try:
            from iaglobal.reflection.reflexion_engine import reflexion_callback_for_loop
            self._loop_detector.set_reflexion_fn(reflexion_callback_for_loop)
        except ImportError:
            logger.warning("[IMMUNITY] ReflexionEngine não disponível - loop repair desativado")
        
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
        node_name = getattr(node, 'name', None)
        if node_name and node_name not in self.nodes:
            self.nodes[node_name] = node
            self._update_graph_hash()
            return node
        strategy = getattr(node, 'strategy', 'default')
        payload = getattr(node, 'payload', getattr(node, 'run', str(node)))
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
        cpu_affinity.pin_to_hash(node.name)
        
        await self.bus.publish(AgentMessage(
            sender="execution_graph", receiver=node.name,
            type="node_start", payload={"node": node.name, "time": time.time()},
        ))
        
        # 2. Lock via thread (Node.acquire é síncrono)
        if not await asyncio.to_thread(node.acquire):
            return {
                "output": None, "latency": 0.0, "success": False,
                "error": f"Node '{node.name}' já está em execução (lock)", 
                "result_text": ""
            }

        start = time.time()
        raw_task = str(input_data.get("task", ""))
        exec_id = str(input_data.get("metadata", {}).get("execution_id", raw_task))
        workdir = make_workdir(node.name, exec_id, raw_task)

        ctx = {"input": input_data, "memory": self.results, "workdir": workdir}
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
                    await workdir.async_append_log(f"contrato insatisfeito: {str(e)[:80]} — fallback")

            # Fallback para node.run
            if not executed and node.run:
                try:
                    result = node.run(ctx)
                    if asyncio.iscoroutine(result):
                        result = await result
                    executed = True
                except Exception:
                    node_run_failed = True
                    raise

#====================================================================================================

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
                                content=result_text, type="code",
                                metadata={"task": task_ref, "score": getattr(result_raw, "score", 0), 
                                          "node": node.name, "evo": True},
                            )
                    else:
                        result_text = str(result_raw) if result_raw is not None else ""
                else:
                    result_raw = result if hasattr(result, "code") else None
                    result_text = result.code if hasattr(result, "code") else str(result)

                if isinstance(result, dict) and result.get("skipped"):
                    logger.info("[GRAPH] Nó '%s' pulado (single-run já executada)", node.name)

            # 2. Caso o nó não tenha retornado nada útil, dispara o Bandit Policy
            if not result_text and not node_run_failed:
                from iaglobal.graphs.bandit import BanditPolicy
                bandit = BanditPolicy(credit=self.credit)
                
                chosen_model = await asyncio.to_thread(bandit.select_model, node.name, node.strategy)
                result_text = await bandit.async_execute_model(
                    model=chosen_model, prompt=raw_task, task_type=node.strategy
                )

            # 3. Validação final do sucesso
            if result_text:
                success = True
                await workdir.async_write_code(result_text)
                await workdir.async_append_log("executado com sucesso")
            elif contract_error:
                last_error = contract_error

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
        if 'bandit' in locals() and 'chosen_model' in locals() and success:
            try:
                await asyncio.to_thread(
                    bandit.update_policy,
                    node=node.name,
                    model=chosen_model,
                    strategy=node.strategy,
                    success=success,
                    latency=latency,
                    reward=1.0 if success else 0.0
                )
            except Exception as e_train:
                logger.warning(f"[GRAPH-ASYNC] Falha ao atualizar bandit: {e_train}")
        
        # Gravação de métricas do nó (Node.record é síncrono)
        await asyncio.to_thread(node.record, success, latency, last_error)

        # Publicação no barramento de eventos (AcetylcholineBus.publish é async)
        await self.bus.publish(AgentMessage(
            sender=node.name, receiver="execution_graph",
            type="node_complete",
            payload={"node": node.name, "success": success, "latency": latency},
        ))

        # Check de imunidade (LoopDetector.check_and_repair é síncrono)
        loop_check = await asyncio.to_thread(
            self._loop_detector.check_and_repair, node.name, success, ctx
        )
        if loop_check.get("in_loop"):
            logger.warning("🛡️ [IMMUNITY-ASYNC] Loop detectado no nó '%s' (%d execuções)",
                         node.name, loop_check.get("executions", 0))
            if loop_check.get("repair_triggered"):
                logger.info("🛡️ [IMMUNITY-ASYNC] Reparação auto-triggered: %s", loop_check.get("repair_result", {}).get("status", "unknown"))

        # Tracing final
        trace = trace_node_completed(trace, {
            "output": result_raw if result_raw is not None else result_text, 
            "latency": latency, 
            "success": success
        }, ctx)
        
        # Registro de homeostase (SLA metrics)
        cost_usd = extra_fields.get("cost", 0.0)
        self._homeostasis.record_execution(success, latency * 1000, cost_usd)

        logger.debug("[TRACE] node=%s duration=%.1fms", node.name, trace.get("duration_ms", 0))

        return {
            "output": result_raw if result_raw is not None else result_text,
            "latency": latency,
            "success": success,
            "error": last_error,
            "result_text": result_text,
            **extra_fields,
        }

    async def _abort_dependent_nodes_async(
        self, execution_id: str, failed_node_name: str, reason: str
    ):
        """Abortamento assíncrono em cascata (Sanity Barrier)."""
        dependents = set()

        def _find_dependents(node_name: str):
            for n_name, n_node in self.nodes.items():
                if failed_node_name in n_node.depends_on and n_name not in dependents:
                    dependents.add(n_name)
                    _find_dependents(n_name)
        
        _find_dependents(failed_node_name)

        if not dependents:
            return

        # Execução paralela dos abortos para não bloquear o loop
        tasks = []
        for dep_name in dependents:
            logger.warning("🛡️ [SANITY BARRIER] Abortando nó '%s' por falha em '%s'", dep_name, failed_node_name)
            
            # Atualização em memória
            self.results[dep_name] = {
                "error": f"Abortado pela Sanity Barrier: falha em '{failed_node_name}'",
                "node": dep_name,
                "status": "ABORTED",
                "success": False,
            }
            
            # Atualização assíncrona no DB
            tasks.append(checkpoint_db.update_node_status_async(
                execution_id, dep_name, "ABORTED",
                error_message=f"Abortado pela Sanity Barrier: nó crítico '{failed_node_name}' falhou: {reason}"
            ))
        
        # Aguarda todas as atualizações de status no banco de dados em paralelo
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def async_run(
        self, input_data: Dict[str, Any], execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        execution_id = execution_id or str(uuid.uuid4())
        input_data.setdefault("metadata", {})["execution_id"] = execution_id
        task_text = str(input_data.get("task", input_data.get("input", {}).get("task", "")))
        input_data["_task_text"] = task_text

        logger.info("🚀 [ASYNC] Iniciando execução orquestrada: %s", execution_id)
        
        # Canonicalização e Hash do Grafo
        self.nodes = canonicalize(self.nodes)
        self._graph_hash = compute_graph_hash(self.nodes)
        
        # Inicialização do Registro
        await asyncio.to_thread(exec_registry.init_execution, execution_id, [n.node_id for n in self.nodes.values()])
        
        self.results = {}
        executed: Set[str] = set()

        # Carregamento de checkpoint assíncrono
        checkpoint = await asyncio.to_thread(checkpoint_db.get_checkpoint, execution_id)
        if checkpoint:
            for node_name, state in checkpoint.items():
                self.results[node_name] = {"output": state.get("result_data"), "status": "COMPLETED", "success": True}
                executed.add(node_name)
                await asyncio.to_thread(exec_registry.complete_node, execution_id, node_name)

        start_time = time.time()

        while len(executed) < len(self.nodes):
            ready_nodes = []
            for name, node in self.nodes.items():
                if name in executed: continue
                if not all(dep in executed for dep in node.depends_on): continue
                
                # Checagem de status assíncrona
                if await asyncio.to_thread(exec_registry.was_executed, execution_id, node.node_id):
                    executed.add(name); continue
                
                # Lógica de ABORT (usando métodos assíncronos)
                # ... (manter lógica de checagem de dependência) ...
                
                if await asyncio.to_thread(exec_registry.claim, execution_id, node.node_id):
                    ready_nodes.append((name, node, node.node_id))

            if not ready_nodes:
                if len(executed) == len(self.nodes): break
                raise RuntimeError(f"Deadlock detectado: {execution_id}")

            # Execução em batch assíncrono
            tasks = [self._execute_node_async(node, input_data) for name, node, node_id in ready_nodes]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (name, node, node_id), result in zip(ready_nodes, results):
                if isinstance(result, Exception) or not result.get("success"):
                    error_msg = str(result.get("error", "Execution Failed")) if isinstance(result, dict) else str(result)
                    await asyncio.to_thread(checkpoint_db.update_node_status, execution_id, name, "FAILED", error_message=error_msg)
                    if node.critical:
                        await self._abort_dependent_nodes_async(execution_id, name, error_msg)
                else:
                    self.results[name] = result
                    await asyncio.to_thread(checkpoint_db.update_node_status, execution_id, name, "COMPLETED")
                
                executed.add(name)

        return self._aggregate(time.time() - start_time, execution_id)

    async def run_parallel(
        self, input_data: Dict[str, Any], execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        execution_id = execution_id or str(uuid.uuid4())
        input_data.setdefault("metadata", {})["execution_id"] = execution_id
        task_text = str(input_data.get("task", input_data.get("input", {}).get("task", "")))
        input_data["_task_text"] = task_text

        logger.info("⚡ [PARALLEL] Iniciando fluxo concorrente: %s", execution_id)

        self.nodes = canonicalize(self.nodes)
        self._graph_hash = compute_graph_hash(self.nodes)

        await asyncio.to_thread(exec_registry.init_execution, execution_id, [n.node_id for n in self.nodes.values()])
        
        self.results = {}
        node_status: Dict[str, str] = {n: "PENDING" for n in self.nodes}
        executed: Set[str] = set()

        checkpoint = await asyncio.to_thread(checkpoint_db.get_checkpoint, execution_id)
        if checkpoint:
            for name, state in checkpoint.items():
                self.results[name] = {"output": state.get("result_data"), "status": "COMPLETED", "success": True}
                node_status[name] = "COMPLETED"
                executed.add(name)
                await asyncio.to_thread(exec_registry.complete, execution_id, name)

        start_time = time.time()

        while len(executed) < len(self.nodes):
            # Escalonamento: Filtra nós prontos
            ready = [
                name for name, node in self.nodes.items()
                if node_status.get(name) == "PENDING" and all(node_status.get(d) == "COMPLETED" for d in (node.depends_on or []))
            ]

            if not ready:
                if len(executed) == len(self.nodes): break
                raise RuntimeError(f"Deadlock detectado: {execution_id}")

            # Execução Concorrente Máxima
            tasks = {name: self._execute_node_async(self.nodes[name], input_data) for name in ready}
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            for name, result in zip(tasks.keys(), results):
                node = self.nodes[name]
                executed.add(name)
                
                # Tratamento de Erro e Sanity Barrier
                if isinstance(result, Exception) or not (isinstance(result, dict) and result.get("success")):
                    error_msg = str(result.get("error", "Failed")) if isinstance(result, dict) else str(result)
                    node_status[name] = "FAILED"
                    await asyncio.to_thread(checkpoint_db.update_node_status, execution_id, name, "FAILED", error_message=error_msg)
                    
                    if node.critical:
                        logger.warning("🛡️ [PARALLEL] Sanity Barrier: abortando dependentes de '%s'", name)
                        await self._abort_dependent_nodes_async(execution_id, name, error_msg)
                        # Atualiza status local dos dependentes abortados
                        for dep in self._find_dependents(name):
                            node_status[dep] = "ABORTED"
                            executed.add(dep)
                else:
                    self.results[name] = result
                    node_status[name] = "COMPLETED"
                    await asyncio.to_thread(checkpoint_db.update_node_status, execution_id, name, "COMPLETED")
                    await asyncio.to_thread(exec_registry.complete_node, execution_id, node.node_id, result.get("result_text", ""))

        return self._aggregate(time.time() - start_time, execution_id)

    async def restart_node_async(self, execution_id: str, node_id: str) -> Dict[str, Any]:
        """Reinicia um nó específico de forma assíncrona."""
        logger.info("🔄 [ASYNC] Restart node: %s | execution_id=%s", node_id, execution_id)

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

    def _aggregate(self, duration: float, execution_id: Optional[str] = None) -> Dict[str, Any]:
        """Agregação final com seleção baseada em pontuação (score)."""
        scored = []
        for name, r in self.results.items():
            if isinstance(r, dict) and r.get("success"):
                output_text = self._get_output_text(r)
                if output_text:
                    score = self._compute_score(name, r)
                    scored.append((output_text, score, name))

        final_text = ""
        if scored:
            scored.sort(key=lambda x: x[1], reverse=True)
            final_text = scored[0][0]
            logger.info("🏆 Melhor resultado: %s (score=%.2f)", scored[0][2], scored[0][1])
        elif self.results:
            # Fallback para o texto mais longo caso nenhum tenha pontuação
            final_text = max((self._get_output_text(r) for r in self.results.values() if isinstance(r, dict)), 
                             key=len, default="")

        return {
            "success": True,
            "execution_time": duration,
            "nodes_executed": len(self.results),
            "final_output": final_text,
            "raw_results": self.results,
            "execution_id": execution_id or "",
        }

    def _compute_score(self, node_name: str, result: dict) -> float:
        """
        Calcula o score de qualidade do nó com normalização de segurança.
        Escala: 0.0 a 1.0.
        """
        score = 0.0

        # 1. Qualidade Funcional (Testes: 50% + 10% bônus)
        tests_passed = max(0, int(result.get("tests_passed", 0)))
        tests_total = max(0, int(result.get("tests_total", 0)))
        if tests_total > 0:
            score += (tests_passed / tests_total) * 0.50
            if tests_passed == tests_total:
                score += 0.10

        # 2. Avaliação de Critic (20%)
        critic_score = max(0.0, min(100.0, float(result.get("critic_score", 0))))
        score += (critic_score / 100.0) * 0.20

        # 3. Validação de Segurança (15%)
        if result.get("security_valid", True):
            score += 0.15

        # 4. Simplicidade/Concisão (10%) - Penaliza código excessivamente longo
        output_text = self._get_output_text(result)
        code_len = len(output_text)
        # 5000 caracteres é o teto para penalidade total
        simplicity = max(0.0, 1.0 - min(code_len / 5000.0, 1.0))
        score += simplicity * 0.10

        # 5. Performance/Latência (5%) - Penaliza latência acima de 30s
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
                    "critical": getattr(node, "critical", False) # Incluído para consistência com a Sanity Barrier
                }
                for name, node in self.nodes.items()
            },
            "timestamp": time.time() # Útil para controle de versão do snapshot
        }
