# iaglobal/pipeline/engine.py

import asyncio
import logging
import re
import time
import threading

from typing import Optional, Dict, Any, Tuple

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Dict, Any

from .pipelinestate import PipelineState
from .result import PipelineResult
from .stages import PipelineStage

from iaglobal._paths import SCRIPTS_DIR, RESULTS_DIR
from iaglobal.validation.engine import ValidationEngine
from iaglobal.providers.provider_router import escolher_modelo, route_generate, async_route_generate, CREDIT_CANDIDATES as credit_candidates_fn
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.utils.helpers import run_async_safe

from iaglobal.utils.logger import start_session_log, stop_session_log, logger as global_logger

logger = logging.getLogger(__name__)

class PipelineEngine:

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.validator = None

    async def execute(
        self, 
        prompt: str, 
        metadata: Optional[Dict[str, Any]] = None, 
        force: bool = False
    ) -> PipelineResult:
        # Ponto de entrada agora é puramente assíncrono
        return await self.async_execute(prompt, metadata, force)

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
            # Inicialização leve
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
                await asyncio.to_thread(self.orchestrator.memory.delete, state.prompt)

            # Execução da Geração (DAG)
            # Garantimos que esta chamada seja a fonte única de verdade para resultados
            await self._async_generation_stage(state, parallel=parallel)
            
            # Validação apenas se necessário
            if not (state.generated_code and len(str(state.generated_code)) > 10):
                logger.info("[PIPELINE] Executando validação de segurança...")
                if self.validator is None:
                    self.validator = ValidationEngine()
                await asyncio.to_thread(self._validation_stage, state)

            # Persistência final
            await self._async_persistence_stage(state)
            await self._async_learn_stage(state)

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
            logger.exception("💥 [ASYNC PIPELINE] Failure: %s", e)
            state.current_stage = PipelineStage.FAILED.name
            return PipelineResult(
                success=False,
                error=str(e),
                metadata={"task_id": state.task_id, "stage": state.current_stage},
            )

