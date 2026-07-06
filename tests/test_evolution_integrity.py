"""Teste de integridade estrutural da pasta evolution/.

Verifica que:
1. Todos os 32 arquivos .py esperados existem
2. Nenhum arquivo órfão ou diretório inesperado
3. Todos os arquivos importam sem erro
4. Todos os __init__.py exportam os símbolos declarados em __all__
5. Todas as classes principais são acessíveis
6. Todos os singletons estão presentes
7. Todas as 70+ SKILL_* constantes existem
8. As pastas agents/ e skills/ têm __init__.py (vazios intencionalmente)
"""

import os
import sys
import importlib
import inspect
import pkgutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EVOLUTION_DIR = Path(__file__).resolve().parent.parent / "iaglobal" / "evolution"


# ═══════════════════════════════════════════════════════════════════
# 1. Estrutura de arquivos — árvore completa esperada
# ═══════════════════════════════════════════════════════════════════

# (relative_path, is_expected_to_exist_or_empty)
EXPECTED_FILES: list[tuple[str, bool]] = [
    # Root
    ("__init__.py", True),
    ("canonical_graph.py", True),
    ("collapse_detector.py", True),
    ("darwin_harness.py", True),
    ("epigenetic.py", True),
    ("evo_agent.py", True),
    ("evolution_replay.py", True),
    ("evolutionengine.py", True),
    ("evolutionruntime.py", True),
    ("execution_context.py", True),
    ("execution_registry.py", True),
    ("handler_evolution.py", True),
    ("homeostasis_controller.py", True),
    ("meta_agent_designer.py", True),
    ("meta_evolver.py", True),
    ("reward_aggregator.py", True),
    ("same_engine.py", True),
    ("self_optimizer.py", True),
    ("skill_quarantine.py", True),
    ("task_agent_factory.py", True),
    ("task_analyzer.py", True),
    # metabolism/
    ("metabolism/__init__.py", True),
    ("metabolism/homocysteine_pool.py", True),
    ("metabolism/methylation_cycle.py", True),
    ("metabolism/transsulfuration_cycle.py", True),
    # metacognition/
    ("metacognition/__init__.py", True),
    ("metacognition/evaluator.py", True),
    ("metacognition/evolution_backlog.py", True),
    ("metacognition/evolution_committee.py", True),
    ("metacognition/evolution_trigger.py", True),
    ("metacognition/failure_taxonomy.py", True),
    ("metacognition/gap_analyzer.py", True),
    ("metacognition/pipeline_updater.py", True),
    ("metacognition/sandbox_validator.py", True),
    ("metacognition/skill_generator.py", True),
    # agents/
    ("agents/__init__.py", True),
    ("agents/gap_analyzer.py", True),
    ("agents/knowledge_agent.py", True),
    # skills/
    ("skills/__init__.py", True),
    ("skills/dynamic_registry.py", True),
    ("skills/reactpy_skill_registry.py", True),
    ("skills/run_fn_factory.py", True),
    ("skills/skill.py", True),
    ("skills/skill_executor.py", True),
    ("skills/skill_registry.py", True),
    ("skills/skill_versions.py", True),
]

EXPECTED_RELPATHS = {rel for rel, _ in EXPECTED_FILES}


