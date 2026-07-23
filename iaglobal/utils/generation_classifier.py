# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Generation classifier — classifica resposta textual do provider em categorias
semânticas (CODE, HTML, MARKDOWN, ERROR_PAGE, EMPTY) para diagnóstico precoce
de respostas inválidas antes do parser.
"""

import enum


class GenerationKind(enum.Enum):
    CODE = "code"
    HTML = "html"
    MARKDOWN = "markdown"
    ERROR_PAGE = "error_page"
    EMPTY = "empty"
    UNKNOWN = "unknown"


def classify_generation(text: str) -> GenerationKind:
    if not text or not text.strip():
        return GenerationKind.EMPTY

    stripped = text.lstrip()

    if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
        return GenerationKind.HTML

    if stripped.startswith("```"):
        return GenerationKind.CODE

    if "<?php" in stripped[:500]:
        return GenerationKind.CODE

    if (
        stripped.startswith("HTTP/")
        or stripped.startswith("404")
        or stripped.startswith("50")
    ):
        if any(
            code in stripped[:50] for code in ("404", "500", "502", "503", "403", "401")
        ):
            return GenerationKind.ERROR_PAGE

    if (
        stripped.startswith("# ")
        or stripped.startswith("##")
        or stripped.startswith("---")
    ):
        return GenerationKind.MARKDOWN

    # Heurísticas para código antes de cair em UNKNOWN
    _code_indicators = (
        "def ",
        "class ",
        "import ",
        "from ",
        "return ",
        "if __name__",
        "function ",
        "const ",
        "let ",
        "var ",
        "fn ",
        "func ",
        "public ",
        "private ",
        "protected ",
        "static ",
        "#include",
        "package ",
        "namespace ",
        "SELECT ",
        "INSERT ",
        "CREATE ",
        "ALTER ",
        "DROP ",
        "{",
        "(",
        "=>",
        "->",
    )
    if any(stripped.startswith(ind) for ind in _code_indicators):
        return GenerationKind.CODE

    return GenerationKind.UNKNOWN
