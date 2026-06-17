from typing import Dict, Any, Union
import logging

from iaglobal.agents.tester_agent import TesterAgent

logger = logging.getLogger(__name__)


async def run_tester(ctx: Dict[str, Any]) -> Dict[str, Any]:
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

    if not code:
        logger.warning("[TESTER] No code found to test")
        return {**ctx, "output": "", "test_output": ""}

    try:
        agent = TesterAgent()
        test_output = await agent.gerar_testes(codigo=code, task=task_str)
        logger.info("[TESTER] Generated %d chars of tests", len(test_output))
        return {**ctx, "output": test_output, "test_output": test_output}
    except Exception as e:
        logger.exception("[TESTER] Failed: %s", e)
        return {**ctx, "output": "", "test_output": ""}
