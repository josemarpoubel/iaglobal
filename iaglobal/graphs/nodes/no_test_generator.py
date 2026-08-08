# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_test_generator.py

"""
Test Generator Node — Desenha e gera suítes de testes automatizados para o código produzido.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""

import time
import asyncio
from typing import Dict, Any

from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.nodes.test_generator")


async def run_test_generator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração inteligente de testes de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "test_generator_tester_agent_llm"

    logger.info(
        "[TEST_GENERATOR] Iniciando geração automatizada de suíte de testes unitários..."
    )

    # Coleta os dados de entrada de forma resiliente do contexto ou memórias estruturadas
    memory = ctx.get("memory", {}) or {}
    coder_data = (
        ctx.get("coder", {}) or memory.get("coder", {}) or memory.get("multi_coder", {})
    )
    code = (
        coder_data.get("output", "")
        if isinstance(coder_data, dict)
        else str(coder_data or "")
    )

    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente especializado em qualidade e testes
        agent = TesterAgent()

        # Como gerações de código de testes realizam inferências pesadas de IA,
        # garantimos execução assíncrona nativa ou desviamos com segurança para Thread Pool
        if asyncio.iscoroutinefunction(agent.gerar_testes):
            result = await agent.gerar_testes(code, task)
        else:
            result = await asyncio.to_thread(agent.gerar_testes, code, task)

        test_output = (
            result.test_code if hasattr(result, "test_code") else str(result or "")
        )

        is_success = (
            result.success
            if hasattr(result, "success")
            else bool(test_output and len(test_output.strip()) > 10)
        )

        if is_success:
            logger.info(
                "[TEST_GENERATOR] Suíte de testes gerada com sucesso: %d caracteres.",
                len(test_output),
            )
        else:
            logger.warning(
                "[TEST_GENERATOR] Geração retornou uma suíte de testes vazia ou curta demais."
            )

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": test_output,
            "test_generator": {"output": test_output},
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get(
                    "estimated_cost", 0.010
                ),  # Geração de código de teste consome tokens de inferência
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[TEST_GENERATOR] Falha crítica no pipeline do Test Generator Node: %s", e
        )

        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "",
            "test_generator": {"output": "", "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
