# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SyntaxSentinel Node — Validação sintática nativa via AST para evitar invocações
desnecessárias de LLM em erros triviais de Python.

Filosofia:
  Erros de sintaxe são frequentemente causados por:
    - parênteses/colchetes/chaves não fechados
    - indentação inconsistente
    - vírgulas sobrando/faltando
    - quebras de linha em expressões

  O AST do Python detecta isso em <1ms, sem custo de ATP/LLM.
  O SyntaxSentinel tenta correções heurísticas antes de delegar ao debug_unificado.

Integração:
  - Entrada: código gerado (string)
  - Saída: código corrigido + execution_metrics + relatório de diagnóstico
  - Fallback: se correção nativa falhar, sinaliza para debug_unificado usar LLM
"""

import ast
import time
import re
from typing import Dict, Any, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.validation.js_validator import detect_lang

logger = get_logger("iaglobal.graphs.nodes.syntax_sentinel")


def _count_unclosed(code: str) -> Dict[str, int]:
    """Conta parênteses/chaves/colchetes não fechados."""
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in code:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
    return {"unclosed": len(stack), "open_chars": "".join(stack)}


def _close_unclosed_brackets(code: str) -> str:
    """Fecha parênteses/chaves/colchetes abertos no final do código."""
    counts = _count_unclosed(code)
    if counts["unclosed"] <= 0:
        return code

    open_to_close = {"(": ")", "[": "]", "{": "}"}
    closing = ""
    for ch in reversed(counts["open_chars"]):
        closing += open_to_close.get(ch, "")

    fixed = code.rstrip()
    if closing:
        fixed = fixed + "\n" + closing

    logger.info("[SYNTAX_SENTINEL] Fechando brackets abertos: %s", counts["open_chars"])
    return fixed


def _remove_trailing_comma_single_line(code: str) -> str:
    """Remove vírgula antes de fecha parênteses/chaves/colchetes na mesma linha."""
    fixed = re.sub(r",\s*([\)\]\}])", r"\1", code)
    if fixed != code:
        logger.info("[SYNTAX_SENTINEL] Removendo trailing comma")
    return fixed


def _normalize_indentation(code: str) -> str:
    """Normaliza indentação mista (tabs → 4 espaços)."""
    if "\t" not in code:
        return code
    lines = code.split("\n")
    normalized = []
    for line in lines:
        # Conta tabs no início
        leading_tabs = len(line) - len(line.lstrip("\t"))
        if leading_tabs:
            spaces = " " * (4 * leading_tabs)
            line = spaces + line.lstrip("\t")
        normalized.append(line)
    fixed = "\n".join(normalized)
    logger.info("[SYNTAX_SENTINEL] Normalizando indentação mista")
    return fixed


# Heurísticas de correção sintática nativa (ATP ≈ 0)
_AUTO_FIXERS = [
    {
        "id": "close_brackets",
        "priority": 1,
        "detect": lambda code: _count_unclosed(code),
        "fix": _close_unclosed_brackets,
    },
    {
        "id": "trailing_comma_single_line",
        "priority": 2,
        "detect": lambda code: bool(re.search(r",\s*[\)\]\}]", code)),
        "fix": _remove_trailing_comma_single_line,
    },
    {
        "id": "indent_normalize",
        "priority": 3,
        "detect": lambda code: "\t" in code,
        "fix": _normalize_indentation,
    },
]


async def _try_ast_parse(code: str) -> Optional[ast.AST]:
    """Tenta fazer parse do código via AST nativo."""
    try:
        return ast.parse(code)
    except SyntaxError as e:
        logger.debug(
            "[SYNTAX_SENTINEL] SyntaxError: linha=%d col=%d msg=%s",
            e.lineno or 1,
            e.offset or 0,
            e.msg,
        )
        return None
    except Exception as e:
        logger.warning("[SYNTAX_SENTINEL] Erro no parse: %s", e)
        return None


def _extract_syntax_error_details(code: str) -> Optional[Dict[str, Any]]:
    """Extrai detalhes do primeiro SyntaxError encontrado."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return {
            "line": e.lineno or 1,
            "column": e.offset or 0,
            "message": e.msg or "Erro de sintaxe",
            "text": (e.text or "").rstrip("\n"),
        }


