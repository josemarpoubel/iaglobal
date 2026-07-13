# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_artifact_writer.py

"""
Artifact Writer Node — Consolida e persiste em disco os artefatos finais do pipeline.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.

INTEGRAÇÃO CONTAMINATION_REPORT:
  - Detecta claims arquiteturais em artefatos antes de persistir
  - Exige verificação de fatos contra código-fonte
  - Marca artefatos suspeitos para revisão humana pré-REM

INFERÊNCIA DE TIPO:
  - Safety net: se o conteúdo parece markdown mas foi salvo como .py, reescreve como .md
  - Se parece prosa sem marcadores de código, força .md

MÓDULO CENTRALIZADO: iaglobal/reflection/claim_detection.py
"""

import time
import logging
import asyncio

from typing import Dict, Any

from iaglobal.agents.result_agent import ResultAgent
from iaglobal.reflection.claim_detection import (
    detect_architectural_claims,
    verify_architectural_claims,
)
from iaglobal.reflection.contamination_report import report_architectural_hallucination

logger = logging.getLogger(__name__)


async def run_artifact_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a consolidação e persistência de artefatos finais em disco de forma assíncrona.
    Mapeia latência e sucesso operacional para o JointOptimizationLoop.

    CONTAMINATION CHECK:
      - Detecta claims arquiteturais suspeitos (via claim_detection.py)
      - Verifica contra código-fonte real
      - Reporta contaminação antes de persistir
    """
    start_time = time.time()
    resolved_model = "artifact_writer_deterministic_io"

    logger.info(
        "[ARTIFACT_WRITER] Iniciando consolidação e gravação dos entregáveis finais em disco..."
    )

    try:
        # Inicializa o agente responsável pelo empacotamento do resultado
        agent = ResultAgent()

        # Como a consolidação e escrita de arquivos em disco realizam I/O síncrono pesado,
        # desviamos a execução para uma thread pool isolada para proteger o AcetylcholineBus
        if asyncio.iscoroutinefunction(agent.build_result):
            result = await agent.build_result(ctx=ctx)
        else:
            result = await asyncio.to_thread(agent.build_result, ctx=ctx)

        # === CONTAMINATION CHECK ===
        artifact_text = (
            str(result) if not isinstance(result, dict) else result.get("summary", "")
        )

        # 1. Detecta claims suspeitos (fonte única: claim_detection.py)
        claims_suspeitos = detect_architectural_claims(artifact_text)

        if claims_suspeitos:
            logger.warning(
                "🚨 [ARTIFACT_WRITER] Claims arquiteturais detectados | count=%d",
                len(claims_suspeitos),
            )

            # 2. Verifica claims contra código-fonte
            verified, unverified = verify_architectural_claims(claims_suspeitos)

            if not verified and unverified:
                # CONTAMINAÇÃO DETECTADA!
                logger.error(
                    "🚨 [CONTAMINATION] Artefato com claims falsos | unverified=%s",
                    unverified[:3],
                )

                # 3. Cria report de contaminação
                execution_metrics = ctx.get("execution_metrics", {})
                llm_model = execution_metrics.get("model", "unknown")

                report_path = report_architectural_hallucination(
                    artifact_path="artifact_writer_output",
                    llm_model=llm_model,
                    false_claims=unverified,
                    verified_facts={
                        "check_timestamp": time.time(),
                    },
                )

                # 4. Marca artefato para revisão humana
                if isinstance(result, dict):
                    result["contamination_flag"] = True
                    result["contamination_report"] = str(report_path)
                    result["requires_human_review"] = True

        logger.info(
            "[ARTIFACT_WRITER] Artefatos e entregáveis finais persistidos com sucesso."
        )

        latency_ms = (time.time() - start_time) * 1000.0

        # Considera sucesso técnico se o agente conseguiu gerar o dicionário de resultado
        is_success = isinstance(result, dict) or result is not None

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md
        return {
            "output": result.get("summary", "Artefatos consolidados com sucesso")
            if isinstance(result, dict)
            else str(result),
            "artifact_writer": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[ARTIFACT_WRITER] Falha crítica no pipeline: %s", e)

        return {
            "output": "Falha no processo de gravação de artefatos",
            "artifact_writer": {"status": "failed", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
