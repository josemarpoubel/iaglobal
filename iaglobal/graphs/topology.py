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

from collections import Counter

PHASES = {
    "definicao": [
        "orchestrator_pump",
        "lineage_proof",
        "agentmailbox",
        "prompt_intake",
        "interpreter",
        "web_classifier",
        "typing_agent",
        "multi_agent",
        "ingestion",
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
        "architecture_validator",
    ],
    "planejamento": [
        "applied_ai_engineer",
        "planner",
        "task_breakdown",
        "execution_plan",
    ],
    "construcao": [
        "coder",
        "multi_coder",
        "frontend_builder",
        "genesis_builder",
        "code_executor",
        "backend_builder",
        "api_builder",
        "database_builder",
    ],
    "qualidade": [
        "test_generator",
        "integrator",
        "reviewer",
        "semantic_validator",
        "security_audit",
        "performance_audit",
        "compliance_audit",
        "lsp_validator",
        "tester",
        "qa",
        "debug_unificado",
        "fix_validator",
        "failure_analysis",
        "risk_analysis",
        "security",
        "performance",
        "validator_retry",
    ],
    "entrega": [
        "documentation",
        "deployment_plan",
        "critic",
        "release",
        "artifact_writer",
        "metrics",
        "optimization",
        "retrospective",
        "reflexion",
        "result_agent",
        "knowledge_writer",
        "memory_writer",
        "memory_cleaner",
        "scheduler",
    ],
    "metacognicao": [
        "evaluator",
        "gap_analyzer",
        "skill_generator",
        "sandbox_validator",
        "evolution_committee",
        "pipeline_updater",
        "evolution_trigger",
        "evolution_knowledge",
        "symbiont_handshake",
        "entropy_sentinel",
        "fusion",
        "auditor_sentinel",
        "apoptosis_kill",
        "system_analysis",
    ],
}

NODE_DEPENDENCIES = {
    "scheduler": ["agentmailbox"],
    "planner": ["agentmailbox"],
    "coder": ["prompt_builder"],
    "multi_coder": ["coder"],
    "frontend_builder": ["multi_coder"],
    "backend_builder": ["multi_coder"],
    "api_builder": ["backend_builder"],
    "database_builder": ["multi_coder", "backend_builder"],
    "code_executor": ["frontend_builder"],
    "enhancement": ["prompt_intake"],
    "prompt_improver": ["prompt_intake"],
    "orchestrator_agent": ["enhancement"],
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
    "database_design": [
        "threat_modeling",
        "performance_design",
        "observability_design",
    ],
    "security_design": ["architecture_validator"],
    "threat_modeling": ["architecture_validator"],
    "performance_design": ["architecture_validator"],
    "observability_design": ["architecture_validator"],
    "applied_ai_engineer": ["architecture_validator"],
    "planner": ["applied_ai_engineer"],
    "task_breakdown": ["architecture_validator"],
    "execution_plan": ["task_breakdown"],
    "test_generator": ["database_builder"],
    "integrator": ["test_generator"],
    "reviewer": ["integrator"],
    "semantic_validator": ["reviewer"],
    "security_audit": ["semantic_validator"],
    "performance_audit": ["security_audit"],
    "compliance_audit": ["performance_audit"],
    "fix_validator": ["compliance_audit"],
    "failure_analysis": ["fix_validator"],
    "documentation": ["fix_validator"],
    "deployment_plan": ["documentation"],
    "release": ["critic"],
    "critic": ["deployment_plan"],
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
    "symbiont_handshake": ["evolution_trigger"],
    "entropy_sentinel": ["symbiont_handshake"],
    "auditor_sentinel": ["entropy_sentinel"],
    "fusion": ["auditor_sentinel"],
    "apoptosis_kill": ["fusion"],
}


def get_node_phase(node_name: str) -> str:
    """Returns the phase name for the given node, or 'unknown'."""
    for phase, nodes in PHASES.items():
        if node_name in nodes:
            return phase
    return "unknown"


