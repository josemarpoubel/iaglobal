import asyncio
import time
import uuid
import logging
import atexit
import threading
from typing import Optional, Dict, Any, List

from iaglobal._paths import DATA_DIR, BACKUP_DIR
from iaglobal.models.event_bus import EventBus, EventType
from iaglobal.core.decision_engine import DecisionEngine
from iaglobal.pipeline.engine import PipelineEngine
from iaglobal.memory.memory_storage import storage
from iaglobal.memory.backup_manager import MemoryManager
from iaglobal.memory.db_manager import db as checkpoint_db
from iaglobal.reflection.reflexion_engine import ReflexionEngine
from iaglobal.providers.provider_router import route_generate, async_route_generate
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.tools.search import search_tool
from iaglobal.core.neuro_orchestrator import NeuroOrchestrator
from iaglobal.evolution.evolutionruntime import EvolutionRuntime
from iaglobal.evolution.self_optimizer import SelfOptimizingAgentSystem

from iaglobal.graphs import ExecutionGraph
from iaglobal.graphs.builder import build_default_graph
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.events import DecisionEvent, store as decision_store, dispatcher as decision_dispatcher
from iaglobal.events.decision_event import DecisionLock

logger = logging.getLogger("ORCHESTRATOR")

class Orchestrator:

    def __init__(
        self,
        planner=None,
        evolution_interval: int = 60,
        evolution_strategies: list[str] = None,
        mutation_rate: float = 0.1,
        model_fn: Optional[callable] = None,
    ):
        logger.info("🧠 Orchestrator inicializando...")

        from iaglobal.tools.tool_router import ToolRouter
        from iaglobal.graphs.execution_graph import ExecutionGraph

        self._model_fn = model_fn

        self.tool_router = ToolRouter(
            tools={
                "search": search_tool
            }
        )

        self.graph = ExecutionGraph(
            tool_router=self.tool_router
        )

        self._seed_pipeline_nodes()

        from iaglobal.evolution.evolutionengine import EvolutionEngine

        strategies = evolution_strategies or ["coding", "research", "fast", "explore"]

        self.evolver = EvolutionEngine(
            graph=self.graph,
            mutation_rate=mutation_rate,
            strategies=strategies
        )

        self.evolution_runtime = EvolutionRuntime(
            evolver=self.evolver,
            interval=evolution_interval
        )
        self.evolution_runtime.start()

        self.neuro = NeuroOrchestrator()
        self.bus = EventBus()
        self.decision_engine = DecisionEngine()
        self.pipeline = PipelineEngine(self)
        self.memory = storage
        self.memory_manager = MemoryManager(
            data_path=str(DATA_DIR),
            backup_path=str(BACKUP_DIR)
        )
        self.credit = CreditAssignmentEngine()
        self.bandit = BanditPolicy(self.credit)
        self.reflection = ReflexionEngine(model_fn=self._model_fn) if model_fn else None
        self.planner = planner
        self.tools = {"search": search_tool}

        self._register_events()
        decision_store.start()
        decision_dispatcher.start()

        self.graph.MAX_RETRY = 3

        atexit.register(self._shutdown)

        logger.info("✅ Orchestrator pronto.")

    def _seed_pipeline_nodes(self):
        graph = build_default_graph(self, "")
        for name, node in graph.nodes.items():
            if name not in self.graph.nodes:
                self.graph.add_node(node)
                logger.info(f"🧬 Pipeline node: {name}")

    def _register_events(self):
        from iaglobal.models.event_bus import EventType as ModelEventType
        self.bus.subscribe(ModelEventType.EXECUTION_COMPLETED, self._on_execution_completed)
        self.bus.subscribe(ModelEventType.EXECUTION_FAILED, self._on_execution_failed)
        self.bus.subscribe(ModelEventType.NODE_FAILED, self._on_node_failed)
        self.bus.subscribe(ModelEventType.EXECUTION_ABORTED, self._on_execution_aborted)
        self.bus.subscribe(ModelEventType.CRITICAL_NODE_FAILED, self._on_critical_node_failed)
        self.bus.subscribe(ModelEventType.SANITY_BARRIER_TRIGGERED, self._on_sanity_barrier_triggered)
        self.bus.subscribe(ModelEventType.MEMORY_SAVED, self._on_memory_saved)

    def _on_execution_completed(self, event):
        try:
            task = event.data.get("task", "")
            result = event.data.get("result", "")
            if task and result:
                self.memory.store(task, result, {"ts": time.time()})
        except Exception as e:
            logger.error(f"Storage subscriber error (success): {e}")

    def _on_execution_failed(self, event):
        try:
            from iaglobal.memory.memory_error import store_error
            store_error(
                prompt=event.data.get("task", ""),
                response_errada=event.data.get("error", ""),
                critica_sandbox="",
                codigo_corrigido=""
            )
        except Exception as e:
            logger.error(f"Storage subscriber error (failure): {e}")

    def _on_node_failed(self, event):
        try:
            execution_id = event.data.get("execution_id", "")
            node_id = event.data.get("node_id", "")
            retry_count = event.data.get("retry_count", 0)

            logger.info(f"🔁 Node failed: {node_id} | retry={retry_count} | exec={execution_id}")

            if retry_count < 3 and execution_id and node_id:
                self.graph.restart_node(execution_id, node_id)
                logger.info(f"✅ Restart automático acionado para {node_id}")
            else:
                logger.warning(f"⚠️ Limite de retries excedido para {node_id}, abortando.")
        except Exception as e:
            logger.error(f"Node failed handler error: {e}")

    def _on_execution_aborted(self, event):
        try:
            execution_id = event.data.get("execution_id", "")
            node_id = event.data.get("node_id", "")
            reason = event.data.get("reason", "")
            logger.warning(f"🚫 Execução abortada: {execution_id} | node={node_id} | reason={reason}")
            checkpoint_db.clear_execution(execution_id)
        except Exception as e:
            logger.error(f"Execution aborted handler error: {e}")

    def _on_critical_node_failed(self, event):
        try:
            execution_id = event.data.get("execution_id", "")
            node_id = event.data.get("node_id", "")
            error_msg = event.data.get("error", "")
            aborted = event.data.get("aborted_dependents", [])

            logger.warning(f"🚨 Nó crítico falhou: {node_id} | exec={execution_id} | erro={error_msg[:100]}")
            logger.warning(f"🚨 Dependentes abortados: {aborted}")

            self._analisar_falha_critica(node_id, error_msg, execution_id)
        except Exception as e:
            logger.error(f"Critical node failed handler error: {e}")

    def _on_sanity_barrier_triggered(self, event):
        try:
            from iaglobal.memory.memory_error import store_error
            failed_node = event.data.get("failed_node", "")
            error = event.data.get("error", "")
            reason = event.data.get("reason", "")
            logger.warning(f"🛡️ Sanity Barrier ativada! Falha: {failed_node} | Motivo: {reason}")
            store_error(
                prompt=f"sanity_barrier:{failed_node}",
                response=f"{reason} | {error[:200]}",
                critique="Sanity Barrier interrompeu pipeline para evitar execução sobre dados corrompidos",
                corrected="",
                error_type="SanityBarrier"
            )
        except Exception as e:
            logger.error(f"Sanity barrier handler error: {e}")

    def _analisar_falha_critica(self, node_id: str, error_msg: str, execution_id: str) -> str:
        try:
            prompt = (
                f"Analise a seguinte falha crítica em um sistema multi-agente:\n\n"
                f"Nó falho: {node_id}\n"
                f"Erro: {error_msg}\n"
                f"ID da Execução: {execution_id}\n\n"
                f"Diagnóstico:\n"
                f"1. Qual a causa raiz provável?\n"
                f"2. Como evitar esta falha no futuro?\n"
                f"3. Recomendações de melhoria para o sistema.\n\n"
                f"Seja objetivo e técnico."
            )

            try:
                from iaglobal.providers.provider_router import route_generate
                from iaglobal.providers.provider_config import ProviderConfig
                model = f"ollama/{ProviderConfig.DEFAULT_OLLAMA_MODEL or 'qwen2.5:0.5b'}"
                analise = route_generate(model=model, prompt=prompt, task_type="general")
            except Exception:
                analise = f"Falha crítica detectada no nó '{node_id}': {error_msg[:200]}. A análise automática não pôde ser gerada."

            logger.info(f"📊 Auto-análise de falha crítica [{node_id}]: {analise[:150]}")

            try:
                from iaglobal.memory.db_manager import db
                db.insert_insight(
                    agent=f"auto_analyst_{node_id}",
                    task_id=execution_id,
                    content=f"Falha crítica em {node_id}: {error_msg[:200]}\nAnálise: {analise[:500]}",
                    score=0.0
                )
                logger.info(f"💾 Insight de falha crítica salvo no banco para execução {execution_id}")
            except Exception as db_err:
                logger.error(f"Erro ao salvar insight de falha: {db_err}")

            return analise
        except Exception as e:
            logger.error(f"Falha no auto-analista crítico: {e}")
            return f"Falha ao analisar erro crítico: {e}"

    def _on_memory_saved(self, event):
        try:
            task = event.data.get("task", "")
            result = event.data.get("result", "")
            success = bool(result)
            latency = event.data.get("latency", 1.0)
            for node in self.graph.nodes.values():
                node.record(success=success, latency=latency)
        except Exception as e:
            logger.error(f"Evolution feed error: {e}")

    def _emit_decision(self, step: str, execution_id: str, **kwargs) -> DecisionEvent:
        event = DecisionEvent(step=step, execution_id=execution_id, **kwargs)
        logger.info(
            f"📝 [DECISION] {step}: {event.reason or event.action or event.status or event.selected or event.result or 'ok'}"
        )
        try:
            self.bus.publish(EventType.PIPELINE_STAGE, {
                "decision_event": event.to_dict(),
                "step": step,
            }, source="orchestrator._emit_decision")
        except Exception:
            pass
        return event

    def resolver(self, task: str):
        logger.info(f"🔍 Resolver: {task[:120]}")
        return self._process(task)

    def run(self, prompt: str, metadata: Optional[Dict[str, Any]] = None, force: bool = False):
        if force:
            try:
                self.memory.delete(prompt)
            except Exception:
                pass
        return self._process(prompt)

    def dispatch(self, task: str):
        return self._process(task)

    def process_task(self, task: str) -> str:
        return self._process(task)

    def orchestrate(self, task: str) -> str:
        return self._process(task)

    def _process(self, task: str, execution_id: Optional[str] = None):
        if not task or len(task.strip()) < 3:
            logger.error("[ORCH] Invalid task")
            return None

        start_time = time.time()
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        # =====================================================================
        # WARMUP: Carregar modelo local na RAM
        # =====================================================================
        try:
            from iaglobal.providers.ollama_provider import warmup
            warmup()
        except Exception:
            pass

        # =====================================================================
        # STAGE 0: PROMPT — Normalizar demanda
        # =====================================================================
        print(f"\n💬 Iniciando o prompt do usuario...")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 0: PROMPT")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        self._emit_decision("prompt", execution_id, action="normalize",
                            reason=f"task={task[:60]}... ({len(task)} chars)")
        payload = {"task": task, "ts": start_time, "execution_id": execution_id,
                   "stages": {}}

        try:
            self.evolver.set_task(task)
        except Exception as e:
            logger.warning("[ORCH] Evolver set_task error: %s", e)

        if self.planner:
            return self.planner.plan(task)

        # =====================================================================
        # STAGE 1: ANALYZE — Verificar memória, analisar requisitos
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 1: ANALYZE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["analyze"] = {"status": "running"}

        cached = self.memory.retrieve(task)
        if cached:
            codigo = cached.get("response") or cached.get("codigo") or ""
            score = cached.get("score", 0) or cached.get("metadata", {}).get("score", 0)
            is_invalid = (
                score < 0.1 or len(codigo) < 10
                or "<coroutine object" in codigo or codigo.startswith("<")
            )
            if is_invalid:
                logger.info("[ORCH] Analyze: cache invalido (score=%.2f) — registrando erro", score)
                self._emit_decision("analyze", execution_id, result="MISS",
                                    reason="cache invalido")
                try:
                    from iaglobal.memory.memory_error import store_error
                    store_error(task, codigo[:200], "cache_invalido", "",
                                error_type="CacheInvalid")
                except Exception:
                    pass
                try:
                    from iaglobal.memory.db_manager import db
                    import hashlib
                    db.insert_insight("orchestrator", hashlib.md5(task.encode()).hexdigest(),
                                      "Cache invalido: score=%.2f" % score, score=0.0)
                except Exception:
                    pass
            elif score >= 0.6 and len(codigo) > 50:
                logger.info("[ORCH] Analyze: MEMORY HIT (score=%.2f)", score)
                self._emit_decision("analyze", execution_id, result="HIT")
                payload["stages"]["analyze"] = {"status": "done", "hit": True}
                payload["stages"]["deliver"] = {"status": "done", "from_cache": True}
                return cached
            else:
                logger.info("[ORCH] Analyze: cache abaixo do limiar — sera sobrescrito")
        else:
            self._emit_decision("analyze", execution_id, result="MISS")
        payload["stages"]["analyze"] = {"status": "done", "hit": False}

        # =====================================================================
        # STAGE 2: PLAN — Selecionar estratégia e provedores
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 2: PLAN")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["plan"] = {"status": "running"}

        _default_ollama_model = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        candidates = [
            f"ollama/{_default_ollama_model}",
            "nvidia/meta/llama-3.3-70b-instruct",
            "openrouter/meta-llama/llama-3.1-8b-instruct",
        ]
        self._emit_decision("plan", execution_id, action="candidate_selection",
                            candidates=list(candidates))

        chosen_model = self.bandit.select_model(
            node="cognitive_dag_root", strategy="dev_fast", candidates=candidates,
        )
        current_score = self.credit.score("cognitive_dag_root", chosen_model, "dev_fast")
        scores_snapshot = {m: self.credit.score("cognitive_dag_root", m, "dev_fast")
                          for m in candidates}

        payload["route"] = {"model": chosen_model, "score": current_score}
        is_exploration = chosen_model != candidates[0] if candidates else False
        self._emit_decision("plan", execution_id, selected=chosen_model,
                            scores_snapshot=scores_snapshot, exploration=is_exploration)
        payload["stages"]["plan"] = {"status": "done", "model": chosen_model}

        # =====================================================================
        # STAGE 3: ALLOCATE — Travar recursos
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 3: ALLOCATE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["allocate"] = {"status": "running"}

        decision_lock = DecisionLock(
            execution_id=execution_id, selected_model=chosen_model,
            strategy="dev_fast", score=current_score,
            scores_snapshot=scores_snapshot,
        )
        payload["decision_lock"] = decision_lock.to_dict()
        self._emit_decision("allocate", execution_id, selected=chosen_model,
                            status="locked")
        payload["stages"]["allocate"] = {"status": "done", "locked": chosen_model}

        # =====================================================================
        # STAGE 4: EXECUTE — Rodar o DAG
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 4: EXECUTE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["execute"] = {"status": "running"}

        try:
            graph_result = self.run_graph_task(
                task, execution_id=execution_id, chosen_model=chosen_model,
                decision_lock=decision_lock,
            )
            payload["result"] = graph_result.get("final_output")
            payload["raw_results"] = graph_result.get("raw_results")
            payload["execution_id"] = graph_result.get("execution_id", execution_id)
            payload["stages"]["execute"]["status"] = "done"
        except Exception as e:
            logger.warning("[ORCH] Execute failed: %s", e)
            try:
                payload["result"] = route_generate(model=chosen_model, prompt=task, task_type="general")
                payload["raw_results"] = {"fallback": payload["result"]}
                payload["stages"]["execute"]["status"] = "done"
            except RuntimeError:
                logger.error("[ORCH] All providers failed.")
                context = self._execute_search(task)
                payload["result"] = "[DEGRADADO - Nenhum provider disponivel]\n" + context[:400]
                payload["raw_results"] = {"error": "All providers failed"}
                payload["stages"]["execute"]["status"] = "degraded"

        # =====================================================================
        # STAGE 5: MONITOR — Métricas de execução
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 5: MONITOR")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["monitor"] = {"status": "running"}

        success = bool(payload.get("result")) and len(payload.get("result", "")) > 50
        latency_ms = int((time.time() - payload["ts"]) * 1000)
        total_nodes = len(payload.get("raw_results", {})) if payload.get("raw_results") else 0
        result_len = len(payload.get("result", "")) if payload.get("result") else 0

        self._emit_decision("monitor", execution_id, selected=chosen_model,
                            reward_signal=0.9 if success else 0.0,
                            latency_ms=latency_ms,
                            metadata={"success": success, "nodes": total_nodes, "chars": result_len})
        payload["stages"]["monitor"] = {
            "status": "done", "success": success, "latency_ms": latency_ms,
            "total_nodes": total_nodes, "result_chars": result_len,
        }
        logger.info("[ORCH] Monitor: success=%s latency=%dms nodes=%d chars=%d",
                     success, latency_ms, total_nodes, result_len)

        # =====================================================================
        # STAGE 6: VALIDATE — Verificar qualidade
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 6: VALIDATE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["validate"] = {"status": "running"}

        VALIDATION_THRESHOLD = 0.1
        validation_score = 0.0
        if payload.get("result"):
            validation_score = min(1.0, result_len / 500.0)
            logger.info("[ORCH] Validate: score=%.2f (len=%d) threshold=%.1f",
                         validation_score, result_len, VALIDATION_THRESHOLD)
        else:
            logger.warning("[ORCH] Validate: resultado vazio")

        validation_passed = validation_score >= VALIDATION_THRESHOLD
        payload["stages"]["validate"] = {
            "status": "done",
            "score": validation_score,
            "passed": validation_passed,
            "threshold": VALIDATION_THRESHOLD,
        }

        if not validation_passed:
            logger.warning("[ORCH] Validate: FALHOU (score=%.2f < %.1f) — bloqueando entrega",
                           validation_score, VALIDATION_THRESHOLD)

        # =====================================================================
        # STAGE 7: CONSOLIDATE — Agregar resultados
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 7: CONSOLIDATE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["consolidate"] = {"status": "running"}

        raw = payload.get("raw_results", {})
        final_artifact = None
        for r in (raw or {}).values():
            if isinstance(r, dict):
                out = r.get("output")
                if out and hasattr(out, "code"):
                    final_artifact = out
                    break

        consolidated = {
            "result": payload.get("result", ""),
            "artifact": final_artifact.code if final_artifact and hasattr(final_artifact, 'code') else None,
            "execution_id": execution_id,
            "model": chosen_model,
        }
        payload["consolidated"] = consolidated
        payload["stages"]["consolidate"] = {"status": "done"}

        # =====================================================================
        # STAGE 8: DELIVER — Persistir e retornar (bloqueado se validate falhou)
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 8: DELIVER")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["deliver"] = {"status": "running"}

        if validation_passed:
            try:
                self.memory.store(
                    payload["task"], payload["result"],
                    {"ts": time.time(), "model": chosen_model, "execution_id": execution_id},
                )
                self._emit_decision("deliver", execution_id, status="stored")
                payload["stages"]["deliver"]["status"] = "done"
                logger.info("[ORCH] Deliver: resultado persistido (%d chars)", result_len)
            except Exception as e:
                logger.error("[ORCH] Deliver error: %s", e)
                payload["stages"]["deliver"]["status"] = "error"
        else:
            logger.warning("[ORCH] Deliver: BLOQUEADO — validate falhou (score=%.2f)", validation_score)
            payload["stages"]["deliver"]["status"] = "blocked_by_validation"
            self._emit_decision("deliver", execution_id, status="blocked",
                                reason="validation_score=%.2f<threshold=%.1f" %
                                (validation_score, VALIDATION_THRESHOLD))

        # =====================================================================
        # STAGE 9: MEASURE RESULTS — KPIs
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 9: MEASURE RESULTS")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["measure"] = {"status": "running"}

        total_time = time.time() - start_time
        kpis = {
            "total_time_s": round(total_time, 2),
            "latency_ms": latency_ms,
            "validation_score": round(validation_score, 2),
            "result_chars": result_len,
            "total_nodes": total_nodes,
            "success": success,
            "model": chosen_model,
        }
        payload["kpis"] = kpis
        logger.info("[ORCH] Measure: total_time=%.2fs validation=%.2f nodes=%d success=%s",
                     total_time, validation_score, total_nodes, success)
        self._emit_decision("measure", execution_id, metadata=kpis)
        payload["stages"]["measure"] = {"status": "done", "kpis": kpis}

        # =====================================================================
        # STAGE 10: IMPROVE — Feedback loop
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  STAGE 10: IMPROVE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["improve"] = {"status": "running"}

        try:
            from iaglobal.memory.db_manager import db
            import hashlib
            task_id = hashlib.md5(task.encode()).hexdigest()
            db.insert_insight("orchestrator", task_id,
                              "Ciclo completo: model=%s time=%.1fs score=%.2f nodes=%d" %
                              (chosen_model, total_time, validation_score, total_nodes),
                              score=validation_score)

            if not success:
                try:
                    from iaglobal.memory.memory_error import store_error
                    store_error(task, str(payload.get("result", ""))[:200],
                                "execucao falhou: validacao=%.2f" % validation_score,
                                "", error_type="OrchestrationFailure")
                except Exception:
                    pass
        except Exception:
            pass
        payload["stages"]["improve"] = {"status": "done"}

        total_elapsed = time.time() - start_time
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  CICLO COMPLETO: %.2fs | %d stages | success=%s",
                     total_elapsed, len(payload["stages"]), success)
        logger.info("[ORCH] ═══════════════════════════════════════════════")

        if final_artifact and hasattr(final_artifact, 'code') and final_artifact.code:
            return final_artifact.code

        return payload.get("result", "")

    async def _async_process(self, task: str, execution_id: Optional[str] = None):
        if not task or len(task.strip()) < 3:
            logger.error("[ORCH] Invalid task")
            return None

        start_time = time.time()
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        try:
            from iaglobal.providers.ollama_provider import warmup
            await asyncio.to_thread(warmup)
        except Exception:
            pass

        print(f"\n💬 Iniciando o prompt do usuario (async)...")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 0: PROMPT")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        self._emit_decision("prompt", execution_id, action="normalize",
                            reason=f"task={task[:60]}... ({len(task)} chars)")
        payload = {"task": task, "ts": start_time, "execution_id": execution_id,
                   "stages": {}}

        try:
            self.evolver.set_task(task)
        except Exception as e:
            logger.warning("[ORCH] Evolver set_task error: %s", e)

        if self.planner:
            return self.planner.plan(task)

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 1: ANALYZE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["analyze"] = {"status": "running"}

        cached = await asyncio.to_thread(self.memory.retrieve, task)
        if cached:
            codigo = cached.get("response") or cached.get("codigo") or ""
            score = cached.get("score", 0) or cached.get("metadata", {}).get("score", 0)
            is_invalid = (
                score < 0.1 or len(codigo) < 10
                or "<coroutine object" in codigo or codigo.startswith("<")
            )
            if is_invalid:
                logger.info("[ORCH] Analyze: cache invalido (score=%.2f) — registrando erro", score)
                self._emit_decision("analyze", execution_id, result="MISS",
                                    reason="cache invalido")
            elif score >= 0.6 and len(codigo) > 50:
                logger.info("[ORCH] Analyze: MEMORY HIT (score=%.2f)", score)
                self._emit_decision("analyze", execution_id, result="HIT")
                payload["stages"]["analyze"] = {"status": "done", "hit": True}
                payload["stages"]["deliver"] = {"status": "done", "from_cache": True}
                return cached
            else:
                logger.info("[ORCH] Analyze: cache abaixo do limiar — sera sobrescrito")
        else:
            self._emit_decision("analyze", execution_id, result="MISS")
        payload["stages"]["analyze"] = {"status": "done", "hit": False}

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 2: PLAN")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["plan"] = {"status": "running"}

        _default_ollama_model = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        candidates = [
            f"ollama/{_default_ollama_model}",
            "nvidia/meta/llama-3.3-70b-instruct",
            "openrouter/meta-llama/llama-3.1-8b-instruct",
        ]
        self._emit_decision("plan", execution_id, action="candidate_selection",
                            candidates=list(candidates))

        chosen_model = self.bandit.select_model(
            node="cognitive_dag_root", strategy="dev_fast", candidates=candidates,
        )
        current_score = self.credit.score("cognitive_dag_root", chosen_model, "dev_fast")
        payload["route"] = {"model": chosen_model, "score": current_score}
        self._emit_decision("plan", execution_id, selected=chosen_model)
        payload["stages"]["plan"] = {"status": "done", "model": chosen_model}

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 3: ALLOCATE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["allocate"] = {"status": "running"}
        decision_lock = DecisionLock(
            execution_id=execution_id, selected_model=chosen_model,
            strategy="dev_fast", score=current_score,
        )
        payload["decision_lock"] = decision_lock.to_dict()
        self._emit_decision("allocate", execution_id, selected=chosen_model, status="locked")
        payload["stages"]["allocate"] = {"status": "done", "locked": chosen_model}

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 4: EXECUTE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["execute"] = {"status": "running"}

        try:
            graph_result = await self.async_run_graph_task(
                task, execution_id=execution_id, chosen_model=chosen_model,
                decision_lock=decision_lock,
            )
            payload["result"] = graph_result.get("final_output")
            payload["raw_results"] = graph_result.get("raw_results")
            payload["execution_id"] = graph_result.get("execution_id", execution_id)
            payload["stages"]["execute"]["status"] = "done"
        except Exception as e:
            logger.warning("[ORCH] Async execute failed: %s", e)
            try:
                payload["result"] = await async_route_generate(model=chosen_model, prompt=task, task_type="general")
                payload["raw_results"] = {"fallback": payload["result"]}
                payload["stages"]["execute"]["status"] = "done"
            except RuntimeError:
                logger.error("[ORCH] All providers failed.")
                context = await asyncio.to_thread(self._execute_search, task)
                payload["result"] = "[DEGRADADO - Nenhum provider disponivel]\n" + context[:400]
                payload["raw_results"] = {"error": "All providers failed"}
                payload["stages"]["execute"]["status"] = "degraded"

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC STAGE 5-10 (sync reusing logic)")
        logger.info("[ORCH] ═══════════════════════════════════════════════")

        success = bool(payload.get("result")) and len(payload.get("result", "")) > 50
        latency_ms = int((time.time() - payload["ts"]) * 1000)
        total_nodes = len(payload.get("raw_results", {})) if payload.get("raw_results") else 0
        result_len = len(payload.get("result", "")) if payload.get("result") else 0

        self._emit_decision("monitor", execution_id, selected=chosen_model,
                            reward_signal=0.9 if success else 0.0, latency_ms=latency_ms)
        payload["stages"]["monitor"] = {"status": "done", "success": success, "latency_ms": latency_ms}

        VALIDATION_THRESHOLD = 0.1
        validation_score = min(1.0, result_len / 500.0) if payload.get("result") else 0.0
        validation_passed = validation_score >= VALIDATION_THRESHOLD
        payload["stages"]["validate"] = {"status": "done", "score": validation_score, "passed": validation_passed}

        raw = payload.get("raw_results", {})
        final_artifact = None
        for r in (raw or {}).values():
            if isinstance(r, dict):
                out = r.get("output")
                if out and hasattr(out, "code"):
                    final_artifact = out
                    break

        if validation_passed:
            try:
                await asyncio.to_thread(
                    self.memory.store, payload["task"], payload["result"],
                    {"ts": time.time(), "model": chosen_model, "execution_id": execution_id},
                )
                payload["stages"]["deliver"] = {"status": "done"}
            except Exception as e:
                logger.error("[ORCH] Deliver error: %s", e)
                payload["stages"]["deliver"] = {"status": "error"}
        else:
            payload["stages"]["deliver"] = {"status": "blocked_by_validation"}

        total_time = time.time() - start_time
        kpis = {"total_time_s": round(total_time, 2), "latency_ms": latency_ms,
                "validation_score": round(validation_score, 2), "result_chars": result_len,
                "total_nodes": total_nodes, "success": success, "model": chosen_model}
        payload["kpis"] = kpis
        payload["stages"]["measure"] = {"status": "done", "kpis": kpis}

        try:
            from iaglobal.memory.db_manager import db
            import hashlib
            task_id = hashlib.md5(task.encode()).hexdigest()
            await asyncio.to_thread(
                db.insert_insight, "orchestrator", task_id,
                "Ciclo async: model=%s time=%.1fs score=%.2f nodes=%d" %
                (chosen_model, total_time, validation_score, total_nodes),
                score=validation_score,
            )
        except Exception:
            pass
        payload["stages"]["improve"] = {"status": "done"}

        total_elapsed = time.time() - start_time
        logger.info("[ORCH] ASYNC CICLO COMPLETO: %.2fs | success=%s", total_elapsed, success)

        if final_artifact and hasattr(final_artifact, 'code') and final_artifact.code:
            return final_artifact.code
        return payload.get("result", "")

    def run_graph_task(
        self,
        task: str,
        execution_id: Optional[str] = None,
        chosen_model: Optional[str] = None,
        decision_lock: Optional[DecisionLock] = None,
    ) -> dict:
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        metadata = {
            "ts": time.time(),
            "execution_id": execution_id,
            "model": chosen_model,
        }
        if decision_lock is not None:
            metadata["decision_lock"] = decision_lock.to_dict()

        # Injeta instruções de especialização do MetaAgentDesigner no contexto
        specialization = {}
        try:
            specialization = dict(getattr(self.evolver.designer, "specialization_instructions", {}))
        except Exception:
            pass

        context = {
            "task": task,
            "metadata": metadata,
            "_specialization": specialization,
        }

        logger.info(f"🕸️ Disparando Grafo com o modelo estratégico: {chosen_model}")
        result = self.graph.run(context, execution_id=execution_id)

        try:
            raw_results = result.get("raw_results", {})
            for node_name, node_result in raw_results.items():
                if isinstance(node_result, dict) and node_name in self.graph.nodes:
                    node = self.graph.nodes[node_name]
                    success = node_result.get("success", False)
                    latency = node_result.get("latency", 1.0)
                    
                    # Registra a métrica no nó. Isso atualiza o CreditAssignmentEngine (self.credit)
                    # garantindo que o Bandit tenha dados mais novos para a próxima rodada!
                    node.record(success=success, latency=latency)
                    
        except Exception as e:
            logger.warning(f"Evolution metrics feed error: {e}")

        return result

    async def async_run_graph_task(
        self,
        task: str,
        execution_id: Optional[str] = None,
        chosen_model: Optional[str] = None,
        decision_lock: Optional[DecisionLock] = None,
        parallel: bool = False,
    ) -> dict:
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        metadata = {
            "ts": time.time(),
            "execution_id": execution_id,
            "model": chosen_model,
        }
        if decision_lock is not None:
            metadata["decision_lock"] = decision_lock.to_dict()

        specialization = {}
        try:
            specialization = dict(getattr(self.evolver.designer, "specialization_instructions", {}))
        except Exception:
            pass

        context = {
            "task": task,
            "metadata": metadata,
            "_specialization": specialization,
        }

        logger.info(f"🕸️ [ASYNC] Disparando Grafo com o modelo estratégico: {chosen_model}")
        if parallel:
            result = await self.graph.run_parallel(context, execution_id=execution_id)
        else:
            result = await self.graph.async_run(context, execution_id=execution_id)

        try:
            raw_results = result.get("raw_results", {})
            for node_name, node_result in raw_results.items():
                if isinstance(node_result, dict) and node_name in self.graph.nodes:
                    node = self.graph.nodes[node_name]
                    success = node_result.get("success", False)
                    latency = node_result.get("latency", 1.0)
                    node.record(success=success, latency=latency)
        except Exception as e:
            logger.warning(f"Evolution metrics feed error: {e}")

        return result

    def _execute_search(self, query: str) -> str:
        try:
            return search_tool(query)
        except Exception as e:
            logger.warning(f"Search fail: {e}")
            return ""

    def _shutdown(self):
        logger.info("💾 Shutdown backup...")
        try:
            if hasattr(self.memory_manager, "snapshot"):
                self.memory_manager.snapshot()
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        try:
            from iaglobal.providers.async_http import close_session
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(close_session())
                else:
                    asyncio.run(close_session())
            except RuntimeError:
                asyncio.run(close_session())
        except Exception:
            pass
