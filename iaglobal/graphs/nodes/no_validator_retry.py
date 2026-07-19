# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Validator Retry Node — AST validation with automatic retry loop.

Fluxo:
  1. Extrai código do coder/multi_coder
  2. Valida sintaxe via ASTGateway
  3. Se válido → passa adiante
  4. Se inválido → constrói CorrectionContext → re-invoca coder via critic
  5. Max 3 tentativas
  6. Reporta falhas sintáticas por provider ao sistema de evolução
"""

import time
from typing import Dict, Any, List, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.security.ast_gateway import ASTGateway

logger = get_logger("iaglobal.graphs.nodes.validator_retry")

_ast_gateway = ASTGateway()
MAX_RETRIES = 3


async def run_validator_retry(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    memory = ctx.get("memory", {})

    code = _extrair_codigo(memory, ctx)
    if not code:
        logger.warning("[VALIDATOR_RETRY] Nenhum código encontrado para validar.")
        return {
            "output": "",
            "code_valid": True,
            "retries": 0,
            "execution_metrics": {
                "model": "validator_retry",
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    attempt = 1
    last_error = ""
    last_result = None
    corrected_code = code
    past_attempts: List[str] = []

    while attempt <= MAX_RETRIES:
        result = _ast_gateway.parse(corrected_code)
        last_result = result

        if result.valid:
            logger.info(
                "[VALIDATOR_RETRY] Código válido após %d tentativa(s) | %d chars",
                attempt,
                len(corrected_code),
            )
            return {
                "output": corrected_code,
                "code_valid": True,
                "retries": attempt - 1,
                "syntax_error": None,
                "execution_metrics": {
                    "model": "validator_retry",
                    "success": True,
                    "latency": (time.time() - start) * 1000.0,
                    "cost": 0.0,
                },
            }

        last_error = result.errors[0] if result.errors else "unknown"
        logger.warning(
            "[VALIDATOR_RETRY] Tentativa %d/%d — erro AST: %s",
            attempt,
            MAX_RETRIES,
            last_error,
        )

        if attempt >= MAX_RETRIES:
            break

        from iaglobal.cognition.correction_context import build_correction_context
        from iaglobal.agents.critic_agent import _get_critic

        cc = build_correction_context(
            code=corrected_code,
            ast_result=result,
            attempt=attempt,
            max_attempts=MAX_RETRIES,
            past_attempts=past_attempts,
        )

        critic = _get_critic()
        correction_result = await critic.arbitrar_geracao(
            node_id="validator_retry",
            prompt=cc.correction_prompt,
            task_type="code",
            context={"delegate_for": "coder"},
        )

        if correction_result and len(str(correction_result).strip()) > 20:
            new_code = _extrair_fenced_code(str(correction_result)) or str(correction_result)
            past_attempts.append(new_code)
            corrected_code = new_code
        else:
            logger.warning(
                "[VALIDATOR_RETRY] Crítico retornou correção inválida — pulando retry"
            )
            break

        attempt += 1

    latency_ms = (time.time() - start) * 1000.0

    await _registrar_falha(last_error, attempt, ctx)

    logger.error(
        "[VALIDATOR_RETRY] Código inválido após %d tentativas: %s | %d chars",
        attempt,
        last_error,
        len(corrected_code),
    )

    return {
        "output": corrected_code,
        "code_valid": False,
        "retries": attempt - 1,
        "syntax_error": last_error,
        "execution_metrics": {
            "model": "validator_retry",
            "success": False,
            "latency": latency_ms,
            "cost": 0.0,
            "error": last_error,
            "retries": attempt - 1,
        },
    }


def _extrair_codigo(memory: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    sources = (
        "multi_coder",
        "coder",
        "debug_coder",
        "backend_builder",
        "frontend_builder",
        "api_builder",
        "database_builder",
    )
    for source in sources:
        artifact = memory.get(source, {})
        if isinstance(artifact, str) and artifact.strip():
            return artifact
        if isinstance(artifact, dict):
            for key in ("output", "code", "content", "integrated_code"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    return val
    return ctx.get("generated_code", "") or ""


def _extrair_fenced_code(text: str) -> Optional[str]:
    import re
    m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


async def _registrar_falha(error: str, attempts: int, ctx: Dict[str, Any]) -> None:
    try:
        from iaglobal.evolution import is_flag_enabled
        from iaglobal.memory.async_memory import AsyncMemory

        if is_flag_enabled("evo_vaccine_persist"):
            mem = AsyncMemory()
            await mem.store(
                key="validator_retry_failure",
                value={
                    "failure_type": "syntax",
                    "error": error,
                    "attempts": attempts,
                    "provider": ctx.get("chosen_model", "unknown"),
                    "ts": time.time(),
                },
                source="validator_retry",
            )
    except Exception as e:
        logger.debug("[VALIDATOR_RETRY] Falha ao registrar falha evolutiva: %s", e)
