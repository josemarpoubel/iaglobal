# iaglobal/pipeline/context/security_snapshot.py
"""
SecuritySnapshot — Agregado imutável de contexto de segurança.

Este módulo define o contrato de dados para segurança, sem acoplamento
com engines de compliance, threat databases ou políticas externas.
A coleta é responsabilidade do PipelineEngine; o provider apenas projeta.

Uso:
    snapshot = SecuritySnapshot(
        compliance=("LGPD", "PCI DSS"),
        threat_model=("fraude", "vazamento"),
        required_validations=("autenticacao", "autorizacao"),
        forbidden_patterns=("eval()", "exec()"),
        sensitive_assets=("usuario", "pagamento"),
    )
    exec_ctx = ExecutionContext(security_snapshot=snapshot)
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SecuritySnapshot:
    """
    Snapshot imutável de contexto de segurança para execução.

    Atributos:
        compliance: Requisitos de conformidade (LGPD, PCI DSS, HIPAA, etc.)
        threat_model: Ameaças identificadas para o domínio
        required_validations: Validações obrigatórias (auth, sanitização, etc.)
        forbidden_patterns: Padrões/códigos proibidos (eval, exec, etc.)
        sensitive_assets: Ativos sensíveis do domínio (dados, entidades)
        security_objectives: Objetivos de segurança (confidencialidade, etc.)

    Todos os campos são tuplas (imutáveis) para garantir que o snapshot
    não seja modificado após criação.
    """

    compliance: Tuple[str, ...] = ()
    threat_model: Tuple[str, ...] = ()
    required_validations: Tuple[str, ...] = ()
    forbidden_patterns: Tuple[str, ...] = ()
    sensitive_assets: Tuple[str, ...] = ()
    security_objectives: Tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Retorna True se nenhum campo tiver conteúdo."""
        return all(
            not field
            for field in (
                self.compliance,
                self.threat_model,
                self.required_validations,
                self.forbidden_patterns,
                self.sensitive_assets,
                self.security_objectives,
            )
        )

    @property
    def total_items(self) -> int:
        """Conta total de itens em todos os campos."""
        return sum(
            len(field)
            for field in (
                self.compliance,
                self.threat_model,
                self.required_validations,
                self.forbidden_patterns,
                self.sensitive_assets,
                self.security_objectives,
            )
        )
