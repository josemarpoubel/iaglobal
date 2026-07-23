# iaglobal/pipeline/engine.py

import asyncio
import logging
import re
import time
import uuid

from pathlib import Path
from typing import Optional, Dict, Any

from .pipelinestate import PipelineState, TaskIntent
from .result import PipelineResult
from .stages import PipelineStage

from iaglobal._paths import SCRIPTS_DIR, RESULTS_DIR
from iaglobal.validation.validation_engine import ValidationEngine
from iaglobal.validation.js_validator import detect_lang
from iaglobal.diagnostics.python_normalizer import normalize_before_repair
from iaglobal.providers.provider_router import CREDIT_CANDIDATES as credit_candidates_fn

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")


class PipelineEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.validator: Optional[ValidationEngine] = None
        self._detected_lang: Optional[str] = None  # FIX BUG #3b

    async def execute(
        self,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> PipelineResult:
        return await self.async_execute(prompt, metadata, force)

    async def async_execute(
        self,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
        parallel: bool = False,
    ) -> PipelineResult:
        """Executa o pipeline de forma assíncrona."""
        state = PipelineState(
            task_id=str(uuid.uuid4()),
            prompt=prompt,
            metadata=metadata or {},
        )
        state.current_stage = PipelineStage.INIT.name

        try:
            if not prompt or not isinstance(prompt, str):
                raise RuntimeError("🚨 [PIPELINE] Prompt vazio ou inválido.")

            # -- Mission Cortex: análise da missão antes de qualquer nó --
            from iaglobal.pipeline.mission import MissionAnalyzer
            from iaglobal.pipeline.context import PipelineExecutionContext

            analyzer = MissionAnalyzer()
            mission = analyzer.analyze(prompt)
            exec_ctx = PipelineExecutionContext(mission=mission)
            state.execution_context = exec_ctx
            # Legado: espelho para nós não migrados (remover quando todos virarem providers)
            state.context["mission"] = mission
            logger.info(
                "🧠 [MISSION] domain=%s | project=%s | entities=%s",
                mission.domain,
                mission.project_type,
                mission.entities,
            )

            # Inicialização do grafo
            if not hasattr(state, "graph") or not state.graph:
                from iaglobal.graphs.execution_graph import ExecutionGraph

                state.graph = ExecutionGraph()

            # Se grafo vazio, construir a partir das skills registradas
            if not state.graph.nodes:
                logger.warning("[PIPELINE] Graph nodes vazios, construindo...")
                try:
                    from iaglobal.graphs.nodes.no_integrator import (
                        build_graph_from_skills,
                    )
                    from iaglobal.evolution.skills.native.skill_registry import (
                        skill_registry,
                    )

                    logger.warning(
                        "[PIPELINE] Antes build - registry size=%d",
                        len(skill_registry._skills),
                    )

                    state.graph = build_graph_from_skills(self.orchestrator)

                    logger.warning(
                        "[PIPELINE] Depois build - graph nodes=%d",
                        len(state.graph.nodes),
                    )
                    roots = [
                        n for n, nd in state.graph.nodes.items() if not nd.depends_on
                    ]
                    logger.warning("[PIPELINE] Nós raiz (sem deps): %s", roots)
                    logger.warning(
                        "[PIPELINE] Nós do grafo: %s", list(state.graph.nodes.keys())
                    )
                except Exception as exc:
                    logger.exception(
                        "❌ [PIPELINE] Falha ao construir grafo automático: %s", exc
                    )

            if not state.graph or not state.graph.nodes:
                raise RuntimeError(
                    "🚨 [PIPELINE] Grafo vazio ou não inicializado. Abortando execução."
                )

            # Inicialização leve do evolver
            try:
                await asyncio.to_thread(self.orchestrator.evolver.set_task, prompt)
            except Exception as e:
                logger.debug("Aviso: Evolver não pôde definir tarefa: %s", e)

            logger.info("🚀 [ASYNC PIPELINE] Starting: %s", state.task_id)

            # Estágio de Cache
            if not force:
                cached = await asyncio.to_thread(self._memory_stage, state)
                if cached:
                    return cached
            else:
                logger.info("🔥 --force: bypassing cache")
                # Verificar se orchestrator tem memory, senão usar memória direta
                if hasattr(self.orchestrator, "memory") and self.orchestrator.memory:
                    memory_instance = self.orchestrator.memory
                else:
                    # Fallback: usar MemoryStorage que tem store/retrieve/delete
                    from iaglobal.memory.memory_storage import MemoryStorage

                    memory_instance = MemoryStorage()

                await asyncio.to_thread(memory_instance.delete, state.prompt)

            # Geração via DAG
            await self._async_generation_stage(state, parallel=parallel)

            # FIX BUG #2: validação quando há código (lógica correta)
            if state.generated_code and len(str(state.generated_code)) > 10:
                logger.info("[PIPELINE] Executando validação de segurança...")
                if self.validator is None:
                    self.validator = ValidationEngine()
                await asyncio.to_thread(self._validation_stage, state)

            # Persistência e aprendizado
            await self._async_persistence_stage(state)
            await self._async_metabolism_stage(state)

            await self._async_learn_stage(state)

            # ── EvolutionFeedbackHook: sinal unificado de feedback evolutivo ──
            try:
                from iaglobal.evolution.evolution_feedback_hook import (
                    EvolutionFeedbackHook,
                    EvolutionSignal,
                )
                from iaglobal.observability.semaphore_tracker import (
                    get_semaphore_tracker,
                )
                from iaglobal.utils.generation_classifier import classify_generation

                candidates = [m for _, m in credit_candidates_fn()]
                chosen_model_for_feedback = None
                try:
                    chosen_model_for_feedback = getattr(
                        self.orchestrator, "bandit", None
                    ) and self.orchestrator.bandit.select_model(
                        node_id="cognitive_dag_root",
                        task_type="dev_fast",
                        candidates=candidates,
                    )
                except Exception:
                    chosen_model_for_feedback = (
                        candidates[0] if candidates else "ollama/qwen2.5:0.5b"
                    )

                _provider, _model = (
                    chosen_model_for_feedback.split("/", 1)
                    if chosen_model_for_feedback and "/" in chosen_model_for_feedback
                    else ("", chosen_model_for_feedback or "")
                )
                _generation_kind = classify_generation(state.generated_code or "").value
                _qa_result = (
                    state.execution_context.context.get("qa")
                    if hasattr(state, "execution_context") and state.execution_context
                    else None
                )

                hook = EvolutionFeedbackHook()
                await hook.apply(
                    bandit=getattr(self.orchestrator, "bandit", None),
                    signal=EvolutionSignal(
                        provider=_provider,
                        model=_model,
                        semaphore_health=get_semaphore_tracker().health_report(),
                        execution_metrics=getattr(state, "execution_metrics", None),
                        generation_kind=_generation_kind,
                        qa_result=_qa_result,
                    ),
                    execution_id=state.task_id,
                )
            except Exception as e:
                logger.debug("[PIPELINE] EvolutionFeedbackHook skip: %s", e)

            state.current_stage = PipelineStage.COMPLETE.name
            # FIX BUG #5: _save_script em thread pool
            script_path = await asyncio.to_thread(self._save_script, state)

            return PipelineResult(
                success=True,
                response=state.generated_code,
                score=state.score,
                metadata={"task_id": state.task_id, "stage": state.current_stage},
                script_path=str(script_path) if script_path else None,
            )

        except Exception as e:
            logger.exception("💥 [ASYNC PIPELINE] Failure: %s", e)
            state.current_stage = PipelineStage.FAILED.name
            return PipelineResult(
                success=False,
                error=str(e),
                metadata={"task_id": state.task_id, "stage": state.current_stage},
            )

    # =========================================================================

    def _memory_stage(self, state: PipelineState) -> Optional[PipelineResult]:
        state.current_stage = PipelineStage.MEMORY.name
        logger.info("📖 lendo o aprendizado anterior ...")

        # Verificar se orchestrator tem memory, senão usar memória direta
        if hasattr(self.orchestrator, "memory") and self.orchestrator.memory:
            memory_instance = self.orchestrator.memory
        else:
            # Fallback: usar MemoryStorage que tem store/retrieve/delete
            from iaglobal.memory.memory_storage import MemoryStorage

            memory_instance = MemoryStorage()

        try:
            cached = memory_instance.retrieve(state.prompt)
        except Exception:
            cached = None

        if cached:
            score = cached.get("score", 0) or cached.get("metadata", {}).get("score", 0)
            codigo = cached.get("response") or cached.get("codigo") or ""
            if (
                score >= 0.6
                and len(codigo) > 100
                and ("def " in codigo or "class " in codigo)
            ):
                metadata = cached.get("metadata", {})
                if metadata.get("script_path") or metadata.get("path"):
                    logger.info(
                        "⚡ já aprendi isso antes! (score=%.2f, %d chars)",
                        score,
                        len(codigo),
                    )
                    return PipelineResult(
                        success=True,
                        response=codigo,
                        score=score,
                        script_path=metadata.get("script_path") or metadata.get("path"),
                        metadata={"cached": True, "task_id": state.task_id},
                    )
            logger.info(
                "📖 aprendizado anterior não se aplica (score=%.2f, %d chars)",
                score,
                len(codigo),
            )

        logger.info("🧠 vou aprender algo novo!")
        return None

    async def _async_generation_stage(
        self, state: PipelineState, parallel: bool = False
    ) -> None:
        state.current_stage = PipelineStage.GENERATION.name
        logger.warning(
            "[PIPELINE] ⚙️ INICIANDO GERAÇÃO | prompt=%s | parallel=%s",
            state.prompt[:50],
            parallel,
        )

        # Auto-detecção de arquivos no prompt
        ingested_context = ""
        try:
            from iaglobal.agents.ingestion.file_ingestion_agent import (
                FileIngestionAgent,
            )

            detected = FileIngestionAgent.detect_file_paths(state.prompt)
            if detected:
                logger.info("[INGEST] %d arquivos detectados no prompt", len(detected))
                result = FileIngestionAgent.ingest(detected)
                if result["file_count"] > 0:
                    parts = [
                        f"--- {f['filename']} ({f['size_kb']} KB) ---\n{f['content'][:5000]}"
                        for f in result["files"]
                    ]
                    ingested_context = "\n\n".join(parts)
                    logger.info(
                        "[INGEST] %d arquivos ingeridos (%d chars)",
                        result["file_count"],
                        result["total_chars"],
                    )
        except Exception as e:
            logger.debug("[INGEST] Auto-detecção: %s", e)

        prompt = state.prompt
        state.intent = (
            TaskIntent.CODE
            if any(
                k in prompt.lower()
                for k in (
                    "crie um",
                    "gere um",
                    "implemente",
                    "função",
                    "programa",
                    "hello world",
                    "script",
                    "python",
                    "classe ",
                )
            )
            else TaskIntent.HTML
            if any(k in prompt.lower() for k in ("html", "página", "site", "frontend"))
            else TaskIntent.JSON
            if any(k in prompt.lower() for k in ("json", "retorne apenas"))
            else TaskIntent.CHAT
            if any(
                k in prompt.lower()
                for k in ("explique", "o que é", "como funciona", "descreva", "resuma")
            )
            else TaskIntent.GENERAL
        )
        if ingested_context:
            prompt = f"{state.prompt}\n\n[ARQUIVOS INGERIDOS]\n{ingested_context}"

        # Seleção de modelo via Bandit
        candidates = [m for _, m in credit_candidates_fn()]
        chosen_model = None
        try:
            chosen_model = self.orchestrator.bandit.select_model(
                node_id="cognitive_dag_root",
                task_type="dev_fast",
                candidates=candidates,
            )
            logger.info("🎯 BANDIT selecionou: %s", chosen_model)
        except Exception as e:
            logger.warning("🎯 BANDIT indisponível (%s), usando fallback", e)
            chosen_model = candidates[0] if candidates else None

        if not chosen_model:
            chosen_model = candidates[0] if candidates else "ollama/qwen2.5:0.5b"
            logger.warning(
                "🎯 chosen_model vazio — fallback hardcoded: %s", chosen_model
            )

        try:
            # FIX BUG #4: validação e init_execution apenas aqui (sem duplicata)
            if not state.graph or not state.graph.nodes:
                raise RuntimeError(
                    "🚨 [PIPELINE] Grafo vazio ou não inicializado. Abortando execução."
                )

            for node_name, node in state.graph.nodes.items():
                if not hasattr(node, "node_id"):
                    raise RuntimeError(
                        f"🚨 [PIPELINE] Nó '{node_name}' não possui node_id válido."
                    )
                if not hasattr(node, "name"):
                    raise RuntimeError(
                        f"🚨 [PIPELINE] Nó '{node_name}' não possui name válido."
                    )

            node_ids = [node.node_id for node in state.graph.nodes.values()]
            await asyncio.to_thread(
                self.orchestrator.execution_registry.init_execution,
                state.task_id,
                node_ids,
            )

            # Usar o grafo já construído e validado pelo PipelineEngine
            ctx = {
                "input": {"task": prompt},
                "memory": getattr(state, "memory", {}),
                "chosen_model": chosen_model,
                "parallel": parallel,
                "__exec_ctx": state.execution_context,
            }
            graph_result = await state.graph.async_run(ctx)
        except Exception as e:
            from iaglobal.core.apoptosis import EvolutionRecoveryEngine

            recovery = EvolutionRecoveryEngine()
            new_agent_id = await recovery.trigger_apoptosis(
                agent_id=state.task_id,
                failure_count=1,
                max_retries=3,
            )
            if new_agent_id:
                logger.info("🔄 [APOPTOSIS] Novo clone gerado: %s...", new_agent_id[:8])
            else:
                logger.error("💀 [APOPTOSIS] Falha crítica na execução do grafo: %s", e)
            raise RuntimeError(f"Falha na execução do grafo: {e}") from e

        if not graph_result or not isinstance(graph_result, dict):
            raise RuntimeError("O Grafo retornou um resultado vazio ou inválido.")

        raw_results = graph_result.get("raw_results", {})

        if not raw_results:
            logger.warning(
                "[PIPELINE] raw_results vazio. Chaves disponíveis: %s",
                list(graph_result.keys()),
            )
        else:
            logger.info(
                "[PIPELINE] raw_results com %d nós: %s",
                len(raw_results),
                list(raw_results.keys()),
            )

        dag_nodes = [
            "result_agent",
            "documentation",
            "code_executor",
            "multi_coder",
            "coder",
        ]

        for node_name in dag_nodes:
            node_result = raw_results.get(node_name)
            if isinstance(node_result, dict):
                output = (
                    node_result.get("output") or node_result.get("final_file") or ""
                )
                if output and len(str(output)) > 10:
                    state.generated_code = str(output)
                    state.score = node_result.get("score", 50)
                    state.script_path = node_result.get("final_file", "")
                    logger.info(
                        "✅ [ASYNC PIPELINE] Sucesso no nó %s: %d chars",
                        node_name,
                        len(state.generated_code),
                    )
                    return

        final_output = graph_result.get("final_output", "")
        if final_output and len(str(final_output)) > 10:
            state.generated_code = str(final_output)
            state.score = 50
            logger.info(
                "✅ [ASYNC PIPELINE] Usando final_output do grafo: %d chars",
                len(state.generated_code),
            )
            return

        for node_name, node_result in raw_results.items():
            if isinstance(node_result, dict):
                output = (
                    node_result.get("output") or node_result.get("final_file") or ""
                )
                if output and len(str(output)) > 10:
                    state.generated_code = str(output)
                    state.score = (
                        node_result.get("score", 50)
                        if isinstance(node_result.get("score"), (int, float))
                        else 50
                    )
                    state.script_path = node_result.get("final_file", "") or ""
                    logger.info(
                        "✅ [ASYNC PIPELINE] Sucesso via '%s' (fallback): %d chars",
                        node_name,
                        len(state.generated_code),
                    )
                    return

        logger.warning(
            "⚠️ [ASYNC PIPELINE] DAG sem saída válida. nodes_executed=%s, final_output_len=%d",
            graph_result.get("nodes_executed"),
            len(str(final_output)),
        )
        raise RuntimeError("Nenhum dos nós da DAG produziu código válido.")

    def _validation_stage(self, state: PipelineState) -> None:
        """
        Validação de código com pipeline completo de normalização.

        Pipeline determinístico:
        1. Normalização (extração, sanitização, ruff format, ruff check, AST parse)
        2. Validação de segurança
        3. Atualização do estado com código validado

        Contrato: Todo código gerado por LLM deve passar por normalização
        antes de validação, pontuação ou persistência.
        """
        state.current_stage = PipelineStage.VALIDATION.name
        logger.info("🛡️ [PIPELINE] Validation stage com pipeline de normalização")

        code = state.generated_code or ""
        code = self._extract_fenced_code(code)

        # Detecta se é código Python ou apenas texto/report
        lang = detect_lang(code)

        # Se for tarefa de análise/auditoria, não valida como código Python
        is_analysis_task = any(
            keyword in state.prompt.lower()
            for keyword in [
                "analyze",
                "analysis",
                "audit",
                "security",
                "vulnerability",
                "review",
                "check",
                "verify",
                "scan",
                "optimize",
                "diagnose",
                "diagnosis",
                "metabolic",
                "metabolism",
                "ivm",
                "routing",
                "weights",
            ]
        )

        # Detecta se é markdown/texto estruturado (não código)
        is_markdown_or_text = (
            code.startswith("#")
            or "**" in code
            or "## " in code
            or "- **" in code
            or "| **" in code
            or ("> " in code and len(code.split("\n")) > 5)
        )

        if is_analysis_task or is_markdown_or_text or state.intent in (TaskIntent.CHAT, TaskIntent.DOCUMENT):
            logger.info(
                "[VALIDATION] Tarefa de análise/texto/chat detectada — pulando validação Python AST"
            )
            state.syntax_valid = True
            return

        # =====================================================================
        # ETAPA 1: NORMALIZAÇÃO CONFORME CONTRATO PYTHONNORMALIZER
        # =====================================================================
        if lang is None or lang == "py":
            logger.info(
                "[VALIDATION] Iniciando pipeline de normalização para código Python"
            )
            normalized_code, syntax_valid, norm_result = normalize_before_repair(code)

            if not syntax_valid:
                logger.warning(
                    f"[VALIDATION] Código inválido após normalização: {norm_result.syntax_error}"
                )
                state.errors.extend(
                    [f"Normalização falhou: {norm_result.syntax_error}"]
                )
                raise ValueError(f"Normalização falhou: {norm_result.syntax_error}")

            # Validação final com ValidationEngine
            logger.info("[VALIDATION] Código normalizado com sucesso, validando...")
            result = self.validator.validate(normalized_code)

            if not result.valid:
                state.errors.extend(result.errors)
                logger.warning("[VALIDATION] Validação falhou: %s", result.errors)
                raise ValueError(result.errors)

            # Código validado e pronto para uso
            state.generated_code = result.code
            state.syntax_valid = True
            logger.info("[VALIDATION] Código aprovado: normalização + validação OK")
        else:
            logger.info(
                "[VALIDATION] Código %s detectado — pulando validação Python AST (%d chars)",
                lang,
                len(code),
            )
            state.generated_code = code
            state.syntax_valid = len(code.strip()) > 10
            if not self._detected_lang and lang in (
                "js",
                "jsx",
                "ts",
                "css",
                "html",
                "json",
            ):
                self._detected_lang = lang

    def _extract_fenced_code(self, code: str) -> str:
        m = re.search(r"```(\w+)?\n(.+?)\n```", code, re.DOTALL)
        if m:
            lang = (m.group(1) or "").lower()
            extracted = m.group(2).strip()
            if extracted:
                logger.info(
                    "[EXTRACT] Código extraído de fence ```%s (%d chars)",
                    lang,
                    len(extracted),
                )
                if lang in self.LANG_EXT:
                    self._detected_lang = lang  # FIX BUG #3a: armazena a linguagem
                return extracted
        return code

    def _save_script(self, state: PipelineState) -> Optional[Path]:
        """Salva o script em disco via save_result_artifact."""
        from iaglobal._paths import save_result_artifact

        code = state.generated_code
        if not code or not code.strip():
            return None
        project_dir = save_result_artifact(state.prompt, {}, code)
        ext = self._detect_extension(code, state.intent)
        return project_dir / f"output{ext}"

    LANG_EXT = {
        "asp": ".asp",
        "aspx": ".aspx",
        "php": ".php",
        "html": ".html",
        "htm": ".html",
        "css": ".css",
        "js": ".js",
        "jsx": ".jsx",
        "ts": ".ts",
        "py": ".py",
        "python": ".py",
        "rb": ".rb",
        "java": ".java",
        "go": ".go",
        "rs": ".rs",
        "c": ".c",
        "cpp": ".cpp",
        "h": ".h",
        "sql": ".sql",
        "xml": ".xml",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yaml",
        "md": ".md",
        "sh": ".sh",
        "bash": ".sh",
        "ps1": ".ps1",
        "bat": ".bat",
        "dockerfile": ".dockerfile",
    }

    def _detect_extension(self, code: str, intent: Optional[TaskIntent] = None) -> str:
        if self._detected_lang and self._detected_lang in self.LANG_EXT:
            return self.LANG_EXT[self._detected_lang]
        if "<?php" in code:
            return ".php"
        if "<%" in code or "<%=" in code:
            return ".asp"
        if "<html" in code.lower() or "<!doctype" in code.lower():
            return ".html"
        if intent in (TaskIntent.CHAT, TaskIntent.DOCUMENT, TaskIntent.ANALYSIS):
            return ".txt"
        return ".py"

    async def _async_persistence_stage(self, state: PipelineState) -> None:
        state.current_stage = PipelineStage.PERSISTENCE.name
        logger.info("📝 archivando aprendizado (async) ...")

        # Verificar se orchestrator tem memory, senão usar memória direta
        if hasattr(self.orchestrator, "memory") and self.orchestrator.memory:
            memory_instance = self.orchestrator.memory
        else:
            # Fallback: usar MemoryStorage que tem store/retrieve/delete
            from iaglobal.memory.memory_storage import MemoryStorage

            memory_instance = MemoryStorage()

        await asyncio.to_thread(
            memory_instance.store,
            state.prompt,
            state.generated_code or "",
            {
                "ts": time.time(),
                "score": state.score,
                "script_path": str(state.script_path) if state.script_path else "",
                "path": str(state.script_path) if state.script_path else "",
            },
        )
        logger.info("✅ tudo ok, aprendi mais uma lição!")

    async def _async_metabolism_stage(self, state: PipelineState) -> None:
        """Promove/rejeita candidatos de skills via ciclo de metilação."""
        state.current_stage = PipelineStage.METABOLISM.name
        logging.getLogger("iaglobal.pipeline").info(
            "[METABOLISM] Ciclo de metilacao (task=%s)", state.task_id[:8]
        )
        try:
            from iaglobal.metabolism import methylation_engine
            from iaglobal.metabolism.homocysteine_pool import homocysteine_pool

            candidates = await asyncio.to_thread(
                homocysteine_pool.get_candidates_for_methylation
            )
            if not candidates:
                logging.getLogger("iaglobal.pipeline").debug(
                    "[METABOLISM] Sem candidatos para metilar"
                )
                return

            for candidate in candidates:
                decision = await methylation_engine.process_candidate(candidate)
                logging.getLogger("iaglobal.pipeline").info(
                    "[METABOLISM] %s -> %s (%s)",
                    candidate.skill.name,
                    decision.decision,
                    decision.reason,
                )
                state.execution_metrics.setdefault("metabolism", []).append(
                    decision.to_dict()
                )
                methylation_engine.replenish_sam_e(amount=10.0)

            report = methylation_engine.get_health_report()
            if report.get("status") == "critical":
                logging.getLogger("iaglobal.pipeline").warning(
                    "[METABOLISM] SAMe critico — reset homocisteina"
                )
                await asyncio.to_thread(methylation_engine.reset_homocysteine)
        except Exception as e:
            logging.getLogger("iaglobal.pipeline").warning(
                "[METABOLISM] Stage skip: %s", e
            )

    async def _async_learn_stage(self, state: PipelineState) -> None:
        if not state.generated_code or len(state.generated_code) < 20:
            return
        try:
            from iaglobal._paths import MEMORIES_DB
            from iaglobal.memory.term_short import ShortTermMemory
            from iaglobal.memory.term_long import LongTermMemory
            from iaglobal.memory.semantic_cache import SemanticCache

            def _learn_sync():
                stm = ShortTermMemory(db_path=MEMORIES_DB)
                ltm = LongTermMemory(db_path=MEMORIES_DB)
                cache = SemanticCache()
                stm.add(f"Q: {state.prompt}", {"type": "query", "source": "pipeline"})
                stm.add(
                    f"A: {state.generated_code[:200]}",
                    {"type": "response", "source": "pipeline"},
                )
                ltm.store(
                    state.generated_code[:500],
                    {"prompt": state.prompt, "source": "pipeline"},
                    source="pipeline",
                )
                cache.set(state.prompt, state.generated_code)

            await asyncio.to_thread(_learn_sync)
            logger.info("[LEARN] STM/LTM/cache atualizados: %s", state.prompt[:60])
        except Exception as e:
            logger.debug("[LEARN] Erro: %s", e)
