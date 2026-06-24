import time
from typing import Dict, Any
import logging
from pathlib import Path
from datetime import datetime

from iaglobal.agents.result_agent import ResultAgent
from iaglobal._paths import save_result_artifact, RESULTS_DIR, LOG_DIR
from iaglobal.memory.memory_error import record_error

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
                logger.info("[RESULT_AGENT] Mensagem recebida de %s: type=%s", msg.sender, msg.type)
                if msg.type == "review_done":
                    payload = msg.payload
                    logger.info("[RESULT_AGENT] Review: score=%s approved=%s", payload.get("score"), payload.get("approved"))

    doc_output = memory.get("documentation", {}).get("output", "")
    if not doc_output:
        doc_output = memory.get("documentation", {}).get("document", "")

    coder_output = memory.get("multi_coder", {}).get("output", "")
    if not coder_output:
        coder_output = memory.get("coder", {}).get("output", "")

    is_code_task = any(lang in task.lower() for lang in ["php", "python", "javascript", "java", "rust", "go", "ruby", "c++", "c#", "typescript", "html", "css", "sql", "shell", "bash"])
    if is_code_task and coder_output:
        output = coder_output
    else:
        output = doc_output or coder_output

    files = {}
    for src in ["frontend_builder", "backend_builder", "database_builder", "api_builder"]:
        src_data = memory.get(src, {})
        if isinstance(src_data, dict):
            src_out = src_data.get("output", "")
            if src_out and len(src_out) > 20:
                files[f"{src}.py"] = src_out

    project_dir = None
    final_path = None

    if output:
        try:
            is_doc = bool(doc_output) and not (is_code_task and coder_output)
            project_dir = save_result_artifact(task=task, files=files, code=output)

            if is_doc and project_dir:
                pdf_found = None
                pdf_name = "output.pdf"
                static_name = "documento.pdf"
                doc_path_in_dir = Path(project_dir) / pdf_name
                static_path = Path(project_dir) / static_name

                from pathlib import Path as P
                for f in P("/tmp").rglob("*.pdf"):
                    if f.stat().st_size > 100:
                        pdf_found = str(f)
                        import shutil
                        shutil.copy(pdf_found, doc_path_in_dir)
                        logger.info("[RESULT] Copia binaria do PDF da sandbox para: %s", doc_path_in_dir)
                        break

                if doc_path_in_dir.exists() and doc_path_in_dir.stat().st_size > 100:
                    import shutil
                    shutil.copy(doc_path_in_dir, static_path)
                    final_path = str(static_path)
                    logger.info("[RESULT] Documento binario copiado de %s -> documento.pdf: %s", pdf_name, final_path)
                else:
                    static_path.write_text(output, encoding="utf-8")
                    final_path = str(static_path)
                    logger.info("[RESULT] Documento texto salvo: %s", final_path)
            elif project_dir:
                out_path = project_dir / "output.txt"
                out_path.write_text(output, encoding="utf-8")
                final_path = str(out_path)
                logger.info("[RESULT] Codigo salvo em: %s", project_dir)
        except Exception as e:
            logger.warning("[RESULT] Falha ao salvar: %s", e)
            record_error("result_agent", str(e), {"task": task[:100]})

    try:
        conv_log = ag_mailbox.get("agentmailbox", {}).get("conversation_log")
        if conv_log:
            log_text = conv_log()
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            conv_path = LOG_DIR / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            conv_path.write_text(log_text, encoding="utf-8")
            logger.info("[RESULT] Conversation log salvo em: %s", conv_path)
    except Exception as e:
        logger.debug("[RESULT] Nao foi possivel salvar conversation log: %s", e)

    # Process inbox again at end to catch any late messages
    if bus is not None and inbox is not None:
        mailbox = inbox.get_or_create("result_agent")
        msgs = mailbox.process_inbox(max_messages=5)
        if msgs:
            for msg in msgs:
                logger.info("[RESULT_AGENT] Mensagem tardia recebida de %s: type=%s", msg.sender, msg.type)

    try:
        from iaglobal.graphs.nodes import Nodes

        rank_result = await Nodes().run_rank(ctx)
        memory["rank"] = {"output": rank_result.get("output")}
        logger.info("[RESULT_AGENT] Rank score=%s", rank_result.get("final_score"))
    except Exception as e:
        logger.debug("[RESULT_AGENT] Rank fallback: %s", e)

    agent = ResultAgent()
    contract = await agent.build_result(ctx=ctx)

    return {
        **ctx,
        "output": output,
        "final_file": final_path or "",
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
        },
        "execution_metrics": {
            "success": bool(output),
            "latency": time.time() - start,
            "cost": 0.0,
            "model": "local",
        },
    }
