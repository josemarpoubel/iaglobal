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
import re
from typing import Dict, Any, List, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.security.ast_gateway import ASTGateway

logger = get_logger("iaglobal.graphs.nodes.validator_retry")

_ast_gateway = ASTGateway()
MAX_RETRIES = 3


def _normalize_unicode_quotes(code: str) -> str:
    """Replace Unicode typographic quotes with ASCII equivalents."""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
    }
    for unicode_q, ascii_q in replacements.items():
        code = code.replace(unicode_q, ascii_q)
    return code


def _sanitize_llm_output(code: str) -> str:
    """Sanitize LLM output before AST validation.

    Removes:
    - Unicode typographic quotes
    - Markdown code fences (```python ... ```)
    - Leading non-code text before first import/class/def
    - Attempts to close unclosed quotes (single, double, triple)

    Strategy:
    0. Normalize Unicode quotes to ASCII
    1. Extract from markdown fences (last occurrence)
    2. Find first valid Python statement (import/class/def/async/await)
    3. Remove all text before it
    4. Fix unclosed quotes
    """
    if not code:
        return code

    # 0. Normalize Unicode typographic quotes before any processing
    code = _normalize_unicode_quotes(code)

    # 1. Extract code from markdown fences (use last match)
    fence_pattern = r"```\w*\n(.*?)\n```"
    matches = list(re.finditer(fence_pattern, code, re.DOTALL))
    if matches:
        code = matches[-1].group(1)

    # 2. Remove leading text before first valid Python statement
    # Look for: import, from, class, def, async def, async with, await
    lines = code.split("\n")
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        # Check for valid Python statement start
        if any(
            stripped.startswith(kw)
            for kw in [
                "import ",
                "from ",
                "class ",
                "def ",
                "async def ",
                "async with ",
                "async for ",
                "await ",
            ]
        ):
            start_idx = i
            break
    code = "\n".join(lines[start_idx:])

    # 3. Fix unclosed quotes using state machine
    code = _fix_unclosed_quotes(code)

    return code.strip()


def _has_unterminated_string(code: str) -> bool:
    """
    Detecta strings não-fechadas usando tokenize do Python.

    Vantagens sobre count('"'):
      - Entende escapes (\" não conta)
      - Entende strings multilinha (triple quotes)
      - Não gera falso positivo em JSON embutido

    Returns:
        True se houver string unterminated, False caso contrário
    """
    import tokenize
    from io import StringIO

    try:
        tokens = list(tokenize.generate_tokens(StringIO(code).readline))
        return False
    except tokenize.TokenError as e:
        error_msg = e.args[0] if e.args else ""
        return "EOF in multi-line string" in error_msg or "EOF in string" in error_msg
    except Exception:
        # Fallback para state machine se tokenize falhar
        return False


def _fix_unclosed_quotes(code: str) -> str:
    """Fix unclosed quotes (single, double, triple) using a state machine."""
    # Primeiro verifica se realmente há strings unterminated
    if not _has_unterminated_string(code):
        return code  # Sem correção necessária

    result = []
    in_double = False
    in_single = False
    in_triple_double = False
    in_triple_single = False
    escape_next = False

    i = 0
    while i < len(code):
        char = code[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\":
            escape_next = True
            result.append(char)
            i += 1
            continue

        # Check for triple quotes
        if i + 2 < len(code):
            three = code[i : i + 3]
            if three == '"""' and not in_single and not in_triple_single:
                in_triple_double = not in_triple_double
                result.append('"""')
                i += 3
                continue
            elif three == "'''" and not in_double and not in_triple_double:
                in_triple_single = not in_triple_single
                result.append("'''")
                i += 3
                continue

        # Regular quotes
        if (
            char == '"'
            and not in_single
            and not in_triple_single
            and not in_triple_double
        ):
            in_double = not in_double
            result.append(char)
        elif (
            char == "'"
            and not in_double
            and not in_triple_double
            and not in_triple_single
        ):
            in_single = not in_single
            result.append(char)
        else:
            result.append(char)

        i += 1

    # Close any unclosed quotes at the end
    if in_triple_double:
        result.append('"""')
    if in_triple_single:
        result.append("'''")
    if in_double:
        result.append('"')
    if in_single:
        result.append("'")

    return "".join(result)


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

    # Sanitize LLM output before validation
    code = _sanitize_llm_output(code)

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

        # Telemetry: structured error logging with response classification
        starts_with = corrected_code[:50] if corrected_code else "EMPTY"

        # Classify response kind
        code_upper = corrected_code.upper().strip() if corrected_code else ""
        if not corrected_code or not corrected_code.strip():
            response_kind = "EMPTY"
        elif corrected_code.strip().startswith("```"):
            response_kind = "MARKDOWN"
        elif corrected_code.strip().startswith(("{", "[", '"')):
            response_kind = "JSON"
        elif corrected_code.strip().startswith("<"):
            response_kind = "HTML"
        elif any(
            corrected_code.lstrip().startswith(kw)
            for kw in [
                "import ",
                "from ",
                "class ",
                "def ",
                "async def ",
                "async with ",
                "async for ",
                "await ",
            ]
        ):
            response_kind = "PYTHON"
        elif len(corrected_code.split()) > 10 and not any(
            c.isdigit() for c in corrected_code[:20]
        ):
            response_kind = "TEXT"
        else:
            response_kind = "UNKNOWN"

        # Find first keyword
        first_keyword = None
        for line in corrected_code.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for kw in [
                "import ",
                "from ",
                "class ",
                "def ",
                "async def ",
                "async with ",
                "async for ",
                "await ",
            ]:
                if line.startswith(kw):
                    first_keyword = kw.strip()
                    break
            if first_keyword:
                break

        # Calculate prefix removed
        lines = corrected_code.split("\n")
        prefix_lines = 0
        prefix_chars = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(
                (
                    "import ",
                    "from ",
                    "class ",
                    "def ",
                    "async def ",
                    "async with ",
                    "async for ",
                    "await ",
                )
            ):
                prefix_lines = i
                prefix_chars = sum(len(lines[j]) for j in range(i))
                break

        error_info = {
            "attempt": attempt,
            "syntax_error": {
                "type": result.error_type or "SyntaxError",
                "message": last_error,
                "line": result.error_line,
                "column": getattr(result, "error_column", None),
            },
            "response_kind": response_kind,
            "first_keyword": first_keyword,
            "starts_with": starts_with,
            "prefix_removed_lines": prefix_lines,
            "prefix_removed_chars": prefix_chars,
            "ast_valid": False,
        }

        logger.warning(
            "[VALIDATOR_RETRY] Tentativa %d/%d — %s | line=%s | kind=%s | keyword=%s | prefix_removed=%d lines",
            attempt,
            MAX_RETRIES,
            last_error,
            result.error_line,
            response_kind,
            first_keyword,
            prefix_lines,
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
            new_code = _extrair_fenced_code(str(correction_result)) or str(
                correction_result
            )
            # Sanitize correction before retry
            new_code = _sanitize_llm_output(new_code)
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

    # Persist failed raw code for debugging
    try:
        from pathlib import Path
        import datetime

        fail_dir = Path("iaglobal/memory/data/validator_retry")
        fail_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fail_file = fail_dir / f"failed_{ts}.py"
        fail_file.write_text(corrected_code, encoding="utf-8")
        logger.debug("[VALIDATOR_RETRY] Falha persistida em: %s", fail_file)
    except Exception as e:
        logger.debug("[VALIDATOR_RETRY] Falha ao persistir código: %s", e)

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
