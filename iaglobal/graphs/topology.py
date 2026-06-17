# SPDX-License-Identifier: MIT
"""
iaglobal/graphs/topology.py
Domínios: 55 nodes -> 7 phases -> dependências intra/inter-phase
"""

PHASES = {
    "definicao": [
        "agentmailbox",         # Inicializa barramento de mensagens entre agentes
        "prompt_intake",       # Intake e classificação do pedido
        "prompt_improver",     # PromptImprover 5 estágios (semântica, constraints, persona, decomposição, reflexão)
        "enhancement",          # Enriquecimento semântico do prompt
        "orchestrator_agent",    # Orquestração da tarefa (boundary core/orchestrator.py)
        "pm",                   # Agenda + prioridades + budget de tokens
        "requirements",          # Engenharia de requisitos
        "domain_analysis",       # Análise de domínio
        "business_rules",        # Regras de negócio e políticas
        "local_knowledge",      # Consulta LTM + knowledge.json + cbor2 ANTES da web
        "search",               # Busca consolidada (DDGS → Agent → WebBrain → Wikipedia)
        "knowledge",            # Geração de insights a partir de knowledge graph
        "knowledge_analyzer",   # Filtra lixo, extrai e persiste conhecimento útil do cache
        "prompt_builder",       # Constrói prompt final com resultados das buscas + conhecimento
        "dependency",           # Análise de dependências de bibliotecas/frameworks
        "technology_selection",  # Seleção de tech stack (backend, frontend, infra)
        "architect",             # Arquitetura de alto nível (diagrama de componentes)
        "system_design",        # Design de sistema (arquitetura + detalhes técnicos)
        "api_design",           # Design de endpoints (OpenAPI/OAS)
        "database_design",      # Schema de banco + migrações + queries
        "security_design",      # Threat modeling + security controls (OWASP Top 10)
        "threat_modeling",
        "performance_design",  # SLOs, latency budgets, observability plan
        "observability_design",
        "architecture_validator" # Validação independente da arquitetura projetada
    ],
    "planejamento": [
        "planner",              # Plano de execução detalhado (etapas táticas)
        "task_breakdown",       # Detalhamento técnico de tasks
        "execution_plan"        # Gantt executável + critical path
    ],
    "construcao": [
    "coder", # Geração de código principal (multi-linguagem)
    "multi_coder", # Codificação paralela/selectiva por partes de código especial
    "code_executor", # Executa código gerado e salva resultado final (.pdf, .py, .html...)
    "frontend_builder", # Construção de frontend (React, Vue, Svelte...)
    "backend_builder", # Construção de backend (FastAPI, Django, Fiber, Gin...)
    "api_builder", # Montagem de API layer (REST/GraphQL/RPC)
    "database_builder" # Build de base: migrations + seed + indexes
    ],
    "qualidade": [
        "test_generator",        # Geração de testes unitários/integração
        "integrator",            # Integração de components → ACC pipeline
        "reviewer",             # Revisão humana-assistida de PR/code
        "semantic_validator",    # Validação semântica (assertions de negócio)
        "security_audit",       # Auditoria de segurança p/ CVEs e OWASP
        "performance_audit",    # Audição de performance / latência / throughput
        "compliance_audit"      # GDPR, LGPD, SOC2, ISO compliance checks
    ],
    "correcao": [
        "qa",
        "tester",
        "debugger",
        "validator",
        "fix_validator",
        "debug_coder",
        "failure_analysis"
    ],
    "entrega": [
        "documentation",        # Geração de docs/manuais de usuário
        "deployment_plan",      # Pipeline de CI/CD, rollback, blue-green
        "release",              # Empacotamento + distribuição + release notes
        "metrics",              # Cálculo de KPIs e SLOs
        "optimization",         # Otimização de código/arquitetura (CPU/memory)
        "retrospective",        # Retrospectiva técnica e aprendizagem
        "result_agent",         # Geração do deliverable final (REPORT.md)
        "critic",               # Avalia qualidade (score 0-100) antes de persistir
        "memory_writer",        # Persiste em LTM/STM + cbor2 + SQLite se aprovado pelo critic
        "memory_cleaner"        # Descarta dados de busca não utilizados
    ],
    "metacognicao": [
        "evaluator",            # Avaliação de solução frente a requirements
        "gap_analyzer",         # Análise de gaps entre delivered vs requested
        "skill_generator",       # Geração de novas skills ou refinamento de existentes
        "sandbox_validator",    # Validação em sandbox antes de aplicar mudanças
        "evolution_committee",  # Orquestração do comitê de evolução
        "pipeline_updater",     # Atualizações estruturais na pipeline DAG
        "evolution_trigger"    # Gatilho para próxima geração evolucionária
    ]
}

