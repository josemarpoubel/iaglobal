# iaglobal/core/orchestrator.py

import os
import asyncio
import time
import uuid
import logging
import atexit
import threading

from pathlib import Path
from iaglobal._paths import DATA_DIR, BACKUP_DIR, save_result_artifact, MEMORIES_DB
from typing import Optional, Dict, Any, List
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
from iaglobal.core.cognitive_proxy import CognitiveProxy
from iaglobal.core.graceful_shutdown import graceful_shutdown
from iaglobal.execution.cpu_affinity import CpuAffinityManager
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.builder import build_pipeline_from_nodes
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.state_store import SystemStateBuffer, SUCCESS, FAILED
from iaglobal.events import DecisionEvent, store as decision_store, dispatcher as decision_dispatcher
from iaglobal.events.decision_event import DecisionLock
from iaglobal.validation.engine import FeedbackEngine
from iaglobal.storage.batch_writer import batch_writer, Event as BatchEvent
from iaglobal.storage.snapshotter import snapshotter
from iaglobal.cognition.outcome_tracker import outcome_tracker, ExecutionOutcome
from iaglobal.tools.tool_router import ToolRouter
from iaglobal.graphs.membrane import Membrane, Organelle, MembraneMessage
from iaglobal.evolution.evolutionengine import EvolutionEngine
from iaglobal.utils.logger import get_logger, logger
from iaglobal.utils.helpers import run_async_safe

logger = logging.getLogger("ORCHESTRATOR")

class Orchestrator:

    def __init__(
        self,
        planner=None,
        evolution_interval: int = 30,
        evolution_strategies: list[str] = None,
        mutation_rate: float = 0.1,
        model_fn: Optional[callable] = None,
    ):
        logger.info("🧠 Orchestrator inicializando...")

        self._runtime_instance = None
        self._model_fn = model_fn
        self._membrane = Membrane()
        self._init_membrane_handlers()

        self.tool_router = ToolRouter(
            tools={
                "search": search_tool
            }
        )

        self.graph = ExecutionGraph(
            tool_router=self.tool_router
        )

        self.evo_graph = ExecutionGraph(
            tool_router=self.tool_router
        )

        self._seed_pipeline_nodes()

        strategies = evolution_strategies or ["coding", "research", "fast", "explore"]

        self.evolver = EvolutionEngine(
            graph=self.evo_graph,
            mutation_rate=mutation_rate,
            strategies=strategies
        )

        self.evolution_runtime = EvolutionRuntime(
            evolver=self.evolver,
            interval=evolution_interval
        )

        self.credit = CreditAssignmentEngine()
        self.bandit = BanditPolicy(self.credit)
        self.neuro = NeuroOrchestrator(bandit=self.bandit)
        self.bus = EventBus()
        self.decision_engine = DecisionEngine(bandit=self.bandit)
        self.pipeline = PipelineEngine(self)
        self.memory = storage
        self.memory_manager = MemoryManager(
            data_path=str(DATA_DIR),
            backup_path=str(BACKUP_DIR)
        )
        self.reflection = ReflexionEngine(model_fn=self._model_fn) if model_fn else None
        self.planner = planner
        self.tools = {"search": search_tool}
        self.cognitive = CognitiveProxy(web_enabled=False, semantic_cache=False)
        self.state_buffer = SystemStateBuffer(max_size=500, snapshot_interval_ops=50)
        self.feedback = FeedbackEngine(snapshotter=snapshotter)

        self.cpu_affinity = CpuAffinityManager()

        self._register_events()
        decision_store.start()
        decision_dispatcher.start()

        self.graph.MAX_RETRY = 1

        # Evolution auto-start desligado por padrão (ativa com EVOLUTION_AUTO=1)
        if os.environ.get("EVOLUTION_AUTO") == "1":
            self.evolution_runtime.start()
            logger.debug("🚀 EvolutionRuntime.start() chamado pelo Orchestrator")
        else:
            logger.debug("⏸️ EvolutionRuntime auto-start desligado (EVOLUTION_AUTO=1 para ativar)")

        graceful_shutdown.add_callback(lambda: self.memory_manager.snapshot() if hasattr(self.memory_manager, "snapshot") else None)
        atexit.register(self._shutdown)

        logger.info("✅ Orchestrator pronto.")

