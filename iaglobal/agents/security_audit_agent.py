# iaglobal/agents/security_audit_agent.py

import re
from iaglobal.utils.logger import logger


class SecurityAuditAgent:
    """Audita o código gerado contra requisitos de segurança."""

    def audit(self, code: str, security_requirements: list,
              knowledge_context: str = "", error_context: str = "") -> dict:
        logger.info("🔍 [SECURITY-AUDIT] Auditando código...")

        issues = []
        severity_count = {"high": 0, "medium": 0, "low": 0}

        patterns = [
            (r"eval\s*\(", "Uso de eval() — execução de código arbitrário", "high"),
            (r"exec\s*\(", "Uso de exec() — execução de código arbitrário", "high"),
            (r"__import__\s*\(", "Uso dinâmico de __import__", "medium"),
            (r"pickle\.loads?", "Pickle pode executar código arbitrário", "high"),
            (r"subprocess\.(call|Popen|run)", "Subprocess pode ser vetor de injeção", "high"),
            (r"os\.system", "os.system — execução de comando no shell", "high"),
            (r"sqlite3\.execute\(.*['\"]", "SQL direto — risco de SQL injection", "high"),
            (r"\.format\(.*\{\}", "Formatação insegura de string", "low"),
            (r"request\.(GET|POST|REQUEST)\[", "Acesso direto a request sem sanitização", "medium"),
            (r"render_template_string", "Server-Side Template Injection (SSTI)", "high"),
            (r"password\s*=\s*['\"][^'\"]{1,8}['\"]", "Senha curta/débil no código", "medium"),
            (r"API_KEY\s*=\s*['\"]", "Chave de API hardcoded", "high"),
            (r"SECRET_KEY\s*=\s*['\"]", "Secret key hardcoded", "high"),
            (r"debug\s*=\s*True", "Debug mode ativo em produção", "medium"),
            (r"ALLOWED_HOSTS\s*=\s*\['\*'\]", "CORS/Hosts excessivamente permissivo", "medium"),
        ]

        if knowledge_context:
            logger.info("🔍 [SECURITY-AUDIT] knowledge context available (%d chars)", len(knowledge_context))

        if error_context:
            logger.info("🔍 [SECURITY-AUDIT] error context available (%d chars)", len(error_context))
            if "eval" in error_context.lower():
                patterns.insert(0, (r"eval|exec|__import__", "[REINCIDENCIA] eval/exec ja causou erro antes", "high"))
            if "sql" in error_context.lower():
                patterns.insert(0, (r"sqlite3\.execute|raw_sql|\.format\(.*['\"]", "[REINCIDENCIA] SQL injection ja ocorreu antes", "high"))
            if "pickle" in error_context.lower():
                patterns.insert(0, (r"pickle\.(loads?|dumps?)", "[REINCIDENCIA] Pickle inseguro ja ocorreu antes", "high"))
            if "hardcoded" in error_context.lower() or "secret" in error_context.lower():
                patterns.insert(0, (r"(API_KEY|SECRET_KEY|PASSWORD)\s*=.*['\"]", "[REINCIDENCIA] Secret hardcoded ja ocorreu antes", "high"))

        for pattern, desc, severity in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({"description": desc, "severity": severity, "pattern": pattern})
                severity_count[severity] = severity_count.get(severity, 0) + 1

        for req in security_requirements:
            req_lower = req.lower()
            if "auth" in req_lower and not re.search(r"(login|logout|session|token|jwt)", code, re.IGNORECASE):
                issues.append({"description": f"Requisito não implementado: {req}", "severity": "high", "pattern": "missing_requirement"})
                severity_count["high"] += 1
            if "sanitize" in req_lower and not re.search(r"(strip|escape|sanitize|validate)", code, re.IGNORECASE):
                issues.append({"description": f"Requisito não implementado: {req}", "severity": "medium", "pattern": "missing_requirement"})
                severity_count["medium"] += 1

        return {
            "security_audit_report": {
                "total_issues": len(issues),
                "severity_count": severity_count,
                "issues": issues,
            },
            "security_issues": issues,
        }
