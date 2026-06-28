# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_sandbox_validator.py

"""
Sandbox Validator Node — Valida o comportamento semântico e a segurança do código em sandbox.
Totalmente integrado às diretrizes de concorrência e telemetria do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.semantic_validator import SemanticValidatorAgent

logger = logging.getLogger(__name__)


async def run_sandbox_validator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a validação semântica em sandbox de forma assíncrona e não-bloqueante.
    Mapeia latência, custo e conformidade técnica para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "semantic_validator_agent_llm"
    
    logger.info("[SANDBOX_VALIDATOR] Iniciando validação semântica e de segurança do código...")
    
    # Coleta os dados de entrada de forma resiliente
    coder_data = ctx.get("coder", {}) or ctx.get("memory", {}).get("coder", {})
    code = coder_data.get("output", "") if isinstance(coder_data, dict) else ""
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    try:
        # Inicializa o agente validador
        agent = SemanticValidatorAgent()
        
        # Como validações assíncronas podem chamar runtimes externos, 
        # garantimos a execução ou desviamos para thread pool se não for nativamente async
        if asyncio.iscoroutinefunction(agent.validate_async):
            result = await agent.validate_async(code=code, task=task)
        else:
            result = await asyncio.to_thread(agent.validate_async, code=code, task=task)
            
        # Extrai os dados no formato legado ou dicionário bruto de forma segura
        result_dict = result.to_legacy_dict() if hasattr(result, "to_legacy_dict") else dict(result)
        
        logger.info("[SANDBOX_VALIDATOR] Validação concluída. Código analisado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se o validador conseguiu emitir um relatório válido
        is_success = isinstance(result_dict, dict)

        # Retorno higienizado cumprindo estritamente as Regras 1, 3 and 5 do AGENTS.md
        return {
            "output": result_dict.get("summary", "Validação de sandbox finalizada"),
            "sandbox_validator": result_dict,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.003)  # Custo estimado de processamento/inferência do validador
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[SANDBOX_VALIDATOR] Falha crítica no pipeline de validação de sandbox: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de validação de sandbox",
            "sandbox_validator": {"valid": False, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

