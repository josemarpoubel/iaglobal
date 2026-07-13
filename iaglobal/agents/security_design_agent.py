# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/security_design_agent.py

"""SecurityDesignAgent — Analisa requisitos de segurança na fase de design com priorização."""

import re
from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum
from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase


# --- 1. Contratos de Dados Rígidos e Priorização ---
class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


@dataclass
class SecurityIssue:
    id: str
    title: str
    severity: Severity
    recommendation: str


@dataclass
class SecurityReport:
    total_issues: int
    critical_count: int
    issues: List[SecurityIssue]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialização limpa para JSON/Mensageria."""
        return {
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "severity": i.severity.value,
                    "recommendation": i.recommendation,
                }
                for i in self.issues
            ],
            "recommendations": self.recommendations,
        }


class SecurityDesignAgent(AgentBase):
    # --- 2. Regex Pré-compiladas com Word Boundaries (\b) ---
    # Evita que "auth" dê match em "author" ou "sql" dê match em "mysql"
    _AUTH_REGEX = re.compile(
        r"\b(auth|authentication|oauth|jwt|login)\b", re.IGNORECASE
    )
    _SQL_REGEX = re.compile(r"\b(sql|query|database)\b", re.IGNORECASE)
    _ORM_REGEX = re.compile(
        r"\b(orm|sqlalchemy|django orm|prisma|hibernate)\b", re.IGNORECASE
    )
    _INPUT_REGEX = re.compile(r"\b(input|payload|request|body)\b", re.IGNORECASE)
    _SANITIZE_REGEX = re.compile(
        r"\b(sanitize|validation|validate|filter|escape)\b", re.IGNORECASE
    )
    _TLS_REGEX = re.compile(r"\b(https|ssl|tls|certificate)\b", re.IGNORECASE)
    _SECRET_REGEX = re.compile(
        r"\b(secret|password|token|key|credential)\b", re.IGNORECASE
    )
    _ENV_REGEX = re.compile(
        r"\b(env|environment|vault|secrets manager)\b", re.IGNORECASE
    )

    # Regex para Requisitos Não-Funcionais (Integração com PM)
    _PRIVACY_REGEX = re.compile(
        r"\b(privacidade|privacy|lgpd|gdpr|pii)\b", re.IGNORECASE
    )
    _ENCRYPT_REGEX = re.compile(r"\b(crypt|encrypt|hash|aes|rsa)\b", re.IGNORECASE)

    def analyze(
        self,
        design_context: Dict[str, Any],
        knowledge_context: str = "",
        error_context: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        logger.info("🔒 [SECURITY-DESIGN] Analisando requisitos de segurança...")

        architecture = design_context.get("architecture", {})
        requirements = design_context.get("requirements", {})

        # Serialização única para os contexts de texto (Performance)
        arch_text = str(architecture)
        req_text = str(requirements)

        # Extração de Requisitos Não-Funcionais (O "Pulo do Gato")
        non_func_reqs = requirements.get("non_functional", [])

        issues: List[SecurityIssue] = []
        recommendations: List[str] = []

        # --- 3. Análise de Reincidência (Error Context) ---
        if error_context:
            err_lower = error_context.lower()
            if self._AUTH_REGEX.search(err_lower):
                issues.append(
                    SecurityIssue(
                        "SEC-001",
                        "Reincidência: Falhas de autenticação",
                        Severity.CRITICAL,
                        "Revisar implementação de autenticação — erro recorrente",
                    )
                )
                recommendations.append(
                    "Revisar implementação de autenticação — erro recorrente"
                )
            if self._SQL_REGEX.search(err_lower) and not self._ORM_REGEX.search(
                err_lower
            ):
                issues.append(
                    SecurityIssue(
                        "SEC-002",
                        "Reincidência: SQL Injection",
                        Severity.CRITICAL,
                        "Impor uso de ORM com query parameterized — erro conhecido",
                    )
                )
                recommendations.append(
                    "Impor uso de ORM com query parameterized — erro conhecido"
                )

        # --- 4. Análise de Arquitetura (Design Context) ---
        if not self._AUTH_REGEX.search(arch_text):
            issues.append(
                SecurityIssue(
                    "SEC-003",
                    "Ausência de mecanismo de autenticação",
                    Severity.HIGH,
                    "Implementar OAuth 2.0 ou JWT-based authentication",
                )
            )
            recommendations.append("Implementar OAuth 2.0 ou JWT-based authentication")

        if self._SQL_REGEX.search(req_text) and not self._ORM_REGEX.search(arch_text):
            issues.append(
                SecurityIssue(
                    "SEC-004",
                    "Uso de SQL direto sem ORM",
                    Severity.CRITICAL,
                    "Utilizar ORM (SQLAlchemy, Django ORM) com query parameterized",
                )
            )
            recommendations.append(
                "Utilizar ORM (SQLAlchemy, Django ORM) com query parameterized"
            )

        if self._INPUT_REGEX.search(arch_text) and not self._SANITIZE_REGEX.search(
            arch_text
        ):
            issues.append(
                SecurityIssue(
                    "SEC-005",
                    "Input de usuário sem sanitização",
                    Severity.HIGH,
                    "Implementar validação e sanitização de inputs (OWASP)",
                )
            )
            recommendations.append(
                "Implementar validação e sanitização de inputs (OWASP)"
            )

        if not self._TLS_REGEX.search(arch_text):
            issues.append(
                SecurityIssue(
                    "SEC-006",
                    "Comunicação sem TLS/SSL",
                    Severity.CRITICAL,
                    "Forçar HTTPS em produção",
                )
            )
            recommendations.append("Forçar HTTPS em produção")

        if self._SECRET_REGEX.search(arch_text) and not self._ENV_REGEX.search(
            arch_text
        ):
            issues.append(
                SecurityIssue(
                    "SEC-007",
                    "Secrets gerenciados sem variáveis de ambiente",
                    Severity.HIGH,
                    "Usar env vars ou vault para gerenciar secrets",
                )
            )
            recommendations.append("Usar env vars ou vault para gerenciar secrets")

        # --- 5. Análise Baseada em Requisitos Não-Funcionais (Integração com PM) ---
        for req in non_func_reqs:
            req_lower = req.lower()
            if self._PRIVACY_REGEX.search(req_lower) and not self._ENCRYPT_REGEX.search(
                arch_text
            ):
                issues.append(
                    SecurityIssue(
                        "SEC-008",
                        "Requisito de privacidade sem criptografia",
                        Severity.HIGH,
                        "Implementar criptografia de dados sensíveis em repouso e trânsito (LGPD/GDPR)",
                    )
                )
                recommendations.append(
                    "Implementar criptografia de dados sensíveis em repouso e trânsito (LGPD/GDPR)"
                )

        # --- 6. Consolidação do Relatório ---
        critical_count = sum(1 for i in issues if i.severity == Severity.CRITICAL)

        report = SecurityReport(
            total_issues=len(issues),
            critical_count=critical_count,
            issues=issues,
            recommendations=list(set(recommendations)),  # Remove duplicatas
        )

        logger.info(
            "🔒 [SECURITY-DESIGN] Concluído | issues=%d (critical=%d)",
            report.total_issues,
            report.critical_count,
        )

        return {
            "security_design_report": report.to_dict(),
            "security_requirements": report.recommendations,
        }