#==========================================================================

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

        # Auto-detecção de arquivos no prompt
        ingested_context = ""
        try:
            from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent
            detected = FileIngestionAgent.detect_file_paths(state.prompt)
            if detected:
                logger.info("[INGEST] %d arquivos detectados no prompt", len(detected))
                result = FileIngestionAgent.ingest(detected)
                if result["file_count"] > 0:
                    parts = []
                    for f in result["files"]:
                        parts.append(f"--- {f['filename']} ({f['size_kb']} KB) ---\n{f['content'][:5000]}")
                    ingested_context = "\n\n".join(parts)
                    logger.info("[INGEST] %d arquivos ingeridos (%d chars)", result["file_count"], result["total_chars"])
        except Exception as e:
            logger.debug("[INGEST] Auto-detecção: %s", e)

        prompt = state.prompt
        if ingested_context:
            prompt = f"{state.prompt}\n\n[ARQUIVOS INGERIDOS]\n{ingested_context}"

        # Escolha do modelo via Bandit (NÃO sobrescrever depois!)
        candidates = [m for _, m in credit_candidates_fn()]
        chosen_model = None
        try:
            chosen_model = self.orchestrator.bandit.select_model(
                node="cognitive_dag_root", strategy="dev_fast", candidates=candidates,
            )
            logger.info("🎯 BANDIT selecionou: %s", chosen_model)
        except Exception as e:
            logger.warning("🎯 BANDIT indisponível (%s), usando fallback de candidatos", e)
            chosen_model = candidates[0] if candidates else None
            logger.info("🎯 Fallback chosen_model: %s", chosen_model)

        # Fallback final: se mesmo assim chosen_model ficou None/vazio, pega o primeiro candidato
        if not chosen_model:
            chosen_model = candidates[0] if candidates else "ollama/qwen2.5:0.5b"
            logger.warning("🎯 chosen_model vazio — usando fallback hardcoded: %s", chosen_model)

        try:
            # Garantimos que a chamada ao grafo seja tratada de forma assíncrona robusta
            graph_result = await self.orchestrator.async_run_graph_task(
                prompt,
                chosen_model=chosen_model,
                parallel=parallel
            )
        except Exception as e:
            logger.error("[PIPELINE] Grafo falhou inesperadamente: %s", e)
            raise RuntimeError(f"Falha na execução do grafo: {e}") from e

        # Verificação de segurança: O grafo retornou um objeto válido?
        if not graph_result or not isinstance(graph_result, dict):
            raise RuntimeError("O Grafo retornou um resultado vazio ou inválido.")

        raw_results = graph_result.get("raw_results", {})

        # Log defensivo: mostra o que veio do grafo pra debug futuro
        if not raw_results:
            logger.warning("[PIPELINE] raw_results está VAZIO. Chaves disponíveis no graph_result: %s",
                           list(graph_result.keys()))
        else:
            logger.info("[PIPELINE] raw_results tem %d nós: %s",
                        len(raw_results), list(raw_results.keys()))

        dag_nodes = ["result_agent", "documentation", "code_executor", "multi_coder", "coder"]

        # Iteração sobre os nós para encontrar a primeira saída válida
        for node_name in dag_nodes:
            node_result = raw_results.get(node_name)

            # Valida se o nó retornou um dicionário antes de tentar acessar chaves
            if isinstance(node_result, dict):
                output = node_result.get("output") or node_result.get("final_file") or ""

                # Consideramos output válido se for string e tiver conteúdo relevante (> 10 chars)
                if output and len(str(output)) > 10:
                    state.generated_code = str(output)
                    state.score = node_result.get("score", 50)
                    state.script_path = node_result.get("final_file", "")

                    logger.info("✅ [ASYNC PIPELINE] Sucesso no nó %s: %d chars", node_name, len(state.generated_code))

                    if state.script_path:
                        logger.info("   Arquivo identificado em: %s", state.script_path)

                    # Retorna imediatamente ao encontrar a primeira saída válida
                    return

        # Fallback 1: tenta o final_output do grafo
        final_output = graph_result.get("final_output", "")
        if final_output and len(str(final_output)) > 10:
            state.generated_code = str(final_output)
            state.score = 50
            logger.info("✅ [ASYNC PIPELINE] Usando final_output do grafo: %d chars", len(state.generated_code))
            return

        # Fallback 2: tenta qualquer nó que tenha gerado código (qualquer nome)
        for node_name, node_result in raw_results.items():
            if isinstance(node_result, dict):
                output = node_result.get("output") or node_result.get("final_file") or ""
                if output and len(str(output)) > 10:
                    state.generated_code = str(output)
                    state.score = node_result.get("score", 50) if isinstance(node_result.get("score"), (int, float)) else 50
                    state.script_path = node_result.get("final_file", "") or ""
                    logger.info("✅ [ASYNC PIPELINE] Sucesso via nó '%s' (fallback): %d chars", node_name, len(state.generated_code))
                    return

        # Se mesmo assim nada
        logger.warning("⚠️ [ASYNC PIPELINE] DAG finalizada sem produzir saída válida. nodes_executed=%s, final_output_len=%d",
                       graph_result.get("nodes_executed"), len(str(final_output)))
        raise RuntimeError("Nenhum dos nós da DAG produziu código válido.")

    def _validation_stage(self, state):

        state.current_stage = PipelineStage.VALIDATION.name

        logger.info("🛡️ [PIPELINE] Validation stage")

        code = state.generated_code or ""
        code = self._extract_fenced_code(code)

        is_python = not any(marker in code for marker in ("<%@", "<?php", "<html", "<!", "<%="))
        if is_python:
            result = self.validator.validate(code)
            if not result.valid:
                state.errors.extend(result.errors)
                logger.warning("[VALIDATION] Falhou: %s", result.errors)
                raise ValueError(result.errors)
            state.generated_code = result.code
            state.syntax_valid = True
        else:
            logger.info("[VALIDATION] Código não-Python (%d chars pós-extração)", len(code))
            state.generated_code = code
            state.syntax_valid = len(code.strip()) > 10

    def _extract_fenced_code(self, code: str) -> str:
        m = re.search(r"```(\w+)?\n(.+?)\n```", code, re.DOTALL)
        if m:
            lang = (m.group(1) or "").lower()
            extracted = m.group(2).strip()
            if extracted:
                logger.info("[EXTRACT] Código extraído de fence ```%s (%d chars)", lang, len(extracted))
                if lang in self.LANG_EXT:
                    self._detected_lang = lang
                return extracted
        return code

    def _save_script(self, state: PipelineState) -> Optional[Path]:
        if state.script_path:
            return Path(state.script_path)
        code = state.generated_code
        if not code or not code.strip():
            return None
        safe_name = re.sub(r'[^\w]', '_', state.prompt.strip()[:48])
        safe_name = safe_name.strip('_') or 'script'
        ext = self._detect_extension(code)
        filename = f"{safe_name}_{state.task_id}{ext}"
        script_path = SCRIPTS_DIR / filename
        script_path.write_text(code, encoding="utf-8")
        logger.info("💾 Script salvo em: %s", script_path)

        result_path = RESULTS_DIR / filename
        result_path.write_text(code, encoding="utf-8")
        logger.info("📦 Resultado salvo em: %s", result_path)

        return script_path

    LANG_EXT = {
        "asp": ".asp", "aspx": ".aspx", "php": ".php", "html": ".html",
        "htm": ".html", "css": ".css", "js": ".js", "ts": ".ts",
        "py": ".py", "python": ".py", "rb": ".rb", "java": ".java",
        "go": ".go", "rs": ".rs", "c": ".c", "cpp": ".cpp", "h": ".h",
        "sql": ".sql", "xml": ".xml", "json": ".json", "yaml": ".yaml",
        "yml": ".yaml", "md": ".md", "sh": ".sh", "bash": ".sh",
        "ps1": ".ps1", "bat": ".bat", "dockerfile": ".dockerfile",
    }

    def _detect_extension(self, code: str) -> str:
        if hasattr(self, "_detected_lang") and self._detected_lang in self.LANG_EXT:
            return self.LANG_EXT[self._detected_lang]
        if "<?php" in code:
            return ".php"
        if "<%" in code or "<%=" in code:
            return ".asp"
        if "<html" in code.lower() or "<!doctype" in code.lower():
            return ".html"
        return ".py"

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

    async def _async_learn_stage(self, state):
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
                stm.add(f"A: {state.generated_code[:200]}", {"type": "response", "source": "pipeline"})
                ltm.store(state.generated_code[:500], {"prompt": state.prompt, "source": "pipeline"}, source="pipeline")
                cache.set(state.prompt, state.generated_code)

            await asyncio.to_thread(_learn_sync)
            logger.info("[LEARN] STM/LTM/cache atualizados: %s", state.prompt[:60])
        except Exception as e:
            logger.debug("[LEARN] Erro: %s", e)


