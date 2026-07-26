# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import time
import asyncio
from typing import Dict, Any
import logging
from pathlib import Path
from datetime import datetime

from iaglobal.agents.result_agent import ResultAgent
from iaglobal._paths import save_result_artifact, LOG_DIR
from iaglobal.memory.memory_error import record_error
from iaglobal.core.artifact import GeneratedArtifact, ArtifactKind

logger = logging.getLogger(__name__)


async def run_result_agent(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager")
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("result_agent")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info(
                    "[RESULT_AGENT] Mensagem recebida de %s: type=%s",
                    msg.sender,
                    msg.type,
                )
                if msg.type == "review_done":
                    payload = msg.payload
                    logger.info(
                        "[RESULT_AGENT] Review: score=%s approved=%s",
                        payload.get("score"),
                        payload.get("approved"),
                    )

    doc_data = memory.get("documentation", {}) or {}
    doc_output = doc_data.get("output", "")
    if not doc_output:
        doc_output = doc_data.get("document", "")
    doc_artifact: GeneratedArtifact = doc_data.get("artifact")

    mc_data = memory.get("multi_coder", {}) or {}
    coder_data = memory.get("coder", {}) or {}
    coder_output = mc_data.get("output", "") or coder_data.get("output", "")
    coder_artifact: GeneratedArtifact = mc_data.get("artifact") or coder_data.get(
        "artifact"
    )

    # Collect builder outputs — always; used both for aggregation and saving
    _BUILDER_KEYS: tuple[tuple[str, str], ...] = (
        ("frontend_builder", "Frontend"),
        ("backend_builder", "Backend"),
        ("database_builder", "Database"),
        ("api_builder", "API"),
    )
    files: dict[str, str] = {}
    builder_has_content = False
    for key, _label in _BUILDER_KEYS:
        src_data = memory.get(key, {})
        if isinstance(src_data, dict):
            src_out = src_data.get("output", "")
            if src_out and len(src_out) > 20:
                files[f"{key}.py"] = src_out
                builder_has_content = True

    is_code_task = any(
        lang in task.lower()
        for lang in [
            "php",
            "python",
            "javascript",
            "java",
            "rust",
            "go",
            "ruby",
            "c++",
            "c#",
            "typescript",
            "html",
            "css",
            "sql",
            "shell",
            "bash",
        ]
    )

    # When builders produced real code, aggregate as the primary output
    if builder_has_content:
        parts: list[str] = []
        for key, label in _BUILDER_KEYS:
            src_data = memory.get(key, {})
            if isinstance(src_data, dict):
                content = src_data.get("output", "")
                if content and len(content) > 20:
                    parts.append(f"# === {label} ===\n{content}")
        output = "\n\n\n".join(parts)
        chosen_artifact = GeneratedArtifact(
            kind=ArtifactKind.CODE,
            content=output,
            source="result_agent.aggregated",
            metadata={"files": list(files.keys())},
        )
    elif is_code_task and coder_output:
        output = coder_output
        chosen_artifact = coder_artifact or GeneratedArtifact.from_str(
            coder_output, source="result_agent.coder"
        )
    else:
        output = doc_output or coder_output
        chosen_artifact = (
            doc_artifact
            or coder_artifact
            or (
                GeneratedArtifact.from_str(output, source="result_agent.fallback")
                if output
                else GeneratedArtifact(
                    kind=ArtifactKind.ERROR,
                    content="",
                    source="result_agent",
                    metadata={"reason": "empty_output"},
                )
            )
        )

    project_dir = None
    final_path = None

    if output:
        try:
            is_doc_p = bool(doc_output) and not (is_code_task and coder_output)
            if chosen_artifact is not None:
                is_doc_p = chosen_artifact.is_search_or_doc
            project_dir = await asyncio.to_thread(
                save_result_artifact, task=task, files=files, code=output
            )

            if is_doc_p and project_dir:
                pdf_found = None
                pdf_name = "output.pdf"
                static_name = "documento.pdf"
                doc_path_in_dir = Path(project_dir) / pdf_name
                static_path = Path(project_dir) / static_name

                from pathlib import Path as P

                def _scan_pdf():
                    pdf_found = None
                    for f in P("/tmp").rglob("*.pdf"):
                        try:
                            if f.stat().st_size > 100:
                                pdf_found = str(f)
                                break
                        except FileNotFoundError:
                            continue
                    return pdf_found

                pdf_found = await asyncio.to_thread(_scan_pdf)

                def _copy_or_write():
                    if (
                        doc_path_in_dir.exists()
                        and doc_path_in_dir.stat().st_size > 100
                    ):
                        import shutil

                        shutil.copy(doc_path_in_dir, static_path)
                        final_path = str(static_path)
                        logger.info(
                            "[RESULT] Documento binario copiado de %s -> documento.pdf: %s",
                            pdf_name,
                            final_path,
                        )
                    else:
                        static_path.write_text(output, encoding="utf-8")
                        final_path = str(static_path)
                        logger.info("[RESULT] Documento texto salvo: %s", final_path)
                    return final_path

                final_path = await asyncio.to_thread(_copy_or_write)
            elif project_dir:
                out_path = project_dir / "output.txt"

                def _write(p=out_path):
                    p.write_text(output, encoding="utf-8")

                await asyncio.to_thread(_write)
                final_path = str(out_path)
                logger.info("[RESULT] Codigo salvo em: %s", project_dir)
        except Exception as e:
            logger.warning("[RESULT] Falha ao salvar: %s", e)
            record_error("result_agent", str(e), {"task": task[:100]})

    try:
        conv_log = ag_mailbox.get("agentmailbox", {}).get("conversation_log")
        if conv_log:
            log_text = conv_log()

            def _mkdir_and_write():
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                conv_path = (
                    LOG_DIR
                    / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                )
                conv_path.write_text(log_text, encoding="utf-8")
                return conv_path

            conv_path = await asyncio.to_thread(_mkdir_and_write)
            logger.info("[RESULT] Conversation log salvo em: %s", conv_path)
    except Exception as e:
        logger.debug("[RESULT] Nao foi possivel salvar conversation log: %s", e)

    # Process inbox again at end to catch any late messages
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("result_agent")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info(
                    "[RESULT_AGENT] Mensagem tardia recebida de %s: type=%s",
                    msg.sender,
                    msg.type,
                )

    try:
        from iaglobal.graphs.nodes import Nodes

        rank_result = await Nodes().run_rank(ctx)
        memory["rank"] = {"output": rank_result.get("output")}
        logger.info("[RESULT_AGENT] Rank score=%s", rank_result.get("final_score"))
    except Exception as e:
        logger.debug("[RESULT_AGENT] Rank fallback: %s", e)

    agent = ResultAgent()
    contract = await agent.build_result(ctx=ctx)

    # Genomic Reflection — ResultAgent propõe mutações à BanditPolicy
    try:
        from iaglobal.evolution.genomic_reflection import (
            genomic_reflection,
            ExecutionMetrics,
        )

        # Coletar métricas da execução atual
        execution_metrics = ctx.get("execution_metrics", {})
        metrics = ExecutionMetrics(
            execution_id=f"exec_{int(time.time())}",
            agent_id="result_agent",
            timestamp=time.time(),
            success=bool(output),
            latency_ms=(time.time() - start) * 1000,
            fitness_score=contract.get("health", {}).get("score", 0.5),
            traits_used={},  # Seria preenchido com traits reais do agente
            outcome_quality=contract.get("health", {}).get("quality", 0.5),
        )

        # Registrar execução
        genomic_reflection.register_execution(metrics)

        # Analisar performance
        analysis = await genomic_reflection.analyze_performance_async("result_agent")

        if analysis.total_executions >= 10:  # Mínimo de execuções para análise
            # Propor mutações
            proposals = await genomic_reflection.propose_mutations_async(
                "result_agent", analysis
            )

            if proposals:
                logger.info(
                    "[RESULT_AGENT] 🧬 %d mutações propostas baseadas em %d execuções",
                    len(proposals),
                    analysis.total_executions,
                )

                # Validar e aplicar mutações (se bandit validator configurado)
                for proposal in proposals:
                    approved = await genomic_reflection.validate_with_bandit_async(
                        proposal
                    )
                    if approved:
                        proposal.status = "approved"
                        await genomic_reflection.apply_mutation_async(proposal)
                        logger.info(
                            "[RESULT_AGENT] ✅ Mutação aplicada: %s → %s",
                            proposal.agent_id,
                            proposal.mutation_type.value,
                        )

    except Exception as e:
        logger.debug("[RESULT_AGENT] Genomic Reflection fallback: %s", e)

    return {
        **ctx,
        "output": output,
        "final_file": final_path or "",
        "artifact": chosen_artifact,
        "result": {
            "task": task,
            "has_output": bool(output),
            "is_document": bool(doc_output) and not (is_code_task and coder_output),
            "files_count": len(files),
            "project_dir": str(project_dir) if project_dir else None,
            "final_file": final_path,
            "summary": contract.get("summary", ""),
            "health": contract.get("health", {}),
            "checksum": contract.get("final_result", {}).get("checksum", ""),
            "artifact_kind": chosen_artifact.kind.value
            if chosen_artifact
            else "UNKNOWN",
        },
        "execution_metrics": {
            "success": bool(output),
            "latency": time.time() - start,
            "cost": 0.0,
            "model": "local",
        },
    }
