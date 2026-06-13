# iaglobal/graphs/nodes/no_integrator.py

from __future__ import annotations

import logging

from dataclasses import dataclass, field

from typing import Dict, Any, Callable, Optional

from iaglobal.evolution.skills.skill_registry import SkillRegistry

from iaglobal.graphs.execution_graph import ExecutionGraph

from iaglobal.graphs.node import Node

from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

_default_registry = SkillRegistry()
_FALLBACK_RUN_FN_CACHE: Dict[str, Callable] = {}

class No_Integrator:
    def __init__(
        self,
        name: str = "no_integrator",
        config: Optional[Dict[str, Any]] = None,
        save_fn: Optional[Any] = None,
        enabled: bool = True,
        artifacts_dir: str = "./artifacts" # Adicionado o parâmetro faltante
    ) -> None:
        self.name = name
        self.config = config or {}
        self.artifacts_dir = artifacts_dir # Agora definido corretamente
        self.enabled = enabled
        self.state: Dict[str, Any] = {}

    async def run_integrator(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        memory = ctx.get("memory", {})

        code_parts = []
        files = {}
        source_count = 0
        
        # Variável para rastrear o último objeto artefato processado
        last_artifact = None

        sources = [
            ("frontend_builder", "frontend"),
            ("backend_builder", "backend"),
            ("database_builder", "database"),
            ("api_builder", "api"),
        ]

        for source_key, source_label in sources:
            artifact = memory.get(source_key, {}).get("output")
            if artifact is None:
                continue

            last_artifact = artifact
            source_count += 1

            if isinstance(artifact, str) and artifact.strip():
                code_parts.append(f"# === {source_label.upper()} ===\n{artifact}")
                files[f"{source_label}.py"] = artifact
            elif hasattr(artifact, "code") and artifact.code:
                code_parts.append(f"# === {source_label.upper()} ===\n{artifact.code}")
                files[f"{source_label}.py"] = artifact.code
            elif isinstance(artifact, dict):
                for key in ("code", "output", "content"):
                    val = artifact.get(key)
                    if val and isinstance(val, str) and val.strip():
                        code_parts.append(f"# === {source_label.upper()} ===\n{val}")
                        files[f"{source_label}.py"] = val
                        break

        # Correção: Acesso seguro ao último artefato dentro do escopo
        if last_artifact and hasattr(last_artifact, "files") and last_artifact.files:
            files.update(last_artifact.files)

        integrated_code = "\n\n".join(code_parts) if code_parts else ""
        
        # Logs simplificados para evitar logs massivos em cada integração
        logger.info("[INTEGRATOR] Integrados %d fontes, total de %d caracteres", source_count, len(integrated_code))

        return {
            "output": {"code": integrated_code, "files": files, "source_count": source_count},
            "integrated_code": integrated_code,
            "files": files,
            "source_count": source_count,
        }

import pkgutil
import importlib
from iaglobal.utils.logger import logger

def register_all(orchestrator):
    """
    Auto-registra todos os nós da pasta iaglobal.graphs.nodes.
    Utiliza introspecção para descobrir nós e evita duplicidades.
    """
    logger.info("🧩 [INTEGRATOR] Iniciando registro dinâmico de nós...")
    
    import iaglobal.graphs.nodes as nodes_pkg
    
    # Rastreia nós já registrados no orchestrator para evitar duplicação
    # Supondo que seu orchestrator tenha uma lista ou método de verificação
    registered_nodes = getattr(orchestrator, "registered_nodes", set())
    
    for _, name, _ in pkgutil.iter_modules(nodes_pkg.__path__):
        if name.startswith("_"):
            continue
            
        if name in registered_nodes:
            logger.debug(f"⏭️ [INTEGRATOR] Nó {name} já está registrado, pulando.")
            continue
            
        try:
            module_path = f"iaglobal.graphs.nodes.{name}"
            module = importlib.import_module(module_path)
            
            # Tenta buscar a função de registro padrão ou uma genérica 'register'
            register_fn = getattr(module, f"register_{name}", getattr(module, "register", None))
            
            if register_fn and callable(register_fn):
                register_fn(orchestrator)
                
                # Adiciona ao set de controle se o orchestrator suportar
                if hasattr(orchestrator, "registered_nodes"):
                    orchestrator.registered_nodes.add(name)
                    
                logger.debug(f"✅ [INTEGRATOR] Registrado: {name}")
            else:
                logger.warning(f"⚠️ [INTEGRATOR] Módulo {name} sem função 'register_{name}' ou 'register'")
                
        except Exception as e:
            logger.error(f"❌ [INTEGRATOR] Falha crítica ao registrar {name}: {e}", exc_info=True)

    logger.info("🚀 [INTEGRATOR] Processo de registro de nós finalizado.")

def build_graph_from_skills(
    orchestrator: Any,
    registry: Optional[SkillRegistry] = None,
) -> ExecutionGraph:
    """
    Constrói dinamicamente o DAG de execução a partir das skills registradas.

    Recursos:
    - Auto-fallback para skills sem run_fn registrada.
    - Auto-atualização do registry quando fallback é encontrado.
    - Validação básica de dependências.
    - Logs detalhados de construção.
    - Suporte futuro para metadados extras.
    - Fail-safe contra erros de criação de nodes.
    """
    registry = registry or _default_registry
    graph = ExecutionGraph()

    created_nodes: set[str] = set()
    missing_skills: list[str] = []
    fallback_skills: list[str] = []

    logger.info(
        "[SKILL-GRAPH] Construindo DAG com %d skills...",
        len(PIPELINE_SKILLS),
    )

    from iaglobal.immunity.emergent_behavior_detector import EmergentBehaviorDetector
    _emergence = EmergentBehaviorDetector()

    for skill_name, opts in PIPELINE_SKILLS:
        try:
            skill = registry.get(skill_name)

            run_fn = (
                skill.run_fn
                if skill and skill.run_fn
                else _get_fallback_run_fn(skill_name, orchestrator)
            )

            if run_fn is None:
                missing_skills.append(skill_name)
                logger.warning(
                    "[SKILL-GRAPH] Skill '%s' não possui implementação.",
                    skill_name,
                )
                continue

            if skill and not skill.run_fn:
                _update_skill_run_fn(registry, skill_name, run_fn)
                fallback_skills.append(skill_name)

                logger.debug(
                    "[SKILL-GRAPH] Fallback registrado para '%s'.",
                    skill_name,
                )

            node_name = opts.get("name", skill_name)
            depends_on = list(opts.get("depends_on", []))
            strategy = opts.get("strategy", "general")
            critical = bool(opts.get("critical", False))

            dep_check = _emergence.check_dependencies(node_name, depends_on)
            if dep_check["has_issues"]:
                for issue in dep_check["issues"]:
                    logger.warning("[IMMUNITY] %s: %s", issue["type"], issue.get("chain", node_name))

            name_check = _emergence.check_skill_name(node_name)
            if name_check["suspicious"]:
                logger.warning("[IMMUNITY] Nome suspeito de skill: '%s'", node_name)

            if skill and skill.run_fn:
                node = skill.to_node(
                    name=node_name,
                    depends_on=depends_on,
                    strategy=strategy,
                    critical=critical,
                )
            else:
                node = Node(
                    name=node_name,
                    run=run_fn,
                    depends_on=depends_on,
                    strategy=strategy,
                    critical=critical,
                    node_type=skill_name,
                )

            graph.add_node(node)
            created_nodes.add(node_name)

            logger.debug(
                "[SKILL-GRAPH] Node '%s' (%s) adicionado.",
                node_name,
                skill_name,
            )

        except Exception as exc:
            logger.exception(
                "[SKILL-GRAPH] Falha ao criar node para skill '%s': %s",
                skill_name,
                exc,
            )

    # ------------------------------------------------------------------
    # Validação pós-construção
    # ------------------------------------------------------------------

    unresolved_deps: dict[str, list[str]] = {}

    for node in getattr(graph, "nodes", {}).values():
        missing = [
            dep
            for dep in getattr(node, "depends_on", [])
            if dep not in created_nodes
        ]

        if missing:
            unresolved_deps[node.name] = missing

    if unresolved_deps:
        for node_name, deps in unresolved_deps.items():
            logger.warning(
                "[SKILL-GRAPH] Dependências não resolvidas em '%s': %s",
                node_name,
                deps,
            )

    logger.info(
        (
            "[SKILL-GRAPH] DAG concluído | "
            "nodes=%d | "
            "fallbacks=%d | "
            "missing=%d | "
            "unresolved=%d"
        ),
        len(created_nodes),
        len(fallback_skills),
        len(missing_skills),
        len(unresolved_deps),
    )

    return graph

def build_default_graph(orchestrator: Any, task: str) -> ExecutionGraph:
    """
    Wrapper compatível que constrói o grafo a partir de skills.
    """
    logger.info(f"🏗️ [INTEGRATOR] Iniciando construção do grafo para: {task}")
    
    # Limpa o cache para garantir que não estamos carregando skills de uma "identidade" antiga
    global _FALLBACK_RUN_FN_CACHE
    _FALLBACK_RUN_FN_CACHE.clear()
    
    # Primeiro: Garante que as habilidades existem (o "ter" habilidades)
    _register_default_skill_implementations(orchestrator)
    
    # Segundo: Monta o grafo baseado nas habilidades registradas
    graph = build_graph_from_skills(orchestrator)
    
    logger.debug(f"🧩 [INTEGRATOR] Grafo montado com {len(graph.nodes)} nós.")
    return graph

def _get_fallback_run_fn(
    skill_name: str,
    orchestrator: Any,
) -> Optional[Callable]:
    """
    Resolve a implementação fallback de uma skill.

    Recursos:
    - cache de run_fn já construídas
    - aliases de nomes
    - busca case-insensitive
    - logging de diagnóstico
    - tratamento seguro de falhas
    """

    if not skill_name:
        return None

    normalized = skill_name.strip().lower()

    aliases = {
        "developer": "coder",
        "codegen": "coder",
        "docs": "documentation",
        "doc": "documentation",
        "release_manager": "release",
        "audit": "security_audit",
        "search_agent": "search",
    }

    normalized = aliases.get(normalized, normalized)

    if normalized in _FALLBACK_RUN_FN_CACHE:
        return _FALLBACK_RUN_FN_CACHE[normalized]


    fallbacks = {
        "prompt_intake": lambda o: _make_prompt_intake_run(),
        "enhancement": lambda o: _make_enhancement_run(),
        "orchestrator_agent": lambda o: _make_orchestrator_run(),
        "pm": lambda o: _make_pm_run(),
        "requirements": lambda o: _make_requirements_run(),
        "architect": lambda o: _make_architect_run(),
        # dominio e design
        "ingestion": lambda o: _make_ingestion_run(),
        "domain_analysis": lambda o: _make_domain_analysis_run(),
        "business_rules": lambda o: _make_business_rules_run(),
        "technology_selection": lambda o: _make_technology_selection_run(),
        "system_design": lambda o: _make_system_design_run(),
        "api_design": lambda o: _make_api_design_run(),
        "database_design": lambda o: _make_database_design_run(),
        "threat_modeling": lambda o: _make_threat_modeling_run(),
        "observability_design": lambda o: _make_observability_design_run(),
        "database_builder": lambda o: _make_database_builder_run(),
        "compliance_audit": lambda o: _make_compliance_audit_run(),
        # conhecimento e pesquisa
        "search": _make_search_run,
        "knowledge": lambda o: _make_knowledge_run(),
        "dependency": lambda o: _make_dependency_run(),
        # analise
        "risk_analysis": lambda o: _make_risk_analysis_run(),
        "security_design": lambda o: _make_security_design_run(),
        "performance_design": lambda o: _make_performance_design_run(),
        # desenvolvimento
        "planner": _make_planner_run,
        "task_breakdown": lambda o: _make_task_breakdown_run(),
        "execution_plan": lambda o: _make_execution_plan_run(),
        "test_generator": lambda o: _make_test_generator_run(),
        "coder": _make_multi_coder_run,
        "frontend_builder": lambda o: _make_html_form_run(o),
        "backend_builder": lambda o: _make_backend_builder_run(o),
        "api_builder": lambda o: _make_api_builder_run(o),
        # validacao
        "reviewer": lambda o: _make_reviewer_run(),
        "validator": lambda o: _make_validator_run(),
        "security_audit": lambda o: _make_security_audit_run(),
        "performance_audit": lambda o: _make_performance_audit_run(),
        # testes
        "tester": lambda o: _make_tester_run(o),
        "debugger": lambda o: _make_debugger_run(o),
        # entrega
        "documentation": lambda o: _make_documentation_run(),
        "release": lambda o: _make_release_run(),
        "metrics": lambda o: _make_metrics_run(),
        "optimization": lambda o: _make_optimization_run(),
        "result_agent": lambda o: _make_result_agent_run(),
        # qualidade e correcao
        "qa": lambda o: _make_qa_run(),
        "fix_validator": lambda o: _make_fix_validator_run(),
        "debug_coder": lambda o: _make_debug_coder_run(),
        "deployment_plan": lambda o: _make_deployment_plan_run(),
        "retrospective": lambda o: _make_retrospective_run(),
        # tier 1 — críticos
        "architecture_validator": lambda o: _make_architecture_validator_run(),
        "semantic_validator": lambda o: _make_semantic_validator_run(),
        "integrator": lambda o: _make_integrator_run(),
        # metacognition
        "evaluator": lambda o: _make_evaluator_run(),
        "gap_analyzer": lambda o: _make_gap_analyzer_run(),
        "skill_generator": lambda o: _make_skill_generator_run(),
        "sandbox_validator": lambda o: _make_sandbox_validator_run(),
        "evolution_committee": lambda o: _make_evolution_committee_run(),
        "pipeline_updater": lambda o: _make_pipeline_updater_run(),
        "evolution_trigger": lambda o: _make_evolution_trigger_run(),
    }

    maker = fallbacks.get(normalized)
    if maker is None:
        logger.warning("[FALLBACK] Nenhum fallback encontrado para: %s", normalized)
        return None

    try:
        run_fn = maker(orchestrator)

        if callable(run_fn):
            _FALLBACK_RUN_FN_CACHE[normalized] = run_fn

        logger.debug(
            "Fallback carregado para skill '%s'",
            normalized,
        )

        return run_fn

    except Exception:
        logger.exception(
            "Falha ao construir fallback da skill '%s'",
            normalized,
        )
        return None

from copy import deepcopy
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def _update_skill_run_fn(
    registry: SkillRegistry,
    skill_name: str,
    run_fn: Callable,
) -> bool:
    """
    Atualiza apenas o run_fn de uma skill existente.

    Retorna:
        True  -> skill atualizada
        False -> skill não encontrada
    """
    existing = registry.get(skill_name)

    if existing is None:
        logger.warning(
            "Tentativa de atualizar skill inexistente: %s",
            skill_name,
        )
        return False

    try:
        # Preserva todos os atributos atuais da skill,
        # inclusive os que possam ser adicionados no futuro.
        updated = deepcopy(existing)
        object.__setattr__(updated, "run_fn", run_fn)

        # Incrementa versão automaticamente quando possível.
        if hasattr(updated, "version"):
            try:
                if isinstance(updated.version, (int, float)):
                    updated.version += 1
            except Exception:
                pass

        registry.register_or_update(updated)

        logger.debug(
            "run_fn atualizado para skill '%s' (versão=%s)",
            skill_name,
            getattr(updated, "version", "n/a"),
        )

        return True

    except Exception:
        logger.exception(
            "Falha ao atualizar run_fn da skill '%s'",
            skill_name,
        )
        raise

def _register_default_skill_implementations(orchestrator: Any) -> None:
    """
    Registra as implementações padrão (run_fn) para todas as skills
    conhecidas no SkillRegistry global.

    Melhorias:
    - Tratamento isolado de erros por skill.
    - Métricas de registro.
    - Validação de templates.
    - Logs consolidados.
    - Estrutura preparada para auto-discovery.
    """
    from iaglobal.evolution.skills.skill_registry import skill_registry as reg
    from iaglobal.evolution.skills.skill import (
        Skill, SKILL_PLANNER, SKILL_TASK_BREAKDOWN, SKILL_EXECUTION_PLAN,
        SKILL_TEST_GENERATOR, SKILL_CODER, SKILL_TESTER, SKILL_DEBUGGER,
        SKILL_ARCHITECT, SKILL_INGESTION, SKILL_DOMAIN_ANALYSIS, SKILL_BUSINESS_RULES,
        SKILL_TECHNOLOGY_SELECTION,         SKILL_SYSTEM_DESIGN, SKILL_API_DESIGN,
        SKILL_DATABASE_DESIGN, SKILL_THREAT_MODELING,
        SKILL_OBSERVABILITY_DESIGN, SKILL_DATABASE_BUILDER,
        SKILL_COMPLIANCE_AUDIT,
        SKILL_SEARCH, SKILL_VALIDATOR, SKILL_REVIEWER,
        SKILL_DOCUMENTATION, SKILL_DEPENDENCY, SKILL_REQUIREMENTS,
        SKILL_ARCHITECTURE_VALIDATOR, SKILL_PRODUCT_MANAGER, SKILL_PROMPT_INTAKE,
        SKILL_RISK_ANALYSIS, SKILL_RELEASE, SKILL_METRICS, SKILL_OPTIMIZATION,
        SKILL_KNOWLEDGE, SKILL_ENHANCEMENT, SKILL_ORCHESTRATOR,
        SKILL_SECURITY_DESIGN, SKILL_PERFORMANCE_DESIGN, SKILL_SECURITY_AUDIT,
        SKILL_PERFORMANCE_AUDIT, SKILL_RESULT_AGENT, SKILL_FRONTEND_BUILDER,
        SKILL_BACKEND_BUILDER, SKILL_API_BUILDER,
        SKILL_EVALUATOR, SKILL_GAP_ANALYZER, SKILL_SKILL_GENERATOR,
        SKILL_PIPELINE_UPDATER, SKILL_EVOLUTION_TRIGGER,
        SKILL_SANDBOX_VALIDATOR, SKILL_EVOLUTION_COMMITTEE,
        SKILL_INTEGRATOR, SKILL_SEMANTIC_VALIDATOR,
        SKILL_QA, SKILL_DEBUG_CODER, SKILL_FIX_VALIDATOR,
        SKILL_DEPLOYMENT_PLAN, SKILL_RETROSPECTIVE,
    )

    skill_templates = {
        "prompt_intake":      SKILL_PROMPT_INTAKE,
        "enhancement":        SKILL_ENHANCEMENT,
        "orchestrator_agent": SKILL_ORCHESTRATOR,
        "pm":                 SKILL_PRODUCT_MANAGER,
        "requirements":       SKILL_REQUIREMENTS,
        "ingestion":          SKILL_INGESTION,
        "architect":          SKILL_ARCHITECT,
        "domain_analysis":    SKILL_DOMAIN_ANALYSIS,
        "business_rules":     SKILL_BUSINESS_RULES,
        "technology_selection": SKILL_TECHNOLOGY_SELECTION,
        "system_design":      SKILL_SYSTEM_DESIGN,
        "api_design":         SKILL_API_DESIGN,
        "database_design":    SKILL_DATABASE_DESIGN,
        "threat_modeling":    SKILL_THREAT_MODELING,
        "observability_design": SKILL_OBSERVABILITY_DESIGN,
        "database_builder":   SKILL_DATABASE_BUILDER,
        "compliance_audit":   SKILL_COMPLIANCE_AUDIT,
        "search":             SKILL_SEARCH,
        "knowledge":          SKILL_KNOWLEDGE,
        "dependency":         SKILL_DEPENDENCY,
        "risk_analysis":      SKILL_RISK_ANALYSIS,
        "security_design":    SKILL_SECURITY_DESIGN,
        "performance_design": SKILL_PERFORMANCE_DESIGN,
        "planner":            SKILL_PLANNER,
        "task_breakdown":     SKILL_TASK_BREAKDOWN,
        "execution_plan":     SKILL_EXECUTION_PLAN,
        "test_generator":     SKILL_TEST_GENERATOR,
        "coder":              SKILL_CODER,
        "frontend_builder":   SKILL_FRONTEND_BUILDER,
        "backend_builder":    SKILL_BACKEND_BUILDER,
        "api_builder":        SKILL_API_BUILDER,
        "reviewer":           SKILL_REVIEWER,
        "validator":          SKILL_VALIDATOR,
        "security_audit":     SKILL_SECURITY_AUDIT,
        "performance_audit":  SKILL_PERFORMANCE_AUDIT,
        "tester":             SKILL_TESTER,
        "debugger":           SKILL_DEBUGGER,
        "documentation":      SKILL_DOCUMENTATION,
        "release":            SKILL_RELEASE,
        "metrics":            SKILL_METRICS,
        "optimization":       SKILL_OPTIMIZATION,
        "result_agent":       SKILL_RESULT_AGENT,
        "qa":                 SKILL_QA,
        "fix_validator":      SKILL_FIX_VALIDATOR,
        "debug_coder":        SKILL_DEBUG_CODER,
        "deployment_plan":    SKILL_DEPLOYMENT_PLAN,
        "retrospective":      SKILL_RETROSPECTIVE,
        "architecture_validator": SKILL_ARCHITECTURE_VALIDATOR,
        "semantic_validator": SKILL_SEMANTIC_VALIDATOR,
        "integrator":         SKILL_INTEGRATOR,
        "evaluator":          SKILL_EVALUATOR,
        "gap_analyzer":       SKILL_GAP_ANALYZER,
        "skill_generator":    SKILL_SKILL_GENERATOR,
        "sandbox_validator":   SKILL_SANDBOX_VALIDATOR,
        "evolution_committee": SKILL_EVOLUTION_COMMITTEE,
        "pipeline_updater":   SKILL_PIPELINE_UPDATER,
        "evolution_trigger":  SKILL_EVOLUTION_TRIGGER,
    }
    skipped = []
    failed = []
    registered = []

    logger.info("[SKILL-GRAPH] Registrando %d skills padrão...", len(skill_templates))
    for skill_name, template in skill_templates.items():
        try:
            if template is None:
                logger.warning(
                    "[SKILL-GRAPH] Template ausente para '%s'",
                    skill_name,
                )
                skipped.append(skill_name)
                continue

            run_fn = _get_fallback_run_fn(skill_name, orchestrator)

            if not callable(run_fn):
                logger.warning(
                    "[SKILL-GRAPH] Skill '%s' sem run_fn válida",
                    skill_name,
                )
                skipped.append(skill_name)
                continue

            updated_skill = Skill(
                name=template.name,
                description=template.description,
                inputs=list(getattr(template, "inputs", [])),
                outputs=list(getattr(template, "outputs", [])),
                constraints=list(getattr(template, "constraints", [])),
                execution_policy=getattr(
                    template,
                    "execution_policy",
                    None,
                ),
                run_fn=run_fn,
                version=getattr(template, "version", "1.0.0"),
                tags=list(getattr(template, "tags", [])),
            )

            reg.register_or_update(updated_skill)

            registered.append(skill_name)

            logger.debug(
                "[SKILL-GRAPH] Skill registrada: %s (v%s)",
                updated_skill.name,
                updated_skill.version,
            )

        except Exception:
            logger.exception(
                "[SKILL-GRAPH] Falha ao registrar skill '%s'",
                skill_name,
            )
            failed.append(skill_name)

    logger.info(
        "[SKILL-GRAPH] Registro concluído | total=%d | registradas=%d | ignoradas=%d | falhas=%d",
        len(skill_templates),
        len(registered),
        len(skipped),
        len(failed),
    )

    if skipped:
        logger.warning(
            "[SKILL-GRAPH] Skills ignoradas: %s",
            ", ".join(sorted(skipped)),
        )

    if failed:
        logger.error(
            "[SKILL-GRAPH] Skills com falha: %s",
            ", ".join(sorted(failed)),
        )

import re
import unicodedata


_SMALL_MODELS = {
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "phi:2b",
    "phi2:2.7b",
    "tinyllama:1.1b",
    "gemma:2b",
    "stablelm2:1.6b",
}


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _detect_ambiguity(task: str) -> float:
    """
    Retorna score entre 0 e 1.

    0.0 = pedido muito claro
    1.0 = pedido extremamente ambíguo

    Utilizado para decidir:
    - necessidade de expandir contexto
    - geração de perguntas de esclarecimento
    - adaptação para modelos pequenos
    """
    tl = _normalize_text(task)

    words = re.findall(r"\w+", tl)
    score = 0.0

    # ------------------------------------------------------------------
    # Tamanho da instrução
    # ------------------------------------------------------------------

    if len(words) <= 2:
        score += 0.60
    elif len(words) <= 5:
        score += 0.35
    elif len(words) <= 10:
        score += 0.15

    # ------------------------------------------------------------------
    # Linguagem vaga
    # ------------------------------------------------------------------

    vague_terms = {
        "qualquer",
        "algum",
        "algo",
        "coisa",
        "melhor",
        "ideal",
        "adequado",
        "legal",
        "bom",
        "simples",
        "rapido",
        "facil",
        "etc",
    }

    score += min(
        sum(term in tl for term in vague_terms) * 0.08,
        0.25,
    )

    # ------------------------------------------------------------------
    # Alternativas múltiplas
    # ------------------------------------------------------------------

    if " ou " in f" {tl} ":
        score += 0.15

    if "/" in task:
        score += 0.05

    # ------------------------------------------------------------------
    # Pergunta aberta
    # ------------------------------------------------------------------

    if "?" in task:
        score += 0.10

    # ------------------------------------------------------------------
    # Comandos genéricos sem contexto
    # ------------------------------------------------------------------

    generic_actions = {
        "crie",
        "criar",
        "faca",
        "fazer",
        "implemente",
        "gere",
        "construa",
        "desenvolva",
    }

    if any(action in tl for action in generic_actions):
        score += 0.10

    # ------------------------------------------------------------------
    # Contexto técnico reduz ambiguidade
    # ------------------------------------------------------------------

    tech_terms = {
        "python",
        "javascript",
        "typescript",
        "java",
        "golang",
        "rust",
        "c#",
        "c++",
        "html",
        "css",
        "react",
        "vue",
        "angular",
        "flask",
        "django",
        "fastapi",
        "node",
        "express",
        "postgres",
        "mysql",
        "sqlite",
        "mongodb",
        "redis",
        "docker",
        "kubernetes",
        "api",
        "rest",
        "graphql",
        "sql",
        "web",
        "backend",
        "frontend",
        "microservice",
        "blockchain",
        "smart contract",
    }

    tech_count = sum(term in tl for term in tech_terms)

    if tech_count >= 3:
        score -= 0.25
    elif tech_count >= 1:
        score -= 0.10

    # ------------------------------------------------------------------
    # Especificações concretas reduzem ambiguidade
    # ------------------------------------------------------------------

    specificity_patterns = [
        r"\d+",
        r"v\d+",
        r"python\s*\d",
        r"node\s*\d",
        r"api",
        r"endpoint",
        r"classe",
        r"class",
        r"funcao",
        r"function",
        r"metodo",
        r"database",
        r"schema",
        r"json",
        r"yaml",
        r"dockerfile",
    ]

    specificity_hits = sum(
        bool(re.search(pattern, tl))
        for pattern in specificity_patterns
    )

    score -= min(specificity_hits * 0.05, 0.25)

    # ------------------------------------------------------------------
    # Pedidos muito curtos e genéricos
    # ------------------------------------------------------------------

    if len(words) <= 4 and tech_count == 0:
        score += 0.20

    # ------------------------------------------------------------------
    # Normalização final
    # ------------------------------------------------------------------

    return max(0.0, min(round(score, 3), 1.0))

def _is_small_model(model_str: str) -> bool:
    """
    Detecta modelos menores ou mais limitados em contexto/raciocínio.
    Suporta nomes completos, aliases e variações de provedores.
    """
    if not model_str:
        return False

    model_name = model_str.split("/")[-1].strip().lower()

    normalized = (
        model_name.replace("_", "-")
        .replace(".", "-")
        .replace(" ", "-")
    )

    candidates = {
        normalized,
        model_name,
    }

    for small in _SMALL_MODELS:
        small_norm = small.lower().replace("_", "-").replace(".", "-")

        if (
            small_norm in normalized
            or normalized in small_norm
            or any(small_norm == c for c in candidates)
        ):
            return True

    small_patterns = (
        "mini",
        "small",
        "tiny",
        "lite",
        "flash",
        "nano",
        "1b",
        "2b",
        "3b",
        "7b",
        "8b",
    )

    return any(p in normalized for p in small_patterns)


_FEW_SHOTS = {
    "web": (
        "\n\n"
        "---\n"
        "EXEMPLO DE RESPOSTA ESPERADA (projeto web completo):\n\n"
        "Estrutura:\n"
        "project/\n"
        "├── app.py\n"
        "├── templates/\n"
        "│   └── index.html\n"
        "├── static/\n"
        "│   └── style.css\n"
        "└── requirements.txt\n\n"

        "# FILE: app.py\n"
        "from flask import Flask, render_template, request\n\n"
        "app = Flask(__name__)\n\n"
        "@app.route('/')\n"
        "def index():\n"
        "    return render_template('index.html')\n\n"
        "@app.route('/submit', methods=['POST'])\n"
        "def submit():\n"
        "    nome = request.form.get('nome', '').strip()\n"
        "    return {'success': True, 'nome': nome}\n\n"
        "if __name__ == '__main__':\n"
        "    app.run(debug=True)\n\n"

        "# FILE: templates/index.html\n"
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "    <link rel='stylesheet' href='/static/style.css'>\n"
        "</head>\n"
        "<body>\n"
        "    <form method='post' action='/submit'>\n"
        "        <input name='nome' placeholder='Seu nome'>\n"
        "        <button type='submit'>Enviar</button>\n"
        "    </form>\n"
        "</body>\n"
        "</html>\n\n"

        "# FILE: requirements.txt\n"
        "flask>=3.0.0\n"
    ),

    "coding": (
        "\n\n"
        "---\n"
        "EXEMPLO DE RESPOSTA ESPERADA (implementação Python):\n\n"

        "from typing import Dict\n\n"

        "def processar_usuario(nome: str, idade: int) -> Dict:\n"
        '    """\n'
        "    Processa dados de um usuário.\n\n"
        "    Args:\n"
        "        nome: Nome do usuário.\n"
        "        idade: Idade do usuário.\n\n"
        "    Returns:\n"
        "        Dicionário contendo dados processados.\n"
        '    """\n'
        "    return {\n"
        "        'nome': nome.strip(),\n"
        "        'idade': idade,\n"
        "        'maior_idade': idade >= 18,\n"
        "    }\n\n"

        "# Exemplo de uso\n"
        "resultado = processar_usuario('Maria', 25)\n"
        "print(resultado)\n"
    ),

    "research": (
        "\n\n"
        "---\n"
        "EXEMPLO DE RESPOSTA ESPERADA (pesquisa estruturada):\n\n"

        "## Resumo Executivo\n"
        "Breve visão geral do tema.\n\n"

        "## Definição\n"
        "Explicação objetiva do conceito.\n\n"

        "## Principais Pontos\n"
        "1. Primeiro aspecto relevante\n"
        "2. Segundo aspecto relevante\n"
        "3. Terceiro aspecto relevante\n\n"

        "## Benefícios\n"
        "- Benefício A\n"
        "- Benefício B\n\n"

        "## Limitações\n"
        "- Limitação A\n"
        "- Limitação B\n\n"

        "## Conclusão\n"
        "Síntese final do assunto.\n\n"

        "## Referências\n"
        "- Fonte 1\n"
        "- Fonte 2\n"
    ),
}

import re
import unicodedata
from collections import defaultdict


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _classify_task_type(task: str) -> str:
    tl = _normalize(task)

    categories = {
        "web": {
            "pagina": 2,
            "html": 3,
            "css": 3,
            "javascript": 3,
            "typescript": 3,
            "frontend": 3,
            "backend": 3,
            "web": 2,
            "site": 2,
            "django": 4,
            "flask": 4,
            "fastapi": 4,
            "react": 4,
            "vue": 4,
            "angular": 4,
            "api": 2,
            "rest": 2,
            "endpoint": 2,
            "formulario": 2,
            "landing page": 3,
            "dashboard": 3,
        },
        "coding": {
            "funcao": 4,
            "function": 4,
            "classe": 4,
            "class": 4,
            "algoritmo": 4,
            "script": 3,
            "codigo": 3,
            "implemente": 4,
            "implementar": 4,
            "crie": 3,
            "criar": 3,
            "desenvolva": 3,
            "python": 3,
            "java": 3,
            "golang": 3,
            "rust": 3,
            "c++": 3,
            "sql": 3,
            "refatore": 4,
            "otimize": 3,
            "debug": 4,
            "corrija": 3,
        },
        "research": {
            "o que e": 4,
            "como funciona": 4,
            "explique": 4,
            "diferenca": 4,
            "compare": 4,
            "comparacao": 4,
            "pesquise": 5,
            "busque": 5,
            "qual a": 3,
            "qual o": 3,
            "quem e": 4,
            "porque": 3,
            "por que": 3,
            "significa": 3,
            "conceito": 3,
            "historia": 3,
            "vantagens": 3,
            "desvantagens": 3,
            "exemplo de": 2,
        },
    }

    scores = defaultdict(int)

    for category, keywords in categories.items():
        for keyword, weight in keywords.items():
            if keyword in tl:
                scores[category] += weight

    # Heurísticas adicionais

    if re.search(r"\b(def|class|import|async|await)\b", tl):
        scores["coding"] += 6

    if re.search(r"\b(html|css|js|jsx|tsx)\b", tl):
        scores["web"] += 5

    if "?" in task:
        scores["research"] += 1

    if re.search(r"\b(crie|implemente|desenvolva|gere)\b", tl):
        scores["coding"] += 2

    if not scores:
        return "general"

    best_category = max(scores.items(), key=lambda x: x[1])

    # evita classificações fracas
    if best_category[1] < 3:
        return "general"

    return best_category[0]

def _build_context_expansion(task: str, task_type: str, is_small: bool) -> str:
    """
    Gera instruções adicionais para melhorar a qualidade da resposta,
    principalmente em modelos menores.
    """
    if not is_small:
        return ""

    task_lower = task.lower()

    base_instructions = [
        "Seja direto, técnico e objetivo.",
        "Estruture a resposta em etapas numeradas.",
        "Explique o raciocínio antes da solução final quando necessário.",
        "Evite respostas vagas ou genéricas.",
        "Forneça exemplos práticos e aplicáveis.",
        "Considere casos de erro, limitações e boas práticas.",
        "Presuma que a solução será utilizada em ambiente real."
    ]

    type_instructions = {
        "code": [
            "Produza código completo e executável.",
            "Inclua imports necessários.",
            "Evite pseudocódigo.",
            "Explique decisões arquiteturais importantes.",
            "Considere performance, legibilidade e manutenção."
        ],
        "web": [
            "Considere experiência do usuário (UX).",
            "Sugira estrutura de páginas e componentes.",
            "Inclua responsividade quando aplicável.",
            "Considere integração com APIs e backend."
        ],
        "analysis": [
            "Identifique causas, impactos e possíveis soluções.",
            "Destaque riscos e pontos de atenção.",
            "Apresente conclusões objetivas."
        ],
        "architecture": [
            "Descreva componentes, responsabilidades e fluxo.",
            "Explique escalabilidade e desacoplamento.",
            "Considere segurança e observabilidade."
        ],
        "data": [
            "Explique estrutura dos dados.",
            "Considere validações e tratamento de inconsistências.",
            "Apresente exemplos de entrada e saída."
        ]
    }

    dynamic_hints = []

    if any(k in task_lower for k in ("api", "rest", "endpoint")):
        dynamic_hints.append(
            "Documente endpoints, payloads, respostas e códigos HTTP."
        )

    if any(k in task_lower for k in ("async", "assíncr", "assincr")):
        dynamic_hints.append(
            "Considere concorrência, await, tratamento de timeout e retries."
        )

    if any(k in task_lower for k in ("docker", "container")):
        dynamic_hints.append(
            "Inclua configuração de containerização e deploy quando relevante."
        )

    if any(k in task_lower for k in ("teste", "test", "pytest")):
        dynamic_hints.append(
            "Inclua exemplos de testes automatizados."
        )

    instructions = list(base_instructions)
    instructions.extend(type_instructions.get(task_type, []))
    instructions.extend(dynamic_hints)

    extra = (
        "\n\n---\n"
        "INSTRUÇÕES ADICIONAIS (modelo pequeno — siga rigorosamente):\n"
        + "\n".join(f"- {item}" for item in instructions)
    )

    few_shot = _FEW_SHOTS.get(task_type)
    if few_shot:
        extra += f"\n\nEXEMPLO DE REFERÊNCIA:\n{few_shot}"

    return extra

def _make_prompt_intake_run() -> Callable:
    """Prompt Intake — delega ao BuilDer."""
    async def run(ctx):
        inst = BuilDer.get_instance()
        return await inst.run_prompt_intake(ctx)
    return run


def _make_interpreter_run() -> Callable:
    """Interpreter — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_interpreter(ctx)
    return run


def _make_requirements_run() -> Callable:
    """Requirements — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_requirements(ctx)
    return run


def _make_pm_run() -> Callable:
    """PM — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_pm(ctx)
    return run


def _make_architect_run() -> Callable:
    """Architect — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_architect(ctx)
    return run


def _make_risk_analysis_run() -> Callable:
    """Risk Analysis — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_risk_analysis(ctx)
    return run


def _make_planner_run(orchestrator: Any) -> Callable:
    """Planner — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_planner(ctx)
    return run


def _make_web_classifier_run() -> Callable:
    """Web Classifier — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_web_classifier(ctx)
    return run


def _classify_web_need(task: str) -> bool:
    """
    Retorna True quando há forte indicação de que a tarefa
    precisa de informações externas ou atualizadas.
    """

    if not task:
        return False

    text = _normalize(task)

    score = 0

    # ------------------------------------------------------------------
    # Forte evidência de WEB
    # ------------------------------------------------------------------
    web_keywords = {
        "api",
        "documentacao",
        "documentacao oficial",
        "release notes",
        "breaking change",
        "versao",
        "versoes",
        "atualizacao",
        "lancamento",
        "noticia",
        "novidade",
        "preco",
        "cotacao",
        "cotacoes",
        "mercado",
        "taxa",
        "ranking",
        "comparacao",
        "review",
        "benchmark",
        "github",
        "gitlab",
        "stackoverflow",
        "npm",
        "pypi",
        "docker hub",
        "huggingface",
        "modelo",
        "llm",
        "openai",
        "anthropic",
        "google ai",
        "maio 2026",
        "junho 2026",
        "2026",
        "hoje",
        "atualmente",
        "recentemente",
        "ultima versao",
        "latest",
        "current",
    }

    # ------------------------------------------------------------------
    # Forte evidência de NÃO WEB
    # ------------------------------------------------------------------
    local_keywords = {
        "crie",
        "criar",
        "implemente",
        "implementar",
        "escreva",
        "gere",
        "gerar",
        "algoritmo",
        "funcao",
        "classe",
        "codigo",
        "script",
        "refatore",
        "otimize",
        "serialize",
        "serializar",
        "sha256",
        "sha3",
        "blockchain",
        "genesis block",
        "estrutura de dados",
        "design pattern",
        "regex",
    }

    # ------------------------------------------------------------------
    # Score por palavras-chave
    # ------------------------------------------------------------------
    for kw in web_keywords:
        if kw in text:
            score += 3

    for kw in local_keywords:
        if kw in text:
            score -= 2

    # ------------------------------------------------------------------
    # Datas específicas normalmente exigem busca
    # ------------------------------------------------------------------
    if re.search(r"\b(20\d{2})\b", text):
        score += 2

    # ------------------------------------------------------------------
    # URLs/domínios
    # ------------------------------------------------------------------
    if re.search(r"https?://|www\.|\.com\b|\.io\b|\.ai\b", text):
        score += 4

    # ------------------------------------------------------------------
    # Linguagem temporal
    # ------------------------------------------------------------------
    temporal_terms = (
        "hoje",
        "agora",
        "atual",
        "recente",
        "ultimas",
        "ultimos",
        "latest",
        "current",
        "newest",
    )

    if any(term in text for term in temporal_terms):
        score += 4

    # ------------------------------------------------------------------
    # Perguntas factuais
    # ------------------------------------------------------------------
    factual_patterns = (
        "qual",
        "quais",
        "quem",
        "quando",
        "onde",
        "quanto custa",
        "quanto vale",
        "existe",
    )

    if any(p in text for p in factual_patterns):
        score += 2

    # ------------------------------------------------------------------
    # Perguntas de implementação normalmente NÃO precisam web
    # ------------------------------------------------------------------
    implementation_patterns = (
        "como implementar",
        "como criar",
        "como desenvolver",
        "como escrever",
        "como codificar",
    )

    if any(p in text for p in implementation_patterns):
        score -= 3

    # ------------------------------------------------------------------
    # Arquivos frontend costumam precisar referência/documentação
    # ------------------------------------------------------------------
    if any(
        ext in text
        for ext in (
            ".html",
            ".css",
            ".js",
            ".tsx",
            ".jsx",
            "react",
            "vue",
            "angular",
            "tailwind",
        )
    ):
        score += 2

    # ------------------------------------------------------------------
    # Textos longos frequentemente indicam análise local
    # ------------------------------------------------------------------
    if len(task) > 1000:
        score -= 1

    return score >= 3

def _make_search_run(orchestrator: Any) -> Callable:
    """Search — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_search(ctx)
    return run


def _make_multi_coder_run(orchestrator: Any) -> Callable:
    """Multi Coder — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_multi_coder(ctx)
    return run


def _make_metrics_run() -> Callable:
    """Metrics — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_metrics(ctx)
    return run


def _make_optimization_run() -> Callable:
    """Optimization — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_optimization(ctx)
    return run


def _make_reflexion_run(orchestrator: Any) -> Callable:
    """Reflexion — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_reflexion(ctx)
    return run


def _make_knowledge_run() -> Callable:
    """Knowledge — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_knowledge(ctx)
    return run


def _make_enhancement_run() -> Callable:
    """Enhancement — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_enhancement(ctx)
    return run


def _make_orchestrator_run() -> Callable:
    """Orchestrator — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_orchestrator_agent(ctx)
    return run


def _make_security_design_run() -> Callable:
    """Security Design — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_security_design(ctx)
    return run


def _make_performance_design_run() -> Callable:
    """Performance Design — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_performance_design(ctx)
    return run


def _make_security_audit_run() -> Callable:
    """Security Audit — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_security_audit(ctx)
    return run


def _make_performance_audit_run() -> Callable:
    """Performance Audit — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_performance_audit(ctx)
    return run


def _make_result_agent_run() -> Callable:
    """Result Agent — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_result_agent(ctx)
    return run


def _make_evaluator_run() -> Callable:
    from iaglobal.evolution.metacognition.evaluator import _run_evaluator
    return lambda ctx: _run_evaluator(ctx)


def _make_gap_analyzer_run() -> Callable:
    from iaglobal.evolution.metacognition.gap_analyzer import _run_gap_analyzer
    return lambda ctx: _run_gap_analyzer(ctx)


def _make_skill_generator_run() -> Callable:
    from iaglobal.evolution.metacognition.skill_generator import _run_skill_generator
    return lambda ctx: _run_skill_generator(ctx)


def _make_sandbox_validator_run() -> Callable:
    from iaglobal.evolution.metacognition.sandbox_validator import _run_sandbox_validator
    return lambda ctx: _run_sandbox_validator(ctx)


def _make_evolution_committee_run() -> Callable:
    from iaglobal.evolution.metacognition.evolution_committee import _run_evolution_committee
    return lambda ctx: _run_evolution_committee(ctx)


def _make_pipeline_updater_run() -> Callable:
    from iaglobal.evolution.metacognition.pipeline_updater import _run_pipeline_updater
    return lambda ctx: _run_pipeline_updater(ctx)


def _make_evolution_trigger_run() -> Callable:
    from iaglobal.evolution.metacognition.evolution_trigger import _run_evolution_trigger
    return lambda ctx: _run_evolution_trigger(ctx)


def _make_architecture_validator_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_architecture_validator(ctx)
    return run


def _make_semantic_validator_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_semantic_validator(ctx)
    return run


def _make_integrator_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_integrator(ctx)
    return run


def _make_task_breakdown_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_task_breakdown(ctx)
    return run


def _make_execution_plan_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_execution_plan(ctx)
    return run


def _make_test_generator_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_test_generator(ctx)
    return run


def _make_ingestion_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_ingestion(ctx)
    return run


def _make_domain_analysis_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_domain_analysis(ctx)
    return run


def _make_business_rules_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_business_rules(ctx)
    return run


def _make_technology_selection_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_technology_selection(ctx)
    return run


def _make_system_design_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_system_design(ctx)
    return run


def _make_api_design_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_api_design(ctx)
    return run


def _make_database_design_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_database_design(ctx)
    return run


def _make_threat_modeling_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_threat_modeling(ctx)
    return run


def _make_observability_design_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_observability_design(ctx)
    return run


def _make_database_builder_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_database_builder(ctx)
    return run


def _make_compliance_audit_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_compliance_audit(ctx)
    return run


def _make_qa_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_qa(ctx)
    return run


def _make_fix_validator_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_fix_validator(ctx)
    return run


def _make_debug_coder_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_debug_coder(ctx)
    return run


def _make_deployment_plan_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_deployment_plan(ctx)
    return run


def _make_retrospective_run() -> Callable:
    async def run(ctx):
        return await BuilDer.get_instance().run_retrospective(ctx)
    return run


def _is_blockchain_task(task: str) -> bool:
    task_lower = task.lower()
    keywords = ["sha3_512", "sha3-512", "genesis", "blockchain", "bit512", "bloco genesis", "kito hamachi"]
    return any(kw in task_lower for kw in keywords)


def _make_html_form_run(orchestrator: Any) -> Callable:
    """HTML Form — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_html_form(ctx)
    return run


def _make_backend_builder_run(orchestrator: Any) -> Callable:
    """PHP Script — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_backend_builder(ctx)
    return run


def _make_api_builder_run(orchestrator: Any) -> Callable:
    """Integrator — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_api_builder(ctx)
    return run


def _make_tester_run(orchestrator: Any) -> Callable:
    """Test Analyzer — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_tester(ctx)
    return run


def _make_debugger_run(orchestrator: Any) -> Callable:
    """Debugger — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_debugger(ctx)
    return run


def _extrair_codigo_puro(texto: str) -> str:
    if not texto:
        return ""
    import re
    match = re.search(r"```(?:python|py)?\s*([\s\S]*?)```", texto, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return texto.strip()


def _extrair_multifile(texto: str) -> dict[str, str]:
    """Extrai múltiplos arquivos de output do LLM.

    1. Se encontrar # FILE: path/arquivo → usa como nome do arquivo
    2. Se não, extrai todos os blocos ```...``` e nomeia por tipo ou ordem
    3. Se só um bloco, retorna {'script.py': texto}
    """
    import re
    files = {}

    # Tenta # FILE: markers primeiro
    pattern = r'#\s*FILE:\s*(\S+(?:/\S+)*)\s*\n(.*?)(?=\n#\s*FILE:\s|\Z)'
    matches = re.findall(pattern, texto, re.DOTALL)
    if matches:
        for path, content in matches:
            path = path.strip()
            content = content.strip()
            if path and content:
                files[path] = content
        return files

    # Se não achou # FILE:, extrai todos os blocos ```...```
    lang_map = {"html": "index.html", "css": "style.css", "js": "script.js",
                 "javascript": "script.js", "jsx": "script.js",
                 "python": "main.py", "py": "main.py", "flask": "app.py",
                 "django": "app.py", "bash": "run.sh", "sh": "run.sh",
                 "json": "data.json", "xml": "data.xml", "yaml": "config.yaml",
                 "yml": "config.yaml", "md": "README.md", "markdown": "README.md",
                 "text": "README.md", "txt": "README.md", "": "output.txt"}
    unnamed_idx = 0
    blocks = re.findall(r'```(\w*)\s*\n(.*?)```', texto, re.DOTALL)
    if len(blocks) > 1:
        for lang, content in blocks:
            content = content.strip()
            if not content:
                continue
            lang = lang.strip().lower()
            if lang in lang_map:
                fname = lang_map[lang]
            else:
                fname = "file_%d.%s" % (unnamed_idx, lang) if lang else "file_%d.txt" % unnamed_idx
                unnamed_idx += 1
            if fname not in files:
                files[fname] = content
            else:
                base, ext = fname.rsplit(".", 1) if "." in fname else (fname, "txt")
                files["%s_%d.%s" % (base, unnamed_idx, ext)] = content
                unnamed_idx += 1
        return files

    # Só um bloco ou texto sem blocos — prefere bloco com código conhecido
    candidates = []
    for lang, content in blocks:
        content = content.strip().rstrip("`")
        if not content:
            continue
        if lang in ("html",):
            return {"index.html": content}
        if lang in ("python", "py", "flask"):
            return {"main.py": content}
        if lang in ("css",):
            return {"style.css": content}
        if lang in ("js", "javascript"):
            return {"script.js": content}
        if content.startswith("<!DOCTYPE") or content.startswith("<html"):
            return {"index.html": content}
        candidates.append(content)
    for c in candidates:
        if _is_python_code(c):
            return {"main.py": c}
    if candidates:
        c = candidates[0].rstrip("`")
        if c.startswith("<!"):
            return {"index.html": c}
        return {"main.py": c} if _is_python_code(c) else {"output.txt": c}
    # Sem blocos — tenta extrair código Python do texto (ex: texto explicativo + código)
    raw = texto.strip().rstrip("`")
    for marker in ("import ", "from ", "def ", "class ", "@app.route", "if __name__"):
        if marker in raw:
            lines = raw.splitlines()
            code_start = next((i for i, l in enumerate(lines) if marker in l), 0)
            code_lines = lines[code_start:]
            code = "\n".join(code_lines)
            if _is_python_code(code):
                return {"main.py": code}
            break
    if raw.startswith("<!DOCTYPE") or raw.startswith("<html"):
        return {"index.html": raw}
    return {"main.py" if _is_python_code(raw) else "output.txt": raw}


def _make_critic_run(orchestrator: Any) -> Callable:
    """Critic — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_critic(ctx)
    return run


def _make_security_run() -> Callable:
    """Security — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_security(ctx)
    return run


def _make_style_validator_run() -> Callable:
    """Style Validator — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_style_validator(ctx)
    return run


def _make_validator_run() -> Callable:
    """Semantic Validator — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_validator(ctx)
    return run


def _make_ast_validator_run() -> Callable:
    """AST Validator — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_ast_validator(ctx)
    return run


_LIGHT_COLORS = {
    "#f4f4f4", "#f0f0f0", "#eee", "#e0e0e0", "#ddd", "#ccc",
    "#fff", "white", "#ffffff", "#f8f8f8", "#f5f5f5", "#fafafa",
}
_DARK_REPLACEMENTS = {
    "#f4f4f4": "#1a1a2e", "#f0f0f0": "#1a1a2e", "#eee": "#16213e",
    "#e0e0e0": "#2a2a3e", "#ddd": "#2a2a3e", "#ccc": "#3a3a4e",
    "white": "#e0e0e0", "#fff": "#e0e0e0", "#ffffff": "#e0e0e0",
    "#f8f8f8": "#1a1a2e", "#f5f5f5": "#16213e", "#fafafa": "#1a1a2e",
}


def _is_python_code(code: str) -> bool:
    """Verifica se o código parece ser Python válido."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _make_reviewer_run() -> Callable:
    """Reviewer — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_reviewer(ctx)
    return run


def _make_performance_run() -> Callable:
    """Performance — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_performance(ctx)
    return run


_performance_patterns = [
    ("Nested loop", r"(?i)(for\s+\w+\s+in\s+.*:\s*\n.*\n.*for\s+)"),
    ("List comprehension in loop", r"(?i)(for\s+.*:\s*\n.*\[.*)"),
    ("Recursive call", r"(?i)(def\s+\w+\([^)]*\):\s*\n.*return\s+\w+\()"),
]

_FRAMEWORK_MODULES = {"django", "flask", "fastapi", "tornado", "aiohttp", "bottle"}

def _imports_framework(code: str) -> bool:
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            for mod in _FRAMEWORK_MODULES:
                if mod in stripped:
                    return True
    return False


def _validate_syntax(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, "SyntaxError: %s (linha %s)" % (e.msg, e.lineno)


def _compute_final_score(artifact: SolutionArtifact) -> float:
    score = 0.0
    tests_weight = 0.50
    if artifact.tests_total > 0:
        score += (artifact.tests_passed / artifact.tests_total) * tests_weight
        if artifact.tests_passed == artifact.tests_total:
            score += 0.05
    critic_val = min(max(artifact.score, 0), 100) / 100.0
    score += critic_val * 0.20
    has_security_error = "SyntaxError" in (artifact.runtime_error or "") or bool(artifact.semantic_errors)
    if not has_security_error:
        score += 0.15
    code_len = len(artifact.code)
    simplicity = max(0, 1.0 - min(code_len / 5000, 1.0))
    score += simplicity * 0.10
    perf_score = 0.05
    score += perf_score
    return min(score, 1.0)


def _make_final_gatekeeper_run(orchestrator: Any) -> Callable:
    """Final Gatekeeper — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_final_gatekeeper(ctx)
    return run


def _make_artifact_writer_run(orchestrator: Any) -> Callable:
    """Artifact Writer — delega ao BuilDer."""
    async def run(ctx):
        BuilDer(orchestrator=orchestrator)
        inst = BuilDer.get_instance()
        return await inst.run_artifact_writer(ctx)
    return run


def _make_dependency_run() -> Callable:
    """Dependency — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_dependency(ctx)
    return run


def _make_documentation_run() -> Callable:
    """Documentation — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_documentation(ctx)
    return run


def _make_release_run() -> Callable:
    """Release — delega ao BuilDer."""
    async def run(ctx):
        return await BuilDer.get_instance().run_release(ctx)
    return run


def _detect_ext_and_name(code: str, task: str = "") -> tuple[str, str]:
    """Detecta extensão e nome do arquivo principal pelo conteúdo."""
    code_stripped = code.strip()
    if code_stripped.startswith("<!DOCTYPE") or code_stripped.startswith("<html"):
        return ".html", "index.html"
    if code_stripped.startswith("<?xml"):
        return ".xml", "output.xml"
    if code_stripped.startswith("{") and ":" in code_stripped[:100]:
        return ".json", "output.json"
    if code_stripped.startswith("body {") or code_stripped.startswith(".") and "{" in code_stripped[:100]:
        return ".css", "style.css"
    if _is_python_code(code):
        return ".py", "main.py"
    return ".txt", "output.txt"


async def run_integrator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    memory = ctx.get("memory", {})
    code_parts = []
    files = {}
    source_count = 0

    sources = [
        ("frontend_builder", "frontend"),
        ("backend_builder", "backend"),
        ("database_builder", "database"),
        ("api_builder", "api"),
    ]

    for source_key, source_label in sources:
        artifact = memory.get(source_key, {}).get("output")
        if artifact is None:
            continue
        source_count += 1
        if isinstance(artifact, str) and artifact.strip():
            code_parts.append(f"# === {source_label.upper()} ===\n{artifact}")
            files[f"{source_label}.py"] = artifact
        elif isinstance(artifact, dict):
            for key in ("code", "output", "content"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    code_parts.append(f"# === {source_label.upper()} ===\n{val}")
                    files[f"{source_label}.py"] = val
                    break

    integrated_code = "\n\n".join(code_parts) if code_parts else ""

    logger.info("[INTEGRATOR] Sources=%d | Total chars=%d", source_count, len(integrated_code))

    return {
        **ctx,
        "output": integrated_code,
        "integrated_code": integrated_code,
        "files": files,
        "source_count": source_count,
    }