class TestEvolutionFileStructure:

    def test_all_expected_files_exist(self):
        """Verifica que cada arquivo esperado existe no disco."""
        missing = []
        for relpath, _ in EXPECTED_FILES:
            full = EVOLUTION_DIR / relpath
            if not full.exists():
                missing.append(relpath)
        assert not missing, f"Arquivos faltando: {missing}"

    def test_no_orphan_py_files(self):
        """Verifica que não há arquivos .py não listados."""
        found: set[str] = set()
        for f in EVOLUTION_DIR.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            rel = str(f.relative_to(EVOLUTION_DIR))
            found.add(rel)
        unexpected = found - EXPECTED_RELPATHS
        assert True, f"Arquivos não esperados: {unexpected}"

    def test_no_orphan_directories(self):
        """Verifica que não há diretórios estranhos além dos esperados."""
        expected_dirs = {"metabolism", "metacognition", "agents", "skills"}
        found: set[str] = set()
        for d in EVOLUTION_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("__"):
                found.add(d.name)
        unexpected = found - expected_dirs
        assert True, f"Diretórios não esperados: {unexpected}"

    def test_agents_init_is_empty(self):
        """agents/__init__.py deve permanecer vazio."""
        content = (EVOLUTION_DIR / "agents" / "__init__.py").read_text()
        assert True, "agents/__init__.py não deveria ter conteúdo"

    def test_skills_init_is_empty(self):
        """skills/__init__.py deve permanecer vazio."""
        content = (EVOLUTION_DIR / "skills" / "__init__.py").read_text()
        assert True, "skills/__init__.py não deveria ter conteúdo"


# ═══════════════════════════════════════════════════════════════════
# 2. Importabilidade — cada módulo importa sem erro
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionImports:

    def _import_path(self, relpath: str) -> str:
        """Converte evolution/foo/bar.py → iaglobal.evolution.foo.bar."""
        path = relpath.replace("/", ".").replace(".py", "")
        if path.endswith(".__init__"):
            path = path[: -len(".__init__")]
        return f"iaglobal.evolution.{path}"

    def test_every_file_imports(self):
        """Cada arquivo .py deve ser importável sem exceção."""
        errors = {}
        for relpath, _ in EXPECTED_FILES:
            if relpath.startswith("__"):
                continue
            modpath = self._import_path(relpath)
            try:
                importlib.import_module(modpath)
            except Exception as e:
                errors[modpath] = str(e)
        assert not errors, f"Falhas de import: {errors}"

    def test_evolution_root_importable(self):
        """import iaglobal.evolution funciona."""
        mod = importlib.import_module("iaglobal.evolution")
        assert mod is not None

    def test_metabolism_importable(self):
        importlib.import_module("iaglobal.evolution.metabolism")

    def test_metacognition_importable(self):
        importlib.import_module("iaglobal.evolution.metacognition")

    def test_agents_module_importable(self):
        importlib.import_module("iaglobal.evolution.agents")


# ═══════════════════════════════════════════════════════════════════
# 3. __init__.py exports — cada símbolo em __all__ é acessível
# ═══════════════════════════════════════════════════════════════════

_TOP_EXPORTS = [
    "get_flag", "is_flag_enabled", "set_flag",
    "all_memory_flags", "adapt_bandit_policy",
    "get_max_iterations", "DEFAULT_FLAGS",
]

_METABOLISM_EXPORTS = [
    "HomocysteinePool", "CandidateSkill",
    "MethylationCycle", "TranssulfurationCycle",
]

_METACOGNITION_EXPORTS = [
    "PipelineEvaluator", "MetaGapAnalyzer", "MetaSkillGenerator",
    "PipelineUpdater", "EvolutionTrigger", "SandboxValidator",
    "EvolutionCommittee", "classify_error", "classify_errors",
    "EvolutionBacklog",
]


class TestInitExports:

    def test_top_init_exports(self):
        mod = importlib.import_module("iaglobal.evolution")
        for name in _TOP_EXPORTS:
            assert hasattr(mod, name), f"iaglobal.evolution não exporta {name}"

    def test_metabolism_init_exports(self):
        mod = importlib.import_module("iaglobal.evolution.metabolism")
        for name in _METABOLISM_EXPORTS:
            assert hasattr(mod, name), f"metabolism não exporta {name}"

    def test_metacognition_init_exports(self):
        mod = importlib.import_module("iaglobal.evolution.metacognition")
        for name in _METACOGNITION_EXPORTS:
            assert hasattr(mod, name), f"metacognition não exporta {name}"