def audit_representations(
    pipeline_nodes: set[str],
    builder_nodes: set[str],
    run_functions: set[str] | None = None,
) -> dict:
    """
    Architecture contract validator.

    Verifies consistency between every architectural representation of
    the execution pipeline:

    - PIPELINE_SKILLS
    - RUN_NODE_NAMES
    - PHASES
    - NODE_DEPENDENCIES

    Returns a dictionary containing:
      - diagnostic flags (result["checks"])
      - set differences
      - reachability information
      - cycle information

    The returned structure is part of the project's architectural
    contract and is consumed by tests/test_topology_contract.py.

    Any new architectural invariant should be implemented here before
    corresponding tests are introduced.
    """
    topology_nodes = set()
    for nodes in PHASES.values():
        topology_nodes.update(nodes)
    topology_nodes.update(NODE_DEPENDENCIES.keys())
    for deps in NODE_DEPENDENCIES.values():
        topology_nodes.update(deps)

    phase_nodes: set[str] = set()
    for nodes in PHASES.values():
        phase_nodes.update(nodes)

    registered = pipeline_nodes | builder_nodes | topology_nodes

    # ── Set differences ──
    pipeline_without_phase = sorted(pipeline_nodes - phase_nodes)
    builder_without_phase = sorted(builder_nodes - phase_nodes)

    # ── Dependencies without phase ──
    dep_nodes: set[str] = set(NODE_DEPENDENCIES.keys())
    for deps in NODE_DEPENDENCIES.values():
        dep_nodes.update(deps)
    dependency_without_phase = sorted(dep_nodes - phase_nodes)

    # ── Duplicate phase assignments ──
    phase_counts = Counter()
    for nodes in PHASES.values():
        phase_counts.update(nodes)
    duplicate_phase_nodes = sorted(
        n for n, count in phase_counts.items() if count > 1
    )

    result: dict = {
        "pipeline_count": len(pipeline_nodes),
        "builder_count": len(builder_nodes),
        "topology_count": len(topology_nodes),
        "pipeline_minus_builder": sorted(pipeline_nodes - builder_nodes),
        "builder_minus_pipeline": sorted(builder_nodes - pipeline_nodes),
        "topology_minus_pipeline": sorted(topology_nodes - pipeline_nodes),
        "pipeline_minus_topology": sorted(pipeline_nodes - topology_nodes),
        "all_three_common": sorted(pipeline_nodes & builder_nodes & topology_nodes),
        "pipeline_without_phase": pipeline_without_phase,
        "builder_without_phase": builder_without_phase,
        "dependency_without_phase": dependency_without_phase,
        "duplicate_phase_nodes": duplicate_phase_nodes,
    }

    # ── Dangling dependency references ──
    dangling = []
    for node, deps in NODE_DEPENDENCIES.items():
        for dep in deps:
            if dep not in topology_nodes and dep not in pipeline_nodes and dep not in builder_nodes:
                dangling.append((node, dep))
    result["dangling_deps"] = dangling

    # ── Orphan functions (run_* without registration) ──
    if run_functions is not None:
        orphan_fn = sorted(run_functions - registered)
    else:
        orphan_fn = []
    result["orphan_run_functions"] = orphan_fn

    # ── Cycle detection (DFS three-color) ──
    color: dict[str, int] = {n: 0 for n in NODE_DEPENDENCIES}
    cycles: list[list[str]] = []

    def _dfs_cycle(n: str, path: list[str]) -> None:
        color[n] = 1
        path.append(n)
        for dep in NODE_DEPENDENCIES.get(n, []):
            if color.get(dep) == 1:
                idx = path.index(dep)
                cycles.append(path[idx:] + [dep])
            elif color.get(dep) == 0:
                _dfs_cycle(dep, path)
        path.pop()
        color[n] = 2

    for n in list(NODE_DEPENDENCIES):
        if color.get(n) == 0:
            _dfs_cycle(n, [])

    result["cycles"] = cycles

    # ── Reachability (roots = PHASES roots + NODE_DEPENDENCIES roots) ──
    roots = set()
    for n in topology_nodes:
        if n not in NODE_DEPENDENCIES:
            roots.add(n)  # PHASES-only nodes are implicit roots
    for n, deps in NODE_DEPENDENCIES.items():
        if not deps:
            roots.add(n)
    all_dep_refs: set[str] = set()
    for deps in NODE_DEPENDENCIES.values():
        all_dep_refs.update(deps)
    for d in all_dep_refs:
        if d not in set(NODE_DEPENDENCIES.keys()):
            roots.add(d)

    visited: set[str] = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        if n in visited:
            continue
        visited.add(n)
        for node_, deps_ in NODE_DEPENDENCIES.items():
            if n in deps_:
                stack.append(node_)

    result["reachable_from_roots"] = len(visited)
    result["total_in_graph"] = len(topology_nodes)
    result["unreachable"] = sorted(topology_nodes - visited)

    # ── Diagnostic flags ──
    result["checks"] = {
        "no_cycles": len(cycles) == 0,
        "no_dangling_deps": len(dangling) == 0,
        "no_orphan_run_functions": len(orphan_fn) == 0,
        "all_unreachable_exist": all(
            n in pipeline_nodes or n in builder_nodes or n in topology_nodes
            for n in result["unreachable"]
        ),
        "no_pipeline_without_phase": len(pipeline_without_phase) == 0,
        "no_builder_without_phase": len(builder_without_phase) == 0,
        "no_dependency_without_phase": len(dependency_without_phase) == 0,
        "no_duplicate_phase_nodes": len(duplicate_phase_nodes) == 0,
    }
    result["valid"] = all(result["checks"].values())
    return result


__all__ = ["PHASES", "NODE_DEPENDENCIES", "get_node_phase", "audit_representations"]
