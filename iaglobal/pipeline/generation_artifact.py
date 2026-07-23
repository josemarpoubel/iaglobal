# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
GenerationArtifact — Contrato comum para saídas de agentes geradores.

Objetivo:
  Padronizar a troca de artefatos entre nós do pipeline, eliminando
  duplicação de lógica de sanitização e validação.

Uso:
  artifact = GenerationArtifact(raw_output=llm_response)
  artifact.sanitize()
  artifact.validate_ast()

  if artifact.is_valid:
      return artifact.sanitized_output
  else:
      return artifact.get_error_context()

Responsabilidades:
  - Detectar linguagem (Python, JS, JSON, Markdown, etc.)
  - Extrair código de fences Markdown
  - Remover texto explicativo antes do código
  - Validar sintaxe (AST para Python)
  - Classificar formato da resposta (MARKDOWN, TEXT, PYTHON, etc.)
  - Prover metadados para telemetria
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ResponseKind(Enum):
    """Classificação do formato da resposta do LLM."""

    MARKDOWN = "markdown"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSON = "json"
    HTML = "html"
    TEXT = "text"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class ValidationStatus(Enum):
    """Status da validação do artefato."""

    NOT_VALIDATED = "not_validated"
    VALID = "valid"
    INVALID = "invalid"
    SKIPPED = "skipped"


