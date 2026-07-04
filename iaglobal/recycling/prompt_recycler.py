"""PromptRecycler — reanalisa prompts de falha e extrai padrões."""

import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PromptRecycler:
    """Recicla prompts que falharam — extrai padrões e gera templates."""

    PATTERNS = {
        "falta_contexto": r"(não (tenho|possuo|sei|entendi)|sem (contexto|informação))",
        "ambiguidade": r"(o que você quer dizer|não ficou claro|pode especificar)",
        "request_invalido": r"(não (posso|consigo|vou) (fazer|gerar|criar))",
    }

    @classmethod
    def recycle(cls, failed_prompts: List[str]) -> Dict[str, Any]:
        findings = {k: 0 for k in cls.PATTERNS}
        for prompt in failed_prompts:
            for name, pattern in cls.PATTERNS.items():
                if re.search(pattern, prompt, re.IGNORECASE):
                    findings[name] += 1

        suggestions = []
        if findings.get("falta_contexto", 0) > 0:
            suggestions.append("Adicionar [CONTEXTO] obrigatório no início do prompt")
        if findings.get("ambiguidade", 0) > 0:
            suggestions.append("Usar formato estruturado com [REGRAS] e [EXEMPLOS]")
        if findings.get("request_invalido", 0) > 0:
            suggestions.append("Verificar constraints antes de gerar")

        return {
            "analyzed": len(failed_prompts),
            "findings": findings,
            "suggestions": suggestions,
            "recycled_templates": len(suggestions),
        }
