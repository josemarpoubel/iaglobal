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

    def normalizar_payload_json(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize dictionary structures with standardized keys and trimmed strings.
        """
        if not isinstance(dados, dict):
            return dados

        dados_limpos = {}
        for chave, valor in dados.items():
            chave_limpa = str(chave).strip().lower()
            
            if isinstance(valor, str):
                dados_limpos[chave_limpa] = valor.strip()
            elif isinstance(valor, dict):
                dados_limpos[chave_limpa] = self.normalizar_payload_json(valor)
            elif isinstance(valor, list):
                dados_limpos[chave_limpa] = [
                    self.normalizar_payload_json(item) if isinstance(item, dict) else item
                    for item in valor
                ]
            else:
                dados_limpos[chave_limpa] = valor

        return dados_limpos

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

def normalize_data(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize data structure."""
    return _normalizer.normalizar_payload_json(dados)

def normalizar_estrutura(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Portuguese alias for normalize_data."""
    return _normalizer.normalizar_payload_json(dados)

def normalize_text(texto: str) -> str:
    """Normalize whitespace in text."""
    return _normalizer.normalize_whitespace(texto)

def get_normalizer() -> DataNormalizer:
    """Get the global normalizer instance."""
    return _normalizer
