# SPDX-License-Identifier: MIT
"""
iaglobal/graphs/topology.py
Domínios: 55 nodes -> 7 phases -> dependências intra/inter-phase

Refatorado conforme leiame.md:
- context_weaver epigenético entre prompt_intake e prompt_improver
- mini_evaluator gates entre fases críticas
- critic movido antes de release (gate de qualidade)
- Unificação das fases qualidade + correção (ciclo interno)
"""

PHASES = {
    "definicao": [
        "agentmailbox",         
        "prompt_intake",       
        "context_weaver",       # Novo: injeta marcadores epigenéticos
        "prompt_improver",     
        "enhancement",          
        "orchestrator_agent",    
        "pm",                   
        "requirements",          
        "domain_analysis",       
        "business_rules",        
        "local_knowledge",      
        "search",               
        "knowledge",            
        "knowledge_analyzer",   
        "prompt_builder",       
        "dependency",           
        "technology_selection",  
        "architect",             
        "system_design",        
        "api_design",           
        "database_design",      
        "security_design",      
        "threat_modeling",
        "performance_design",  
        "observability_design",
        "architecture_validator" ,
        "mini_evaluator_post_arch",  # Gate após arquitetura
        "immune_check"              # Anti-parasitas digital
    ],
    "planejamento": [
        "planner",              
        "task_breakdown",       
        "execution_plan"        
    ],
    "construcao": [
        "coder", 
        "multi_coder", 
        "frontend_builder", 
        "code_executor", 
        "backend_builder", 
        "api_builder", 
        "database_builder",
        "mini_evaluator_post_build"  # Gate pós construção
    ],
    "qualidade": [  # Unificada: qualidade + correção (ciclo interno)
        "test_generator",        
        "integrator",            
        "reviewer",             
        "semantic_validator",   
        "security_audit",       
        "performance_audit",    
        "compliance_audit",
        "debug_coder",  # Ciclo interno de correção (máx 3 retries)
        "fix_validator",
        "failure_analysis"  # Só executa se retry estourar
    ],
    "entrega": [
        "documentation",        
        "deployment_plan",      
        "critic",              # MOVED: agora antes do release (gate de qualidade)
        "release",              # Só executa se critic aprovar
        "metrics",             
        "optimization",         
        "retrospective",        
        "result_agent",         
        "knowledge_writer",      
        "memory_writer",        
        "memory_cleaner"        
    ],
    "metacognicao": [
        "evaluator",            
        "gap_analyzer",         
        "skill_generator",       
        "sandbox_validator",    # Validação com KPIs objetivos
        "evolution_committee",  
        "pipeline_updater",     
        "evolution_trigger",
        "entropy_sentinel",   # Vigilância de integridade genética (FIRST!)
        "immune_monitor",   # Monitor custo-benefício contínuo
        "apoptosis_kill"    # Apoptose programada para parasitas
    ]
}

# Dicionário de dependências intra-phase e inter-phase
NODE_DEPENDENCIES = {
    "scheduler": ["agentmailbox"],
    "immune_check": ["mini_evaluator_post_arch"],  # Anti-parasitas após arch
    "planner": ["immune_check", "agentmailbox"],  # Pode vir de mailbox ou immune_check
    "coder": ["prompt_builder"],
    "multi_coder": ["coder"],
    "frontend_builder": ["multi_coder"],
    "backend_builder": ["multi_coder"],
    "api_builder": ["backend_builder"],
    "database_builder": ["multi_coder", "backend_builder"],
    "code_executor": ["frontend_builder"],
    "immune_check_build": ["code_executor"],  # Anti-parasitas pós-build
    "mini_evaluator_post_build": ["immune_check_build"],  # Gate pós construção
    "enhancement": ["prompt_intake"],
    "context_weaver": ["prompt_intake"],  # Novo gate epigenético
    "prompt_improver": ["context_weaver"],  # Agora usa context_weaver
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
    "mini_evaluator_post_arch": ["architecture_validator"],  # Gate após arquitetura
    "immune_check": ["mini_evaluator_post_arch"],  # Anti-parasitas digital
    "planner": ["immune_check"],  # Aguarda verificação imunológica
    "mini_evaluator_post_build": ["code_executor"],  # Gate pós construção
    "task_breakdown": ["immune_check"],  # After immune check, not planner
    "execution_plan": ["task_breakdown"],
    "test_generator": ["database_builder"],
    "integrator": ["test_generator"],
    "reviewer": ["integrator"],
    "semantic_validator": ["reviewer"],
    "security_audit": ["semantic_validator"],
    "performance_audit": ["security_audit"],
    "compliance_audit": ["performance_audit"],
    "debug_coder": ["compliance_audit"],  # Ciclo interno de correção
    "fix_validator": ["debug_coder"],
    "failure_analysis": ["fix_validator"],  # Só se retry estourar
    "documentation": ["fix_validator"],
    "deployment_plan": ["documentation"],
    "release": ["critic"],  # Gate do critic
    "critic": ["deployment_plan"],  # MOVED: antes do release
    "metrics": ["release"],
    "optimization": ["metrics"],
    "retrospective": ["optimization"],
    "result_agent": ["retrospective"],
    "knowledge_writer": ["result_agent"],
    "memory_writer": ["critic"],
    "memory_cleaner": ["memory_writer"],
    "evaluator": ["result_agent"],
    "gap_analyzer": ["evaluator"],
    "skill_generator": ["gap_analyzer", "evaluator"],
    "sandbox_validator": ["skill_generator"],
    "evolution_committee": ["skill_generator", "sandbox_validator"],
    "pipeline_updater": ["evolution_committee"],
    "evolution_trigger": ["pipeline_updater"],
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