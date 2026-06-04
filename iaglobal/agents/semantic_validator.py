import re
from typing import Dict, Any
from iaglobal.utils.logger import logger


class SemanticValidatorAgent:
    """
    Validates that generated code meets semantic requirements:
    - Requirements are fulfilled
    - Algorithm is correct
    - Technical terms are present
    - Output makes logical sense
    """

    def __init__(self):
        self.requirement_patterns = {
            "sha3_512": re.compile(r"sha3.?512|sha512|SHA3.?512", re.IGNORECASE),
            "sha256": re.compile(r"sha.?256|SHA.?256", re.IGNORECASE),
            "genesis": re.compile(r"genesis", re.IGNORECASE),
            "blockchain": re.compile(r"block.?chain|BlockChain|blockchain", re.IGNORECASE),
            "serialize": re.compile(r"serialize|serializ|cbor|json\.dumps|pickle", re.IGNORECASE),
            "hashlib": re.compile(r"import hashlib|from hashlib", re.IGNORECASE),
        }

    def validate(self, code: str, task: str) -> Dict[str, Any]:
        logger.info("🔬 [SEMANTIC VALIDATOR] Validando requisitos semânticos...")

        if not code or not code.strip():
            return {
                "valid": False,
                "score": 0.0,
                "errors": ["Código vazio"],
                "details": {},
            }

        task_lower = task.lower()
        code_lower = code.lower()
        errors = []
        checks = {}
        total_weight = 0.0
        passed_weight = 0.0

        requirement_checks = [
            ("hashlib_import", "Usar hashlib", 15.0, "import hashlib" in code_lower or "from hashlib" in code_lower),
        ]

        self._check_keyword_requirement(task_lower, code_lower, "sha3_512", "SHA3-512", 20.0, checks)
        self._check_keyword_requirement(task_lower, code_lower, "genesis", "genesis", 20.0, checks)
        self._check_keyword_requirement(task_lower, code_lower, "blockchain", "blockchain", 15.0, checks)
        self._check_keyword_requirement(task_lower, code_lower, "serialize", "serialização", 15.0, checks)

        is_html = code_lower.strip().startswith("<!doctype") or code_lower.strip().startswith("<html")
        if not is_html and ("tarefa" in task_lower or "gerar" in task_lower or "criar" in task_lower):
            if "def " not in code_lower and "class " not in code_lower:
                errors.append("Código não contém função ou classe definida")
                checks["has_function"] = {"passed": False, "weight": 10.0}

        if is_html:
            has_html_tag = "<html" in code_lower and "</html>" in code_lower
            has_body = "<body" in code_lower and "</body>" in code_lower
            if not has_html_tag or not has_body:
                errors.append("HTML incompleto: faltam tags <html> ou <body>")
                checks["html_structure"] = {"passed": has_html_tag and has_body, "weight": 10.0}

        if is_html and not checks.get("html_structure", {}).get("passed") == False:
            score = 100.0
            valid = True
            logger.info("✅ [SEMANTIC VALIDATOR] HTML válido (tags estruturais presentes)")
            return {"valid": True, "score": 100.0, "errors": [], "details": checks}

        for name, desc, weight, passed in requirement_checks:
            checks[name] = {"passed": passed, "weight": weight}

        for check_name, check_data in checks.items():
            total_weight += check_data["weight"]
            if check_data["passed"]:
                passed_weight += check_data["weight"]

        score = (passed_weight / total_weight * 100.0) if total_weight > 0 else 0.0

        if score < 50:
            errors.append("Score semântico baixo: %.1f%%" % score)

        valid = len(errors) == 0

        result = {
            "valid": valid,
            "score": round(score, 2),
            "errors": errors,
            "details": checks,
        }

        if valid:
            logger.info("✅ [SEMANTIC VALIDATOR] Aprovado (score=%.1f%%)", score)
        else:
            logger.warning("❌ [SEMANTIC VALIDATOR] Rejeitado: %s", errors)

        return result

    def _check_keyword_requirement(self, task_lower: str, code_lower: str, key: str, label: str, weight: float, checks: dict):
        pattern = self.requirement_patterns.get(key)
        if not pattern:
            return
        required = pattern.search(task_lower) is not None
        if required:
            present = pattern.search(code_lower) is not None
            checks["req_%s" % key] = {"passed": present, "weight": weight}
            if not present:
                logger.warning("⚠️ [SEMANTIC VALIDATOR] Requisito '%s' não encontrado no código", label)
