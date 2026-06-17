from typing import Dict, Any
import logging

from iaglobal.agents.knowledge_writer_agent import KnowledgeWriterAgent

logger = logging.getLogger(__name__)


async def run_knowledge_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))
    code = ""

    for source in ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder"):
        artifact = memory.get(source, {}).get("output")
        if artifact is None:
            continue
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not task_str and not code:
        logger.warning("[KNOWLEDGE_WRITER] No task or code to learn from")
        return {**ctx, "output": {"status": "empty"}}

    try:
        agent = KnowledgeWriterAgent()
        result = agent.learn_from_conversation(prompt=task_str, response=code, source="pipeline")
        logger.info("[KNOWLEDGE_WRITER] concepts=%d defs=%d faqs=%d",
                    len(result.get("concepts", [])),
                    len(result.get("definitions", [])),
                    len(result.get("faqs", [])))
        return {**ctx, "output": result, "knowledge_writer_result": result}
    except Exception as e:
        logger.exception("[KNOWLEDGE_WRITER] Failed: %s", e)
        return {**ctx, "output": {"status": "error", "error": str(e)}}