# ==========================================================

    def _init_membrane_handlers(self):
        from iaglobal.graphs.membrane import Organelle
        self._membrane.register_handler(Organelle.METACOGNITION, self._membrane_metacognition_handler)
        self._membrane.register_handler(Organelle.IMMUNITY, self._membrane_immunity_handler)
        logger.info("[MEMBRANE] Handlers registrados: metacognition, immunity")

    def _membrane_metacognition_handler(self, msg) -> dict:
        logger.info("[MEMBRANE] Metacognition executando via membrana (event=%s)", msg.event_type)
        return {"status": "routed", "event": msg.event_type}

    def _membrane_immunity_handler(self, msg) -> dict:
        logger.debug("[MEMBRANE] Immunity check via membrana")
        return {"status": "ok", "event": msg.event_type}

    def _seed_pipeline_nodes(self):
        graph = build_pipeline_from_nodes(None)
        # Reaproveita o grafo construido como self.graph (evita re-registro duplicado)
        self.graph = graph
        # Popula evo_graph com os mesmos nos (sem re-log)
        for name, node in graph.nodes.items():
            if name not in self.evo_graph.nodes:
                self.evo_graph.nodes[name] = node
        logger.info(f"🧬 Pipeline com {len(graph.nodes)} nodes carregado para execução DAG")

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
                from iaglobal.providers.provider_config import ProviderConfig
                model = f"ollama/{ProviderConfig.DEFAULT_OLLAMA_MODEL or 'qwen2.5:0.5b'}"
                from iaglobal.providers.provider_router import async_route_generate
                analise = run_async_safe(async_route_generate, model=model, prompt=prompt, task_type="general")
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

        # Lazy Import para evitar circularidade e garantir que o store esteja pronto
        from iaglobal.events import store as decision_store
        
        # Garante que o banco está conectado antes de qualquer processamento
        try:
            decision_store.start()
        except Exception as e:
            logger.error(f"[ORCH] Falha ao iniciar Decision Store: {e}")
            return None

        start_time = time.time()
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        # =====================================================================
        # WARMUP: Carregar modelo local na RAM
        # =====================================================================
        try:
            from iaglobal.providers.ollama_provider import warmup
            if not warmup():
                logger.warning("[ORCH] Ollama warmup falhou — modelo pode nao estar disponivel localmente")
        except Exception as e:
            logger.warning("[ORCH] Ollama warmup exception: %s", e)

        # =====================================================================
        # PHASE 1: MONITOR — Prompt → Analyze → Plan → Allocate → Execute → Monitor
        # =====================================================================
        print(f"\n💬 Iniciando o prompt do usuario...")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  PHASE 1: MONITOR")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload = {"task": task, "ts": start_time, "execution_id": execution_id,
                   "stages": {}}
        payload["stages"]["monitor"] = {"status": "running"}

        self._emit_decision("prompt", execution_id, action="normalize",
                            reason=f"task={task[:60]}... ({len(task)} chars)")

        try:
            self.evolver.set_task(task)
        except Exception as e:
            logger.warning("[ORCH] Evolver set_task error: %s", e)

        # ── Sub-phase: Analyze ─────────────────────────────────────────
        payload["stages"]["analyze"] = {"status": "running"}

        # TaskFingerprint para idempotência
        fingerprint = None
        classification = None
        try:
            fingerprint = self.cognitive.fingerprinter.fingerprint(task)[0]
            payload["fingerprint"] = fingerprint.key()
            classification = self.cognitive.classifier.classify(fingerprint)
            payload["classification"] = classification
            logger.info("[ORCH] Fingerprint: %s | domain=%s",
                        fingerprint.key(), classification.get("domain", "unknown"))
        except Exception as e:
            logger.debug("[ORCH] Fingerprint/classify failed: %s", e)

        # Rastrear estado inicial
        try:
            self.state_buffer.set(f"task:{execution_id}", {
                "task": task[:200], "ts": start_time, "fingerprint": fingerprint.key() if fingerprint else None,
            })
            self.state_buffer.set(f"stage:analyze:{execution_id}", {"status": "running"})
        except Exception as e:
            logger.debug("[ORCH] State buffer init failed: %s", e)

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
        # ENRICH: Injetar contexto STM/LTM no prompt via CognitiveProxy
        # =====================================================================
        try:
            ctx_data, sources = self.cognitive._build_context(task)
            sections = []
            if ctx_data:
                for item in ctx_data.get("stm", []):
                    sections.append(f"- {item['content'][:200]}")
                for item in ctx_data.get("ltm", []):
                    sections.append(f"- [LTM] {item['content'][:200]}")
            if sections:
                enriched_task = (
                    f"[CONTEXTO DE MEMÓRIA]\n"
                    + "\n".join(sections)
                    + f"\n\n[TAREFA]\n{task}"
                )
                payload["enriched_task"] = enriched_task
                logger.info("[ORCH] Enriched task with %d memory items", len(sections))
            self.cognitive.stm.add(f"Q: {task}", {"type": "query"})
        except Exception as e:
            logger.warning("[ORCH] Enrich failed: %s", e)

        # ── Sub-phase: Plan ────────────────────────────────────────────
        payload["stages"]["plan"] = {"status": "running"}

        # BanditPolicy é a única fonte de verdade para seleção de modelos
        candidates = self.bandit.default_candidates()
        self._emit_decision("plan", execution_id, action="candidate_selection",
                            candidates=list(candidates))

        chosen_model = self.bandit.select_model(
            node="cognitive_dag_root", strategy="dev_fast",
        )
        current_score = self.credit.score("cognitive_dag_root", chosen_model, "dev_fast")
        scores_snapshot = {m: self.credit.score("cognitive_dag_root", m, "dev_fast")
                          for m in candidates}

        payload["route"] = {"model": chosen_model, "score": current_score}
        is_exploration = chosen_model != candidates[0] if candidates else False
        self._emit_decision("plan", execution_id, selected=chosen_model,
                            scores_snapshot=scores_snapshot, exploration=is_exploration)
        payload["stages"]["plan"] = {"status": "done", "model": chosen_model}

        # ── Sub-phase: Allocate ─────────────────────────────────────────
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

        # ── Sub-phase: Execute ──────────────────────────────────────────
        payload["stages"]["execute"] = {"status": "running"}

        try:
            self.state_buffer.set(f"stage:execute:{execution_id}", {"status": "running", "model": chosen_model})
        except Exception:
            pass

        prompt_for_llm = payload.get("enriched_task", task)
        try:
            pipeline_result = self.pipeline.execute(task, metadata={"execution_id": execution_id, "force": True})
            payload["result"] = pipeline_result.response if pipeline_result and pipeline_result.success else None
            payload["raw_results"] = {"pipeline": payload.get("result")}
            payload["stages"]["execute"]["status"] = "done"
            try:
                self.state_buffer.set(f"stage:execute:{execution_id}", {"status": "done"})
            except Exception:
                pass
        except Exception as e:
            logger.warning("[ORCH] Pipeline execute failed: %s", e)
            try:
                payload["result"] = run_async_safe(async_route_generate, model=chosen_model, prompt=prompt_for_llm, task_type="general")
                payload["raw_results"] = {"fallback": payload["result"]}
                payload["stages"]["execute"]["status"] = "done"
            except RuntimeError:
                logger.error("[ORCH] All providers failed.")
                context = self._execute_search(task)
                payload["result"] = "[DEGRADADO - Nenhum provider disponivel]\n" + context[:400]
                payload["raw_results"] = {"error": "All providers failed"}
                payload["stages"]["execute"]["status"] = "degraded"

        if payload.get("result"):
            try:
                result_text = str(payload["result"])
                save_result_artifact(task=task, files={}, code=result_text)
                logger.info("[ORCH] Result saved to result/ directory")
            except Exception as e:
                logger.warning("[ORCH] Failed to save result artifact: %s", e)

        # Store result in LTM via CognitiveProxy (só se validado)
        if payload.get("result") and hasattr(self, "cognitive") and validation_passed:
            try:
                fp = payload.get("fingerprint")
                self.cognitive._store_result(
                    task, str(payload["result"])[:1000],
                    fingerprint=fp, success=True
                )
                logger.info("[ORCH] Result stored in LTM (score=%.2f)", validation_score)
            except Exception as e:
                logger.debug("[ORCH] LTM store failed: %s", e)

        # ── Sub-phase: Monitor Metrics ──────────────────────────────────
        payload["stages"]["metrics"] = {"status": "running"}
        payload["stages"]["monitor"]["status"] = "done"

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
        # PHASE 2: VALIDATE — FeedbackEngine (AST + sintaxe + segurança)
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  PHASE 2: VALIDATE")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["validate"] = {"status": "running"}

        validation_passed = False
        validation_score = 0.0
        validation_errors = []

        if payload.get("result"):
            result_text = str(payload["result"])
            fb_result = self.feedback.validate(result_text, {"retry_count": 0})
            validation_score = fb_result.score
            validation_passed = fb_result.valid
            validation_errors = fb_result.errors

            logger.info("[ORCH] Validate: score=%.2f valid=%s errors=%s",
                        validation_score, validation_passed, validation_errors[:2])

            # Fallback: se FeedbackEngine rejeitou, tenta validação por tamanho
            if not validation_passed and len(result_text) > 100:
                logger.info("[ORCH] Validate: FeedbackEngine rejeitou, mas resultado tem %d chars — aceitando como fallback", len(result_text))
                validation_passed = True
                validation_score = max(validation_score, min(1.0, len(result_text) / 500.0))

            # Se ROLLBACK, restaura snapshot
            if fb_result.decision == Decision.ROLLBACK:
                snap_data = snapshotter.rollback()
                if snap_data:
                    try:
                        self.state_buffer.load_snapshot(snap_data)
                        logger.info("[ORCH] Validate: ROLLBACK executado — estado restaurado")
                    except Exception:
                        pass
        else:
            logger.warning("[ORCH] Validate: resultado vazio")

        payload["stages"]["validate"] = {
            "status": "done",
            "score": validation_score,
            "passed": validation_passed,
            "errors": validation_errors,
        }

        if not validation_passed:
            logger.warning("[ORCH] Validate: FALHOU (score=%.2f) — bloqueando entrega",
                           validation_score)

        # =====================================================================
        # PHASE 3: CONSOLIDATE — Agregar resultados
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  PHASE 3: CONSOLIDATE")
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
        # PHASE 4: DELIVER — Persistir via BatchWriter + memória
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  PHASE 4: DELIVER")
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

            # BatchWriter: registrar evento de entrega
            try:
                batch_writer.enqueue(BatchEvent(
                    event_type="delivery",
                    payload={
                        "execution_id": execution_id,
                        "model": chosen_model,
                        "success": success,
                        "latency_ms": latency_ms,
                        "fingerprint": payload.get("fingerprint"),
                    },
                    critical=False,
                ))
            except Exception as e:
                logger.debug("[ORCH] BatchWriter enqueue failed: %s", e)
        else:
            logger.warning("[ORCH] Deliver: BLOQUEADO — validate falhou (score=%.2f)", validation_score)
            payload["stages"]["deliver"]["status"] = "blocked_by_validation"
            self._emit_decision("deliver", execution_id, status="blocked",
                                reason="validation_score=%.2f" % validation_score)

        # =====================================================================
        # PHASE 5: LEARN — Measure → Improve → Metacognition
        # =====================================================================
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  PHASE 5: LEARN")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload["stages"]["learn"] = {"status": "running"}
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

        # Registrar outcome no tracker
        try:
            outcome_tracker.record(ExecutionOutcome(
                execution_id=execution_id,
                success=success,
                model=chosen_model,
                latency_ms=latency_ms,
                score=validation_score,
                fingerprint=payload.get("fingerprint"),
                classification=payload.get("classification"),
            ))
        except Exception as e:
            logger.debug("[ORCH] Outcome tracker failed: %s", e)

        payload["stages"]["measure"] = {"status": "done", "kpis": kpis}

        # ── Sub-phase: Improve ──────────────────────────────────────────
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

        # Snapshot automático via state_buffer
        try:
            self.state_buffer.set(f"task:{execution_id}:done", {
                "success": success,
                "ts": time.time(),
                "model": chosen_model,
                "score": validation_score,
            })
            if success and hasattr(self.state_buffer, 'should_snapshot') and self.state_buffer.should_snapshot():
                snap_data = self.state_buffer.get_snapshot_data()
                snapshotter.create_snapshot(snap_data)
                self.state_buffer.mark_snapshot_done()
                logger.info("[ORCH] Snapshot automático criado")
        except Exception as e:
            logger.debug("[ORCH] Snapshot failed: %s", e)

        payload["stages"]["improve"] = {"status": "done"}

        # ── Sub-phase: Metacognition ────────────────────────────────────
        payload["stages"]["metacognition"] = {"status": "running"}

        if success:
            try:
                metacog_ctx = self._build_metacognition_context(payload, task, execution_id)
                metacog_results = run_async_safe(self._run_metacognition_flow, metacog_ctx)
                payload["metacognition"] = metacog_results
                payload["stages"]["metacognition"]["status"] = "done"
                logger.info("[ORCH] Metacognition: score=%s triggered=%s",
                            metacog_results.get("evaluator", {}).get("score", "?"),
                            metacog_results.get("evolution_trigger", {}).get("evolution_triggered", "?"))
            except Exception as e:
                logger.warning("[ORCH] Metacognition error: %s", e)
                payload["stages"]["metacognition"]["status"] = "error"
                payload["stages"]["metacognition"]["error"] = str(e)
        else:
            payload["stages"]["metacognition"]["status"] = "skipped"
            logger.info("[ORCH] Metacognition skipped (pipeline não teve sucesso)")

        total_elapsed = time.time() - start_time
        payload["stages"]["learn"]["status"] = "done"
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  CICLO COMPLETO: %.2fs | 5 phases | success=%s",
                     total_elapsed, success)
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
            ok = await asyncio.to_thread(warmup)
            if not ok:
                logger.warning("[ORCH] Ollama warmup falhou (async) — modelo pode nao estar disponivel localmente")
        except Exception as e:
            logger.warning("[ORCH] Ollama warmup exception (async): %s", e)

        print(f"\n💬 Iniciando o prompt do usuario (async)...")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC PHASE 1: MONITOR")
        logger.info("[ORCH] ═══════════════════════════════════════════════")
        payload = {"task": task, "ts": start_time, "execution_id": execution_id,
                   "stages": {}}
        payload["stages"]["monitor"] = {"status": "running"}

        self._emit_decision("prompt", execution_id, action="normalize",
                            reason=f"task={task[:60]}... ({len(task)} chars)")

        try:
            self.evolver.set_task(task)
        except Exception as e:
            logger.warning("[ORCH] Evolver set_task error: %s", e)

        # ── Sub-phase: Analyze ─────────────────────────────────────────
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

        # ── Sub-phase: Plan ────────────────────────────────────────────
        payload["stages"]["plan"] = {"status": "running"}

        # BanditPolicy é a única fonte de verdade para seleção de modelos
        candidates = self.bandit.default_candidates()
        self._emit_decision("plan", execution_id, action="candidate_selection",
                            candidates=list(candidates))

        chosen_model = self.bandit.select_model(
            node="cognitive_dag_root", strategy="dev_fast",
        )
        current_score = self.credit.score("cognitive_dag_root", chosen_model, "dev_fast")
        payload["route"] = {"model": chosen_model, "score": current_score}
        self._emit_decision("plan", execution_id, selected=chosen_model)
        payload["stages"]["plan"] = {"status": "done", "model": chosen_model}

        # ── Sub-phase: Allocate ─────────────────────────────────────────
        payload["stages"]["allocate"] = {"status": "running"}
        decision_lock = DecisionLock(
            execution_id=execution_id, selected_model=chosen_model,
            strategy="dev_fast", score=current_score,
        )
        payload["decision_lock"] = decision_lock.to_dict()
        self._emit_decision("allocate", execution_id, selected=chosen_model, status="locked")
        payload["stages"]["allocate"] = {"status": "done", "locked": chosen_model}

        # ── Sub-phase: Execute ──────────────────────────────────────────
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

        payload["stages"]["monitor"]["status"] = "done"

        logger.info("[ORCH] ═══════════════════════════════════════════════")
        logger.info("[ORCH]  ASYNC PHASE 2-5: VALIDATE → CONSOLIDATE → DELIVER → LEARN")
        logger.info("[ORCH] ═══════════════════════════════════════════════")

        success = bool(payload.get("result")) and len(payload.get("result", "")) > 50
        latency_ms = int((time.time() - payload["ts"]) * 1000)
        total_nodes = len(payload.get("raw_results", {})) if payload.get("raw_results") else 0
        result_len = len(payload.get("result", "")) if payload.get("result") else 0

        self._emit_decision("monitor", execution_id, selected=chosen_model,
                            reward_signal=0.9 if success else 0.0, latency_ms=latency_ms)
        payload["stages"]["monitor"] = {"status": "done", "success": success, "latency_ms": latency_ms}

        # VALIDAÇÃO via FeedbackEngine
        validation_passed = False
        validation_score = 0.0
        validation_errors = []
        if payload.get("result"):
            result_text = str(payload["result"])
            fb_result = self.feedback.validate(result_text, {"retry_count": 0})
            validation_score = fb_result.score
            validation_passed = fb_result.valid or len(result_text) > 100
            validation_errors = fb_result.errors
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
        payload["stages"]["learn"] = {"status": "running"}

        # ── Sub-phase: Metacognition (async) ────────────────────────────
        payload["stages"]["metacognition"] = {"status": "running"}
        if success:
            from iaglobal.graphs.membrane import MembraneMessage, Organelle
            try:
                metacog_ctx = self._build_metacognition_context(payload, task, execution_id)
                msg = MembraneMessage(
                    source=Organelle.CORE, target=Organelle.METACOGNITION,
                    event_type="execute",
                    payload={"ctx": metacog_ctx, "task": task, "execution_id": execution_id},
                )
                metacog_results = self._membrane.send(msg)
                if metacog_results is None:
                    metacog_results = await self._run_metacognition_flow(metacog_ctx)
                payload["metacognition"] = metacog_results
                payload["stages"]["metacognition"]["status"] = "done"
            except Exception as e:
                logger.warning("[ORCH] Async Metacognition error: %s", e)
                payload["stages"]["metacognition"]["status"] = "error"
                payload["stages"]["metacognition"]["error"] = str(e)
        else:
            payload["stages"]["metacognition"]["status"] = "skipped"

        payload["stages"]["learn"]["status"] = "done"
        total_elapsed = time.time() - start_time
        logger.info("[ORCH] ASYNC CICLO COMPLETO: %.2fs | 5 phases | success=%s", total_elapsed, success)

        if final_artifact and hasattr(final_artifact, 'code') and final_artifact.code:
            return final_artifact.code
        return payload.get("result", "")

    def _build_metacognition_context(self, payload: dict, task: str, execution_id: str) -> dict:
        """Constrói o contexto para o fluxo de metacognição."""
        raw_results = payload.get("raw_results", {})
        memory = {}
        for node_name, node_result in raw_results.items():
            if isinstance(node_result, dict):
                memory[node_name] = {"output": node_result.get("output")}

        return {
            "input": {"task": task, "enhanced_task": task},
            "memory": memory,
            "execution_id": execution_id,
            "graph": self.graph,
            "metadata": {
                "ts": time.time(),
                "execution_id": execution_id,
                "model": payload.get("kpis", {}).get("model", "unknown"),
            },
        }

    async def _run_metacognition_flow(self, ctx: dict) -> dict:
        """Executa os 7 nós da metacognição em sequência."""
        from iaglobal.evolution.metacognition.evaluator import _run_evaluator
        from iaglobal.evolution.metacognition.gap_analyzer import _run_gap_analyzer
        from iaglobal.evolution.metacognition.skill_generator import _run_skill_generator
        from iaglobal.evolution.metacognition.sandbox_validator import _run_sandbox_validator
        from iaglobal.evolution.metacognition.evolution_committee import _run_evolution_committee
        from iaglobal.evolution.metacognition.pipeline_updater import _run_pipeline_updater
        from iaglobal.evolution.metacognition.evolution_trigger import _run_evolution_trigger

        results = {}
        if "memory" not in ctx:
            ctx["memory"] = {}

        eval_result = await _run_evaluator(ctx)
        results["evaluator"] = eval_result
        ctx["memory"]["evaluator"] = {"output": eval_result}

        gap_result = await _run_gap_analyzer(ctx)
        results["gap_analyzer"] = gap_result
        ctx["memory"]["gap_analyzer"] = {"output": gap_result}

        skill_result = await _run_skill_generator(ctx)
        results["skill_generator"] = skill_result
        ctx["memory"]["skill_generator"] = {"output": skill_result}

        sandbox_result = await _run_sandbox_validator(ctx)
        results["sandbox_validator"] = sandbox_result
        ctx["memory"]["sandbox_validator"] = {"output": sandbox_result}

        committee_result = await _run_evolution_committee(ctx)
        results["evolution_committee"] = committee_result
        ctx["memory"]["evolution_committee"] = {"output": committee_result}

        await self._run_metabolism_cycle(ctx, committee_result)

        update_result = await _run_pipeline_updater(ctx)
        results["pipeline_updater"] = update_result
        ctx["memory"]["pipeline_updater"] = {"output": update_result}

        evo_result = await _run_evolution_trigger(ctx)
        results["evolution_trigger"] = evo_result

        from iaglobal.recycling.skill_recycler import SkillRecycler
        try:
            recycled = SkillRecycler.recycle(max_generations=5)
            if recycled.get("count", 0) > 0:
                logger.info("[RECYCLING] %d skills recicladas", recycled["count"])
        except Exception as ex:
            logger.debug("[RECYCLING] SkillRecycler: %s", ex)

        from iaglobal.memory.semantic_cache import SemanticCache
        try:
            cache = SemanticCache()
            pruned = cache.prune_old_embeddings(max_age_days=30)
            if pruned.get("archived", 0) > 0:
                logger.info("[RECYCLING] %d embeddings arquivados", pruned["archived"])
        except Exception as ex:
            logger.debug("[RECYCLING] EmbeddingPruner: %s", ex)

        return results

    @staticmethod
    async def _run_metabolism_cycle(ctx: dict, committee_result: dict) -> None:
        from iaglobal.evolution.metabolism.methylation_cycle import MethylationCycle
        from iaglobal.evolution.metabolism.transsulfuration_cycle import TranssulfurationCycle

        evaluations = committee_result.get("evaluations", []) if isinstance(committee_result, dict) else []
        methylation = MethylationCycle()
        transsulfuration = TranssulfurationCycle()
        approved_skills = {e["skill_name"] for e in evaluations if e.get("approved")}
        rejected_skills = {e["skill_name"] for e in evaluations if not e.get("approved")}

        from iaglobal.evolution.metabolism.homocysteine_pool import homocysteine_pool
        for candidate in homocysteine_pool.get_pending():
            name = candidate.skill.name
            if name in approved_skills:
                methylation.run(candidate)
            elif name in rejected_skills:
                transsulfuration.run(candidate)

    def run_graph_task(
        self,
        task: str,
        execution_id: Optional[str] = None,
        chosen_model: Optional[str] = None,
        decision_lock: Optional[DecisionLock] = None,
        enriched_task: Optional[str] = None,
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
            "input": {"task": task, "enhanced_task": enriched_task or task},
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

#======================================================================================

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
        node_names = list(self.graph.nodes.keys())
        if node_names:
            self.cpu_affinity.map_balanced(node_names)
            report = self.cpu_affinity.dispersion_report()
            logger.info(f"[CPU] {len(node_names)} nós mapeados em {report['total_cores']} cores | "
                        f"eficiência={report['efficiency']:.2f} | desbalanceamento={report['imbalance']}")
        if parallel:
            result = await self.graph.run_parallel(context, execution_id=execution_id)
        else:
            result = await self.graph.async_run(context, execution_id=execution_id)

#======================================================================================

        try:
            # Garantir que result seja um dicionário antes de acessar
            if not isinstance(result, dict):
                logger.error("O resultado do grafo não é um dicionário. Tipo: %s", type(result))
                return result

            raw_results = result.get("raw_results", {})

            # Debug visual para rastrear o que está saindo da DAG
            for node, data in raw_results.items():
                # Evita erro se 'data' não for printável ou estiver malformado
                content_preview = str(data)[:100] if data else "Vazio"
                print(f"DEBUG: Nó {node} retornou: {type(data)} - Conteúdo: {content_preview}...")

            # Processamento de métricas dos nós
            for node_name, node_result in raw_results.items():
                if isinstance(node_result, dict) and hasattr(self, 'graph') and node_name in self.graph.nodes:
                    node = self.graph.nodes[node_name]
                    success = node_result.get("success", False)
                    latency = node_result.get("latency", 1.0)
                    
                    # Verifica se o método record existe no nó antes de chamar
                    if hasattr(node, 'record'):
                        node.record(success=success, latency=latency)

            # CORREÇÃO: Chamada segura para o rebalanceamento
            # Passamos a lista de nós e ignoramos argumentos extras para evitar o erro de 'positional argument'
            if hasattr(self.cpu_affinity, 'rebalance_if_needed'):
                try:
                    # Se o método original falha com 2 argumentos, usamos *args para aceitar o extra
                    self.cpu_affinity.rebalance_if_needed(list(raw_results.keys()))
                except TypeError:
                    # Fallback: tenta chamar sem argumentos ou apenas com o primeiro se necessário
                    self.cpu_affinity.rebalance_if_needed()

        except Exception as e:
            # Log de aviso suave: não queremos que a falha de métrica mate a execução da pipeline
            logger.warning("Evolution metrics feed error (ignorando): %s", e)

        return result

#======================================================================================

    def _execute_search(self, query: str) -> str:
        try:
            return search_tool(query)
        except Exception as e:
            logger.warning(f"Search fail: {e}")
            return ""

    def _shutdown(self):
        graceful_shutdown.sync_cleanup()
