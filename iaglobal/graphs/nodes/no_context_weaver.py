# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_context_weaver.py
"""
Context Weaver — Injeta marcadores epigenéticos no prompt.
Modifica a expressão das skills sem alterar o DNA (skills).
Fatores: domínio, histórico de erros, criticidade do projeto.

Atualizado para usar domain do prompt_intake.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def run_context_weaver(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Injeta contexto epigenético no prompt antes de chegar ao PromptImprover.
    Marcadores incluem: domínio detectado, histórico de falhas, criticidade.
    """
    start_time = time.time()

    memory = ctx.get("memory", {})

    # Prioriza domain do prompt_intake
    prompt_intake_domain = "unknown"
    prompt_data = memory.get("prompt_intake", {})
    if isinstance(prompt_data, dict) and isinstance(prompt_data.get("prompt"), dict):
        prompt_intake_domain = prompt_data.get("prompt", {}).get("domain", "unknown")

    # Fallback para task original
    task = str(ctx.get("input", {}).get("task", ""))
    if not task:
        task = prompt_data.get("task", "") or str(ctx.get("input", {}).get("task", ""))

    domain_markers = []
    task_lower = task.lower()

    # Domínios web/mobile - prioriza domain detectado
    if prompt_intake_domain == "web" or any(
        kw in task_lower
        for kw in [
            "pagina",
            "site",
            "landing",
            "email",
            "newsletter",
            "dark",
            "escuro",
            "html",
            "css",
            "frontend",
        ]
    ):
        domain_markers.append("web:responsive")
    if "mobile" in prompt_intake_domain or any(
        kw in task_lower for kw in ["mobile", "android", "ios", "app"]
    ):
        domain_markers.append("mobile:first")

    # Domínios financeiros - prioriza domain detectado
    if prompt_intake_domain == "financeiro" or any(
        kw in task_lower
        for kw in ["mercado", "financeiro", "acao", "bolsa", "investimento", "dolar"]
    ):
        domain_markers.append("financeiro:dark_theme")

    # Histórico de falhas (de failure_analysis anterior)
    failure_history = memory.get("failure_analysis", {})
    if failure_history.get("error_type") != "none":
        domain_markers.append("risk:high")

    # Constrói contexto epigenético
    epigenetic_context = (
        f"[EPIGENETIC_MARKERS: {', '.join(domain_markers)}]" if domain_markers else ""
    )

    logger.info(
        "[CONTEXT_WEAVER] Domain=%s | Contexto epigenético injetado: %s",
        prompt_intake_domain,
        epigenetic_context,
    )

    latency_ms = (time.time() - start_time) * 1000.0

    return {
        "output": f"{epigenetic_context}\n{task}".strip(),
        "epigenetic_context": epigenetic_context,
        "domain_markers": domain_markers,
        "detected_domain": prompt_intake_domain,
        "execution_metrics": {
            "model": "context_weaver",
            "success": True,
            "latency": latency_ms,
            "cost": 0.0,
        },
    }
