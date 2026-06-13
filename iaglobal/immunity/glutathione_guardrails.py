"""GlutathioneGuardrails — validação AST/Regex automática contra padrões perigosos."""

import ast
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = [
    (r"eval\s*\(", "eval() detectado — risco de injeção de código"),
    (r"exec\s*\(", "exec() detectado — risco de execução arbitrária"),
    (r"__import__\s*\(", "__import__() detectado — risco de injeção de módulo"),
    (r"pickle\.loads\s*\(", "pickle.loads() detectado — risco de deserialização maliciosa"),
    (r"subprocess\.(call|Popen|run)\s*\(", "subprocess detectado — risco de execução de comando"),
    (r"os\.system\s*\(", "os.system() detectado — risco de execução de comando"),
    (r"shutil\.rmtree\s*\(", "shutil.rmtree() detectado — risco de deleção de arquivos"),
    (r"shelve\.open\s*\(", "shelve.open() detectado — risco de persistência arbitrária"),
    (r"marshal\.(loads|load)\s*\(", "marshal detectado — risco de deserialização insegura"),
]

FORBIDDEN_IMPORTS = {
    "pdb", "traceback", "inspect", "ctypes",
    "multiprocessing", "threading", "socket",
    "http.server", "socketserver",
}


class GlutathioneGuardrails:
    """Sistema imunológico — valida código contra padrões perigosos antes da execução."""

    @classmethod
    def validate(cls, code: str) -> Dict[str, Any]:
        issues = []
        for pattern, msg in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({"type": "pattern_block", "message": msg})

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                            issues.append({"type": "import_block", "message": f"Import proibido: {alias.name}"})
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                        issues.append({"type": "import_block", "message": f"ImportFrom proibido: {node.module}"})
        except SyntaxError as e:
            issues.append({"type": "syntax_error", "message": f"Erro de sintaxe: {e}"})

        return {
            "safe": len(issues) == 0,
            "issues": issues,
            "issue_count": len(issues),
        }

    @classmethod
    def register_guardrail(cls, rule: Dict[str, Any]):
        from iaglobal.evolution.skills.skill import Skill
        from iaglobal.evolution.skills.skill_registry import skill_registry
        guardrail = Skill(
            name=rule.get("name", f"guardrail_{hash(str(rule)) % 10000:04d}"),
            description=rule.get("description", "Auto-generated guardrail"),
            inputs=["code"],
            outputs=["decision"],
            constraints=["deterministic", "fast"],
            tags=["guardrail", "auto_generated"],
            status="production",
        )
        skill_registry.register_or_update(guardrail)