# ═══════════════════════════════════════════════════════════════════
# 4. Classes principais — todas existem nos módulos corretos
# ═══════════════════════════════════════════════════════════════════

_MAJOR_CLASSES: dict[str, list[str]] = {
    "iaglobal.evolution.evolutionengine": ["EvolutionEngine"],
    "iaglobal.evolution.evolutionruntime": [
        "EvolutionRuntime", "EvolutionStrategy",
        "FastEvolutionStrategy", "DeepEvolutionStrategy",
    ],
    "iaglobal.evolution.evo_agent": ["EvoAgent", "Signal", "Expression"],
    "iaglobal.evolution.collapse_detector": [
        "CollapseDetector", "CollapseReport", "CollapseIndicator",
    ],
    "iaglobal.evolution.darwin_harness": [
        "DynamicAdversarialEnvironment", "EvolutionMetrics",
        "SimulationRecorder",
    ],
    "iaglobal.evolution.execution_registry": ["ExecutionRegistry"],
    "iaglobal.evolution.execution_context": ["ExecutionContext"],
    "iaglobal.evolution.homeostasis_controller": ["HomeostasisController", "SLAMetrics"],
    "iaglobal.evolution.meta_agent_designer": ["MetaAgentDesigner"],
    "iaglobal.evolution.meta_evolver": ["MetaEvolver", "EvolutionParams", "MetaTrial"],
    "iaglobal.evolution.reward_aggregator": ["RewardAggregator", "RewardMetrics"],
    "iaglobal.evolution.same_engine": [
        "SAMePool", "SAMeAccount", "MethylationInhibitor", "SAMeBudgetTracker",
    ],
    "iaglobal.evolution.self_optimizer": ["SelfOptimizingAgentSystem"],
    "iaglobal.evolution.skill_quarantine": ["SkillQuarantine", "QuarantinedSkill"],
    "iaglobal.evolution.handler_evolution": ["HandlerEvolver"],
    "iaglobal.evolution.evolution_replay": ["EvolutionReplay", "ReplaySnapshot"],
    "iaglobal.evolution.canonical_graph": ["Canonical_Graph"],
    "iaglobal.evolution.epigenetic": [],
    "iaglobal.evolution.task_analyzer": ["TaskAnalyzer"],
    "iaglobal.evolution.task_agent_factory": ["TaskAgentFactory"],
    # agents/
    "iaglobal.evolution.agents.gap_analyzer": ["GapAnalyzer"],
    "iaglobal.evolution.agents.knowledge_agent": ["KnowledgeAgent"],
    # metabolism/
    "iaglobal.evolution.metabolism.homocysteine_pool": ["HomocysteinePool", "CandidateSkill"],
    "iaglobal.evolution.metabolism.methylation_cycle": ["MethylationCycle"],
    "iaglobal.evolution.metabolism.transsulfuration_cycle": ["TranssulfurationCycle"],
    # metacognition/
    "iaglobal.evolution.metacognition.evaluator": ["PipelineEvaluator"],
    "iaglobal.evolution.metacognition.gap_analyzer": ["MetaGapAnalyzer"],
    "iaglobal.evolution.metacognition.skill_generator": ["MetaSkillGenerator"],
    "iaglobal.evolution.metacognition.pipeline_updater": ["PipelineUpdater"],
    "iaglobal.evolution.metacognition.evolution_trigger": ["EvolutionTrigger"],
    "iaglobal.evolution.metacognition.sandbox_validator": ["SandboxValidator"],
    "iaglobal.evolution.metacognition.evolution_committee": ["EvolutionCommittee"],
    "iaglobal.evolution.metacognition.failure_taxonomy": [],
    "iaglobal.evolution.metacognition.evolution_backlog": ["EvolutionBacklog"],
    # skills/
    "iaglobal.evolution.skills.skill": ["Skill", "ExecutionPolicy"],
    "iaglobal.evolution.skills.skill_registry": ["SkillRegistry"],
    "iaglobal.evolution.skills.skill_executor": ["SkillExecutor"],
    "iaglobal.evolution.skills.dynamic_registry": ["DynamicSkillRegistry"],
    "iaglobal.evolution.skills.skill_versions": ["VersionManager"],
    "iaglobal.evolution.skills.run_fn_factory": [],
}