async def run_syntax_sentinel(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida código via AST e aplica correções heurísticas nativas.

    Args:
        ctx: Dict com:
            - memory["coder"], memory["multi_coder"], etc.: código para validar
            - input.task: tarefa atual

    Returns:
        Dict com:
            - output: código validado/corrigido
            - syntax_valid: bool
            - syntax_error: detalhes do erro ou None
            - auto_fixed: bool (se correção foi aplicada)
            - execution_metrics: latência/custo/sucesso
    """
    start = time.time()
    resolved_model = "syntax_sentinel"
    memory = ctx.get("memory", {})

    # Extrai código das mesmas fontes do debug_unificado
    code = ""
    sources = (
        "multi_coder",
        "coder",
        "debug_coder",
        "backend_builder",
        "frontend_builder",
        "api_builder",
    )
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
        logger.warning("[SYNTAX_SENTINEL] Nenhum código encontrado.")
        return {
            "output": "",
            "syntax_valid": False,
            "syntax_error": None,
            "auto_fixed": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": 0.0,
                "cost": 0.0,
            },
        }

    # Se for JS/JSX, delega silenciosamente (não tenta ast.parse em JS)
    js_lang = detect_lang(code)
    if js_lang in ("js", "jsx", "ts"):
        logger.info(
            "[SYNTAX_SENTINEL] Código %s detectado — pulando validação Python AST",
            js_lang,
        )
        return {
            "output": code,
            "syntax_valid": True,
            "syntax_error": None,
            "auto_fixed": False,
            "lang": js_lang,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    # Tenta parse direto — se já for válido, custo zero
    parsed = await _try_ast_parse(code)
    if parsed is not None:
        latency = (time.time() - start) * 1000.0
        logger.info(
            "[SYNTAX_SENTINEL] Código válido | latency=%.2fms",
            latency,
        )
        return {
            "output": code,
            "syntax_valid": True,
            "syntax_error": None,
            "auto_fixed": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency,
                "cost": 0.0,
            },
        }

    # Parse falhou — extrai detalhes do erro
    error_details = _extract_syntax_error_details(code)
    logger.warning(
        "[SYNTAX_SENTINEL] Erro de sintaxe | linha=%d col=%d msg=%s",
        error_details.get("line", 1),
        error_details.get("column", 0),
        error_details.get("message", "desconhecido"),
    )

    # Aplica auto-fixers priorizados
    fixed_code = code
    applied_fixes = []
    for fixer in sorted(_AUTO_FIXERS, key=lambda f: f["priority"]):
        try:
            if fixer["detect"](fixed_code):
                new_code = fixer["fix"](fixed_code)
                if new_code != fixed_code:
                    fixed_code = new_code
                    applied_fixes.append(fixer["id"])
                    # Revalida após cada fix para parar cedo
                    if await _try_ast_parse(fixed_code) is not None:
                        break
        except Exception as e:
            logger.debug("[SYNTAX_SENTINEL] Fixer %s falhou: %s", fixer["id"], e)

    latency = (time.time() - start) * 1000.0
    auto_fixed = fixed_code != code and (await _try_ast_parse(fixed_code) is not None)
    syntax_valid = await _try_ast_parse(fixed_code) is not None

    if auto_fixed:
        logger.info(
            "[SYNTAX_SENTINEL] Auto-corrigido | fixes=%s | latency=%.2fms",
            applied_fixes,
            latency,
        )
    else:
        logger.info(
            "[SYNTAX_SENTINEL] Não foi possível corrigir nativamente | latency=%.2fms → delegando ao debug_unificado",
            latency,
        )

    return {
        "output": fixed_code,
        "syntax_valid": syntax_valid,
        "syntax_error": error_details if not syntax_valid else None,
        "auto_fixed": auto_fixed,
        "applied_fixes": applied_fixes,
        "execution_metrics": {
            "model": resolved_model,
            "success": True,
            "latency": latency,
            "cost": 0.0,
        },
    }
