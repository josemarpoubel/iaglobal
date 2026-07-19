# iaglobal/cognition/correction_context.py
"""
CorrectionContext — Transforma erros de validação AST em prompts de correção acionáveis.

Fluxo:
  1. Recebe ASTResult (via ASTGateway)
  2. Extrai error_type, line, snippet, fix_hint
  3. Monta prompt contextualizado para re-invocação do coder
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

from iaglobal.security.ast_gateway import ASTResult


@dataclass
class CorrectionContext:
    original_code: str
    attempt: int
    max_attempts: int
    errors: List[str] = field(default_factory=list)
    error_type: Optional[str] = None
    error_line: Optional[int] = None
    error_snippet: Optional[str] = None
    fix_hint: Optional[str] = None
    past_attempts: List[str] = field(default_factory=list)

    @property
    def correction_prompt(self) -> str:
        lines = [f"O código abaixo FALHOU na validação AST (tentativa {self.attempt}/{self.max_attempts}):"]
        lines.append("")
        lines.append("Erro detectado:")
        if self.error_type:
            lines.append(f"  Tipo: {self.error_type}")
        if self.error_line:
            lines.append(f"  Linha: {self.error_line}")
        if self.error_snippet:
            lines.append(f"  Trecho: {self.error_snippet.strip()}")
        for err in self.errors:
            lines.append(f"  Mensagem: {err}")
        if self.fix_hint:
            lines.append(f"  Correção sugerida: {self.fix_hint}")
        if self.past_attempts:
            lines.append(f"\nTentativas anteriores de correção ({len(self.past_attempts)}):")
            for i, prev in enumerate(self.past_attempts, 1):
                preview = prev[:200].replace("\n", "\\n")
                lines.append(f"  [{i}] {preview}...")
        lines.append(f"\nCódigo atual (com erro):\n```python\n{self.original_code}\n```")
        lines.append(f"\nReescreva o código corrigindo APENAS o erro apontado acima.")
        lines.append(f"Responda APENAS com o código corrigido em bloco ```python.")
        return "\n".join(lines)

    def to_failure_record(self, provider: str = "") -> Dict[str, Any]:
        return {
            "failure_type": "syntax",
            "provider": provider,
            "error_type": self.error_type,
            "error": self.errors[0] if self.errors else "unknown",
            "line": self.error_line,
            "attempts": self.attempt,
            "resolved": False,
        }


def build_correction_context(
    code: str,
    ast_result: ASTResult,
    attempt: int = 1,
    max_attempts: int = 3,
    past_attempts: Optional[List[str]] = None,
) -> CorrectionContext:
    """Constrói CorrectionContext a partir de ASTResult."""
    return CorrectionContext(
        original_code=code,
        attempt=attempt,
        max_attempts=max_attempts,
        errors=ast_result.errors,
        error_type=ast_result.error_type,
        error_line=ast_result.error_line,
        error_snippet=ast_result.error_snippet,
        fix_hint=ast_result.fix_hint,
        past_attempts=past_attempts or [],
    )
