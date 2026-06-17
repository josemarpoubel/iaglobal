from typing import Dict, Any, Union
import logging

from iaglobal.agents.reflexion_agent import ReflexionAgent

logger = logging.getLogger(__name__)


async def run_reflexion(ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        logger.warning("[REFLEXION] No code found to analyze")
        return {**ctx, "output": "", "reflexion_analysis": ""}

    resultado_sandbox = {
        "sucesso": memory.get("code_executor", {}).get("success", True),
        "output": memory.get("code_executor", {}).get("output", ""),
        "erro": memory.get("code_executor", {}).get("error", ""),
    }

    try:
        agent = ReflexionAgent()
        analysis = await agent.analisar_resultado(codigo=code, resultado_sandbox=resultado_sandbox, task=task_str)
        logger.info("[REFLEXION] Analysis generated: %d chars", len(analysis))
        return {**ctx, "output": analysis, "reflexion_analysis": analysis}
    except Exception as e:
        logger.exception("[REFLEXION] Failed: %s", e)
        return {**ctx, "output": "", "reflexion_analysis": ""}
