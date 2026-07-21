# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_failure_analysis.py

"""
Failure Analysis Node — Diagnostica e gera relatórios/guardrails para exceções de runtime.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Tuple

from iaglobal.agents.failure_analysis_agent import FailureAnalysisAgent

logger = logging.getLogger(__name__)


def _execute_sync_analysis(
    error_log: str, task_str: str, generated_code: str = ""
) -> Tuple[dict, dict, dict]:
    """Encapsula toda a computação síncrona e escrita em disco para rodar em thread pool."""
    # 1. Coleta e geração de relatórios estáticos de sistema
    system_data = FailureAnalysisAgent.collect_system_data() or {}
    report = FailureAnalysisAgent.generate_report(system_data) or {}

    logger.info(
        "[FAILURE_ANALYSIS] Dados coletados: %d erros, %d chamadas de provedores",
        system_data.get("errors", {}).get("total", 0),
        system_data.get("metrics", {}).get("total_calls", 0),
    )

    # 2. Análise cognitiva profunda do log de erro + verificação de requisitos funcionais
    result = {
        "error_type": "clean",
        "findings": [],
        "suggestion_count": 0,
        "guardrail": None,
        "requirement_violations": [],
    }
    result = (
        FailureAnalysisAgent.analyze(
            error_log=error_log, prompt=task_str, code=generated_code
        )
        or result
    )
    result["guardrail"] = FailureAnalysisAgent.generate_guardrail(result)

    req_violations = result.get("requirement_violations", [])
    if req_violations:
        logger.warning(
            "[FAILURE_ANALYSIS] 🧬 %d violação(ões) de requisito funcional detectada(s)!",
            len(req_violations),
        )
        for v in req_violations:
            logger.warning(
                "  ⚠️  [REQ] %s | check=%s | hint=%s",
                v.get("requirement", "?"),
                v.get("check", "?"),
                v.get("hint", ""),
            )

    logger.info(
        "[FAILURE_ANALYSIS] Tipo de erro=%s | Sugestões=%d | Guardrail ativo=%s | Violações funcionais=%d",
        result.get("error_type"),
        result.get("suggestion_count", 0),
        bool(result.get("guardrail")),
        len(req_violations),
    )

    # 3. Escrita física do relatório em disco rígido
    paths = FailureAnalysisAgent.persist_report(system_data, report) or {}
    if "report_path" in paths:
        result["report_path"] = paths["report_path"]
        result["data_path"] = paths["data_path"]

    return result, system_data, report


async def run_failure_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a análise forense de exceções e telemetria de forma assíncrona.
    Mapeia latência e custos de diagnóstico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "failure_analysis_deterministic_engine"

    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))

    # Extração resiliente de logs de erro de execuções anteriores
    debugger_data = memory.get("debugger") or {}
    error_log = (
        (memory.get("code_executor") or {}).get("error", "")
        or (memory.get("code_executor") or {}).get("exec_error", "")
        or (debugger_data.get("debug_result") or {}).get("error", "")
    )

    # Extrai o código gerado para verificação de requisitos funcionais
    generated_code = (
        (memory.get("code_executor") or {}).get("output", "")
        or (memory.get("code_executor") or {}).get("code", "")
        or (memory.get("coder") or {}).get("output", "")
        or (memory.get("multi_coder") or {}).get("output", "")
        or (memory.get("frontend_builder") or {}).get("output", "")
        or (memory.get("backend_builder") or {}).get("output", "")
    ) or ""

    logger.info(
        "[FAILURE_ANALYSIS] Iniciando ciclo assíncrono de auditoria forense de falhas..."
    )

    try:
        # DESPACHA TODO O PROCESSAMENTO DE DISCO E CÁLCULO SÍNCRONO PARA A THREAD POOL ISOLADA
        result, system_data, report = await asyncio.to_thread(
            _execute_sync_analysis, error_log, task_str, generated_code
        )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": result,
            "failure_analysis": result,
            "system_errors": system_data.get("errors", {}),
            "provider_metrics": system_data.get("metrics", {}),
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,  # Análise e persistência locais de infraestrutura
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[FAILURE_ANALYSIS] Falha crítica no pipeline do Failure Analysis Node: %s",
            e,
        )

        return {
            "output": {"error_type": "unknown", "findings": [], "suggestion_count": 0},
            "failure_analysis": {"error_type": "unknown", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