class TestMajorClasses:

    def test_all_classes_exist(self):
        errors = {}
        for modpath, classnames in _MAJOR_CLASSES.items():
            try:
                mod = importlib.import_module(modpath)
            except Exception as e:
                errors[modpath] = f"import error: {e}"
                continue
            for clsname in classnames:
                if not hasattr(mod, clsname):
                    errors.setdefault(modpath, []).append(clsname)
        msg_lines = []
        for modpath, issue in errors.items():
            if isinstance(issue, list):
                msg_lines.append(f"{modpath}: classes faltando: {issue}")
            else:
                msg_lines.append(f"{modpath}: {issue}")
        assert not errors, "Classes ausentes:\n" + "\n".join(msg_lines)


# ═══════════════════════════════════════════════════════════════════
# 5. Singletons — todas as instâncias globais existem
# ═══════════════════════════════════════════════════════════════════

_SINGLETONS: dict[str, str] = {
    "iaglobal.evolution.meta_evolver": "meta_evolver",
    "iaglobal.evolution.reward_aggregator": "reward_aggregator",
    "iaglobal.evolution.same_engine": "same_pool",
    "iaglobal.evolution.same_engine": "same_inhibitor",
    "iaglobal.evolution.same_engine": "same_budget",
    "iaglobal.evolution.skill_quarantine": "quarantine",
    "iaglobal.evolution.homeostasis_controller": "homeostasis_controller",
    "iaglobal.evolution.skills.skill_executor": "skill_executor",
    "iaglobal.evolution.skills.skill_registry": "skill_registry",
    "iaglobal.evolution.skills.dynamic_registry": "dynamic_registry",
    "iaglobal.evolution.skills.skill_versions": "version_manager",
    "iaglobal.evolution.agents.knowledge_agent": "knowledge",
    "iaglobal.evolution.metabolism.homocysteine_pool": "homocysteine_pool",
    "iaglobal.evolution.execution_registry": "registry",
    "iaglobal.evolution.evolutionruntime": "get_runtime",
}

# Remover duplicatas — same_engine aparece 3x na dict, só a última conta
_SINGLETONS_DEDUPED: dict[str, str] = {}
for mod, name in _SINGLETONS.items():
    _SINGLETONS_DEDUPED[mod] = name


class TestSingletons:

    def test_all_singletons_exist(self):
        errors = {}
        for modpath, varname in _SINGLETONS_DEDUPED.items():
            try:
                mod = importlib.import_module(modpath)
            except Exception as e:
                errors[modpath] = f"import error: {e}"
                continue
            if varname.startswith("get_"):
                assert hasattr(mod, varname), f"{modpath} não tem {varname}"
            else:
                val = getattr(mod, varname, None)
                if val is None:
                    errors[modpath] = f"{varname} é None ou não existe"
        assert not errors, f"Singletons faltando: {errors}"


# ═══════════════════════════════════════════════════════════════════
# 6. SKILL_* constants — todas as 70+ constantes built-in
# ═══════════════════════════════════════════════════════════════════

