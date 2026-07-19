# iaglobal/graphs/pipeline_definition.py

from __future__ import annotations

from typing import Dict, List, Any

# ==========================================================
# SINGLE SOURCE OF TRUTH
# ==========================================================

PIPELINE_SKILLS: List[tuple[str, Dict[str, Any]]] = [
    # ======================================================
    # PHASE 0 — METABOLIC PRE-CONDITIONING
    # ======================================================
    ("orchestrator_pump", {"strategy": "fast", "depends_on": []}),
    ("lineage_proof", {"strategy": "fast", "depends_on": []}),
    # ======================================================
    # PHASE 1 — DISCOVERY & UNDERSTANDING
    # ======================================================
    ("agentmailbox", {"strategy": "fast", "depends_on": ["orchestrator_pump"]}),
    ("prompt_intake", {"strategy": "general", "depends_on": []}),
    ("enhancement", {"strategy": "general", "depends_on": ["prompt_intake"]}),
    ("interpreter", {"strategy": "fast", "depends_on": ["prompt_intake"]}),
    ("web_classifier", {"strategy": "fast", "depends_on": ["prompt_intake"]}),
    (
        "orchestrator_agent",
        {"strategy": "general", "critical": True, "depends_on": ["enhancement"]},
    ),
    ("pm", {"strategy": "general", "depends_on": ["orchestrator_agent"]}),
    ("requirements", {"strategy": "general", "critical": True, "depends_on": ["pm"]}),
    ("ingestion", {"strategy": "general", "depends_on": ["requirements"]}),
    ("domain_analysis", {"strategy": "research", "depends_on": ["requirements"]}),
    ("business_rules", {"strategy": "general", "depends_on": ["domain_analysis"]}),
    # ======================================================
    # PHASE 2 — KNOWLEDGE
    # ======================================================
    ("local_knowledge", {"strategy": "fast", "depends_on": ["business_rules"]}),
    ("search", {"strategy": "research", "depends_on": ["business_rules"]}),
    ("knowledge", {"strategy": "fast", "depends_on": ["local_knowledge", "search"]}),
    ("knowledge_analyzer", {"strategy": "fast", "depends_on": ["knowledge"]}),
    (
        "dependency",
        {
            "strategy": "fast",
            "critical": True,
            "depends_on": ["knowledge", "knowledge_analyzer"],
        },
    ),
    ("prompt_builder", {"strategy": "general", "depends_on": ["dependency"]}),
    (
        "prompt_improver",
        {
            "strategy": "general",
            "depends_on": [
                "prompt_intake"
            ],  # ← Corrige: depende do prompt BRUTO do usuário
            "critical": True,
        },
    ),
    ("technology_selection", {"strategy": "research", "depends_on": ["dependency"]}),
    # ======================================================
    # PHASE 3 — ARCHITECTURE
    # ======================================================
    (
        "architect",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": ["business_rules", "technology_selection"],
        },
    ),
    ("risk_analysis", {"strategy": "general", "depends_on": ["architect"]}),
    ("system_design", {"strategy": "general", "depends_on": ["architect"]}),
    ("api_design", {"strategy": "general", "depends_on": ["architect"]}),
    ("database_design", {"strategy": "general", "depends_on": ["architect"]}),
    (
        "security_design",
        {"strategy": "general", "critical": True, "depends_on": ["architect"]},
    ),
    ("threat_modeling", {"strategy": "security", "depends_on": ["security_design"]}),
    ("performance_design", {"strategy": "general", "depends_on": ["architect"]}),
    ("observability_design", {"strategy": "general", "depends_on": ["architect"]}),
    (
        "architecture_validator",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": [
                "system_design",
                "api_design",
                "database_design",
                "security_design",
                "performance_design",
                "observability_design",
            ],
        },
    ),
    # ======================================================
    # PHASE 3.5 — AI ENGINEERING OPTIMIZATION
    # ======================================================
    (
        "applied_ai_engineer",
        {
            "strategy": "general",
            "critical": False,
            "depends_on": ["architecture_validator"],
        },
    ),
    # ======================================================
    # PHASE 4 — PLANNING
    # ======================================================
    (
        "planner",
        {
            "strategy": "general",
            "depends_on": [
                "prompt_improver"
            ],  # ← Corrige: planner usa prompt MELHORADO
            "critical": True,
        },
    ),
    (
        "task_breakdown",
        {"strategy": "general", "critical": True, "depends_on": ["planner"]},
    ),
    ("execution_plan", {"strategy": "general", "depends_on": ["task_breakdown"]}),
    (
        "multi_coder",
        {"strategy": "general", "depends_on": ["execution_plan", "prompt_builder"]},
    ),
    # ======================================================
    # PHASE 5 — BUILD
    # ======================================================
    (
        "coder",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": ["execution_plan", "prompt_builder"],
        },
    ),
    (
        "frontend_builder",
        {
            "strategy": "frontend",  # ← Evita colisão com SKILL_FRONTEND_BUILDER
            "depends_on": ["coder"],
        },
    ),
    (
        "backend_builder",
        {
            "strategy": "backend",  # ← Evita colisão com SKILL_BACKEND_BUILDER
            "depends_on": ["coder"],
        },
    ),
    (
        "database_builder",
        {
            "strategy": "database",  # ← Evita colisão com SKILL_DATABASE_BUILDER
            "depends_on": ["coder"],
        },
    ),
    (
        "api_builder",
        {
            "strategy": "api",  # ← Evita colisão com SKILL_API_BUILDER
            "depends_on": ["backend_builder"],
        },
    ),
    (
        "test_generator",
        {
            "strategy": "general",
            "depends_on": [
                "frontend_builder",
                "backend_builder",
                "api_builder",
                "database_builder",
            ],
        },
    ),
    (
        "integrator",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": [
                "frontend_builder",
                "backend_builder",
                "api_builder",
                "database_builder",
            ],
        },
    ),
    ("genesis_builder", {"strategy": "general", "depends_on": ["integrator"]}),
    (
        "code_executor",
        {"strategy": "general", "depends_on": ["integrator", "frontend_builder"]},
    ),
    # ======================================================
    # PHASE 6 — VALIDATION
    # ======================================================
    (
        "reviewer",
        {"strategy": "general", "critical": True, "depends_on": ["integrator"]},
    ),
    (
        "semantic_validator",
        {"strategy": "general", "critical": True, "depends_on": ["reviewer"]},
    ),
    ("security_audit", {"strategy": "security", "depends_on": ["semantic_validator"]}),
    (
        "performance_audit",
        {"strategy": "general", "depends_on": ["semantic_validator"]},
    ),
    ("compliance_audit", {"strategy": "general", "depends_on": ["semantic_validator"]}),
    ("performance", {"strategy": "general", "depends_on": ["semantic_validator"]}),
    ("security", {"strategy": "security", "depends_on": ["semantic_validator"]}),
    # ======================================================
    # PHASE 7 — QA
    # ======================================================
    ("qa", {"strategy": "general", "depends_on": ["integrator"]}),
    ("tester", {"strategy": "general", "critical": True, "depends_on": ["qa"]}),
    (
        "validator_retry",
        {
            "strategy": "fast",
            "critical": True,
            "depends_on": ["lsp_validator"],
        },
    ),
    (
        "debug_unificado",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": ["tester", "validator_retry"],
        },
    ),
    ("fix_validator", {"strategy": "general", "depends_on": ["debug_unificado"]}),
    # ======================================================
    # PHASE 7.5 — CRITICAL APPROVAL GATE
    # ======================================================
    (
        "critic",
        {
            "strategy": "general",
            "critical": True,
            "depends_on": ["fix_validator", "tester"],
            "approval_gate": True,  # Se reprovar, volta para coder/frontend_builder
            "retry_nodes": ["frontend_builder", "backend_builder", "coder"],
        },
    ),
    # ======================================================
    # PHASE 8 — DELIVERY
    # ======================================================
    (
        "documentation",
        {"strategy": "general", "depends_on": ["tester", "semantic_validator"]},
    ),
    ("deployment_plan", {"strategy": "general", "depends_on": ["documentation"]}),
    (
        "release",
        {"strategy": "general", "critical": True, "depends_on": ["deployment_plan"]},
    ),
    ("artifact_writer", {"strategy": "general", "depends_on": ["release"]}),
    # ======================================================
    # PHASE 9 — OBSERVABILITY
    # ======================================================
    ("metrics", {"strategy": "fast", "depends_on": ["release"]}),
    ("optimization", {"strategy": "fast", "depends_on": ["metrics"]}),
    ("retrospective", {"strategy": "general", "depends_on": ["optimization"]}),
    ("reflexion", {"strategy": "general", "depends_on": ["retrospective"]}),
    # ======================================================
    # PHASE 10 — MEMORY
    # ======================================================
    (
        "result_agent",
        {"strategy": "general", "critical": True, "depends_on": ["retrospective"]},
    ),
    # Critic foi movido para PHASE 7.5 (approval gate)
    ("memory_writer", {"strategy": "fast", "depends_on": ["critic"]}),
    ("memory_cleaner", {"strategy": "fast", "depends_on": ["memory_writer"]}),
    # ======================================================
    # PHASE 11 — EVOLUTION
    # ======================================================
    ("evaluator", {"strategy": "general", "depends_on": ["memory_cleaner"]}),
    ("gap_analyzer", {"strategy": "general", "depends_on": ["evaluator"]}),
    ("skill_generator", {"strategy": "general", "depends_on": ["gap_analyzer"]}),
    ("sandbox_validator", {"strategy": "general", "depends_on": ["skill_generator"]}),
    (
        "evolution_committee",
        {"strategy": "general", "depends_on": ["sandbox_validator"]},
    ),
    (
        "pipeline_updater",
        {"strategy": "general", "depends_on": ["evolution_committee"]},
    ),
    ("evolution_trigger", {"strategy": "general", "depends_on": ["pipeline_updater"]}),
    # ======================================================
    # ORPHAN AGENTS — handlers delegating to agent classes
    # ======================================================
    ("failure_analysis", {"strategy": "fast", "depends_on": ["code_executor"]}),
    ("knowledge_writer", {"strategy": "general", "depends_on": ["multi_coder"]}),
    ("multi_agent", {"strategy": "general", "depends_on": ["prompt_intake"]}),
    ("typing_agent", {"strategy": "fast", "depends_on": ["prompt_intake"]}),
    # ======================================================
    # PHASE 7.5 — LSP VALIDATION (static analysis)
    # ======================================================
    (
        "lsp_validator",
        {"strategy": "fast", "critical": True, "depends_on": ["multi_coder", "coder"]},
    ),
    # ======================================================
    # PHASE 12 — SYSTEM HEALTH ANALYSIS
    # ======================================================
    (
        "system_analysis",
        {"strategy": "general", "critical": False, "depends_on": ["result_agent"]},
    ),
]

# ==========================================================
# HELPERS
# ==========================================================

PIPELINE_MAP = {name: cfg for name, cfg in PIPELINE_SKILLS}

PIPELINE_NAMES = [name for name, _ in PIPELINE_SKILLS]

# Injetado automaticamente para resolver assinaturas ausentes