# Dicionário de dependências intra-phase e inter-phase
NODE_DEPENDENCIES = {
    # Scheduler fix — roda cedo para corrigir claim antes dos outros nós
    "scheduler": ["agentmailbox"],
    # Construção
    "coder": ["prompt_builder"],
    "multi_coder": ["coder"],
    "code_executor": ["multi_coder"],
    "frontend_builder": ["multi_coder"],
    "backend_builder": ["multi_coder"],
    "api_builder": ["backend_builder"],
    "database_builder": ["multi_coder", "backend_builder"],
    # Definição
    "enhancement": ["prompt_intake"],
    "prompt_improver": ["prompt_intake"],
    "pm": ["requirements"],
    "requirements": ["domain_analysis"],
    "domain_analysis": ["business_rules"],
    "local_knowledge": ["business_rules"],
    "search": ["business_rules"],
    "knowledge": ["local_knowledge", "search", "dependency"],
    "knowledge_analyzer": ["knowledge"],
    "prompt_builder": ["knowledge", "knowledge_analyzer"],
    "dependency": ["technology_selection"],
    "technology_selection": ["architect"],
    "architect": ["system_design"],
    "system_design": ["api_design", "database_design"],
    "api_design": ["security_design"],
    "database_design": ["threat_modeling", "performance_design", "observability_design"],
    "security_design": ["architecture_validator"],
    "threat_modeling": ["architecture_validator"],
    "performance_design": ["architecture_validator"],
    "observability_design": ["architecture_validator"],
    # Planejamento
    "task_breakdown": ["planner"],
    "execution_plan": ["task_breakdown"],
    # Construção
    "frontend_builder": ["coder"],
    "backend_builder": ["coder"],
    "api_builder": ["backend_builder"],
    "database_builder": ["coder", "backend_builder"],
    # Qualidade
    "test_generator": ["database_builder"],
    "integrator": ["test_generator"],
    "reviewer": ["integrator"],
    "semantic_validator": ["reviewer"],
    "security_audit": ["semantic_validator"],
    "performance_audit": ["security_audit"],
    "compliance_audit": ["performance_audit"],
    # Correção
    "tester": ["qa"],
    "validator": ["tester", "debugger"],
    "fix_validator": ["validator"],
    "debug_coder": ["fix_validator"],
    "failure_analysis": ["code_executor"],
    # Entrega
    "documentation": ["debug_coder"],
    "deployment_plan": ["documentation"],
    "release": ["deployment_plan"],
    "metrics": ["release"],
    "optimization": ["metrics"],
    "retrospective": ["optimization"],
    "result_agent": ["retrospective"],
    "critic": ["result_agent"],
    "memory_writer": ["critic"],
    "memory_cleaner": ["memory_writer"],
    # Metacognição
    "evaluator": ["result_agent"],
    "gap_analyzer": ["evaluator"],
    "skill_generator": ["gap_analyzer", "evaluator"],
    "sandbox_validator": ["skill_generator"],
    "evolution_committee": ["skill_generator", "sandbox_validator"],
    "pipeline_updater": ["evolution_committee"],
    "evolution_trigger": ["pipeline_updater"],
    # Evolution Core
    "evolution_knowledge": ["knowledge_analyzer"],
    "evolution_homocysteine": ["skill_generator"],
    "evolution_methylation": ["evolution_homocysteine"],
    "evolution_skill_executor": ["evolution_dynamic_registry"],
    "evolution_dynamic_registry": ["evolution_homocysteine"]
}

def get_node_phase(node_name: str) -> str:
    """Returns the phase name for the given node, or 'unknown'."""
    for phase, nodes in PHASES.items():
        if node_name in nodes:
            return phase
    return "unknown"


__all__ = ["PHASES", "NODE_DEPENDENCIES", "get_node_phase"]