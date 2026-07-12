# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
JSLanguageValidator — Validação sintática nativa para JavaScript/JSX via esprima.

Filosofia:
  Espelha o SyntaxSentinel (Python) mas para JS/JSX/TS.
  Usa esprima (pure Python, sem GPU) para parsear e detectar erros de sintaxe.
  Aplica correções heurísticas antes de delegar ao debug_unificado.

Integração:
  - Entrada: código JS/JSX (string)
  - Saída: código validado/corrigido + diagnóstico
  - Fallback: se correção nativa falhar, sinaliza para debug_unificado usar LLM
"""
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.validation.js_validator")


@dataclass
class JSValidationResult:
    valid: bool
    code: Optional[str]
    errors: List[str]
    warnings: List[str] = field(default_factory=list)
    fixed: bool = False
    applied_fixes: List[str] = field(default_factory=list)
    lang: str = "js"


def detect_lang(code: str) -> Optional[str]:
    """Detecta se o código é JavaScript/JSX/TypeScript."""
    if not code or not code.strip():
        return None
    first_line = code.strip().split("\n")[0].strip()
    has_jsx_tag = bool(re.search(r'<[A-Za-z][A-Za-z0-9]*[\s/>]', code))
    has_import_export = bool(re.search(r'\b(import|export)\s', first_line))
    has_js_arrow = bool(re.search(r'(const|let|var)\s+\w+\s*=\s*(\(|\w+\s*=>)', code))
    has_js_function = bool(re.search(r'\bfunction\s*\*?\s*\(', first_line))
    has_typescript = bool(re.search(r':\s*(string|number|boolean|void|any|never|unknown)\s*[=(,;]', code))
    has_require = bool(re.search(r'\brequire\s*\(', code))
    has_react = bool(re.search(r'from\s+[\'"]react[\'"]', code))
    has_js_var = bool(re.search(r'\b(const|let|var)\s+\w+\s*[=;]', code))
    has_console_log = bool(re.search(r'\bconsole\.\w+\s*\(', code))
    has_async_await = bool(re.search(r'\b(async|await)\s', code))
    has_module_exports = bool(re.search(r'module\.exports\s*=', code))

    if not (has_jsx_tag or has_import_export or has_js_arrow or has_js_function
            or has_require or has_react or has_js_var or has_console_log
            or has_async_await or has_module_exports):
        return None

    if has_typescript:
        return "ts"
    if has_jsx_tag or has_react:
        return "jsx"
    return "js"


def _count_unclosed(code: str) -> Dict[str, int]:
    """Conta parênteses/chaves/colchetes não fechados (ignorando strings/regex)."""
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    in_string = None
    i = 0
    while i < len(code):
        ch = code[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in "\"'`":
            in_string = ch
            i += 1
            continue
        if ch == "/" and i + 1 < len(code) and code[i + 1] in "/*":
            if code[i + 1] == "/":
                while i < len(code) and code[i] != "\n":
                    i += 1
                continue
            if code[i + 1] == "*":
                i += 2
                while i + 1 < len(code) and not (code[i] == "*" and code[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
        i += 1
    return {"unclosed": len(stack), "open_chars": "".join(stack)}


def _close_unclosed_brackets(code: str) -> str:
    """Fecha parênteses/chaves/colchetes abertos."""
    counts = _count_unclosed(code)
    if counts["unclosed"] <= 0:
        return code
    open_to_close = {"(": ")", "[": "]", "{": "}"}
    closing = ""
    for ch in reversed(counts["open_chars"]):
        closing += open_to_close.get(ch, "")
    fixed = code.rstrip() + "\n" + closing
    logger.info("[JS_VALIDATOR] Fechando brackets abertos: %s", counts["open_chars"])
    return fixed


def _close_unclosed_strings(code: str) -> str:
    """Fecha strings não fechadas (simples, duplas, template literals)."""
    in_string = None
    for i, ch in enumerate(code):
        if in_string:
            if ch == "\\":
                continue
            if ch == in_string:
                in_string = None
        elif ch in "\"'`":
            in_string = ch
    if in_string:
        fixed = code.rstrip() + in_string
        logger.info("[JS_VALIDATOR] Fechando string não fechada: %s", in_string)
        return fixed
    return code


def _normalize_indentation(code: str) -> str:
    """Normaliza indentação mista (tabs → 4 espaços)."""
    if "\t" not in code:
        return code
    lines = code.split("\n")
    normalized = []
    for line in lines:
        leading_tabs = len(line) - len(line.lstrip("\t"))
        if leading_tabs:
            line = " " * (4 * leading_tabs) + line.lstrip("\t")
        normalized.append(line)
    fixed = "\n".join(normalized)
    logger.info("[JS_VALIDATOR] Normalizando indentação mista")
    return fixed


_AUTO_FIXERS = [
    {
        "id": "close_brackets",
        "priority": 1,
        "detect": lambda code: _count_unclosed(code)["unclosed"] > 0,
        "fix": _close_unclosed_brackets,
    },
    {
        "id": "close_strings",
        "priority": 2,
        "detect": lambda code: (
            code.count("'") % 2 != 0 or code.count('"') % 2 != 0 or code.count("`") % 2 != 0
        ),
        "fix": _close_unclosed_strings,
    },
    {
        "id": "indent_normalize",
        "priority": 3,
        "detect": lambda code: "\t" in code,
        "fix": _normalize_indentation,
    },
]


def _get_parse_options(code: str) -> Tuple[str, Dict[str, Any]]:
    """Determina opções de parse baseado no conteúdo do código."""
    has_import_export = bool(re.search(r'\b(import|export)\s', code))
    has_jsx = bool(re.search(r'<[A-Za-z][A-Za-z0-9]*[\s>]', code)) or bool(re.search(r'from\s+[\'"]react[\'"]', code))

    if has_import_export:
        source_type = "module"
    else:
        source_type = "script"

    options = {"jsx": has_jsx}
    return source_type, options


def _try_parse(code: str) -> Optional[Dict[str, Any]]:
    """Tenta fazer parse via esprima."""
    try:
        import esprima
        source_type, options = _get_parse_options(code)
        if source_type == "module":
            ast = esprima.parseModule(code, options)
        else:
            ast = esprima.parseScript(code, options)
        return ast
    except Exception as e:
        return None


def _extract_syntax_error(code: str) -> Optional[Dict[str, Any]]:
    """Extrai detalhes do primeiro erro de sintaxe via esprima."""
    try:
        import esprima
        source_type, options = _get_parse_options(code)
        if source_type == "module":
            esprima.parseModule(code, options)
        else:
            esprima.parseScript(code, options)
        return None
    except Exception as e:
        msg = str(e)
        line_match = re.search(r"Line (\d+)", msg)
        col_match = re.search(r"Column (\d+)", msg)
        return {
            "line": int(line_match.group(1)) if line_match else 1,
            "column": int(col_match.group(1)) if col_match else 0,
            "message": msg.split("\n")[0] if msg else "Erro de sintaxe JS",
        }


class JSLanguageValidator:
    """Validador de sintaxe JavaScript/JSX usando esprima."""

    def validate(self, code: str) -> JSValidationResult:
        """Valida código JS/JSX e retorna resultado."""
        if not code or not code.strip():
            return JSValidationResult(
                valid=False, code=None, errors=["Código vazio"],
            )

        lang = detect_lang(code)
        if lang is None:
            return JSValidationResult(
                valid=False, code=None, errors=["Código não parece ser JavaScript/JSX"],
                lang="unknown",
            )

        ast = _try_parse(code)
        if ast is not None:
            return JSValidationResult(
                valid=True, code=code, errors=[], lang=lang,
            )

        error = _extract_syntax_error(code)
        return JSValidationResult(
            valid=False, code=code, errors=[error["message"]],
            warnings=[], lang=lang,
        )

    def auto_fix(self, code: str) -> JSValidationResult:
        """Aplica correções heurísticas e revalida."""
        start = time.time()
        original = code
        applied_fixes = []

        fixed_code = code
        for fixer in sorted(_AUTO_FIXERS, key=lambda f: f["priority"]):
            try:
                if fixer["detect"](fixed_code):
                    new_code = fixer["fix"](fixed_code)
                    if new_code != fixed_code:
                        fixed_code = new_code
                        applied_fixes.append(fixer["id"])
                        if _try_parse(fixed_code) is not None:
                            break
            except Exception as e:
                logger.debug("[JS_VALIDATOR] Fixer %s falhou: %s", fixer["id"], e)

        latency = (time.time() - start) * 1000.0
        ast = _try_parse(fixed_code)
        syntax_valid = ast is not None
        auto_fixed = fixed_code != original and syntax_valid

        lang = detect_lang(fixed_code) or "js"
        error = None if syntax_valid else _extract_syntax_error(fixed_code)

        if auto_fixed:
            logger.info(
                "[JS_VALIDATOR] Auto-corrigido | fixes=%s lang=%s latency=%.2fms",
                applied_fixes, lang, latency,
            )
        elif syntax_valid:
            logger.info(
                "[JS_VALIDATOR] Código válido sem correções | lang=%s latency=%.2fms",
                lang, latency,
            )
        else:
            logger.info(
                "[JS_VALIDATOR] Não foi possível corrigir nativamente | lang=%s latency=%.2fms",
                lang, latency,
            )

        return JSValidationResult(
            valid=syntax_valid,
            code=fixed_code,
            errors=[error["message"]] if error else [],
            fixed=auto_fixed,
            applied_fixes=applied_fixes,
            lang=lang,
        )