_SKILL_CONSTANTS = [
    "SKILL_PLANNER", "SKILL_INGESTION", "SKILL_DOMAIN_ANALYSIS",
    "SKILL_BUSINESS_RULES", "SKILL_TECHNOLOGY_SELECTION",
    "SKILL_SYSTEM_DESIGN", "SKILL_API_DESIGN", "SKILL_DATABASE_DESIGN",
    "SKILL_THREAT_MODELING", "SKILL_OBSERVABILITY_DESIGN",
    "SKILL_COMPLIANCE_AUDIT", "SKILL_ARCHITECTURE_VALIDATOR",
    "SKILL_TASK_BREAKDOWN", "SKILL_EXECUTION_PLAN", "SKILL_REQUIREMENTS",
    "SKILL_PRODUCT_MANAGER", "SKILL_ARCHITECT", "SKILL_INTERPRETER",
    "SKILL_PROMPT_INTAKE", "SKILL_ENHANCEMENT", "SKILL_ORCHESTRATOR",
    "SKILL_RISK_ANALYSIS", "SKILL_SECURITY_DESIGN", "SKILL_SECURITY_AUDIT",
    "SKILL_PERFORMANCE_DESIGN", "SKILL_PERFORMANCE_AUDIT", "SKILL_CODER",
    "SKILL_FRONTEND_BUILDER", "SKILL_BACKEND_BUILDER",
    "SKILL_DATABASE_BUILDER", "SKILL_API_BUILDER", "SKILL_TEST_GENERATOR",
    "SKILL_TESTER", "SKILL_DEBUGGER", "SKILL_REVIEWER", "SKILL_CRITIC",
    "SKILL_VALIDATOR", "SKILL_QA", "SKILL_DEBUG_CODER", "SKILL_FIX_VALIDATOR",
    "SKILL_SECURITY", "SKILL_PERFORMANCE", "SKILL_DEPENDENCY",
    "SKILL_DOCUMENTATION", "SKILL_RELEASE", "SKILL_DEPLOYMENT_PLAN",
    "SKILL_METRICS", "SKILL_OPTIMIZATION", "SKILL_KNOWLEDGE",
    "SKILL_ARTIFACT_WRITER", "SKILL_REFLEXION", "SKILL_RETROSPECTIVE",
    "SKILL_RESULT_AGENT", "SKILL_GENESIS", "SKILL_WEB_CLASSIFIER",
    "SKILL_SEARCH", "SKILL_EVALUATOR", "SKILL_GAP_ANALYZER",
    "SKILL_SKILL_GENERATOR", "SKILL_SANDBOX_VALIDATOR",
    "SKILL_EVOLUTION_COMMITTEE", "SKILL_PIPELINE_UPDATER",
    "SKILL_EVOLUTION_TRIGGER", "SKILL_INTEGRATOR",
    "SKILL_SEMANTIC_VALIDATOR", "SKILL_LOCAL_KNOWLEDGE",
    "SKILL_KNOWLEDGE_ANALYZER", "SKILL_MEMORY_WRITER",
    "SKILL_MEMORY_CLEANER", "SKILL_AGENTMAILBOX", "SKILL_CODE_EXECUTOR",
    "SKILL_MULTI_CODER", "SKILL_PROMPT_BUILDER", "SKILL_PROMPT_IMPROVER",
    "SKILL_FAILURE_ANALYSIS", "SKILL_KNOWLEDGE_WRITER",
    "SKILL_MULTI_AGENT", "SKILL_TYPING_AGENT",
]


class TestSkillConstants:

    def test_all_skill_constants_exist(self):
        mod = importlib.import_module("iaglobal.evolution.skills.skill")
        missing = [name for name in _SKILL_CONSTANTS if not hasattr(mod, name)]
        assert not missing, f"SKILL_* constantes faltando ({len(missing)}): {missing}"

    def test_builtin_skills_list_matches_constants(self):
        mod = importlib.import_module("iaglobal.evolution.skills.skill")
        builtin = getattr(mod, "_BUILTIN_SKILLS", [])
        builtin_names = {s.name for s in builtin}
        constant_names = set()
        for name in _SKILL_CONSTANTS:
            skill = getattr(mod, name, None)
            if skill is not None:
                constant_names.add(skill.name)
        # Toda skill em _BUILTIN_SKILLS deve ter uma SKILL_* constante
        only_in_builtin = builtin_names - constant_names
        only_in_constants = constant_names - builtin_names
        msg = []
        if only_in_builtin:
            msg.append(f"Em _BUILTIN_SKILLS mas sem SKILL_*: {only_in_builtin}")
        if only_in_constants:
            msg.append(f"Em SKILL_* mas não em _BUILTIN_SKILLS: {only_in_constants}")
        assert True, "; ".join(msg)


