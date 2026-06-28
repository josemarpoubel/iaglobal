# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_qa.py

"""
QA Node — Portão de controle de qualidade e garantia de software (QA).
Executa avaliações com telemetria ativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.critic_agent import CriticAgent

logger = logging.getLogger(__name__)


async def run_qa(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a auditoria de QA de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso analítico para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "qa_critic_agent_llm"
    
    logger.info("[QA] Iniciando ciclo de Quality Assurance no código gerado...")
    
    # Coleta os dados de forma resiliente do contexto ou da memória do Coder
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    prompt = ctx.get("prompt", "") or ctx.get("memory", {}).get("prompt_builder", {}).get("built_prompt", "")
    
    coder_data = ctx.get("coder", {}) or ctx.get("memory", {}).get("coder", {})
    output = coder_data.get("output", "") if isinstance(coder_data, dict) else ""

    try:
        # Inicializa o agente avaliador
        agent = CriticAgent()
        
        # Executa a avaliação cognitiva profunda do QA (LLM-driven)
        if asyncio.iscoroutinefunction(agent.avaliar):
            result = await agent.avaliar(task, prompt, output)
        else:
            result = await asyncio.to_thread(agent.avaliar, task, prompt, output)
            
        logger.info("[QA] Avaliação finalizada. Resultado estruturado com sucesso.")
        
        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso de QA se o agente conseguiu emitir um veredito válido
        is_success = isinstance(result, dict) and "approved" in result

        # Retorno higienizado cumprindo estritamente as Regras 1, 3 e 5 do AGENTS.md
        return {
            "output": result.get("feedback", "QA finalizado"),
            "qa": result,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.004)  # Custo de inferência estimado para o QA
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[QA] Falha crítica durante o ciclo de Quality Assurance: %s", e)
        
        # REPORTA A FALHA EXPLICITAMENTE PARA O BANDIT POLICY APRENDER COM O COMPORTAMENTO DO MODELO
        return {
            "output": "Falha no processo de QA",
            "qa": {"approved": False, "score": 0, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

