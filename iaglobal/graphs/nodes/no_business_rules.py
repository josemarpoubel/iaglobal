# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_business_rules.py

"""
Business Rules Node — Extrai e consolida as regras de negócio do sistema.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md com telemetria ativa.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_business_rules(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consolida as regras de negócio a partir da análise de domínio anterior.
    Mapeia latência e sucesso para o JointOptimizationLoop de forma passiva.
    """
    start_time = time.time()
    resolved_model = "business_rules_deterministic_engine"

    # Executa ajudantes de contexto do Singleton central
    task = ctx.get("task", "") or ctx.get("input", {}).get("task", "")
    memory = ctx.get("memory", {})

    logger.info("[BUSINESS] Iniciando mapeamento e extração de regras de negócio...")

    try:
        # Captura de forma resiliente os inputs gerados pela análise de domínio
        domain_out = memory.get("domain_analysis", {}).get("output", {})
        entities = (
            domain_out.get("entities", []) if isinstance(domain_out, dict) else []
        )

        # Processamento determinístico das regras com base nas entidades mapeadas
        rules = [
            f"RN-{i + 1}: A entidade '{entity}' deve possuir ciclo de vida e gerenciamento estrito no sistema."
            for i, entity in enumerate(entities[:10])
        ]

        if not rules:
            rules = [
                "RN-0: O sistema deve cumprir integralmente o escopo e restrições do requisito principal."
            ]

        logger.info(
            "[BUSINESS] Sucesso! Mapeadas %d regras de negócio essenciais.", len(rules)
        )
        self._log(ctx, f"business_rules: {len(rules)} rules generated")

        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem desestruturar o ctx na RAM)
        return {
            "output": {"rules": rules, "count": len(rules)},
            "rules": rules,
            "rule_count": len(rules),
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0,  # Processamento determinístico local leve
            },
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception(
            "[BUSINESS] Falha crítica no pipeline do Business Rules Node: %s", e
        )

        return {
            "output": {"rules": [], "count": 0},
            "rules": [],
            "rule_count": 0,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
