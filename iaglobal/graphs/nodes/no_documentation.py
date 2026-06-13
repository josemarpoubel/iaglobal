"""Documentation handler — gera documento/PDF formatado para tarefas de documentacao."""
from typing import Dict, Any
import logging

from iaglobal.providers.provider_router import async_route_generate
from iaglobal.memory.memory_error import record_error

logger = logging.getLogger(__name__)


async def run_documentation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    # Prefere output do coder (que ja deve ter gerado conteudo de documento)
    coder_output = memory.get("coder", {}).get("output", "")
    if not coder_output:
        coder_output = memory.get("multi_coder", {}).get("output", "")

    built_prompt = memory.get("prompt_builder", {}).get("built_prompt", "")
    if not built_prompt:
        built_prompt = memory.get("prompt_builder", {}).get("output", "")

    if not task and not coder_output and not built_prompt:
        record_error("documentation", "Empty task", {"task": task})
        return {**ctx, "output": "", "document": ""}

    specialization = (
        ctx.get("input", {})
        .get("_specialization", {})
        .get("coder", "")
    )

    base_content = coder_output or built_prompt or task

    system = (
        "Voce e um redator tecnico gerando documentos formatados e prontos para publicacao.\n"
        "Formate o documento de forma limpa, bem estruturada, com secoes claras.\n"
        "Nao gere codigo — gere o documento final completo.\n"
        "Se o formato solicitado for PDF, inclua a estrutura completa do documento "
        "(titulo, introducao, secoes, conclusao) em formato texto rico."
    )
    if specialization:
        system = specialization

    prompt = (
        f"{system}\n\n"
        f"Tarefa original: {task}\n\n"
        f"Conteudo base:\n{base_content}\n\n"
        f"Gere o documento final completo e formatado, pronto para ser salvo como PDF. "
        f"Inclua titulo, secoes, listas e todo o conteudo necessario."
    )

    try:
        doc = await async_route_generate(
            model="", prompt=prompt, task_type="documentation"
        )
        if doc and len(doc) > 100:
            logger.info("[DOCUMENTATION] Documento gerado: %d chars", len(doc))
            return {**ctx, "output": doc, "document": doc}
        record_error("documentation", "Empty/short document", {"task": task[:100]})
    except Exception as e:
        logger.warning("[DOCUMENTATION] Falha: %s", e)
        record_error("documentation", str(e), {"task": task[:100]})

    return {**ctx, "output": "", "document": ""}