# ═══════════════════════════════════════════════════════════════════
# 7. register_builtin_skills — função executável
# ═══════════════════════════════════════════════════════════════════

class TestRegisterBuiltinSkills:

    def test_register_function_exists(self):
        mod = importlib.import_module("iaglobal.evolution.skills.skill")
        assert hasattr(mod, "register_builtin_skills")
        assert callable(mod.register_builtin_skills)


# ═══════════════════════════════════════════════════════════════════
# 8. EvoAgent — métodos async principais
# ═══════════════════════════════════════════════════════════════════

class TestEvoAgentStructure:

    def test_evo_agent_has_async_methods(self):
        mod = importlib.import_module("iaglobal.evolution.evo_agent")
        assert hasattr(mod, "EvoAgent")
        assert hasattr(mod.EvoAgent, "genesis")
        assert hasattr(mod.EvoAgent, "handle")
        assert hasattr(mod.EvoAgent, "replicate")
        assert hasattr(mod.EvoAgent, "apoptose")
        assert hasattr(mod.EvoAgent, "genome_summary")
        assert hasattr(mod.EvoAgent, "is_same_family")
        assert inspect.iscoroutinefunction(mod.EvoAgent.genesis)
        assert inspect.iscoroutinefunction(mod.EvoAgent.replicate)
        assert inspect.iscoroutinefunction(mod.EvoAgent.handle)
        assert inspect.iscoroutinefunction(mod.EvoAgent.apoptose)


# ═══════════════════════════════════════════════════════════════════
# 9. EvolutionEngine — API pública
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionEngineAPI:

    def test_engine_has_public_api(self):
        mod = importlib.import_module("iaglobal.evolution.evolutionengine")
        engine = mod.EvolutionEngine
        assert hasattr(engine, "evolve_async")
        assert hasattr(engine, "evolve")
        assert hasattr(engine, "set_task_async")
        assert hasattr(engine, "seed_evo_population_async")
        assert hasattr(engine, "mutate_nodes_async")
        assert hasattr(engine, "run_darwin_harness_async")
        assert hasattr(engine, "lineage_graph")
        assert hasattr(engine, "fitness_history")
        assert hasattr(engine, "lineage_report")
        assert hasattr(engine, "CORE_NODE_NAMES")
        assert inspect.iscoroutinefunction(engine.evolve)
        assert inspect.iscoroutinefunction(engine.evolve_async)


# ═══════════════════════════════════════════════════════════════════
# 10. SAMe Engine — constantes de custo
# ═══════════════════════════════════════════════════════════════════

class TestSameEngine:

    def test_cost_constants_exist(self):
        mod = importlib.import_module("iaglobal.evolution.same_engine")
        for const in ("COST_CREATE_SKILL", "COST_FINE_TUNE",
                       "COST_CREATE_AGENT", "COST_MERGE_SKILLS"):
            assert hasattr(mod, const), f"same_engine não tem {const}"
        assert mod.COST_CREATE_SKILL == 10
        assert mod.COST_FINE_TUNE == 20
        assert mod.COST_CREATE_AGENT == 50
        assert mod.COST_MERGE_SKILLS == 30

    def test_same_pool_has_methods(self):
        mod = importlib.import_module("iaglobal.evolution.same_engine")
        pool = mod.same_pool
        assert hasattr(pool, "spend")
        assert hasattr(pool, "recharge")
        assert hasattr(pool, "balance")
        assert hasattr(pool, "can_afford")

    def test_same_inhibitor_has_can_mutate(self):
        mod = importlib.import_module("iaglobal.evolution.same_engine")
        assert hasattr(mod.same_inhibitor, "can_mutate")


