"""GlutathioneGuardrails — validação AST/Regex automática contra padrões perigosos com integração SAMe."""

import ast
import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = [
    (r"eval\s*\(", "eval() detectado — risco de injeção de código"),
    (r"exec\s*\(", "exec() detectado — risco de execução arbitrária"),
    (r"__import__\s*\(", "__import__() detectado — risco de injeção de módulo"),
    (
        r"pickle\.loads\s*\(",
        "pickle.loads() detectado — risco de deserialização maliciosa",
    ),
    (
        r"subprocess\.(call|Popen|run)\s*\(",
        "subprocess detectado — risco de execução de comando",
    ),
    (r"os\.system\s*\(", "os.system() detectado — risco de execução de comando"),
    (
        r"shutil\.rmtree\s*\(",
        "shutil.rmtree() detectado — risco de deleção de arquivos",
    ),
    (
        r"shelve\.open\s*\(",
        "shelve.open() detectado — risco de persistência arbitrária",
    ),
    (
        r"marshal\.(loads|load)\s*\(",
        "marshal detectado — risco de deserialização insegura",
    ),
]

FORBIDDEN_IMPORTS = {
    "pdb",
    "traceback",
    "inspect",
    "ctypes",
    "multiprocessing",
    "threading",
    "socket",
    "http.server",
    "socketserver",
}

# Cost constants for SAMe integration
COST_VALIDATION_BASIC = 5
COST_VALIDATION_DEEP = 15
COST_AUTO_CORRECTION = 25

MCP_RATE_LIMITS = {
    "web_search": {"calls_per_minute": 10, "cooldown_seconds": 6},
    "web_fetch": {"calls_per_minute": 15, "cooldown_seconds": 4},
    "execute_code": {"calls_per_minute": 5, "cooldown_seconds": 12},
    "read_file": {"calls_per_minute": 30, "cooldown_seconds": 2},
    "write_file": {"calls_per_minute": 10, "cooldown_seconds": 6},
}


