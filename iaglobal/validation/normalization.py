"""Code normalization and data sanitization module."""

import re
from typing import Any, Dict, List
from iaglobal.utils.logger import logger

import re


def normalizar_codigo(texto: str) -> str:
    """
    Remove markdown e lixo de LLM.
    """

    if not texto:
        return ""

    # Remove fences
    texto = re.sub(r"```python", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"```", "", texto)

    # Remove espaços extremos
    texto = texto.strip()

    return texto

class DataNormalizer:
    """Normalizes code and data structures."""
    
    def __init__(self):
        # Regex for markdown code blocks
        self.regex_markdown = re.compile(r"```(?:python|py)?\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)

    def limpar_codigo_fonte(self, texto_bruto: str) -> str:
        """
        Extract pure Python code removing markdown, comments, and excess whitespace.
        """
        if not texto_bruto:
            return ""

        # 1. Extract from markdown if wrapped
        match = self.regex_markdown.search(texto_bruto)
        if match:
            codigo_extraido = match.group(1)
        else:
            # Fallback
            codigo_extraido = texto_bruto.replace("```python", "").replace("```", "")

        line_buffer = []
        for line in codigo_extraido.splitlines():
            # Remove trailing whitespace
            line_limpa = line.rstrip()
            
            # Remove invisible characters
            line_limpa = "".join(ch for ch in line_limpa if ch.isprintable() or ch in ("\t", "\n", "\r", " "))
            line_buffer.append(line_limpa)

        # Join and strip
        codigo_final = "\n".join(line_buffer).strip()
        return codigo_final

    def normalize_whitespace(self, texto: str) -> str:
        """Normalize excessive whitespace."""
        # Remove multiple spaces
        texto = re.sub(r' +', ' ', texto)
        # Remove multiple newlines
        texto = re.sub(r'\n\n+', '\n\n', texto)
        return texto.strip()

# Global normalizer instance
_normalizer = DataNormalizer()

def normalize_code(texto: str) -> str:
    """Extract and sanitize Python code."""
    return _normalizer.limpar_codigo_fonte(texto)

def normalizar_codigo(texto: str) -> str:
    """Portuguese alias for normalize_code."""
    return _normalizer.limpar_codigo_fonte(texto)


