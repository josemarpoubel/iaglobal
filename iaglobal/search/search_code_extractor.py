"""
search_code_extractor.py — Extrai blocos de código estruturados de resultados de busca.

Metáfora biológica:
  - Resultado de busca = plasma sanguíneo (nutrientes brutos)
  - CodeBlock = eritrócito (hemácia que carrega oxigênio/utilidade)
  - Este módulo = medula óssea (extrai células úteis do plasma)
"""

import re
import ast
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from iaglobal.security.ast_gateway import ASTGateway

logger = logging.getLogger("iaglobal")

_ast_gateway = ASTGateway()


@dataclass
class CodeBlock:
    language: str
    code: str
    source: str = ""
    confidence: float = 0.5
    line_count: int = 0

    def __post_init__(self):
        self.line_count = len(self.code.splitlines())


SOURCE_RE = re.compile(r"^===+\s*(\S+)\s*===+", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`]{10,})`")  # inline code >= 10 chars


class SearchCodeExtractor:
    """Extrai blocos de código reutilizáveis de textos de busca."""

    LANGUAGE_EXT_MAP = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "ts": ".ts",
        "tsx": ".tsx",
        "html": ".html",
        "css": ".css",
        "bash": ".sh",
        "shell": ".sh",
        "sql": ".sql",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yaml",
        "xml": ".xml",
        "php": ".php",
        "rust": ".rs",
        "go": ".go",
        "java": ".java",
        "ruby": ".rb",
        "react": ".tsx",
        "jsx": ".jsx",
    }

    def extract(self, search_text: str, min_lines: int = 3) -> List[CodeBlock]:
        """Extrai todos os blocos de código do texto de busca."""
        if not search_text or not search_text.strip():
            return []
        blocks: List[CodeBlock] = []
        sources = self._split_sources(search_text)
        for source_name, source_body in sources:
            source_blocks = self._extract_from_source(source_body, source_name)
            blocks.extend(source_blocks)
        filtered = [b for b in blocks if b.line_count >= min_lines]
        filtered.sort(key=lambda b: b.line_count, reverse=True)
        return filtered

    def extract_by_language(
        self, search_text: str, language: str, min_lines: int = 3
    ) -> List[CodeBlock]:
        """Extrai blocos de uma linguagem específica."""
        all_blocks = self.extract(search_text, min_lines)
        return [b for b in all_blocks if b.language == language]

    def extract_html_components(self, html_blocks_or_text: list) -> dict:
        """Extrai componentes HTML: head, body, style, script separadamente.

        Aceita lista de CodeBlock com language='html' OU texto bruto.
        Se for texto, primeiro extrai os blocos HTML internamente.
        """
        if isinstance(html_blocks_or_text, str):
            all_blocks = self.extract(html_blocks_or_text, min_lines=2)
            html_blocks = [b for b in all_blocks if b.language in ("html",)]
        else:
            html_blocks = [
                b
                for b in html_blocks_or_text
                if hasattr(b, "language") and b.language in ("html",)
            ]
        result = {"head": [], "body": [], "style": [], "script": []}
        for block in html_blocks:
            code = block.code if hasattr(block, "code") else block
            head = self._extract_tag(code, "head")
            body = self._extract_tag(code, "body")
            style = self._extract_tag(code, "style")
            script = self._extract_tag(code, "script")
            if head:
                result["head"].append(head)
            if body:
                result["body"].append(body)
            if style:
                result["style"].append(style)
            if script:
                result["script"].append(script)
            if not any([head, body, style, script]):
                result["body"].append(code)
        return result

    def _split_sources(self, text: str) -> List[tuple]:
        """Divide o texto agregado em seções por fonte."""
        sections = SOURCE_RE.split(text)
        if len(sections) <= 1:
            return [("raw", text)]
        sources = []
        for i in range(1, len(sections), 2):
            name = sections[i].strip()
            body = sections[i + 1].strip() if i + 1 < len(sections) else ""
            sources.append((name, body))
        if not sources:
            sources.append(("raw", text))
        return sources

    def _extract_from_source(self, text: str, source_name: str) -> List[CodeBlock]:
        """Extrai blocos de código de uma única fonte."""
        blocks: List[CodeBlock] = []
        seen_codes: set = set()
        for match in CODE_BLOCK_RE.finditer(text):
            lang = (match.group(1) or "text").lower()
            code = match.group(2).strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            confidence = self._calc_confidence(code, lang)
            blocks.append(
                CodeBlock(
                    language=lang,
                    code=code,
                    source=source_name,
                    confidence=confidence,
                )
            )
        for match in INLINE_CODE_RE.finditer(text):
            code = match.group(1).strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            blocks.append(
                CodeBlock(
                    language="text",
                    code=code,
                    source=source_name,
                    confidence=0.3,
                )
            )
        return blocks

    def _calc_confidence(self, code: str, language: str) -> float:
        """Estima confiança do bloco baseado em validade sintática."""
        conf = 0.5
        if language in ("python", "py"):
            result = _ast_gateway.parse(code)
            if result.valid:
                conf += 0.4
            if re.search(r"def |class |import |from ", code):
                conf += 0.1
        elif language == "html":
            if re.search(
                r"<!DOCTYPE|<html|<head|<body|<div|<style", code, re.IGNORECASE
            ):
                conf += 0.3
            if code.count("<") > 3 and code.count(">") > 3:
                conf += 0.2
        elif language == "css":
            if re.search(r"\{.*\}", code, re.DOTALL):
                conf += 0.3
            if re.search(r"@media|display|color|margin|padding|flex|grid", code):
                conf += 0.2
        elif language == "javascript" or language == "js":
            if re.search(
                r"function|const |let |var |=>|document|window|addEventListener", code
            ):
                conf += 0.3
            try:
                _check_js_syntax(code)
                conf += 0.2
            except Exception:
                pass
        return min(conf, 1.0)

    @staticmethod
    def _extract_tag(html: str, tag: str) -> str:
        """Extrai conteúdo de uma tag HTML."""
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""


def _check_js_syntax(code: str) -> None:
    """Validação básica de JS: checa brackets balanceados."""
    stack = []
    pairs = {"{": "}", "(": ")", "[": "]"}
    for ch in code:
        if ch in pairs:
            stack.append(ch)
        elif ch in pairs.values():
            if not stack or pairs[stack.pop()] != ch:
                raise SyntaxError("Unbalanced brackets")


def extract_from_search_results(
    search_results: str, min_lines: int = 3
) -> List[CodeBlock]:
    """Função de conveniência — extrai blocos de código de search_results."""
    extractor = SearchCodeExtractor()
    return extractor.extract(search_results, min_lines=min_lines)