class GlutathioneGuardrails:
    """Sistema imunológico — valida código contra padrões perigosos antes da execução com integração SAMe."""

    @classmethod
    def validate(cls, code: str, agent_name: str = "unknown") -> Dict[str, Any]:
        issues = []
        threat_level = "none"

        for pattern, msg in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({"type": "pattern_block", "message": msg})
                threat_level = "critical"

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                            issues.append(
                                {
                                    "type": "import_block",
                                    "message": f"Import proibido: {alias.name}",
                                }
                            )
                            threat_level = "critical"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                        issues.append(
                            {
                                "type": "import_block",
                                "message": f"ImportFrom proibido: {node.module}",
                            }
                        )
                        threat_level = "critical"
        except SyntaxError as e:
            issues.append({"type": "syntax_error", "message": f"Erro de sintaxe: {e}"})
            threat_level = "warning"

        # SAMe integration: check if agent can afford validation
        sam_cost = (
            COST_VALIDATION_DEEP
            if threat_level == "critical"
            else COST_VALIDATION_BASIC
        )
        sam_status = cls._check_sam_budget(
            agent_name, sam_cost, threat_level == "critical"
        )

        return {
            "safe": len(issues) == 0,
            "issues": issues,
            "issue_count": len(issues),
            "threat_level": threat_level,
            "sam_budget_check": sam_status,
        }

    @classmethod
    def _check_sam_budget(
        cls, agent_name: str, cost: int, critical: bool = False
    ) -> Dict[str, Any]:
        """Check SAMe budget and spend if sufficient."""
        try:
            from iaglobal.evolution.same_engine import same_pool, same_inhibitor

            if same_inhibitor.can_mutate(agent_name, cost, critical):
                spent = same_pool.spend(agent_name, cost)
                return {"has_budget": spent, "cost": cost, "critical": critical}
            return {
                "has_budget": False,
                "cost": cost,
                "reason": "SAMe insuficiente para validação imunológica",
            }
        except Exception as e:
            logger.warning("[GLUTATHIONE-SAME] Falha ao verificar budget SAMe: %s", e)
            return {
                "has_budget": True,
                "cost": 0,
                "error": str(e),
            }  # Allow if SAMe unavailable

    @classmethod
    def defend_and_correct(
        cls, code: str, agent_name: str = "unknown"
    ) -> Dict[str, Any]:
        """Validate code and attempt auto-correction if threats detected."""
        validation = cls.validate(code, agent_name)

        if validation["safe"]:
            return validation

        # Consume SAMe for auto-correction
        sam_status = cls._check_sam_budget(
            agent_name, COST_AUTO_CORRECTION, critical=True
        )

        if not sam_status.get("has_budget"):
            logger.warning(
                "[GLUTATHIONE-SAME] Ameaça detectada mas SAMe insuficiente para correção automática"
            )
            return {
                **validation,
                "auto_corrected": False,
                "correction_blocked": True,
                "sam_error": sam_status.get("reason", "Budget exceeded"),
            }

        # Attempt auto-correction
        try:
            corrected = cls._apply_auto_correction(code, validation["issues"])
            return {
                **validation,
                "auto_corrected": True,
                "corrected_code": corrected,
                "sam_spent": COST_AUTO_CORRECTION,
            }
        except Exception as e:
            logger.error("[GLUTATHIONE-SAME] Falha na correção automática: %s", e)
            return {
                **validation,
                "auto_corrected": False,
                "correction_error": str(e),
            }

    @classmethod
    def _apply_auto_correction(cls, code: str, issues: List[Dict]) -> str:
        """Apply lightweight auto-correction for common threats."""
        corrected = code

        # Pattern-based corrections
        for issue in issues:
            msg = issue.get("message", "")

            # Comment out dangerous calls
            if "eval()" in msg:
                corrected = re.sub(
                    r"\beval\s*\([^)]*\)", "# eval() BLOCKED - segurança", corrected
                )
            elif "exec(" in msg:
                corrected = re.sub(
                    r"\bexec\s*\([^)]*\)", "# exec() BLOCKED - segurança", corrected
                )
            elif "subprocess" in msg:
                corrected = re.sub(
                    r"\bsubprocess\.(call|Popen|run)\s*\([^)]*\)",
                    "# subprocess BLOCKED - segurança",
                    corrected,
                )
            elif "os.system" in msg:
                corrected = re.sub(
                    r"\bos\.system\s*\([^)]*\)",
                    "# os.system BLOCKED - segurança",
                    corrected,
                )
            elif "shutil.rmtree" in msg:
                corrected = re.sub(
                    r"\bshutil\.rmtree\s*\([^)]*\)",
                    "# shutil.rmtree BLOCKED - segurança",
                    corrected,
                )
            elif "pickle.loads" in msg:
                corrected = re.sub(
                    r"\bpickle\.loads\s*\([^)]*\)",
                    "# pickle.loads BLOCKED - segurança",
                    corrected,
                )

        return corrected

    @classmethod
    def check_mcp_rate_limit(
        cls, tool_name: str, agent_name: str = "unknown"
    ) -> Dict[str, Any]:
        """Verifica rate limit de chamadas MCP para um agente."""
        limits = MCP_RATE_LIMITS.get(tool_name)
        if not limits:
            return {"allowed": True, "reason": "Sem limite configurado"}

        if not hasattr(cls, "_mcp_call_log"):
            cls._mcp_call_log = {}

        from collections import defaultdict
        import time

        if not hasattr(cls, "_mcp_call_log_store"):
            cls._mcp_call_log_store = defaultdict(list)

        now = time.time()
        window = 60.0
        key = f"{agent_name}:{tool_name}"
        calls = [t for t in cls._mcp_call_log_store[key] if now - t < window]
        cls._mcp_call_log_store[key] = calls

        if len(calls) >= limits["calls_per_minute"]:
            logger.warning(
                "[GLUTATHIONE-RATE] %s excedeu limite MCP %s: %d/min",
                agent_name,
                tool_name,
                len(calls),
            )
            return {
                "allowed": False,
                "reason": f"Rate limit: {limits['calls_per_minute']}/min",
            }

        cls._mcp_call_log_store[key].append(now)
        return {"allowed": True, "calls_in_window": len(calls) + 1}

    @classmethod
    def register_guardrail(cls, rule: Dict[str, Any]):
        from iaglobal.evolution.skills.native.skill import Skill
        from iaglobal.evolution.skills.native.skill_registry import skill_registry

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
