# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
GenerationClassifier — Classifica o tipo de artefato gerado por LLM.

Tipos de artefato:
- CODE: Código executável (Python, HTML, JS, CSS, etc.)
- MARKDOWN: Documentação ou explicação em markdown
- SEARCH_RESULT: Resultados de busca (links, texto descritivo)
- HTML: Página HTML completa
- JSON: Dados estruturados em JSON
- TEXT: Texto puro (sem formatação)

Uso:
    classifier = GenerationClassifier()
    artifact_type = classifier.classify(text)
    if artifact_type == "CODE":
        # Processar como código
    elif artifact_type == "MARKDOWN":
        # Processar como documentação
    ...
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class ArtifactClassification:
    type: str
    confidence: float
    markers: list[str]


class GenerationClassifier:
    """Classifica o tipo de artefato gerado por LLM."""

    def __init__(self):
        self._code_markers = [
            r"def \w+\(.*\):",
            r"class \w+\(.*\):",
            r"import \w+",
            r"from \w+ import",
            r"async def \w+\(.*\):",
            r"function \w+\(.*\)\s*{",
            r"print\(",
            r"const \w+ =",
            r"let \w+ =",
            r"var \w+ =",
            r"if __name__ ==",
            r"console\.log\(",
            r"console\.error\(",
            r"console\.warn\(",
            r"return ",
            r"app\.",
            r"document\.",
            r"window\.",
            r"=>",
        ]

        self._markdown_markers = [
            r"^#{1,6}\s+.*",
            r"^\s*[-*•]\s+.*",
            r"^>\s+.*",
            r"```",
            r"\*\*.*\*\*",
            r"__.*__",
        ]

        self._search_markers = [
            r"https?://\S+",
            r"\.com/\S+",
            r"\.br/\S+",
            r"pesquisa",
            r"resultados",
            r"links? úteis",
            r"veja também",
            r"conforme",
            r"conforme os resultados",
            r"conforme a pesquisa",
        ]

        self._html_markers = [
            r"<!DOCTYPE html>",
            r"<html",
            r"<head",
            r"<body",
            r"<div",
            r"<script",
            r"<style",
            r"<meta",
            r"<title",
            r"<link",
            r"<img",
        ]

        self._json_markers = [
            r"\{\s*[" + r'"' + r"']",
            r"\{\s*\w+\s*:\s*",
            r"\}",
            r"\[\s*\{",
            r"\[\s*\"",
        ]

    def classify(self, text: str) -> ArtifactClassification:
        """
        Classifica o tipo de artefato gerado.

        Args:
            text: Texto a ser classificado

        Returns:
            ArtifactClassification: Tipo, confiança e marcadores encontrados
        """
        if not text or not isinstance(text, str):
            return ArtifactClassification(
                type="TEXT",
                confidence=1.0,
                markers=["texto vazio ou inválido"],
            )

        text_lower = text.lower()
        markers_found = []

        # 1. Verificar se é JSON
        if self._looks_like_json(text):
            markers_found.append("json")
            return ArtifactClassification(
                type="JSON",
                confidence=0.95,
                markers=markers_found,
            )

        # 2. Verificar se é CODE (antes de HTML — modelo pequeno pode
        #    envelopar código em scaffold HTML; o código é o conteúdo primário)
        if self._looks_like_code(text, text_lower):
            markers_found.append("code")
            return ArtifactClassification(
                type="CODE",
                confidence=0.80,
                markers=markers_found,
            )

        # 3. Verificar se é HTML
        if self._looks_like_html(text):
            markers_found.append("html")
            return ArtifactClassification(
                type="HTML",
                confidence=0.90,
                markers=markers_found,
            )

        # 4. Verificar se é MARKDOWN
        if self._looks_like_markdown(text):
            markers_found.append("markdown")
            return ArtifactClassification(
                type="MARKDOWN",
                confidence=0.85,
                markers=markers_found,
            )

        # 5. Verificar se é SEARCH_RESULT
        if self._looks_like_search_result(text, text_lower):
            markers_found.append("search")
            return ArtifactClassification(
                type="SEARCH_RESULT",
                confidence=0.90,
                markers=markers_found,
            )

        # 6. Default: TEXT
        return ArtifactClassification(
            type="TEXT",
            confidence=0.70,
            markers=["texto puro"],
        )

    def _looks_like_json(self, text: str) -> bool:
        """Verifica se o texto parece JSON."""
        text_stripped = text.strip()
        if text_stripped.startswith("{") and text_stripped.endswith("}"):
            return True
        if text_stripped.startswith("[") and text_stripped.endswith("]"):
            return True
        return any(marker in text for marker in self._json_markers)

    def _looks_like_html(self, text: str) -> bool:
        """Verifica se o texto parece HTML."""
        return any(marker in text for marker in self._html_markers)

    def _looks_like_markdown(self, text: str) -> bool:
        """Verifica se o texto parece MARKDOWN."""
        return any(
            re.search(marker, text, re.MULTILINE) for marker in self._markdown_markers
        )

    def _looks_like_search_result(self, text: str, text_lower: str) -> bool:
        """Verifica se o texto parece resultado de busca."""
        if any(marker in text_lower for marker in self._search_markers):
            return True
        if "http" in text_lower and ("com" in text_lower or "br" in text_lower):
            return True
        return False

    def _looks_like_code(self, text: str, text_lower: str) -> bool:
        """Verifica se o texto parece código executável."""
        if len(text.strip()) < 10:
            return False
        return any(re.search(marker, text) for marker in self._code_markers)
