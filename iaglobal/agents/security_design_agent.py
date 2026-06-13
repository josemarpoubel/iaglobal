# iaglobal/agents/security_design_agent.py

from iaglobal.utils.logger import logger


class SecurityDesignAgent:
    """Analisa requisitos de segurança na fase de design."""

    def analyze(self, design_context: dict, knowledge_context: str = "", error_context: str = "", **kwargs) -> dict:
        logger.info("🔒 [SECURITY-DESIGN] Analisando requisitos de segurança...")

        architecture = design_context.get("architecture", {})
        requirements = design_context.get("requirements", {})

        issues = []
        recs = []

        arch_text = str(architecture)
        req_text = str(requirements)

        if knowledge_context:
            logger.info("🔒 [SECURITY-DESIGN] knowledge context available (%d chars)", len(knowledge_context))
        if error_context:
            logger.info("🔒 [SECURITY-DESIGN] error context available (%d chars)", len(error_context))
            if "auth" in error_context.lower() or "login" in error_context.lower():
                issues.append("[REINCIDENCIA] Problemas de autenticação detectados em execuções anteriores")
                recs.append("Revisar implementação de autenticação — erro recorrente")
            if "sql" in error_context.lower():
                issues.append("[REINCIDENCIA] SQL injection recorrente — necessário ORM obrigatório")
                recs.append("Impor uso de ORM com query parameterized — erro conhecido")

        if "auth" not in arch_text.lower() and "login" not in arch_text.lower():
            issues.append("Sem mecanismo de autenticação identificado")
            recs.append("Implementar OAuth 2.0 ou JWT-based authentication")

        if "sql" in req_text.lower() and "orm" not in arch_text.lower():
            issues.append("Uso de SQL direto sem ORM — risco de SQL injection")
            recs.append("Utilizar ORM (SQLAlchemy, Django ORM) com query parameterized")

        if "input" in arch_text.lower() and "sanitize" not in arch_text.lower():
            issues.append("Input de usuário sem sanitização visível")
            recs.append("Implementar validação e sanitização de inputs (OWASP)")

        if "https" not in arch_text.lower() and "ssl" not in arch_text.lower():
            issues.append("Comunicação sem TLS/SSL")
            recs.append("Forçar HTTPS em produção")

        if "secret" in arch_text.lower() and "env" not in arch_text.lower():
            issues.append("Secrets gerenciados sem variáveis de ambiente")
            recs.append("Usar env vars ou vault para gerenciar secrets")

        report = {
            "total_issues": len(issues),
            "issues": issues,
            "recommendations": recs,
        }

        return {
            "security_design_report": report,
            "security_requirements": recs,
        }
