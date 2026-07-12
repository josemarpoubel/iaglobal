# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/security_audit_agent.py

import re
from typing import List
from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase


def _contem_padrao_regex_perigoso(code: str) -> bool:
    """
    Detecta padrões regex que podem causar catastrophic backtracking.
    
    Args:
        code: Código a ser analisado
        
    Returns:
        True se padrão perigoso detectado, False caso contrário
    """
    # Patterns regex perigosos que podem causar DoS
    dangerous_patterns = [
        r'(\w+\\s*\\*\\s*){100,}',  # Repetição excessiva
        r'(.*\\s*){100,}',  # Repetição excessiva de qualquer caractere
        r'(\\[a-zA-Z0-9]{100,})',  # Sequências longas de escapes
        r'(\\([^\\]|$)){100,}',  # Sequências longas de escapes incompletos
    ]
    
    for pattern in dangerous_patterns:
        try:
            # Tentar compilar o pattern para verificar se é válido
            re.compile(pattern)
            # Se compilar, verificar se existe no código
            if re.search(pattern, code):
                return True
        except re.error:
            # Pattern inválido, ignorar
            continue
    
    return False


class SecurityAuditAgent(AgentBase):
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

        # Validar código antes de aplicar patterns (prevenir regex DoS)
        if _contem_padrao_regex_perigoso(code):
            logger.error("🚫 [SECURITY-AUDIT] Código contém padrão regex perigoso — potencial DoS")
            issues.append({
                "description": "Código contém padrão regex perigoso — potencial negação de serviço (DoS)",
                "severity": "high",
                "pattern": "regex_dos"
            })
            severity_count["high"] = severity_count.get("high", 0) + 1
            # Não continuar com a auditoria se padrão perigoso detectado
            return {
                "security_audit_report": {
                    "total_issues": len(issues),
                    "severity_count": severity_count,
                    "issues": issues,
                },
                "security_issues": issues,
            }
        
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
