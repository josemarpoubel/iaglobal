# iaglobal/pipeline/engine.py

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .pipelinestate import PipelineState
from .result import PipelineResult
from .stages import PipelineStage

from iaglobal._paths import SCRIPTS_DIR
from iaglobal.validation.engine import ValidationEngine
from iaglobal.providers.provider_router import escolher_modelo, route_generate, async_route_generate, CREDIT_CANDIDATES as credit_candidates_fn
from iaglobal.providers.provider_config import ProviderConfig

logger = logging.getLogger("IA_GLOBAL_PIPELINE")


class PipelineEngine:

    def __init__(self, orchestrator):

        self.orchestrator = orchestrator

    def execute(
        self,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> PipelineResult:

        metadata = metadata or {}

        state = PipelineState(
            task_id=str(time.time()),
            prompt=prompt,
            metadata=metadata,
        )

        try:
            try:
                self.orchestrator.evolver.set_task(prompt)
            except Exception:
                pass

            logger.info(f"🚀 [PIPELINE] Starting: {state.task_id}")

            if not force:
                cached = self._memory_stage(state)
                if cached:
                    return cached

            if force:
                logger.info("🔥 --force: bypassing cache, forcing regeneration")
                try:
                    self.orchestrator.memory.delete(state.prompt)
                except Exception:
                    pass

            self._generation_stage(state)
            self.validator = ValidationEngine()
            self._persistence_stage(state)

            state.current_stage = PipelineStage.COMPLETE.name
            script_path = self._save_script(state)

            return PipelineResult(
                success=True,
                response=state.generated_code,
                score=state.score,
                metadata={"task_id": state.task_id, "stage": state.current_stage},
                script_path=str(script_path) if script_path else None,
            )

        except Exception as e:
            logger.exception(f"💥 [PIPELINE] Failure: {e}")
            state.current_stage = PipelineStage.FAILED.name
            state.errors.append(str(e))
            return PipelineResult(
                success=False,
                error=str(e),
                errors=state.errors,
                metadata={"task_id": state.task_id, "stage": state.current_stage},
            )

    async def async_execute(
        self,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
        parallel: bool = False,
    ) -> PipelineResult:

        metadata = metadata or {}
        state = PipelineState(
            task_id=str(time.time()),
            prompt=prompt,
            metadata=metadata,
        )

        try:
            try:
                await asyncio.to_thread(self.orchestrator.evolver.set_task, prompt)
            except Exception:
                pass

            logger.info(f"🚀 [ASYNC PIPELINE] Starting: {state.task_id}")

            if not force:
                cached = await asyncio.to_thread(self._memory_stage, state)
                if cached:
                    return cached

            if force:
                logger.info("🔥 --force: bypassing cache, forcing regeneration")
                try:
                    await asyncio.to_thread(self.orchestrator.memory.delete, state.prompt)
                except Exception:
                    pass

            await self._async_generation_stage(state, parallel=parallel)
            self.validator = ValidationEngine()
            await self._async_persistence_stage(state)

            state.current_stage = PipelineStage.COMPLETE.name
            script_path = self._save_script(state)

            return PipelineResult(
                success=True,
                response=state.generated_code,
                score=state.score,
                metadata={"task_id": state.task_id, "stage": state.current_stage},
                script_path=str(script_path) if script_path else None,
            )

        except Exception as e:
            logger.exception(f"💥 [ASYNC PIPELINE] Failure: {e}")
            state.current_stage = PipelineStage.FAILED.name
            state.errors.append(str(e))
            return PipelineResult(
                success=False,
                error=str(e),
                errors=state.errors,
                metadata={"task_id": state.task_id, "stage": state.current_stage},
            )

    def _memory_stage(self, state: PipelineState):

        state.current_stage = PipelineStage.MEMORY.name

        logger.info("📖 lendo o aprendizado anterior ...")
        try:
            cached = self.orchestrator.memory.retrieve(state.prompt)
        except Exception:
            cached = None

        if cached:
            score = cached.get("score", 0) or cached.get("metadata", {}).get("score", 0)
            codigo = cached.get("response") or cached.get("codigo") or ""
            if score >= 0.6 and len(codigo) > 100 and ("def " in codigo or "class " in codigo):
                metadata = cached.get("metadata", {})
                if metadata.get("script_path") or metadata.get("path"):
                    logger.info("⚡ já aprendi isso antes! (score=%.2f, %d chars)", score, len(codigo))
                    return PipelineResult(
                        success=True,
                        response=codigo,
                        score=score,
                        script_path=metadata.get("script_path") or metadata.get("path"),
                        metadata={
                            "cached": True,
                            "task_id": state.task_id,
                        },
                    )
            logger.info("📖 aprendizado anterior não se aplica (score=%.2f, %d chars)", score, len(codigo))

        logger.info("🧠 vou aprender algo novo!")
        return None

    async def _async_generation_stage(self, state: PipelineState, parallel: bool = False):
        state.current_stage = PipelineStage.GENERATION.name
        logger.info("⚙️ processando sua solicitação (async) ...")

        candidates = [m for _, m in credit_candidates_fn()]
        try:
            chosen_model = self.orchestrator.bandit.select_model(
                node="cognitive_dag_root", strategy="dev_fast", candidates=candidates,
            )
            logger.info("🎯 BANDIT selecionou: %s", chosen_model)
        except Exception:
            cand = credit_candidates_fn()
            chosen_model = cand[0][1] if cand else None
            logger.info("🎯 BANDIT indisponível, fallback: %s", chosen_model)

        try:
            graph_result = await self.orchestrator.async_run_graph_task(
                state.prompt, chosen_model=chosen_model, parallel=parallel,
            )
            raw_results = graph_result.get("raw_results", {})

            artifact_writer_result = raw_results.get("artifact_writer", {})
            if isinstance(artifact_writer_result, dict) and artifact_writer_result.get("persisted"):
                state.generated_code = artifact_writer_result.get("artifact_code", "")
                state.script_path = artifact_writer_result.get("path")
                state.score = artifact_writer_result.get("score", 0)
                artifact_obj = artifact_writer_result.get("artifact")
                if artifact_obj and hasattr(artifact_obj, "metadata"):
                    state.metadata["artifact"] = artifact_obj
                logger.info("✅ [ASYNC PIPELINE] Artifact persisted at %s", state.script_path)
                return

            final_artifact = None
            for node_name in ["final_gatekeeper", "debugger", "tester"]:
                node_result = raw_results.get(node_name, {})
                output = node_result.get("output") if isinstance(node_result, dict) else None
                if output and hasattr(output, "code") and output.code:
                    final_artifact = output
                    break

            if final_artifact and final_artifact.code:
                state.generated_code = final_artifact.code
                state.score = final_artifact.score if final_artifact.score else 0.0
                return

            final_output = graph_result.get("final_output", "")
            if final_output:
                state.generated_code = str(final_output) if not isinstance(final_output, str) else final_output
                return

            raise RuntimeError("DAG pipeline não produziu código")

        except Exception as e:
            logger.error("❌ Async DAG pipeline falhou: %s", e)
            _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
            fallback_models = [f"ollama/{_default_ollama}"]

            last_error = None
            for modelo in fallback_models:
                try:
                    resposta = await async_route_generate(model=modelo, prompt=state.prompt, task_type="general")
                    if resposta:
                        state.generated_code = resposta
                        return
                except Exception as e2:
                    last_error = str(e2)

            raise RuntimeError(last_error or "No model produced output.")

    def _generation_stage(self, state: PipelineState):

        state.current_stage = PipelineStage.GENERATION.name

        logger.info("⚙️ processando sua solicitação ...")

        candidates = [m for _, m in credit_candidates_fn()]
        try:
            chosen_model = self.orchestrator.bandit.select_model(
                node="cognitive_dag_root",
                strategy="dev_fast",
                candidates=candidates,
            )
            logger.info("🎯 BANDIT selecionou: %s", chosen_model)
        except Exception:
            cand = credit_candidates_fn()
            chosen_model = cand[0][1] if cand else None
            logger.info("🎯 BANDIT indisponível, fallback: %s", chosen_model)

        try:
            graph_result = self.orchestrator.run_graph_task(state.prompt, chosen_model=chosen_model)
            raw_results = graph_result.get("raw_results", {})

            artifact_writer_result = raw_results.get("artifact_writer", {})
            if isinstance(artifact_writer_result, dict) and artifact_writer_result.get("persisted"):
                state.generated_code = artifact_writer_result.get("artifact_code", "")
                state.script_path = artifact_writer_result.get("path")
                state.score = artifact_writer_result.get("score", 0)
                artifact_obj = artifact_writer_result.get("artifact")
                if artifact_obj and hasattr(artifact_obj, "metadata"):
                    state.metadata["artifact"] = artifact_obj
                logger.info("✅ [PIPELINE] Artifact persisted at %s", state.script_path)
                return

            final_artifact = None
            for node_name in ["final_gatekeeper", "debugger", "tester"]:
                node_result = raw_results.get(node_name, {})
                output = node_result.get("output") if isinstance(node_result, dict) else None
                if output and hasattr(output, "code") and output.code:
                    final_artifact = output
                    break

            if final_artifact and final_artifact.code:
                state.generated_code = final_artifact.code
                state.score = final_artifact.score if final_artifact.score else 0.0
                return

            final_output = graph_result.get("final_output", "")
            if final_output:
                state.generated_code = str(final_output) if not isinstance(final_output, str) else final_output
                return

            raise RuntimeError("DAG pipeline não produziu código")

        except Exception as e:
            logger.error("❌ DAG pipeline falhou: %s", e)

            _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
            fallback_models = [
                f"ollama/{_default_ollama}",
            ]

            last_error = None
            for modelo in fallback_models:
                try:
                    resposta = route_generate(
                        model=modelo,
                        prompt=state.prompt,
                        task_type="general",
                    )
                    if resposta:
                        state.generated_code = resposta
                        return
                except Exception as e2:
                    last_error = str(e2)

            raise RuntimeError(last_error or "No model produced output.")

    def _validation_stage(self, state):

        state.current_stage = PipelineStage.VALIDATION.name

        logger.info("🛡️ [PIPELINE] Validation stage")

        result = self.validator.validate(state.generated_code)

        if not result.valid:
            state.errors.extend(result.errors)
            raise ValueError(result.errors)

        state.generated_code = result.code
        state.syntax_valid = True

    def _save_script(self, state: PipelineState) -> Optional[Path]:
        if state.script_path:
            return Path(state.script_path)
        code = state.generated_code
        if not code or not code.strip():
            return None
        safe_name = re.sub(r'[^\w]', '_', state.prompt.strip()[:48])
        safe_name = safe_name.strip('_') or 'script'
        filename = f"{safe_name}_{state.task_id}.py"
        path = SCRIPTS_DIR / filename
        path.write_text(code, encoding="utf-8")
        logger.info("💾 Script salvo em: %s", path)
        return path

    async def _async_persistence_stage(self, state: PipelineState):
        state.current_stage = PipelineStage.PERSISTENCE.name
        logger.info("📝 archivando aprendizado (async) ...")
        await asyncio.to_thread(
            self.orchestrator.memory.store,
            state.prompt,
            state.generated_code or "",
            {"ts": time.time(), "score": state.score,
             "script_path": str(state.script_path) if state.script_path else "",
             "path": str(state.script_path) if state.script_path else ""},
        )
        logger.info("✅ tudo ok, aprendi mais uma lição!")

    def _persistence_stage(self, state: PipelineState):

        state.current_stage = PipelineStage.PERSISTENCE.name

        logger.info("📝 archivando aprendizado ...")

        self.orchestrator.memory.store(
            state.prompt,
            state.generated_code or "",
            {"ts": time.time(), "score": state.score,
             "script_path": str(state.script_path) if state.script_path else "",
             "path": str(state.script_path) if state.script_path else ""},
        )

        logger.info("✅ tudo ok, aprendi mais uma lição!")
