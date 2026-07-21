# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_prompt_builder.py

"""
Prompt Builder Node — Consolida tarefas, buscas e bases de conhecimento em um prompt injetável.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""

import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.memory.memory_error import record_error

logger = logging.getLogger(__name__)

_PROMPT_BUILDER_CONTRACT = None


def _get_pb_contract():
    global _PROMPT_BUILDER_CONTRACT
    if _PROMPT_BUILDER_CONTRACT is None:
        from iaglobal.graphs.contracts.node_contract import NodeContract

        _PROMPT_BUILDER_CONTRACT = NodeContract(
            required_inputs=["dependency", "knowledge"],
        )
    return _PROMPT_BUILDER_CONTRACT


async def run_prompt_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a montagem e concatenação do prompt contextual de forma assíncrona.
    Mapeia latência, seções e sucesso estrutural para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "prompt_builder_deterministic_engine"

    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    _get_pb_contract().validate("prompt_builder", memory)

    logger.info(
        "[PROMPT_BUILDER] Iniciando consolidação e engenharia de contexto do prompt..."
    )

    try:
        search_sources = ["search"]
        sections = ["=== TAREFA ORIGINAL ===\n" + task]

        # Varre e concatena os resultados de buscas anteriores de forma resiliente
        for src in search_sources:
            src_data = memory.get(src, {})
            src_output = (
                src_data.get("output", "")
                if isinstance(src_data, dict)
                else str(src_data or "")
            )
            if src_output and len(src_output) > 20:
                label = src.replace("search_", "search ").title()
                sections.append(f"=== {label.upper()} ===\n{src_output[:2000]}")

        # Injeta o resumo da base de conhecimento extraída
        knowledge_data = memory.get("knowledge", {}) or {}
        knowledge_summary = knowledge_data.get("summary", "")
        if knowledge_summary:
            sections.append("=== CONHECIMENTO EXTRAIDO ===\n" + knowledge_summary)

        # Injeta os conceitos e termos identificados por frequência
        knowledge_concepts = knowledge_data.get("concepts", []) or []
        if knowledge_concepts:
            concept_lines = [
                f"  - {c['name']} (freq: {c['frequency']})"
                for c in knowledge_concepts[:10]
                if isinstance(c, dict)
            ]
            if concept_lines:
                sections.append(
                    "=== CONCEITOS IDENTIFICADOS ===\n" + "\n".join(concept_lines)
                )

        built_prompt = "\n\n".join(sections)
        is_success = True

        # Portão de segurança: se o prompt consolidado falhar nos limites mínimos de tamanho
        if not built_prompt or len(built_prompt) < 50:
            # Desvia a gravação de log de erro em banco para thread pool se for síncrona
            await asyncio.to_thread(
                record_error,
                "prompt_builder",
                "Prompt built too short",
                {"task": task[:100], "len": len(built_prompt or "")},
            )
            built_prompt = task
            is_success = False

        logger.info(
            "[PROMPT_BUILDER] Engenharia concluída: %d caracteres estruturados em %d seções.",
            len(built_prompt),
            len(sections),
        )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": built_prompt,
            "built_prompt": built_prompt,
            "prompt_sections": {
                src: bool(
                    memory.get(src, {}).get("output")
                    if isinstance(memory.get(src), dict)
                    else memory.get(src)
                )
                for src in search_sources
            },
            "success": is_success,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0,  # Processamento de strings local e determinístico
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[PROMPT_BUILDER] Falha crítica no pipeline do Prompt Builder Node: %s", e
        )
        await asyncio.to_thread(
            record_error, "prompt_builder", str(e), {"task": task[:100]}
        )

        return {
            "output": task,
            "built_prompt": task,
            "prompt_sections": {},
            "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
