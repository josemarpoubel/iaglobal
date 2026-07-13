# iaglobal/graphs/edges.py
"""
Definição de arestas (edges) do pipeline DAG.
Cada tupla (src, dst) define dependência de execução.
"""

# Pipeline V3 - Ordem de execução dos nós
EDGES = [
    # Fase 1: Entrada
    ("prompt_intake", "interpreter"),
    ("interpreter", "enhancement"),
    ("enhancement", "orchestrator_agent"),
    # Fase 2: Requisitos
    ("orchestrator_agent", "pm"),
    ("pm", "requirements"),
    # Fase 3: Arquitetura
    ("requirements", "architect"),
    ("architect", "domain_analysis"),
    ("architect", "business_rules"),
    ("architect", "technology_selection"),
    # Fase 4: Design
    ("technology_selection", "system_design"),
    ("system_design", "api_design"),
    ("system_design", "database_design"),
    ("system_design", "security_design"),
    ("security_design", "threat_modeling"),
    ("system_design", "performance_design"),
    ("system_design", "observability_design"),
    # Fase 5: Construção
    ("system_design", "planner"),
    ("planner", "task_breakdown"),
    ("task_breakdown", "execution_plan"),
    ("execution_plan", "coder"),
    ("execution_plan", "frontend_builder"),
    ("execution_plan", "backend_builder"),
    ("execution_plan", "database_builder"),
    ("execution_plan", "api_builder"),
    # Fase 6: Qualidade
    ("coder", "validator"),
    ("validator", "semantic_validator"),
    ("semantic_validator", "reviewer"),
    ("reviewer", "tester"),
    ("tester", "security_audit"),
    ("security_audit", "performance_audit"),
    ("performance_audit", "compliance_audit"),
    # Fase 7: LSP Validation (syntax + imports)
    ("coder", "lsp_validator"),
    ("multi_coder", "lsp_validator"),
    ("lsp_validator", "debug_unificado"),
    # Fase 8: Depuração Unificada + Integração
    ("tester", "debug_unificado"),
    ("debug_unificado", "fix_validator"),
    ("fix_validator", "integrator"),
    ("integrator", "rank"),
    # Fase 9: Metacognição
    ("rank", "evaluator"),
    ("evaluator", "gap_analyzer"),
    ("gap_analyzer", "skill_generator"),
    ("skill_generator", "sandbox_validator"),
    ("sandbox_validator", "evolution_committee"),
    ("evolution_committee", "pipeline_updater"),
    ("pipeline_updater", "evolution_trigger"),
    # Fase 10: Entrega
    ("rank", "documentation"),
    ("documentation", "deployment_plan"),
    ("deployment_plan", "release"),
    ("release", "metrics"),
    ("metrics", "optimization"),
    ("optimization", "retrospective"),
    ("retrospective", "result_agent"),
    # Fase 11: Análise Metabólica Final
    ("result_agent", "system_analysis"),
]


# Mapeamento de dependências para validação
def validate_edges(edges):
    """Valida que todas as arestas referenciam nós válidos."""
    all_nodes = set()
    for src, dst in edges:
        all_nodes.add(src)
        all_nodes.add(dst)
    return all_nodes
