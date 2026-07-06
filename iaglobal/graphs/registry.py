# iaglobal/graphs/registry.py
"""
Registry central de nós do pipeline.
Mapeia nomes de skills para fabricas de nós.
"""
from .nodes import create_skill_node


NODE_REGISTRY: dict = {
    "scheduler": lambda: create_skill_node("scheduler"),
    "prompt_intake": lambda: create_skill_node("prompt_intake"),
    "enhancement": lambda: create_skill_node("enhancement"),
    "orchestrator_agent": lambda: create_skill_node("orchestrator_agent"),
    "pm": lambda: create_skill_node("pm"),
    "requirements": lambda: create_skill_node("requirements"),
    "ingestion": lambda: create_skill_node("ingestion"),
    "domain_analysis": lambda: create_skill_node("domain_analysis"),
    "business_rules": lambda: create_skill_node("business_rules"),
    "search": lambda: create_skill_node("search"),
    "knowledge": lambda: create_skill_node("knowledge"),
    "dependency": lambda: create_skill_node("dependency"),
    "technology_selection": lambda: create_skill_node("technology_selection"),
    "architect": lambda: create_skill_node("architect"),
    "system_design": lambda: create_skill_node("system_design"),
    "api_design": lambda: create_skill_node("api_design"),
    "database_design": lambda: create_skill_node("database_design"),
    "security_design": lambda: create_skill_node("security_design"),
    "threat_modeling": lambda: create_skill_node("threat_modeling"),
    "performance_design": lambda: create_skill_node("performance_design"),
    "observability_design": lambda: create_skill_node("observability_design"),
    "architecture_validator": lambda: create_skill_node("architecture_validator"),
    "applied_ai_engineer": lambda: create_skill_node("applied_ai_engineer"),
    "planner": lambda: create_skill_node("planner"),
    "task_breakdown": lambda: create_skill_node("task_breakdown"),
    "execution_plan": lambda: create_skill_node("execution_plan"),
    "coder": lambda: create_skill_node("coder"),
    "frontend_builder": lambda: create_skill_node("frontend_builder"),
    "backend_builder": lambda: create_skill_node("backend_builder"),
    "database_builder": lambda: create_skill_node("database_builder"),
    "api_builder": lambda: create_skill_node("api_builder"),
    "test_generator": lambda: create_skill_node("test_generator"),
    "integrator": lambda: create_skill_node("integrator"),
    "reviewer": lambda: create_skill_node("reviewer"),
    "semantic_validator": lambda: create_skill_node("semantic_validator"),
    "security_audit": lambda: create_skill_node("security_audit"),
    "performance_audit": lambda: create_skill_node("performance_audit"),
    "compliance_audit": lambda: create_skill_node("compliance_audit"),
    "qa": lambda: create_skill_node("qa"),
    "tester": lambda: create_skill_node("tester"),
    "debugger": lambda: create_skill_node("debugger"),
    "validator": lambda: create_skill_node("validator"),
    "fix_validator": lambda: create_skill_node("fix_validator"),
    "debug_coder": lambda: create_skill_node("debug_coder"),
    "documentation": lambda: create_skill_node("documentation"),
    "deployment_plan": lambda: create_skill_node("deployment_plan"),
    "release": lambda: create_skill_node("release"),
    "metrics": lambda: create_skill_node("metrics"),
    "optimization": lambda: create_skill_node("optimization"),
    "retrospective": lambda: create_skill_node("retrospective"),
    "result_agent": lambda: create_skill_node("result_agent"),
    "knowledge_writer": lambda: create_skill_node("knowledge_writer"),
    "failure_analysis": lambda: create_skill_node("failure_analysis"),
    "evaluator": lambda: create_skill_node("evaluator"),
    "gap_analyzer": lambda: create_skill_node("gap_analyzer"),
    "skill_generator": lambda: create_skill_node("skill_generator"),
    "sandbox_validator": lambda: create_skill_node("sandbox_validator"),
    "evolution_committee": lambda: create_skill_node("evolution_committee"),
    "pipeline_updater": lambda: create_skill_node("pipeline_updater"),
    "evolution_trigger": lambda: create_skill_node("evolution_trigger"),
}


def register_node(name: str, factory):
    """Registra novo nó no registry."""
    NODE_REGISTRY[name] = factory


def get_node(name: str):
    """Recupera nó pelo nome."""
    factory = NODE_REGISTRY.get(name)
    if factory:
        return factory()
    return None