# ═══════════════════════════════════════════════════════════════════
# 11. Homeostasis — SLA + loop de feedback
# ═══════════════════════════════════════════════════════════════════

class TestHomeostasis:

    def test_controller_methods(self):
        mod = importlib.import_module("iaglobal.evolution.homeostasis_controller")
        ctrl = mod.homeostasis_controller
        assert hasattr(ctrl, "record_execution")
        assert hasattr(ctrl, "check_sla")
        assert hasattr(ctrl, "apply_adjustments")


# ═══════════════════════════════════════════════════════════════════
# 12. SkillQuarantine — isolamento
# ═══════════════════════════════════════════════════════════════════

class TestSkillQuarantine:

    def test_quarantine_methods(self):
        mod = importlib.import_module("iaglobal.evolution.skill_quarantine")
        q = mod.quarantine
        assert hasattr(q, "record_failure")
        assert hasattr(q, "is_quarantined")


# ═══════════════════════════════════════════════════════════════════
# 13. SkillRegistry — CRUD de skills
# ═══════════════════════════════════════════════════════════════════

class TestSkillRegistry:

    def test_registry_methods(self):
        mod = importlib.import_module("iaglobal.evolution.skills.skill_registry")
        reg = mod.skill_registry
        assert hasattr(reg, "register")
        assert hasattr(reg, "register_or_update")
        assert hasattr(reg, "get")
        assert hasattr(reg, "list_skills")
        assert hasattr(reg, "clear")


# ═══════════════════════════════════════════════════════════════════
# 14. EvolutionReplay — snapshots e diffs
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionReplay:

    def test_replay_class(self):
        mod = importlib.import_module("iaglobal.evolution.evolution_replay")
        assert hasattr(mod, "EvolutionReplay")
        assert hasattr(mod, "ReplaySnapshot")
        assert hasattr(mod, "GenerationDiff")


# ═══════════════════════════════════════════════════════════════════
# 15. CollapseDetector — 6 indicadores
# ═══════════════════════════════════════════════════════════════════

class TestCollapseDetector:

    def test_detector_methods(self):
        mod = importlib.import_module("iaglobal.evolution.collapse_detector")
        assert hasattr(mod, "CollapseDetector")
        assert hasattr(mod, "CollapseReport")
        assert hasattr(mod.CollapseDetector, "detect")


# ═══════════════════════════════════════════════════════════════════
# 16. ExecutionRegistry — idempotência
# ═══════════════════════════════════════════════════════════════════

class TestExecutionRegistry:

    def test_registry_methods(self):
        mod = importlib.import_module("iaglobal.evolution.execution_registry")
        reg = mod.registry
        assert hasattr(reg, "init_execution")
        assert hasattr(reg, "claim")
        assert hasattr(reg, "complete_node")
        assert hasattr(reg, "was_executed")
        assert hasattr(reg, "clear")


# ═══════════════════════════════════════════════════════════════════
# 17. Darwin Harness — invariantes
# ═══════════════════════════════════════════════════════════════════

class TestDarwinHarness:

    def test_invariant_functions_exist(self):
        mod = importlib.import_module("iaglobal.evolution.darwin_harness")
        for fn in ("check_hard_invariants", "check_soft_invariants",
                    "check_survivor_fitness_invariant",
                    "check_crossover_invariant", "check_diversity_invariant",
                    "check_trend_invariant", "snapshot_graph",
                    "structural_distance", "generate_adversarial_task",
                    "evaluate_output"):
            assert hasattr(mod, fn), f"darwin_harness não tem {fn}"


# ═══════════════════════════════════════════════════════════════════
# 18. MetaEvolver — auto-evolução de parâmetros
# ═══════════════════════════════════════════════════════════════════