@dataclass
class GenerationArtifact:
    """
    Artefato padronizado de geração de código.

    Atributos:
        raw_output: Saída bruta do LLM (com markdown, texto explicativo, etc.)
        sanitized_output: Código sanitizado (sem fences, sem texto antes)
        language: Linguagem detectada (python, javascript, etc.)
        response_kind: Formato da resposta (MARKDOWN, TEXT, PYTHON, etc.)
        validation_status: Status da validação
        validation_errors: Lista de erros de validação
        metadata: Metadados para telemetria
    """

    raw_output: str
    sanitized_output: str = ""
    language: Optional[str] = None
    response_kind: ResponseKind = ResponseKind.UNKNOWN
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.sanitized_output and self.raw_output:
            self.sanitize()

    def sanitize(self) -> str:
        """
        Sanitiza saída do LLM:
          1. Extrai código de fences Markdown (última ocorrência)
          2. Remove texto antes do primeiro statement válido
          3. Detecta linguagem
          4. Classifica formato da resposta

        Returns:
            Código sanitizado
        """
        code = self.raw_output or ""

        # Classificar formato da resposta
        self.response_kind = self._classify_response(code)

        # 1. Extrair de fences Markdown
        fence_pattern = r"```\w*\n(.*?)\n```"
        matches = list(re.finditer(fence_pattern, code, re.DOTALL))
        if matches:
            code = matches[-1].group(1)
            self.metadata["extracted_from_fence"] = True
        else:
            self.metadata["extracted_from_fence"] = False

        # 2. Detectar linguagem
        self.language = self._detect_language(code)

        # 3. Remover texto antes do primeiro statement válido
        code = self._remove_leading_text(code)

        self.sanitized_output = code.strip()
        self.metadata["sanitized"] = True

        return self.sanitized_output

    def _classify_response(self, code: str) -> ResponseKind:
        """Classifica o formato da resposta do LLM."""
        if not code or not code.strip():
            return ResponseKind.EMPTY

        code_stripped = code.strip()

        if code_stripped.startswith("```"):
            return ResponseKind.MARKDOWN

        if code_stripped.startswith(("{", "[", '"')):
            return ResponseKind.JSON

        if code_stripped.startswith("<"):
            return ResponseKind.HTML

        if self._looks_like_python(code_stripped):
            return ResponseKind.PYTHON

        if self._looks_like_javascript(code_stripped):
            return ResponseKind.JAVASCRIPT

        # Se tem muitas palavras e poucos símbolos de código
        if len(code_stripped.split()) > 10 and not any(
            c.isdigit() for c in code_stripped[:20]
        ):
            return ResponseKind.TEXT

        return ResponseKind.UNKNOWN

    def _looks_like_python(self, code: str) -> bool:
        """Verifica se parece código Python."""
        keywords = [
            "import ",
            "from ",
            "class ",
            "def ",
            "async def ",
            "async with ",
            "async for ",
            "await ",
            "if ",
            "for ",
            "while ",
            "try:",
            "except",
            "with ",
            "return ",
        ]
        return any(code.lstrip().startswith(kw) for kw in keywords)

    def _looks_like_javascript(self, code: str) -> bool:
        """Verifica se parece código JavaScript."""
        keywords = [
            "function ",
            "const ",
            "let ",
            "var ",
            "class ",
            "export ",
            "import ",
            "async ",
            "await ",
            "if ",
            "for ",
            "while ",
            "try {",
            "catch",
            "return ",
        ]
        return any(code.lstrip().startswith(kw) for kw in keywords)

    def _detect_language(self, code: str) -> Optional[str]:
        """Detecta linguagem do código."""
        if self._looks_like_python(code):
            return "python"
        if self._looks_like_javascript(code):
            return "javascript"
        if code.strip().startswith(("{", "[", '"')):
            return "json"
        if code.strip().startswith("<"):
            return "html"
        return None

    def _remove_leading_text(self, code: str) -> str:
        """Remove texto antes do primeiro statement válido."""
        lines = code.split("\n")
        start_idx = 0

        # Calcular prefixo removido para telemetria
        prefix_lines = 0
        prefix_chars = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Pular linhas vazias e comentários
            if not stripped or stripped.startswith("#"):
                continue

            # Verificar keywords de Python
            python_keywords = [
                "import ",
                "from ",
                "class ",
                "def ",
                "async def ",
                "async with ",
                "async for ",
                "await ",
            ]
            if any(stripped.startswith(kw) for kw in python_keywords):
                start_idx = i
                prefix_lines = i
                prefix_chars = sum(len(lines[j]) for j in range(i))
                self.metadata["prefix_removed_lines"] = prefix_lines
                self.metadata["prefix_removed_chars"] = prefix_chars
                break

        return "\n".join(lines[start_idx:])

    def validate_ast(self) -> bool:
        """
        Valida sintaxe Python usando AST.

        Returns:
            True se válido, False se inválido
        """
        if not self.sanitized_output:
            self.validation_status = ValidationStatus.INVALID
            self.validation_errors.append("Código vazio")
            return False

        # Pular validação se não for Python
        if self.language != "python":
            self.validation_status = ValidationStatus.SKIPPED
            self.metadata["validation_skipped_reason"] = "not_python"
            return True

        try:
            from iaglobal.security.ast_gateway import ASTGateway

            gateway = ASTGateway()
            result = gateway.parse(self.sanitized_output)

            if result.valid:
                self.validation_status = ValidationStatus.VALID
                self.validation_errors = []
                return True
            else:
                self.validation_status = ValidationStatus.INVALID
                self.validation_errors = result.errors
                self.metadata["error_line"] = result.error_line
                self.metadata["error_type"] = result.error_type
                return False

        except Exception as e:
            self.validation_status = ValidationStatus.INVALID
            self.validation_errors.append(str(e))
            return False

    def is_valid(self) -> bool:
        """Verifica se o artefato é válido."""
        if self.validation_status == ValidationStatus.NOT_VALIDATED:
            self.validate_ast()
        return self.validation_status == ValidationStatus.VALID

    def get_error_context(self) -> Dict[str, Any]:
        """Retorna contexto de erro para correção."""
        return {
            "raw_output": self.raw_output,
            "sanitized_output": self.sanitized_output,
            "language": self.language,
            "response_kind": self.response_kind.value,
            "validation_status": self.validation_status.value,
            "validation_errors": self.validation_errors,
            "metadata": self.metadata,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializa artefato para dict."""
        return {
            "raw_output": self.raw_output,
            "sanitized_output": self.sanitized_output,
            "language": self.language,
            "response_kind": self.response_kind.value,
            "validation_status": self.validation_status.value,
            "is_valid": self.is_valid(),
            "metadata": self.metadata,
        }


def create_artifact(
    raw_output: str, language: Optional[str] = None
) -> GenerationArtifact:
    """Factory function para criar GenerationArtifact."""
    artifact = GenerationArtifact(raw_output=raw_output)
    if language:
        artifact.language = language
    return artifact
