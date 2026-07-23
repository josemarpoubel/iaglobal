# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SearchResultProcessor — ToolLibrary tool que agentes (Coder, Debugger, etc.)
podem chamar via _resolve_with_tools() para processar resultados de busca web.

Diferente da injeção passiva via SearchMiddleware.enrich(), essa ferramenta
permite que o próprio agente decida processar os resultados com Python,
extraindo código, fatos e referências de forma estruturada.
"""

import json
import re
from typing import Any, Dict, List


def process_search_results(
    raw_text: str, max_code_blocks: int = 3, max_facts: int = 6
) -> str:
    """Processa texto bruto de busca web e retorna resumo estruturado.

    Args:
        raw_text: Texto bruto dos resultados de busca (snippets, código, etc.)
        max_code_blocks: Máximo de blocos de código a extrair
        max_facts: Máximo de fatos/bullet points a incluir

    Returns:
        String formatada com Fatos, Código Relevante, e Referências
    """
    if not raw_text or not raw_text.strip():
        return ""

    code_blocks: List[Dict[str, str]] = []
    for match in re.finditer(r"```(\w*)\n(.*?)```", raw_text, re.DOTALL):
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        if len(code) > 20:
            code_blocks.append({"lang": lang, "code": code})

    urls = list(dict.fromkeys(re.findall(r"https?://[^\s)>\"']+", raw_text)))

    bullets: List[str] = []
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 30:
            bullets.append(stripped[2:].split("(score=")[0].strip()[:200])

    parts: List[str] = []

    if bullets:
        parts.append("## Fatos")
        for b in bullets[:max_facts]:
            parts.append(f"- {b}")

    if code_blocks:
        parts.append("## Código Relevante")
        for cb in code_blocks[:max_code_blocks]:
            label = cb["lang"].capitalize() if cb["lang"] != "text" else "Código"
            parts.append(f"```{cb['lang']}\n{cb['code']}\n```")

    if urls:
        parts.append("## Referências")
        for u in urls[:5]:
            parts.append(f"- {u}")

    return "\n\n".join(parts)


def process_search_results_structured(raw_text: str) -> Dict[str, Any]:
    """Versão estruturada — retorna dict em vez de string formatada.

    Útil quando o agente quer inspecionar código/fatos individualmente
    em vez de receber texto pré-formatado.
    """
    code_blocks: List[Dict[str, str]] = []
    for match in re.finditer(r"```(\w*)\n(.*?)```", raw_text, re.DOTALL):
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        if len(code) > 20:
            code_blocks.append({"lang": lang, "code": code})

    urls = list(dict.fromkeys(re.findall(r"https?://[^\s)>\"']+", raw_text)))

    bullets: List[str] = []
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 30:
            bullets.append(stripped[2:].split("(score=")[0].strip()[:200])

    return {
        "code_blocks": code_blocks[:5],
        "urls": urls[:10],
        "facts": bullets[:10],
        "char_count": len(raw_text),
        "source_count": len(urls) + len(bullets),
    }


from iaglobal.tools.tool_library import tool_library

tool_library.register(
    name="search_context_processor",
    fn=process_search_results,
    tags=[
        "search",
        "web",
        "context",
        "processor",
        "code extraction",
        "fact extraction",
        "url extraction",
        "structured output",
    ],
    description=(
        "Processa resultados de busca web em formato estruturado com "
        "blocos de código, fatos e referências. Parâmetros: "
        "raw_text (str), max_code_blocks (int=3), max_facts (int=6). "
        "Retorna string formatada markdown. Use quando precisar extrair "
        "informação relevante de resultados de busca."
    ),
)

tool_library.register(
    name="search_context_processor_structured",
    fn=process_search_results_structured,
    tags=[
        "search",
        "web",
        "context",
        "processor",
        "structured",
        "json",
        "data extraction",
    ],
    description=(
        "Processa resultados de busca web e retorna dict estruturado "
        "com code_blocks, urls, facts. Parâmetro: raw_text (str). "
        "Retorna dict para inspeção programática. Use quando precisar "
        "analisar resultados de busca com código Python."
    ),
)
