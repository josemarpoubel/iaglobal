# iaglobal/pipeline/context/providers/security.py
"""
SecurityContextProvider — provider especializado para segurança e compliance.

Projeta do SecuritySnapshot:
  - Security Objectives (objetivos de segurança)
  - Compliance (requisitos de conformidade)
  - Threat Model (ameaças identificadas)
  - Sensitive Assets (ativos sensíveis)
  - Required Validations (validações obrigatórias)
  - Forbidden Patterns (padrões proibidos)

Este provider NÃO acessa diretamente engines de compliance ou threat databases.
Ele apenas projeta o SecuritySnapshot já coletado pelo PipelineEngine.

Uso:
    # PipelineEngine coleta contexto de segurança → SecuritySnapshot
    snapshot = SecuritySnapshot(
        compliance=("LGPD", "PCI DSS"),
        threat_model=("fraude", "vazamento"),
        ...
    )
    exec_ctx = PipelineExecutionContext(security_snapshot=snapshot)

    # Provider apenas projeta
    provider = provider_registry.get("security")
    node_ctx = provider.build(exec_ctx, node_name="security")
"""

from .base import ProjectionProvider, SectionSpec
from ..protocol import PipelineExecutionContext
from ..contextproviderregistry import provider_registry


SecurityContextProvider = ProjectionProvider(
    requires=(PipelineExecutionContext,),
    sections=(
        SectionSpec(
            "security_objectives",
            "Objetivos de Segurança",
            100,
            "security_snapshot.security_objectives",
        ),
        SectionSpec("compliance", "Compliance", 95, "security_snapshot.compliance"),
        SectionSpec(
            "threat_model", "Modelo de Ameaças", 90, "security_snapshot.threat_model"
        ),
        SectionSpec(
            "sensitive_assets",
            "Ativos Sensíveis",
            85,
            "security_snapshot.sensitive_assets",
        ),
        SectionSpec(
            "required_validations",
            "Validações Obrigatórias",
            80,
            "security_snapshot.required_validations",
        ),
        SectionSpec(
            "forbidden_patterns",
            "Padrões Proibidos",
            75,
            "security_snapshot.forbidden_patterns",
        ),
    ),
)

provider_registry.register("security", SecurityContextProvider)
