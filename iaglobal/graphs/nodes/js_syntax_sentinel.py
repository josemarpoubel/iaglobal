# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
JS SyntaxSentinel Node — Validação sintática nativa para JavaScript/JSX via esprima.

Filosofia:
  Espelha o syntax_sentinel (Python) mas para JS/JSX.
  Erros de sintaxe JS são detectados em <1ms sem custo de ATP/LLM.
  Tenta correções heurísticas antes de delegar ao debug_unificado.

Integração:
  - Entrada: código gerado (string)
  - Saída: código corrigido + execution_metrics + relatório de diagnóstico
  - Fallback: se correção nativa falhar, sinaliza para debug_unificado usar LLM
"""
import time
from typing import Dict, Any, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.validation.js_validator import (
    JSLanguageValidator,
    detect_lang,
    _extract_syntax_error,
    _try_parse,
)

logger = get_logger("iaglobal.graphs.nodes.js_syntax_sentinel")

_validator = JSLanguageValidator()


async def run_js_syntax_sentinel(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida código JS/JSX via esprima e aplica correções heurísticas nativas.

    Interface compatível com run_syntax_sentinel (Python).

    Args:
        ctx: Dict com:
            - memory["coder"], memory["multi_coder"], etc.: código para validar
            - input.task: tarefa atual

    Returns:
        Dict com:
            - output: código validado/corrigido
            - syntax_valid: bool
            - syntax_error: detalhes do erro ou None
            - auto_fixed: bool
            - lang: linguagem detectada ("js", "jsx", None)
            - execution_metrics: latência/custo/sucesso
    """
    start = time.time()
    resolved_model = "js_syntax_sentinel"
    memory = ctx.get("memory", {})

    code = ""
    sources = ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder")
    for source in sources:
        artifact = memory.get(source, {})
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if isinstance(artifact, dict):
            for key in ("output", "code", "content", "integrated_code"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    code = val
                    break
            if code:
                break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[JS_SYNTAX_SENTINEL] Nenhum código encontrado.")
        return {
            "output": "",
            "syntax_valid": False,
            "syntax_error": None,
            "auto_fixed": False,
            "lang": None,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": 0.0,
                "cost": 0.0,
            },
        }

    lang = detect_lang(code)
    if lang is None:
        logger.info("[JS_SYNTAX_SENTINEL] Código não-JS detectado — pulando validação JS")
        return {
            "output": code,
            "syntax_valid": True,
            "syntax_error": None,
            "auto_fixed": False,
            "lang": None,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    # Tenta parse direto — se já for válido, custo zero
    ast = _try_parse(code)
    if ast is not None:
        latency = (time.time() - start) * 1000.0
        logger.info("[JS_SYNTAX_SENTINEL] Código %s válido | latency=%.2fms", lang, latency)
        return {
            "output": code,
            "syntax_valid": True,
            "syntax_error": None,
            "auto_fixed": False,
            "lang": lang,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency,
                "cost": 0.0,
            },
        }

    # Parse falhou — extrai detalhes do erro
    error_details = _extract_syntax_error(code)
    logger.warning(
        "[JS_SYNTAX_SENTINEL] Erro de sintaxe %s | linha=%d col=%d msg=%s",
        lang,
        error_details.get("line", 1),
        error_details.get("column", 0),
        error_details.get("message", "desconhecido"),
    )

    # Aplica auto-fix
    result = _validator.auto_fix(code)
    latency = (time.time() - start) * 1000.0

    return {
        "output": result.code or code,
        "syntax_valid": result.valid,
        "syntax_error": error_details if not result.valid else None,
        "auto_fixed": result.fixed,
        "applied_fixes": result.applied_fixes,
        "lang": lang,
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency,
            "cost": 0.0,
        },
    }