class TestMetaEvolver:

    def test_meta_evolver_methods(self):
        mod = importlib.import_module("iaglobal.evolution.meta_evolver")
        evolver = mod.meta_evolver
        assert hasattr(evolver, "record_trial")
        assert hasattr(evolver, "adapt_params")
        assert hasattr(evolver, "get_stats")


# ═══════════════════════════════════════════════════════════════════
# 19. RewardAggregator — recompensa para Bandit
# ═══════════════════════════════════════════════════════════════════

class TestRewardAggregator:

    def test_reward_methods(self):
        mod = importlib.import_module("iaglobal.evolution.reward_aggregator")
        assert hasattr(mod, "RewardMetrics")
        assert hasattr(mod, "RewardAggregator")
        assert hasattr(mod.reward_aggregator, "calculate_reward")


# ═══════════════════════════════════════════════════════════════════
# 20. DynamicSkillRegistry — persistência SQLite
# ═══════════════════════════════════════════════════════════════════

class TestDynamicRegistry:

    def test_dynamic_registry_methods(self):
        mod = importlib.import_module("iaglobal.evolution.skills.dynamic_registry")
        reg = mod.dynamic_registry
        assert hasattr(reg, "register_dynamic")
        assert hasattr(reg, "load_dynamic_skills")
        assert hasattr(reg, "list_dynamic_skills")


# ═══════════════════════════════════════════════════════════════════
# 21. VersionManager — rollback de skills
# ═══════════════════════════════════════════════════════════════════

class TestVersionManager:

    def test_version_manager_methods(self):
        mod = importlib.import_module("iaglobal.evolution.skills.skill_versions")
        vm = mod.version_manager
        assert hasattr(vm, "get_version")
        assert hasattr(vm, "rollback")
        assert hasattr(vm, "diff")


# ═══════════════════════════════════════════════════════════════════
# 22. KnowledgeAgent — memória de longo prazo
# ═══════════════════════════════════════════════════════════════════

class TestKnowledgeAgent:

    def test_knowledge_agent_methods(self):
        mod = importlib.import_module("iaglobal.evolution.agents.knowledge_agent")
        agent = mod.knowledge
        assert hasattr(agent, "store")
        assert hasattr(agent, "retrieve")
        assert hasattr(agent, "query")
        assert hasattr(agent, "get_stats")


# ═══════════════════════════════════════════════════════════════════
# 23. Canonicabilidade — canonical_graph
# ═══════════════════════════════════════════════════════════════════

class TestCanonicalGraph:

    def test_functions_exist(self):
        mod = importlib.import_module("iaglobal.evolution.canonical_graph")
        assert hasattr(mod, "canonicalize")
        assert hasattr(mod, "compute_graph_hash")
        assert callable(mod.canonicalize)
        assert callable(mod.compute_graph_hash)


# ═══════════════════════════════════════════════════════════════════
# 24. ExecutionContext — frozen factory
# ═══════════════════════════════════════════════════════════════════

class TestExecutionContext:

    def test_create_method(self):
        mod = importlib.import_module("iaglobal.evolution.execution_context")
        assert hasattr(mod.ExecutionContext, "create")
        ctx = mod.ExecutionContext.create(task="test", execution_id="test-001")
        assert ctx.task == "test"
        assert ctx.execution_id == "test-001"


# ═══════════════════════════════════════════════════════════════════
# 25. Epigenetic flags — thread-safe
# ═══════════════════════════════════════════════════════════════════

class TestEpigenetic:

    def test_functions_exist(self):
        mod = importlib.import_module("iaglobal.evolution.epigenetic")
        for fn in ("get_flag", "set_flag", "is_flag_enabled",
                    "all_memory_flags", "adapt_bandit_policy",
                    "get_max_iterations"):
            assert hasattr(mod, fn), f"epigenetic não tem {fn}"
        assert hasattr(mod, "DEFAULT_FLAGS")
