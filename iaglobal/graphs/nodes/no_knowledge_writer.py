# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
from typing import Dict, Any
import logging

from iaglobal.agents.knowledge_writer_agent import KnowledgeWriterAgent

logger = logging.getLogger(__name__)


async def run_knowledge_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    for source in (
        "multi_coder",
        "coder",
        "debug_coder",
        "backend_builder",
        "frontend_builder",
        "api_builder",
    ):
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            _found_in = source
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            _found_in = source
            break

    if not task_str and not code:
        logger.warning("[KNOWLEDGE_WRITER] No task or code to learn from")
        return {**ctx, "output": {"status": "empty"}}

    try:
        agent = KnowledgeWriterAgent()
        if code:
            logger.info(
                "[KNOWLEDGE_WRITER] Aprendendo de source=%s len=%d",
                _found_in,
                len(code),
            )
            result = agent.learn_from_conversation(
                prompt=task_str, response=code, source=_found_in
            )
        else:
            result = agent.learn_from_text(task_str, source="pipeline")
        consolidation = agent.consolidate_session()
        if consolidation.get("status") == "consolidated":
            logger.info(
                "[KNOWLEDGE_WRITER] Session consolidated: %d entries",
                consolidation["entries"],
            )
        logger.info(
            "[KNOWLEDGE_WRITER] concepts=%d defs=%d faqs=%d",
            len(result.get("concepts", [])),
            len(result.get("definitions", [])),
            len(result.get("faqs", [])),
        )
        return {**ctx, "output": result, "knowledge_writer_result": result}
    except Exception as e:
        logger.exception("[KNOWLEDGE_WRITER] Failed: %s", e)
        return {**ctx, "output": {"status": "error", "error": str(e)}}
