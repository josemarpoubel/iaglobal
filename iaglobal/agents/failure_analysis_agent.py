"""FailureAnalysisAgent — analisa logs de falha e extrai padrões para guardrails."""

import re
import logging
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import logger

PATTERNS = {
    "syntax_error": r"SyntaxError|IndentationError|NameError|TypeError",
    "import_error": r"ModuleNotFoundError|ImportError|No module named",
    "security": r"sql injection|xss|command injection|path traversal|pickle\.loads|eval\(|exec\(",
    "hallucination": r"unknown library|fake_module|nonexistent|não encontrad[ao]",
    "timeout": r"timeout|Timeout|timed out|deadline exceeded",
    "api_error": r"401|403|404|500|Unauthorized|Forbidden|Rate limit|quota",
}


class FailureAnalysisAgent:
    """Analisa logs de falha e classifica por tipo, extraindo padrões para guardrails."""

    @classmethod
    def analyze(cls, error_log: str, prompt: str = "", code: str = "") -> Dict[str, Any]:
        findings = []
        guardrail_suggestions = []

        for category, pattern in PATTERNS.items():
            matches = re.findall(pattern, error_log, re.IGNORECASE)
            if matches:
                findings.append({"category": category, "matches": len(matches), "detail": matches[:3]})

                if category == "syntax_error":
                    guardrail_suggestions.append({
                        "type": "ast_validator",
                        "rule": "compile_check",
                        "description": "Validar sintaxe via compile() antes de executar",
                    })
                elif category == "import_error":
                    guardrail_suggestions.append({
                        "type": "import_blocklist",
                        "rule": f"block_unknown_{matches[0].lower() if matches else 'module'}",
                        "description": f"Bloquear import de módulos não verificados",
                    })
                elif category == "security":
                    guardrail_suggestions.append({
                        "type": "pattern_block",
                        "rule": "security_hotfix",
                        "description": f"Bloquear padrão: {matches[0] if matches else 'security'}",
                    })
                elif category == "hallucination":
                    guardrail_suggestions.append({
                        "type": "regex_ban",
                        "rule": "anti_hallucination",
                        "description": "Banir bibliotecas inexistentes via regex",
                    })

        return {
            "error_type": findings[0]["category"] if findings else "unknown",
            "findings": findings,
            "suggestion_count": len(guardrail_suggestions),
            "guardrail_suggestions": guardrail_suggestions,
        }

    @classmethod
    def generate_guardrail(cls, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if analysis["suggestion_count"] == 0:
            return None
        suggestion = analysis["guardrail_suggestions"][0]
        return {
            "name": f"guardrail_{analysis['error_type']}_{hash(str(suggestion)) % 10000:04d}",
            "type": suggestion["type"],
            "rule": suggestion["rule"],
            "description": suggestion["description"],
        }
