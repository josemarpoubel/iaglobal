"""HallucinationDetector — analisa output por padrões de alucinação."""

import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SUSPICIOUS_PATTERNS = [
    (r"\b(import|from)\s+(unknown|nonexistent|lorem_ipsum|fakelib)\b", "lib_inventada"),
    (r"(function|método|biblioteca|lib) (não encontrad[oa]|inexistente)", "reconhecimento_falha"),
    (r"confiança[:\s]+(0\.\d{2}|1\.0)", "confiança_sem_evidencia"),
    (r"(acredito|acho|provavelmente|talvez|possivelmente)", "incerteza"),
    (r"(não tenho certeza|não sei|não posso afirmar)", "falta_conhecimento"),
]

FAKE_LIBS = {
    "tensorflow_super", "pytorch_lightning_plus", "sklearn_advanced",
    "flask_pro", "django_ultimate", "numpy_ml", "pandas_ai",
    "fake_module", "nonexistent_package", "lorem_ipsum_utils",
}


class HallucinationDetector:
    """Detecta padrões de alucinação em outputs de LLM."""

    @classmethod
    def check(cls, text: str) -> Dict[str, Any]:
        findings = []

        for pattern, label in SUSPICIOUS_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                findings.append({"pattern": label, "matches": len(matches), "detail": matches[:3]})

        imported = set(re.findall(r"(?:import|from)\s+(\w+)", text))
        fake_found = imported & FAKE_LIBS
        if fake_found:
            findings.append({"pattern": "lib_inventada", "matches": len(fake_found), "detail": list(fake_found)})

        score = max(0.0, 1.0 - (len(findings) * 0.25))
        hallucinating = len(findings) >= 2

        return {
            "hallucinating": hallucinating,
            "score": round(score, 2),
            "findings": findings,
            "finding_count": len(findings),
        }

    @classmethod
    def analyze_node_output(cls, node_name: str, output: Any) -> Dict[str, Any]:
        text = str(output) if output else ""
        return cls.check(text)
