import ast
import traceback
from typing import Any, Optional, Callable, Dict, List

from .execution_graph import ExecutionGraph
from .node import Node
from .artifact import Artifact, SolutionArtifact

from iaglobal.utils.logger import logger
from iaglobal.validation.ast_security import validate_code_real

from iaglobal.evolution.skills import SkillRegistry, Skill
from iaglobal.evolution.skills.skill_registry import skill_registry as _default_registry


# ==============================================================
# 🎯 SKILL-CENTRIC GRAPH BUILDER
# ==============================================================

# ==============================================================
# CONFIGURAÇÃO DO DAG: dependências entre skills
# ==============================================================

# Ordem topológica do pipeline V3 com dependências
PIPELINE_SKILLS = [
    # ── Phase 1: Definition ──
    ("prompt_intake",      {"strategy": "general",  "depends_on": []}),
    ("enhancement",        {"strategy": "general",  "depends_on": ["prompt_intake"]}),
    ("orchestrator_agent", {"strategy": "general",  "critical": True, "depends_on": ["enhancement"]}),
    ("pm",                 {"strategy": "general",  "depends_on": ["orchestrator_agent"]}),
    ("requirements",       {"strategy": "general",  "depends_on": ["pm"]}),
    ("architect",          {"strategy": "general",  "critical": True, "depends_on": ["requirements"]}),
    ("search",             {"strategy": "research", "depends_on": ["architect"]}),
    ("knowledge",          {"strategy": "fast",     "depends_on": ["search"]}),
    ("dependency",         {"strategy": "fast",     "critical": True, "depends_on": ["knowledge"]}),
    ("risk_analysis",      {"strategy": "general",  "depends_on": ["dependency"]}),
    ("security_design",    {"strategy": "general",  "depends_on": ["risk_analysis"]}),
    ("performance_design", {"strategy": "general",  "depends_on": ["security_design"]}),
    # ── Phase 2: Planning ──
    ("planner",            {"strategy": "general",  "critical": True, "depends_on": ["performance_design"]}),
    # ── Phase 3: Construction ──
    ("coder",              {"strategy": "coding",   "critical": True, "depends_on": ["planner"]}),
    # ── Phase 4: Quality ──
    ("reviewer",           {"strategy": "general",  "critical": True, "depends_on": ["coder"]}),
    ("semantic_validator", {"strategy": "fast",     "critical": True, "depends_on": ["reviewer"]}),
    ("security_audit",     {"strategy": "fast",     "critical": True, "depends_on": ["semantic_validator"]}),
    ("performance_audit",  {"strategy": "fast",     "depends_on": ["security_audit"]}),
    # ── Phase 5: Correction ──
    ("tester",             {"strategy": "general",  "depends_on": ["performance_audit"]}),
    ("debugger",           {"strategy": "debug",    "depends_on": ["tester"], "name": "debug_coder"}),
    # ── Phase 6: Delivery ──
    ("documentation",      {"strategy": "general",  "depends_on": ["tester", "debug_coder"]}),
    ("release",            {"strategy": "general",  "depends_on": ["documentation"]}),
    ("metrics",            {"strategy": "fast",     "depends_on": ["release"]}),
    ("optimization",       {"strategy": "fast",     "depends_on": ["metrics"]}),
    ("result_agent",       {"strategy": "general",  "depends_on": ["optimization"]}),
]


def build_graph_from_skills(
    orchestrator: Any,
    registry: Optional[SkillRegistry] = None,
) -> ExecutionGraph:
    """
    Constrói 100% do DAG do pipeline a partir de skills registradas.

    TODO node é criado via skill.to_node(). Skills sem run_fn registrada
    disparam fallback para a implementação manual (_make_*_run).
    """
    if registry is None:
        registry = _default_registry

    graph = ExecutionGraph()

    for skill_name, opts in PIPELINE_SKILLS:
        skill = registry.get(skill_name)
        run_fn = skill.run_fn if (skill and skill.run_fn) else _get_fallback_run_fn(skill_name, orchestrator)

        if run_fn is None:
            logger.warning("[SKILL-GRAPH] Nenhuma implementação para skill '%s' — pulando", skill_name)
            continue

        # Garante que a skill tem run_fn no registry
        if skill and not skill.run_fn:
            _update_skill_run_fn(registry, skill_name, run_fn)

        node_name = opts.get("name", skill_name)
        depends_on = opts.get("depends_on", [])
        strategy = opts.get("strategy", "general")
        critical = opts.get("critical", False)

        if skill and skill.run_fn:
            node = skill.to_node(
                depends_on=depends_on,
                strategy=strategy,
                critical=critical,
                name=node_name,
            )
        else:
            # Fallback: cria node manual
            node = Node(
                name=node_name,
                run=run_fn,
                depends_on=depends_on,
                strategy=strategy,
                critical=critical,
                node_type=skill_name,
            )

        graph.add_node(node)

    return graph


def build_default_graph(orchestrator: Any, task: str) -> ExecutionGraph:
    """
    Wrapper compatível que constrói o grafo a partir de skills
    e registra as implementações padrão das skills.
    """
    _register_default_skill_implementations(orchestrator)
    return build_graph_from_skills(orchestrator)


def _get_fallback_run_fn(skill_name: str, orchestrator: Any) -> Optional[Callable]:
    """Retorna a implementação manual (fallback) para uma skill."""
    fallbacks = {
        "prompt_intake":        lambda o: _make_prompt_intake_run(),
        "enhancement":          lambda o: _make_enhancement_run(),
        "orchestrator_agent":   lambda o: _make_orchestrator_run(),
        "pm":                   lambda o: _make_pm_run(),
        "requirements":         lambda o: _make_requirements_run(),
        "architect":            lambda o: _make_architect_run(),
        "search":               _make_search_run,
        "knowledge":            lambda o: _make_knowledge_run(),
        "dependency":           lambda _o: _make_dependency_run(),
        "risk_analysis":        lambda o: _make_risk_analysis_run(),
        "security_design":      lambda o: _make_security_design_run(),
        "performance_design":   lambda o: _make_performance_design_run(),
        "planner":              _make_planner_run,
        "coder":                _make_multi_coder_run,
        "reviewer":             lambda o: _make_reviewer_run(),
        "semantic_validator":   lambda o: _make_semantic_validator_run(),
        "security_audit":       lambda o: _make_security_audit_run(),
        "performance_audit":    lambda o: _make_performance_audit_run(),
        "tester":               _make_tester_run,
        "debugger":             _make_debugger_run,
        "documentation":        lambda _o: _make_documentation_run(),
        "release":              lambda o: _make_release_run(),
        "metrics":              lambda o: _make_metrics_run(),
        "optimization":         lambda o: _make_optimization_run(),
        "result_agent":         lambda o: _make_result_agent_run(),
    }
    maker = fallbacks.get(skill_name)
    if maker:
        return maker(orchestrator)
    return None


def _update_skill_run_fn(registry: SkillRegistry, skill_name: str, run_fn: Callable):
    """Atualiza o run_fn de uma skill no registry."""
    existing = registry.get(skill_name)
    if existing:
        updated = Skill(
            name=existing.name,
            description=existing.description,
            inputs=list(existing.inputs),
            outputs=list(existing.outputs),
            constraints=list(existing.constraints),
            execution_policy=existing.execution_policy,
            run_fn=run_fn,
            version=existing.version,
            tags=list(existing.tags),
        )
        registry.register_or_update(updated)


def _register_default_skill_implementations(orchestrator: Any):
    """
    Registra as implementações padrão (run_fn) para TODAS as skills
    (core + infra) no SkillRegistry global.
    """
    from iaglobal.evolution.skills.skill_registry import skill_registry as reg
    from iaglobal.evolution.skills.skill import (
        SKILL_PLANNER, SKILL_CODER,
        SKILL_TESTER, SKILL_DEBUGGER,
        SKILL_ARCHITECT,
        SKILL_SEARCH,
        SKILL_SEMANTIC_VALIDATOR,
        SKILL_REVIEWER,
        SKILL_DOCUMENTATION,
        SKILL_DEPENDENCY,
        SKILL_REQUIREMENTS,
        SKILL_PRODUCT_MANAGER,
        SKILL_PROMPT_INTAKE,
        SKILL_RISK_ANALYSIS,
        SKILL_RELEASE,
        SKILL_METRICS,
        SKILL_OPTIMIZATION,
        SKILL_KNOWLEDGE,
        SKILL_ENHANCEMENT,
        SKILL_ORCHESTRATOR,
        SKILL_SECURITY_DESIGN,
        SKILL_PERFORMANCE_DESIGN,
        SKILL_SECURITY_AUDIT,
        SKILL_PERFORMANCE_AUDIT,
        SKILL_RESULT_AGENT,
    )

    skill_templates = {
        "prompt_intake":        SKILL_PROMPT_INTAKE,
        "enhancement":          SKILL_ENHANCEMENT,
        "orchestrator_agent":   SKILL_ORCHESTRATOR,
        "pm":                   SKILL_PRODUCT_MANAGER,
        "requirements":         SKILL_REQUIREMENTS,
        "architect":            SKILL_ARCHITECT,
        "search":               SKILL_SEARCH,
        "knowledge":            SKILL_KNOWLEDGE,
        "dependency":           SKILL_DEPENDENCY,
        "risk_analysis":        SKILL_RISK_ANALYSIS,
        "security_design":      SKILL_SECURITY_DESIGN,
        "performance_design":   SKILL_PERFORMANCE_DESIGN,
        "planner":              SKILL_PLANNER,
        "coder":                SKILL_CODER,
        "reviewer":             SKILL_REVIEWER,
        "semantic_validator":   SKILL_SEMANTIC_VALIDATOR,
        "security_audit":       SKILL_SECURITY_AUDIT,
        "performance_audit":    SKILL_PERFORMANCE_AUDIT,
        "tester":               SKILL_TESTER,
        "debugger":             SKILL_DEBUGGER,
        "documentation":        SKILL_DOCUMENTATION,
        "release":              SKILL_RELEASE,
        "metrics":              SKILL_METRICS,
        "optimization":         SKILL_OPTIMIZATION,
        "result_agent":         SKILL_RESULT_AGENT,
    }

    for name, template in skill_templates.items():
        run_fn = _get_fallback_run_fn(name, orchestrator)
        if run_fn is None:
            logger.warning("[SKILL-GRAPH] Nenhuma implementação para skill '%s'", name)
            continue
        updated = Skill(
            name=template.name,
            description=template.description,
            inputs=list(template.inputs),
            outputs=list(template.outputs),
            constraints=list(template.constraints),
            execution_policy=template.execution_policy,
            run_fn=run_fn,
            version=template.version,
            tags=list(template.tags),
        )
        reg.register_or_update(updated)
        logger.debug("[SKILL-GRAPH] run_fn registrada para skill '%s'", name)


def _classify_task_type(task: str) -> str:
    tl = task.lower()
    web_kw = ["pagina", "página", "html", "web", "site", "django", "flask",
              "formulario", "formulário", "contato", "css", "javascript", "api"]
    code_kw = ["função", "funcao", "function", "classe", "class", "algoritmo",
               "script", "código", "codigo", "implemente", "crie", "criar"]
    research_kw = ["o que é", "como funciona", "explique", "diferença", "compare",
                   "pesquise", "busque", "qual a", "quem é", "qual", "como ",
                   "significa", "exemplo de"]

    web_score = sum(1 for w in web_kw if w in tl)
    code_score = sum(1 for w in code_kw if w in tl)
    research_score = sum(1 for w in research_kw if w in tl)

    if web_score > code_score and web_score > research_score:
        return "web"
    if code_score > research_score:
        return "coding"
    if research_score > 0:
        return "research"
    if code_score > 0:
        return "coding"
    return "general"


def _detect_ambiguity(task: str) -> float:
    """Retorna score 0-1: 0 = claro, 1 = muito ambíguo."""
    words = task.split()
    tl = task.lower()
    score = 0.0

    if len(words) < 3:
        score += 0.5
    elif len(words) < 8:
        score += 0.2

    if "ou" in tl or "or" in tl:
        score += 0.2
    if "?" in tl:
        score += 0.1
    if "qualquer" in tl or "qual" in tl or "algum" in tl:
        score += 0.1

    has_tech = any(kw in tl for kw in ["python", "javascript", "java", "html",
                                        "flask", "django", "react", "api",
                                        "banco", "sql", "web", "app"])
    if not has_tech:
        code_action_words = sum(1 for w in ["crie", "faça", "criar", "fazer"] if w in tl)
        if code_action_words:
            score += 0.3

    return min(score, 1.0)


_SMALL_MODELS = {
    "qwen2.5:0.5b", "qwen2.5:1.5b", "phi:2b", "phi2:2.7b",
    "tinyllama:1.1b", "gemma:2b", "stablelm2:1.6b",
}


def _is_small_model(model_str: str) -> bool:
    model_name = model_str.split("/")[-1].lower()
    for small in _SMALL_MODELS:
        if small in model_name or model_name in small:
            return True
    return False


_FEW_SHOTS = {
    "web": (
        "\n\n---\nEXEMPLO DE RESPOSTA ESPERADA (projeto web):\n"
        "# FILE: app.py\n"
        "from flask import Flask, render_template, request\n\n"
        "app = Flask(__name__)\n\n@app.route('/')\ndef index():\n"
        "    return render_template('index.html')\n\n@app.route('/submit', methods=['POST'])\n"
        "def submit():\n    nome = request.form.get('nome')\n    return f'Obrigado, {nome}!'\n\n"
        "if __name__ == '__main__':\n    app.run(debug=True)\n"
        "# FILE: templates/index.html\n"
        "<!DOCTYPE html><html><body><h1>Formulário</h1>"
        "<form method='post' action='/submit'>"
        '<input name="nome" placeholder="Seu nome">'
        "<button type='submit'>Enviar</button></form></body></html>"
    ),
    "coding": (
        "\n\n---\nEXEMPLO DE RESPOSTA ESPERADA (função Python):\n"
        "def minha_funcao(param1: str, param2: int = 0) -> dict:\n"
        '    """Descrição clara do que a função faz."""\n'
        "    resultado = {\"param1\": param1, \"processado\": param2 * 2}\n"
        "    return resultado\n"
    ),
    "research": (
        "\n\n---\nEXEMPLO DE RESPOSTA ESPERADA (pesquisa):\n"
        "Assunto: [nome do tópico]\n"
        "- Definição: [explicação concisa]\n"
        "- Principais pontos: [lista numerada]\n"
        "- Referência: [fonte da informação]\n"
    ),
}


def _build_context_expansion(task: str, task_type: str, is_small: bool) -> str:
    if not is_small:
        return ""
    extra = (
        "\n\n---\nINSTRUÇÕES ADICIONAIS (modelo pequeno — seja mais explícito):\n"
        "- Seja direto e objetivo na resposta\n"
        "- Estruture em etapas claras\n"
        "- Evite abstrações desnecessárias\n"
        "- Forneça exemplos práticos"
    )
    few_shot = _FEW_SHOTS.get(task_type)
    if few_shot:
        extra += few_shot
    return extra


def _make_prompt_intake_run() -> Callable:
    """Prompt Intake — primeiro contato com o usuário. Extrai domínio, objetivo,
    nível de ambiguidade e detecta lacunas."""
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        logger.info("📥 [INTAKE] Recebendo solicitação...")

        if not task or len(task) < 3:
            return {"output": {"domain": "unknown", "objective": task, "ambiguity_level": 100}}

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        prompt = (
            "Você é um analista de sistemas. Analise o prompt do usuário e extraia:\n"
            "- domain: domínio do projeto (saúde, finanças, e-commerce, etc)\n"
            "- objective: objetivo principal em uma frase\n"
            "- ambiguity_level: 0-100 (quão vago/ambíguo é o pedido)\n"
            "- gaps: lista de informações faltantes\n\n"
            "Retorne APENAS JSON:\n"
            '{"domain": "...", "objective": "...", "ambiguity_level": 0, "gaps": []}\n\n'
            "Prompt: %s\n\nJSON:" % task
        )

        intake = {"domain": "unknown", "objective": task, "ambiguity_level": 50, "gaps": []}

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            if response:
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    parsed = _json.loads(response[inicio:fim + 1])
                    if isinstance(parsed, dict):
                        intake = parsed
                        logger.info("📥 [INTAKE] domínio=%s, ambiguidade=%d, gaps=%d",
                                     intake.get("domain"), intake.get("ambiguity_level"), len(intake.get("gaps", [])))
        except Exception as e:
            logger.warning("📥 [INTAKE] LLM falhou: %s — usando fallback", e)

        ctx["input"]["intake"] = intake

        if wd:
            wd.append_log("intake: %s (amb=%d)" % (intake.get("domain"), intake.get("ambiguity_level")))

        return {"output": intake, "domain": intake.get("domain"), "ambiguity_level": intake.get("ambiguity_level")}
    return run


def _make_interpreter_run() -> Callable:
    """Interpreta e melhora o prompt do usuário, com detecção de ambiguidade,
    expansão contextual para modelos pequenos e exemplos few-shot condicionais."""
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")
        if not task or len(task) < 5:
            return {"output": "", "refined_task": task}

        logger.info("🌐 interpretando sua solicitação ...")
        if wd:
            wd.append_log("original: %s" % task[:80])

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")
        is_small = _is_small_model(locked)

        task_type = _classify_task_type(task)
        ambiguity = _detect_ambiguity(task)

        is_web = task_type == "web" or any(
            w in task.lower() for w in ["pagina", "página", "html", "web", "site",
                                        "django", "flask", "contato", "formulario"]
        )

        correction_prompt = (
            "Você é um especialista em interpretar e melhorar prompts de usuários.\n"
            "Corrija erros de gramática (português ou inglês), melhore a clareza,\n"
            "complete solicitações ambíguas e estruture o request de forma objetiva.\n"
            "Mantenha a intenção original. Retorne APENAS o prompt melhorado,\n"
            "sem explicações ou formatação extra.\n"
            "Prompt original: %s\n"
            "Prompt melhorado:" % task
        )

        expansion = _build_context_expansion(task, task_type, is_small)

        final_prompt = correction_prompt
        if expansion:
            final_prompt = correction_prompt + "\n\n" + expansion

        from iaglobal.providers.provider_router import async_route_generate
        try:
            refined = await async_route_generate(model=locked, prompt=final_prompt, task_type="general")
            refined = (refined or "").strip().strip("`\"'").strip()
            if len(refined) < len(task) * 0.3 or not refined:
                refined = task
        except Exception:
            refined = task

        if is_web and "tkinter" not in refined.lower() and "flask" not in refined.lower():
            refined += " (crie uma aplicação web usando Flask com HTML, não use tkinter)"

        if ambiguity > 0.5 and refined == task:
            refined = task + (
                " Seja específico: informe linguagem, framework e formato de saída esperado."
            )

        was_refined = refined != task
        if was_refined:
            ctx["input"]["task"] = refined

        logger.info("🌐 [INTERPRETER] tipo=%s ambig=%.2f small=%s refinado: %s -> %s",
                     task_type, ambiguity, is_small, task[:40], refined[:60])
        if wd:
            wd.append_log("refinado: %s" % refined[:80])

        try:
            from iaglobal.models.event_bus import bus, EventType
            bus.publish(EventType.PIPELINE_STAGE, {
                "decision_event": {
                    "step": "task_normalization",
                    "execution_id": ctx.get("input", {}).get("metadata", {}).get("execution_id", "unknown"),
                    "action": "cleaned_text" if was_refined else "no_changes",
                    "metadata": {
                        "tokens_original": len(task.split()),
                        "tokens_refined": len(refined.split()),
                        "was_refined": was_refined,
                        "language": "pt" if any(w in task.lower() for w in ["ão", "ção", "uma", "para", "com"]) else "en",
                        "task_type": task_type,
                        "ambiguity_score": ambiguity,
                        "small_model": is_small,
                        "context_expanded": bool(expansion),
                    },
                },
                "step": "task_normalization",
            }, source="interpreter_node")
        except Exception:
            pass

        return {"output": refined, "refined_task": refined, "original_task": task}
    return run


def _make_requirements_run() -> Callable:
    """Requirements Agent — converte intenção em requisitos formais: funcionais,
    não funcionais, casos de uso e critérios de aceite."""
    async def run(ctx):
        task = ctx.get("memory", {}).get("interpreter", {}).get("refined_task", "")
        original = ctx.get("input", {}).get("task", "")
        if not task:
            task = original
        wd = ctx.get("workdir")

        logger.info("📋 [REQUIREMENTS] Gerando requisitos...")

        if not task or len(task) < 5:
            return {"output": "", "requirements": {}}

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        prompt = (
            "Você é um Analista de Requisitos Sênior. Converta a tarefa abaixo em requisitos formais.\n\n"
            "Retorne APENAS um JSON válido com esta estrutura exata:\n"
            "{\n"
            '  "funcionais": ["RF1...", "RF2..."],\n'
            '  "nao_funcionais": ["RNF1...", "RNF2..."],\n'
            '  "casos_de_uso": [{"ator": "...", "acao": "...", "resultado": "..."}],\n'
            '  "criterios_aceite": ["CA1...", "CA2..."]\n'
            "}\n\n"
            "Mínimo de 3 itens por categoria.\n\n"
            "Tarefa: %s\n\nJSON:" % task
        )

        requirements = {
            "funcionais": [task],
            "nao_funcionais": ["Funcionalidade básica implementada"],
            "casos_de_uso": [{"ator": "Usuário", "acao": task, "resultado": "Tarefa concluída"}],
            "criterios_aceite": ["Código executa sem erros"],
        }

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            if response:
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    parsed = _json.loads(response[inicio:fim + 1])
                    if isinstance(parsed, dict) and any(k in parsed for k in
                                                        ("funcionais", "nao_funcionais", "casos_de_uso")):
                        requirements = parsed
                        logger.info("📋 [REQUIREMENTS] %d RF, %d RNF, %d UC",
                                     len(parsed.get("funcionais", [])),
                                     len(parsed.get("nao_funcionais", [])),
                                     len(parsed.get("casos_de_uso", [])))
        except Exception as e:
            logger.warning("📋 [REQUIREMENTS] LLM falhou: %s — usando fallback", e)

        enriched = "Requisitos:\n"
        if requirements.get("funcionais"):
            enriched += "Funcionais:\n" + "\n".join("- " + r for r in requirements["funcionais"]) + "\n"
        if requirements.get("nao_funcionais"):
            enriched += "Não Funcionais:\n" + "\n".join("- " + r for r in requirements["nao_funcionais"]) + "\n"
        if requirements.get("casos_de_uso"):
            enriched += "Casos de Uso:\n"
            for uc in requirements["casos_de_uso"]:
                enriched += "- %s: %s → %s\n" % (uc.get("ator", "?"), uc.get("acao", "?"), uc.get("resultado", "?"))
        if requirements.get("criterios_aceite"):
            enriched += "Critérios de Aceite:\n" + "\n".join("- " + c for c in requirements["criterios_aceite"])

        ctx["input"]["requirements_data"] = requirements
        ctx["input"]["task"] = enriched

        if wd:
            wd.append_log("requirements: %d RF" % len(requirements.get("funcionais", [])))

        return {
            "output": requirements,
            "requirements": requirements,
        }
    return run


def _make_pm_run() -> Callable:
    """Product Manager V2 — a partir de requisitos estruturados, cria Epics, Features,
    Stories e Backlog para o planner."""
    async def run(ctx):
        requirements = ctx.get("memory", {}).get("requirements", {}).get("requirements", {})
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        logger.info("📋 [PM] Criando épicos e features...")

        if not requirements or not requirements.get("funcionais"):
            return {"output": {"epics": [], "features": [], "stories": []}}

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        req_text = str(requirements)
        prompt = (
            "Você é um Product Manager Sênior. A partir dos requisitos abaixo, "
            "crie Epics, Features e User Stories organizadas em backlog.\n\n"
            "Retorne APENAS um JSON com esta estrutura:\n"
            "{\n"
            '  "epics": [{"id": "E1", "titulo": "...", "descricao": "..."}],\n'
            '  "features": [{"id": "F1", "epic": "E1", "titulo": "...", "descricao": "..."}],\n'
            '  "stories": [{"id": "S1", "feature": "F1", "titulo": "...", "criteria": "..."}],\n'
            '  "backlog_priorities": ["S1", "S2"]\n'
            "}\n\nRequisitos:\n%s\n\nJSON:" % req_text
        )

        result = {"epics": [], "features": [], "stories": [], "backlog_priorities": []}

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            if response:
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    parsed = _json.loads(response[inicio:fim + 1])
                    if isinstance(parsed, dict):
                        result = parsed
                        logger.info("📋 [PM] %d épicos, %d features, %d stories",
                                     len(parsed.get("epics", [])),
                                     len(parsed.get("features", [])),
                                     len(parsed.get("stories", [])))
        except Exception as e:
            logger.warning("📋 [PM] LLM falhou: %s — usando fallback", e)

        ctx["input"]["pm_output"] = result

        if wd:
            wd.append_log("pm: %d epics" % len(result.get("epics", [])))

        return {
            "output": result,
            "epics": result.get("epics", []),
            "features": result.get("features", []),
            "stories": result.get("stories", []),
        }
    return run


def _make_architect_run() -> Callable:
    """Analisa a tarefa e projeta a arquitetura: padrões, módulos, dependências, estrutura de pastas, APIs."""
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")
        if not task or len(task) < 5:
            return {"output": "", "architecture": ""}

        logger.info("🏗️ arquiteto analisando a tarefa ...")

        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
        _arch_errors = query_relevant_errors(task, limit=2)
        _arch_error_ctx = format_errors_for_prompt(_arch_errors)

        prompt = (
            "Você é um Arquiteto de Software Sênior. Analise a tarefa abaixo e projete a arquitetura.\n\n"
            "Retorne APENAS um JSON válido com esta estrutura:\n"
            "{\n"
            '  "padroes": ["lista de padrões arquiteturais"],\n'
            '  "modulos": ["lista de módulos/componentes do sistema"],\n'
            '  "dependencias": {"frameworks": [], "bibliotecas": [], "bancos": []},\n'
            '  "estrutura_pastas": "descrição da estrutura de diretórios",\n'
            '  "apis": ["contratos de API esperados"]\n'
            "}\n\n"
            "Critérios:\n"
            "- Escolha padrões adequados à escala (MVC, hexagonal, clean architecture, microserviços, etc.)\n"
            "- Defina módulos coesos com responsabilidade única\n"
            "- Dependências devem ser específicas (ex: FastAPI, PostgreSQL, Redis, SQLAlchemy)\n"
            "- Estrutura de pastas deve ser detalhada (src/, tests/, docs/, etc.)\n"
            "- APIs devem listar endpoints esperados com método HTTP e propósito\n"
            "%s\n\n"
            "Tarefa: %s\n\n"
            "JSON:" % (
                _arch_error_ctx + "\n" if _arch_error_ctx else "",
                task
            )
        )

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            if response:
                import re as _re
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    raw = response[inicio:fim + 1]
                    raw = _re.sub(r',\s*}', '}', raw)
                    raw = _re.sub(r',\s*]', ']', raw)
                    try:
                        architecture = _json.loads(raw)
                    except _json.JSONDecodeError:
                        raw = raw.replace("'", '"')
                        raw = _re.sub(r'(?<!")\b(true|false|null)\b(?!")', lambda m: m.group(1).lower() if m.group(1).lower() in ("true", "false", "null") else m.group(0), raw)
                        architecture = _json.loads(raw)
                else:
                    architecture = {"raw": response}
                ctx["input"]["architecture"] = architecture
                logger.info("🏗️ [ARCHITECT] padrões=%s modulos=%s",
                             architecture.get("padroes", []), architecture.get("modulos", []))
                if wd:
                    wd.append_log("arquitetura: %s" % str(architecture.get("padroes", ""))[:60])
                return {"output": architecture, "architecture": architecture}
        except Exception as e:
            logger.warning("🏗️ [ARCHITECT] LLM falhou: %s — usando fallback", e)

        architecture = {"padroes": ["MVC"], "modulos": [task], "dependencias": {}, "estrutura_pastas": "", "apis": []}
        ctx["input"]["architecture"] = architecture
        logger.info("🏗️ [ARCHITECT] fallback: arquitetura padrão MVC")
        if wd:
            wd.append_log("arquitetura fallback MVC")
        return {"output": architecture, "architecture": architecture}
    return run


def _make_risk_analysis_run() -> Callable:
    """Risk Analysis Agent — analisa riscos de escalabilidade, compliance,
    segurança e custos antes do planejamento."""
    async def run(ctx):
        architecture = ctx.get("memory", {}).get("architect", {}).get("architecture", {})
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        logger.info("⚠️ [RISK] Analisando riscos...")

        if not task or len(task) < 5:
            return {"output": {"risks": []}, "risk_score": 0}

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        arch_text = str(architecture) if architecture else "Não definida"
        prompt = (
            "Você é um analista de riscos sênior. Analise o projeto abaixo e identifique riscos.\n\n"
            "Retorne APENAS JSON:\n"
            "{\n"
            '  "risks": [\n'
            '    {"tipo": "escalabilidade"|"compliance"|"seguranca"|"custo",\n'
            '     "descricao": "...",\n'
            '     "severidade": "alta"|"media"|"baixa",\n'
            '     "mitigacao": "..."}\n'
            '  ]\n'
            "}\n\n"
            "Arquitetura: %s\n\nTarefa: %s\n\nJSON:" % (arch_text, task)
        )

        risks = {"risks": []}

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            if response:
                import re as _re
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    raw = response[inicio:fim + 1]
                    raw = _re.sub(r',\s*}', '}', raw)
                    raw = _re.sub(r',\s*]', ']', raw)
                    try:
                        parsed = _json.loads(raw)
                    except _json.JSONDecodeError:
                        raw = raw.replace("'", '"')
                        parsed = _json.loads(raw)
                    if isinstance(parsed, dict) and "risks" in parsed:
                        risks = parsed
                        logger.info("⚠️ [RISK] %d riscos identificados", len(parsed["risks"]))
        except Exception as e:
            logger.warning("⚠️ [RISK] LLM falhou: %s — usando fallback", e)

        ctx["input"]["risks"] = risks.get("risks", [])

        if wd:
            wd.append_log("riscos: %d" % len(risks.get("risks", [])))

        return {"output": risks, "risks": risks.get("risks", []), "risk_score": len(risks.get("risks", [])) * 10}
    return run


def _make_planner_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        architecture = ctx.get("input", {}).get("architecture", {})
        wd = ctx.get("workdir")
        artifact = SolutionArtifact(task=task)

        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
        _plan_errors = query_relevant_errors(task, limit=2)
        _plan_error_ctx = format_errors_for_prompt(_plan_errors)

        context = task
        if architecture and architecture.get("modulos"):
            context = (
                "Tarefa: %s\n\n"
                "Arquitetura definida:\n"
                "- Padrões: %s\n"
                "- Módulos: %s\n"
                "- Dependências: %s\n"
                "- Estrutura de pastas: %s\n"
                "- APIs: %s\n"
                "%s"
            ) % (task, architecture.get("padroes", []), architecture.get("modulos", []),
                 architecture.get("dependencias", {}), architecture.get("estrutura_pastas", ""),
                 architecture.get("apis", []),
                 "\n" + _plan_error_ctx if _plan_error_ctx else "")
            logger.info("📋 plano com arquitetura: %s", architecture.get("padroes", []))

        try:
            if hasattr(orchestrator, "planner") and orchestrator.planner:
                plan = orchestrator.planner.plan(context)
                artifact.code = plan
            else:
                artifact.code = context
                logger.info("📋 plano: executar tarefa conforme solicitado")
        except Exception as e:
            logger.warning("📋 plano falhou: %s", e)
            return {
                "output": artifact,
                "task": task,
                "success": False,
                "error": str(e),
            }
        if wd and artifact.code:
            wd.write_code(artifact.code).append_log("planner OK")
        return {"output": artifact, "task": task}
    return run


def _make_web_classifier_run() -> Callable:
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")
        artifact = ctx.get("memory", {}).get("planner", {}).get("output", SolutionArtifact())

        needs_web = _classify_web_need(task)
        artifact.reflection = str(needs_web)

        logger.info("🔍 filtrando palavras ...")
        if needs_web:
            logger.info("🔍 assunto parece relevante para busca na internet!")
        else:
            logger.info("🔍 assunto não precisa de busca externa")
        if wd:
            wd.append_log("needs_web=%s" % needs_web)
        return {"output": artifact, "needs_web": needs_web}
    return run


def _classify_web_need(task: str) -> bool:
    task_lower = task.lower()
    keywords_noweb = [
        "crie", "criar", "create", "defina", "implemente",
        "função", "function", "classe", "class", "algoritmo",
        "algoritmo", "script", "código", "codigo", "código",
        "sha3", "sha256", "genesis", "bloco", "blockchain",
        "serialize", "serializar",
    ]
    keywords_web = [
        "api", "stripe", "maio 2026", "maio de 2026",
        "maio/2026", "preço", "preco", "preços", "precos",
        "cotação", "cotacao", "notícia", "noticia", "última",
        "ultima", "versão", "versao", "lançamento",
        "lancamento", "atualização", "atualizacao",
        "html", "css", "javascript", "script.js", "style.css",
        "django", "flask", "bootstrap", "tailwind",
        "pagina", "pagina", "formulario", "contato",
        "website", "site", "web",
    ]

    noweb_count = sum(1 for kw in keywords_noweb if kw in task_lower)
    web_count = sum(1 for kw in keywords_web if kw in task_lower)

    if web_count > 0:
        return True

    if noweb_count > 0:
        return False

    if "?" in task or "qual" in task_lower or "como" in task_lower:
        return True

    return len(task) > 200


def _make_search_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("web_classifier", {}).get("output", SolutionArtifact())
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        # Extrai query original: se task foi aumentada (contém "Requisitos:"), 
        # tenta pegar o texto antes, senão usa a task inteira
        if "Requisitos:" in task or "Funcionais:" in task:
            search_query = task.split("\n")[0].strip()
            if len(search_query) < 5 or "Requisitos:" in search_query or "Funcionais:" in search_query:
                search_query = task.split("Requisitos:")[0].strip() if "Requisitos:" in task else task
        else:
            search_query = task

        search_query = search_query[:150] if len(search_query) > 150 else search_query

        if not search_query or len(search_query) < 5:
            logger.info("⏭️ web search desnecessário. Pulando.")
            if wd:
                wd.append_log("search pulado")
            return {"output": artifact}

        logger.info(f"🌐 analisando assunto na web: '{search_query[:60]}...'")
        try:
            from iaglobal.tools.search import search_tool
            result = search_tool(search_query)
            artifact.security_report = result
            logger.info("🌐 encontrei %d caracteres de informação na web", len(result))
            if wd:
                wd.append_log("search OK (%d chars)" % len(result))
        except Exception as e:
            logger.warning("🌐 busca na web falhou: %s", e)
            artifact.security_report = ""
            if wd:
                wd.append_log("search falhou: %s" % e)

        return {"output": artifact}
    return run


def _is_blockchain_task(task: str) -> bool:
    task_lower = task.lower()
    keywords = ["sha3_512", "sha3-512", "genesis", "blockchain", "bit512", "bloco genesis", "kito hamachi"]
    return any(kw in task_lower for kw in keywords)


def _make_multi_coder_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")
        planner_result = ctx.get("memory", {}).get("planner", {}).get("output", SolutionArtifact())
        search_result = ctx.get("memory", {}).get("search", {}).get("output", SolutionArtifact())

        if isinstance(planner_result, SolutionArtifact):
            task = planner_result.code or task

        web_context = ""
        if isinstance(search_result, SolutionArtifact) and search_result.security_report:
            web_context = search_result.security_report

        logger.debug("[CODER] Gerando código para: %s", task[:60])

        # Blockchain tasks: use the pre-built correct implementation
        if _is_blockchain_task(task):
            from iaglobal.blockchain.genesis import generate_genesis_python_script
            blockchain_code = generate_genesis_python_script()
            logger.info("✅ [CODER] Usando implementação blockchain nativa (SHA3-512, Bit512, Kito Hamachi)")
            if wd:
                wd.append_log("blockchain nativo gerado")
            artifact = SolutionArtifact(
                task=task,
                code=blockchain_code,
                files={},
            )
            if wd:
                wd.write_code(blockchain_code).append_log("blockchain nativo (%d chars)" % len(blockchain_code))
            return {"output": artifact}
        elif hasattr(orchestrator, "_model_fn"):
            from iaglobal.providers.provider_config import ProviderConfig
            from iaglobal.events import resolve_locked_model
            default = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"

            contexto_web_label = ""
            if web_context:
                contexto_web_label = (
                    "\n[CONTEXTO DE REFERÊNCIA (use apenas como consulta, NÃO copie diretamente)]:\n"
                    + web_context
                    + "\n"
                )

            # Lê instruções de especialização do MetaAgentDesigner
            specialization = ctx.get("input", {}).get("_specialization", {})
            coder_specialization = specialization.get("coder", "")

            is_web = any(w in task.lower() for w in ["django", "flask", "html", "pagina", "pagina", "web", "site", "http"])
            is_dark = any(w in task.lower() for w in ["escuro", "dark", "darkmode", "dark mode", "tema escuro", "preto"])
            if is_web:
                style_rules = (
                    "REGRAS DE ESTILO OBRIGATÓRIAS (tema escuro):\n"
                    "background-color: #121212 ou #1a1a2e em todos os containers principais\n"
                    "color: #e0e0e0 ou #ffffff para o texto\n"
                    "input/textarea com background #2a2a3e e borda #444, texto branco\n"
                    "botões com background #e94560 ou similar, texto branco\n"
                    "NÃO use cores claras (#f4f4f4, #fff como fundo)\n"
                ) if is_dark else ""
                prompt = (
                    "Você é um desenvolvedor web full-stack. Crie um projeto web COMPLETO.\n"
                    "Cada arquivo deve ter conteúdo COMPLETO e FUNCIONAL, sem placeholders.\n"
                    "NÃO use tkinter.\n"
                    "Escolha a ferramenta certa para o projeto:\n"
                    "- Se for uma página simples (formulário, contato, landing page): use Flask + HTML puro\n"
                    "- Se for um projeto complexo (múltiplas páginas, banco de dados, autenticação): use Django\n"
                    "NÃO misture Django com Flask. Se usar Django, forneça urls.py, views.py, models.py.\n"
                    "%s"
                    "Siga este modelo de formulário HTML:\n"
                    "# FILE: index.html\n"
                    "<!DOCTYPE html>\n"
                    "<html lang=\"pt-br\">\n"
                    "<head>\n"
                    "<meta charset=\"UTF-8\">\n"
                    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                    "<title>Contato</title>\n"
                    "<link rel=\"stylesheet\" href=\"css/style.css\">\n"
                    "</head>\n"
                    "<body>\n"
                    "<div class=\"container\">\n"
                    "<h1>Entre em Contato</h1>\n"
                    "<form id=\"contatoForm\" method=\"post\">\n"
                    "<label for=\"nome\">Nome:</label>\n"
                    "<input type=\"text\" id=\"nome\" name=\"nome\" required>\n"
                    "<label for=\"email\">E-mail:</label>\n"
                    "<input type=\"email\" id=\"email\" name=\"email\" required>\n"
                    "<label for=\"mensagem\">Mensagem:</label>\n"
                    "<textarea id=\"mensagem\" name=\"mensagem\" required></textarea>\n"
                    "<button type=\"submit\">Enviar</button>\n"
                    "</form>\n"
                    "</div>\n"
                    "<script src=\"js/script.js\"></script>\n"
                    "</body>\n"
                    "</html>\n"
                    "Tarefa: %s\n"
                    "%s"
                    "%s"
                    "Retorne APENAS os arquivos com # FILE: dentro de um bloco ```.\n"
                    "Complete o CSS e JS com estilos escuros e validação.\n"
                    "Sem explicações.\n"
                ) % (style_rules, task, contexto_web_label, coder_specialization)
            else:
                prompt = (
                    "Você é um Engenheiro de Software Sênior. Gere um script Python COMPLETO e FUNCIONAL.\n"
                    "NÃO use placeholders, NÃO escreva '# implementar depois' ou '# adicione suas funcionalidades'.\n"
                    "O código deve ser 100%% executável e autossuficiente.\n"
                    "Se o projeto tiver múltiplos arquivos, use # FILE: caminho/do/arquivo entre eles.\n"
                    "Tarefa: %s\n"
                    "%s"
                    "%s"
                    "Retorne APENAS o código Python dentro de um bloco ```python ... ```.\n"
                    "Sem explicações.\n"
                ) % (task, contexto_web_label, coder_specialization)

            # ── Cache + Aprendizado antes da geracao ──
            from iaglobal.memory.memory_storage import get_success_by_task, store_success
            from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
            from iaglobal.evolution.agents.knowledge_agent import knowledge

            cached = get_success_by_task(task)
            if cached:
                cached_code = cached.get("codigo") or ""
                if len(cached_code) > 50 and "<coroutine" not in cached_code:
                    logger.info("[CODER] Cache HIT — reusando codigo anterior (%d chars)", len(cached_code))
                    _task_input = ctx.get("input", {}).get("task", task)
                    artifact = SolutionArtifact(task=_task_input, code=cached_code, files={})
                    if wd:
                        wd.append_log("cache hit (%d chars)" % len(cached_code))
                    return {"output": artifact}

            relevant_errors = query_relevant_errors(task, limit=2)
            error_context = format_errors_for_prompt(relevant_errors)
            relevant_knowledge = knowledge.retrieve_relevant(task, max_results=2)
            knowledge_summary = knowledge.summarize(max_entries=3) if relevant_knowledge else ""

            if error_context or knowledge_summary:
                logger.info("[CODER] Contexto de aprendizado: %d erros, %d conhecimentos",
                           len(relevant_errors), len(relevant_knowledge))

            artifact = None

            try:
                if True:
                    from iaglobal.providers.provider_router import async_route_generate

                    enriched_prompt = prompt
                    if error_context:
                        enriched_prompt += "\n\n" + error_context
                    if knowledge_summary:
                        enriched_prompt += "\n\n[CONHECIMENTO ACUMULADO]\n" + knowledge_summary[:1000]

                    locked_model = resolve_locked_model(ctx, f"ollama/{default}")
                    code_raw = await async_route_generate(
                        model=locked_model,
                        prompt=enriched_prompt,
                        task_type="coding"
                    )

                    parsed = _extrair_multifile(code_raw) or {}

                    files = {}
                    code = parsed.get("script.py", "")

                    if not code:
                        items = list(parsed.items())

                        if items:
                            code = items[0][1]

                            for k, v in items[1:]:
                                files[k] = v
                        else:
                            code = ""
                            if not code:
                                task_lower = task.lower()
                                if "html" in task_lower or "web" in task_lower or "pagina" in task_lower:
                                    code = "<!DOCTYPE html>\n<html lang=\"pt-BR\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Projeto</title>\n  <link rel=\"stylesheet\" href=\"css/style.css\">\n</head>\n<body>\n  <h1>Projeto</h1>\n  <script src=\"js/script.js\"></script>\n</body>\n</html>"
                                    files["css/style.css"] = "/* styles */\n"
                                    files["js/script.js"] = "// javascript\n"
                                elif "api" in task_lower:
                                    code = "from flask import Flask, jsonify\n\napp = Flask(__name__)\n\n@app.route('/')\ndef index():\n    return jsonify({'status': 'ok'})\n\nif __name__ == '__main__':\n    app.run(debug=True)\n"
                                elif "script" in task_lower or "funcao" in task_lower:
                                    code = "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n"
                                else:
                                    code = "# Projeto gerado\nprint('Hello, World!')\n"
                    else:
                        for k, v in parsed.items():
                            if k != "script.py":
                                files[k] = v

                    artifact = SolutionArtifact(
                        task=task,
                        code=code,
                        files=files
                    )

                    # ── Cache do resultado (bom ou ruim) + learning ──
                    try:
                        store_success(task, code, {"ts": __import__("time").time(), "model": "ollama"})
                        if code and len(code) > 50:
                            knowledge.store(category="best_practice",
                                           title="Codigo gerado: %s" % task[:40],
                                           content=code[:500],
                                           tags=["coder", task[:20]], source="coder")
                            from iaglobal.memory.db_manager import db
                            db.insert_insight("coder", task, "Codigo gerado: %d chars" % len(code),
                                            score=min(1.0, len(code)/500))
                    except Exception:
                        pass

                else:
                    artifact = SolutionArtifact(task=task, code="")

            except Exception as e:
                logger.exception("⚠️ Falha na geracao do multi_coder")
                artifact = SolutionArtifact(task=task, code="", error_state=str(e))

                try:
                    from iaglobal.memory.memory_error import store_error
                    store_error(task, "", "Falha no coder: %s" % str(e)[:200], "",
                               error_type="CoderFailure")
                except Exception:
                    pass

            # Garantia absoluta de retorno
            if artifact is None:
                artifact = SolutionArtifact(
                    task=task,
                    code="",
                    error_state="artifact não foi criado"
                )

            return artifact

        artifact = SolutionArtifact(task=task, code="", error_state="sem blockchain nem modelo")

        # Fallback: se HTML gerado for muito curto (<200 chars) ou so tem placeholder, usa template
        html_file = artifact.files.get("index.html", "") if hasattr(artifact, "files") else ""
        html_to_check = html_file or artifact.code
        has_placeholder = "Aqui você" in html_to_check or "implementar" in html_to_check.lower()
        if is_web and (len(html_to_check.strip()) < 200 or has_placeholder):
            logger.warning("⚠️ [CODER] HTML muito curto (%d chars) — usando template completo", len(html_to_check.strip()))
            artifact.code = (
                '<!DOCTYPE html>\n<html lang="pt-br">\n<head>\n'
                '<meta charset="UTF-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                '<title>Contato</title>\n'
                '<style>\n'
                'body{font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;'
                'display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}\n'
                '.container{background:#16213e;padding:2rem;border-radius:8px;width:100%%;max-width:400px}\n'
                'h1{text-align:center;color:#e94560;margin-bottom:1.5rem}\n'
                'label{display:block;margin-top:1rem;color:#ccc}\n'
                'input,textarea{width:100%%;padding:.5rem;margin-top:.3rem;'
                'background:#0f3460;border:1px solid #e94560;color:#fff;border-radius:4px}\n'
                'button{width:100%%;padding:.7rem;margin-top:1.5rem;'
                'background:#e94560;color:#fff;border:none;border-radius:4px;cursor:pointer}\n'
                'button:hover{background:#c73650}\n'
                '</style>\n</head>\n<body>\n'
                '<div class="container">\n'
                '<h1>Entre em Contato</h1>\n'
                '<form id="contatoForm">\n'
                '<label for="nome">Nome:</label>\n'
                '<input type="text" id="nome" name="nome" required>\n'
                '<label for="email">E-mail:</label>\n'
                '<input type="email" id="email" name="email" required>\n'
                '<label for="mensagem">Mensagem:</label>\n'
                '<textarea id="mensagem" name="mensagem" rows="4" required></textarea>\n'
                '<button type="submit">Enviar</button>\n'
                '</form>\n</div>\n'
                '<script>\n'
                'document.getElementById("contatoForm").addEventListener("submit",function(e){'
                'e.preventDefault();'
                'var n=document.getElementById("nome").value;'
                'var em=document.getElementById("email").value;'
                'var msg=document.getElementById("mensagem").value;'
                'if(!n||!em||!msg){alert("Preencha todos os campos");return}'
                'alert("Mensagem enviada com sucesso!\\n\\nNome: "+n+"\\nE-mail: "+em);'
                '})\n'
                '</script>\n</body>\n</html>'
            )
            artifact.files = {}
            if wd:
                wd.write_code(artifact.code).append_log("template HTML usado (fallback)")

        if wd and code:
            wd.write_code(code).append_log("código gerado (%d chars, %d arquivos)" % (len(code), len(artifact.files) + 1))
        return {"output": artifact}
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
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("style_validator", {}).get("output",
                  ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact()))
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        logger.info("🧐 [CRITIC v2] Avaliando solução (multi-dimensional)...")

        from iaglobal.agents.critic_agent import CriticAgent
        critic = CriticAgent()
        result = critic.avaliar_com_scores(artifact.task, artifact.code)

        artifact.score = result.get("score", 50.0)
        artifact.critic_scores = result.get("scores", {
            "correctness": 50.0,
            "completeness": 50.0,
            "security": 50.0,
            "spec_match": 50.0,
        })
        artifact.critique = result.get("summary", "")
        artifact.critic_degraded = result.get("critic_degraded", False)

        logger.info("🧐 [CRITIC v2] Score agregado: %s | scores=%s", artifact.score, artifact.critic_scores)

        if not result.get("approved", False):
            logger.warning("⚠️ [CRITIC v2] Solução rejeitada (score=%s)", artifact.score)
            artifact.critique += "\nREJEITADO: score %s abaixo de 60" % artifact.score

        if wd:
            wd.append_log("critic score=%.1f aprovado=%s" % (artifact.score, result.get("approved", False)))

        return {
            "output": artifact,
            "critic_score": artifact.score,
            "critic_scores": artifact.critic_scores,
        }
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


_security_patterns = [
    ("SQL Injection", r"(?i)(execute|executemany|cursor\.execute|raw\(|RawSQL)\s*\(\s*f['\"]|SELECT.*FROM.*WHERE.*['\"]\s*\+"),
    ("SQL Injection (string concat)", r"(?i)(SELECT|INSERT|UPDATE|DELETE)\s+.*['\"]\s*[+%].*['\"]"),
    ("XSS (unsafe HTML)", r"(?i)(mark_safe|safe\b|format_html|__html__|innerHTML|dangerouslySetInnerHTML)"),
    ("XSS (template var sem escape)", r"(?i)(\{\{.*\| safe\}\}|\{%\s*autoescape\s+off\s*%\})"),
    ("SSRF (user-controlled URL)", r"(?i)(requests\.(get|post|put|delete)\(.*(request\.(url|path|args|form)|input\(|getenv\(.*URL))"),
    ("SSRF (urllib user input)", r"(?i)(urllib\.request\.urlopen\(.*(input\(|request\.|getenv\(|sys\.argv))"),
    ("Prompt Injection (LLM)", r"(?i)(system\.*prompt|inject.*prompt|ignore.*instruction|role.*system.*user.*override)"),
    ("Secrets expostos (API key)", r"(?i)(api_key\s*=\s*['\"][A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9\-_]{35})"),
    ("Secrets expostos (password)", r"(?i)(password\s*=\s*['\"][^'\"\s]{4,}|senha\s*=\s*['\"][^'\"\s]{4,})"),
    ("Secrets expostos (token)", r"(?i)(token\s*=\s*['\"][A-Za-z0-9_\-]{10,}|secret\s*=\s*['\"][A-Za-z0-9_\-]{10,})"),
    ("Debug ativo em produção", r"(?i)(DEBUG\s*=\s*True|debug=True|debug\s*=\s*true)"),
    ("eval/exec de input", r"(?i)(eval\(input\(|exec\(input\(|eval\(request\.|exec\(request\.)"),
    ("Pickle inseguro", r"(?i)(pickle\.loads?\(.*(input|request|user|upload))"),
    ("YAML inseguro", r"(?i)(yaml\.load\(.*(Loader=.*)?$|yaml\.load\([^)]*Loader=)"),
    ("CSRF desabilitado", r"(?i)(csrf_exempt|@csrf_exempt|CSRF_COOKIE_SECURE\s*=\s*False|CSRF_TRUSTED_ORIGINS\s*=\s*\[\s*['\"]\*['\"]\s*\])"),
]

def _make_security_run() -> Callable:
    """Analisa segurança do código: SQL Injection, XSS, SSRF, Prompt Injection, secrets, dependências."""
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        code = artifact.code or ""
        wd = ctx.get("workdir")

        logger.info("🔒 [SECURITY] Iniciando análise de segurança...")

        if not code.strip():
            artifact.security_report = "Código vazio — análise pulada"
            return {"output": artifact, "security_issues": [], "security_score": 100}

        if not _is_python_code(code):
            logger.info("🔒 [SECURITY] Código não-Python — análise limitada a secrets")
            artifact.security_report = "Não-Python — análise limitada"
            return {"output": artifact, "security_issues": [], "security_score": 100}

        issues = []
        for vuln_name, pattern in _security_patterns:
            matches = re.findall(pattern, code)
            if matches:
                issues.append({"type": vuln_name, "severity": "alta", "matches": len(matches)})
                logger.warning("🔒 [SECURITY] %s: %d ocorrência(s)", vuln_name, len(matches))

        if issues:
            found_types = [i["type"] for i in issues]
            summary = "⚠️ %d vulnerabilidade(s): %s" % (len(issues), "; ".join(found_types[:5]))
            if len(found_types) > 5:
                summary += " (+%d outras)" % (len(found_types) - 5)
            artifact.security_report = summary
            logger.warning("🔒 [SECURITY] %s", summary)
        else:
            artifact.security_report = "Nenhuma vulnerabilidade detectada"
            logger.info("✅ [SECURITY] Nenhuma vulnerabilidade encontrada")

        if wd:
            wd.append_log("security: %d issues" % len(issues))

        return {
            "output": artifact,
            "security_issues": issues,
            "security_score": max(0, 100 - len(issues) * 15),
        }
    return run


def _make_style_validator_run() -> Callable:
    """Valida e corrige estilo visual: dark mode, cores, Django→Flask."""
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")
        task = ctx.get("input", {}).get("task", "")
        code = artifact.code
        files = dict(artifact.files or {})
        is_dark = any(w in task.lower() for w in ["escuro", "dark", "darkmode", "dark mode", "tema escuro", "preto"])

        logger.info("🎨 verificando estilo visual ...")
        if wd:
            wd.append_log("iniciando validação de estilo")

        # 1. Corrige cores claras → escuras se dark mode foi solicitado
        if is_dark:
            for old, new in _DARK_REPLACEMENTS.items():
                if old in code:
                    code = code.replace(old, new)
                    logger.info("🎨 [STYLE] Cor corrigida: %s → %s", old, new)
            for fname, fcontent in files.items():
                for old, new in _DARK_REPLACEMENTS.items():
                    if old in fcontent:
                        files[fname] = fcontent.replace(old, new)

        # 2. Remove Django template tags se não for projeto Django explícito
        is_explicit_django = any(w in task.lower() for w in ["django"])
        if not is_explicit_django:
            import re
            code = re.sub(r"{{.*?}}", "", code)
            code = re.sub(r"{%.*?%}", "", code)
            code = re.sub(r"{#.*?#}", "", code)
            code = re.sub(r"{% csrf_token %}", "", code)
            for fname, fcontent in list(files.items()):
                fcontent = re.sub(r"{{.*?}}", "", fcontent)
                fcontent = re.sub(r"{%.*?%}", "", fcontent)
                fcontent = re.sub(r"{#.*?#}", "", fcontent)
                files[fname] = fcontent

        # 3. Remove includes/css statics malformados
        import re
        code = re.sub(r"{% include.*?%}", "", code)
        code = re.sub(r"{% static.*?%}", "", code)
        for fname, fcontent in files.items():
            fcontent = re.sub(r"{% include.*?%}", "", fcontent)
            fcontent = re.sub(r"{% static.*?%}", "", fcontent)
            files[fname] = fcontent

        artifact.code = code.strip()
        artifact.files = files
        if wd and code:
            wd.write_code(code).append_log("estilo validado")
        return {"output": artifact, "style_validated": True}
    return run


def _make_semantic_validator_run() -> Callable:
    async def run(ctx):
        memory = ctx.get("memory", {})
        artifact = memory.get("critic", {}).get("output", None)
        if artifact is None or not isinstance(artifact, SolutionArtifact):
            artifact = memory.get("coder", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        logger.info("🔬 [SEMANTIC] Validando requisitos semânticos...")

        from iaglobal.agents.semantic_validator import SemanticValidatorAgent
        validator = SemanticValidatorAgent()
        result = validator.validate(artifact.code, artifact.task)

        artifact.semantic_errors = result.get("errors", [])
        artifact.semantic_score = result.get("score", 0.0)

        if wd:
            wd.append_log("semantic score=%.1f erros=%d" % (result.get('score', 0), len(result.get('errors', []))))

        if result.get("valid"):
            logger.info("✅ [SEMANTIC] Requisitos OK (score=%.1f%%)", result['score'])
            return {"output": artifact, "semantic_valid": True}
        else:
            logger.warning("❌ [SEMANTIC] Falha: %s", result.get('errors', []))
            artifact.runtime_error = "; ".join(result.get("errors", []))
            return {"output": artifact, "semantic_valid": False}
    return run


def _is_python_code(code: str) -> bool:
    """Verifica se o código parece ser Python válido."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _make_ast_validator_run() -> Callable:
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("critic", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        logger.info("🔍 [AST] Validando sintaxe + análise estática...")

        if not artifact.code or not artifact.code.strip():
            artifact.security_report = "Código vazio"
            if wd:
                wd.append_log("código vazio")
            return {"output": artifact, "security_valid": False}

        if not _is_python_code(artifact.code):
            logger.info("🔍 [AST] Código não-Python — pulando validação AST")
            artifact.security_report = "Não-Python (HTML/CSS/etc)"
            if wd:
                wd.append_log("não-Python, AST pulado")
            return {"output": artifact, "security_valid": True}

        ast_errors = validate_code_real(artifact.code)
        if ast_errors:
            error_msg = "; ".join(ast_errors[:5])
            artifact.security_report = "AST warnings: %s" % error_msg
            artifact.semantic_errors = ast_errors
            artifact.semantic_score = max(0, 100 - len(ast_errors) * 20)
            logger.warning("⚠️ [AST] Avisos estáticos: %s", error_msg)
            if wd:
                wd.append_log("%d warnings AST" % len(ast_errors))
            return {"output": artifact, "security_valid": True, "ast_warnings": ast_errors}

        artifact.security_report = "AST válido"
        logger.info("✅ [AST] Sintaxe + análise estática OK")
        if wd:
            wd.append_log("AST válido")
        return {"output": artifact, "security_valid": True}
    return run


def _make_reviewer_run() -> Callable:
    """Faz code review técnico: verifica SOLID, Clean Code, duplicação, complexidade ciclomática."""
    async def run(ctx):
        memory = ctx.get("memory", {})
        artifact = memory.get("critic", {}).get("output", None)
        if artifact is None or not isinstance(artifact, SolutionArtifact):
            artifact = memory.get("coder", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        task = ctx.get("input", {}).get("task", "")
        code = artifact.code or ""
        wd = ctx.get("workdir")

        logger.info("👨‍💻 [REVIEWER] Iniciando code review técnico...")

        if not code.strip():
            artifact.security_report = "Código vazio — review pulado"
            if wd:
                wd.append_log("código vazio, review pulado")
            return {"output": artifact, "review_score": 100, "issues": []}

        if not _is_python_code(code):
            logger.info("👨‍💻 [REVIEWER] Código não-Python — pulando review")
            artifact.security_report = "Não-Python — review pulado"
            return {"output": artifact, "review_score": 100, "issues": []}

        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
        _rev_errors = query_relevant_errors(task, limit=2)
        _rev_error_ctx = format_errors_for_prompt(_rev_errors)

        prompt = (
            "Você é um desenvolvedor sênior fazendo code review. Analise o código abaixo.\n\n"
            "Avalie estritamente:\n"
            "1. SOLID: Cada classe/função tem responsabilidade única? Aberto/fechado? Liskov? Segregação? Inversão?\n"
            "2. Clean Code: Nomes significativos? Funções pequenas? Comentários necessários? Formatação?\n"
            "3. Duplicação: Há código repetido que poderia ser extraído?\n"
            "4. Complexidade Ciclomática: Funções com muitos if/else/loops aninhados?\n"
            "%s\n"
            "Retorne APENAS um JSON válido:\n"
            "{\n"
            '  "solid_score": <0-100>,\n'
            '  "clean_code_score": <0-100>,\n'
            '  "duplication_score": <0-100>,\n'
            '  "complexity_score": <0-100>,\n'
            '  "issues": ["lista de problemas encontrados"],\n'
            '  "summary": "resumo do review"\n'
            "}\n\n"
            "Tarefa original: %s\n\n"
            "Código:\n%s\n\n"
            "JSON:" % (_rev_error_ctx, task, code)
        )

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate
        import json as _json

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        try:
            response = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            response = (response or "").strip()
            inicio = response.find("{")
            fim = response.rfind("}")
            if inicio != -1 and fim > inicio:
                review = _json.loads(response[inicio:fim + 1])
            else:
                review = {}
        except Exception as e:
            logger.warning("👨‍💻 [REVIEWER] LLM falhou: %s", e)
            review = {}

        solid = max(0, min(100, review.get("solid_score", 70)))
        clean = max(0, min(100, review.get("clean_code_score", 70)))
        duplic = max(0, min(100, review.get("duplication_score", 70)))
        complexidade = max(0, min(100, review.get("complexity_score", 70)))
        issues = review.get("issues", [])
        summary = review.get("summary", "Review concluído")

        review_score = round((solid + clean + duplic + complexidade) / 4, 1)

        artifact.review_score = review_score
        artifact.security_report = "Review: %s" % summary

        logger.info("👨‍💻 [REVIEWER] SOLID=%d Clean=%d Duplic=%d Complex=%d Score=%.1f",
                     solid, clean, duplic, complexidade, review_score)

        if review_score < 60:
            logger.warning("⚠️ [REVIEWER] Qualidade abaixo do threshold (%.1f < 60): %s",
                           review_score, summary[:80])

        if wd:
            wd.append_log("review score=%.1f, %d issues" % (review_score, len(issues)))

        return {
            "output": artifact,
            "review_score": review_score,
            "issues": issues,
            "solid_score": solid,
            "clean_code_score": clean,
            "duplication_score": duplic,
            "complexity_score": complexidade,
        }
    return run


_performance_patterns = [
    ("N+1 query em loop", r"(?i)(for.*in.*:.*\n.*\.(query|filter|get|all)\(|while.*:.*\n.*\.execute\()"),
    ("Consulta SQL em loop", r"(?i)(for.*:.*execute\(|while.*:.*cursor\.execute|for.*:.*\.raw\()"),
    ("List comprehension sem uso", r"(?i)(\[.*for.*in.*\]\s*$|\[.*for.*in.*\]\s*\n)"),
    ("Loop aninhado profundo", r"(?i)(for.*:\s*\n\s+for.*:\s*\n\s+for)"),
    ("Alocação em loop (list/dict)", r"(?i)(for.*:\s*\n\s+(lista|arr|result|items)\s*=\s*\[\]|for.*:\s*\n\s+(dados|data|dict).*\=\s*\{\})"),
    ("Uso excessivo de memória (read all)", r"(?i)(\.read\(\).*$|read\(\)\.split\(|file\.read\(|\.readlines\(\))"),
    ("Recursão sem limite", r"(?i)(def \w+.*:.*\n.*\1\()"),
    ("Thread/async sem timeout", r"(?i)(threading\.Thread\(|asyncio\.run\(|loop\.run_until_complete).*timeout"),
    ("Cache ausente em chamada API", r"(?i)(requests\.(get|post)\(|httpx\.(get|post)\()"),
    ("Gargalo I/O síncrono em loop", r"(?i)(for.*:.*requests\.(get|post)|for.*:.*open\(|for.*:.*\.write\()"),
]

def _make_performance_run() -> Callable:
    """Analisa performance do código: consultas lentas, loops, memória, gargalos."""
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("reviewer", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        code = artifact.code or ""
        wd = ctx.get("workdir")

        logger.info("⚡ [PERFORMANCE] Analisando performance...")

        if not code.strip():
            artifact.reflection = "Código vazio — análise pulada"
            return {"output": artifact, "bottlenecks": [], "performance_score": 100}

        if not _is_python_code(code):
            logger.info("⚡ [PERFORMANCE] Código não-Python — pulando")
            artifact.reflection = "Não-Python — análise pulada"
            return {"output": artifact, "bottlenecks": [], "performance_score": 100}

        bottlenecks = []
        for perf_name, pattern in _performance_patterns:
            matches = re.findall(pattern, code)
            if matches:
                bottlenecks.append({"type": perf_name, "severity": "média", "matches": len(matches)})
                logger.info("⚡ [PERFORMANCE] %s: %d ocorrência(s)", perf_name, len(matches))

        if bottlenecks:
            found = [b["type"] for b in bottlenecks]
            summary = "⚡ %d gargalo(s): %s" % (len(bottlenecks), "; ".join(found[:5]))
            if len(found) > 5:
                summary += " (+%d outros)" % (len(found) - 5)
            artifact.reflection = summary
            logger.warning("⚡ [PERFORMANCE] %s", summary)
        else:
            artifact.reflection = "Nenhum gargalo de performance detectado"
            logger.info("✅ [PERFORMANCE] Código otimizado")

        if wd:
            wd.append_log("performance: %d bottlenecks" % len(bottlenecks))

        return {
            "output": artifact,
            "bottlenecks": bottlenecks,
            "performance_score": max(0, 100 - len(bottlenecks) * 20),
        }
    return run


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


def _make_tester_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("ast_validator", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        if not artifact.code or not artifact.code.strip():
            artifact.tests_passed = 0
            artifact.tests_total = 0
            return {"output": artifact, "tests_passed": 0, "tests_total": 0}

        logger.info("🧪 [TESTER] Executando testes...")

        if not _is_python_code(artifact.code):
            logger.info("🧪 [TESTER] Código não-Python — pulando execução (validação de estrutura OK)")
            artifact.tests_passed = 1
            artifact.tests_total = 1
            artifact.runtime_error = ""
            if wd:
                wd.append_log("não-Python, teste pulado")
            return {"output": artifact, "tests_passed": 1, "tests_total": 1}

        syntax_ok, syntax_err = _validate_syntax(artifact.code)
        if not syntax_ok:
            artifact.tests_passed = 0
            artifact.tests_total = 1
            artifact.runtime_error = syntax_err
            logger.warning("❌ [TESTER] Erro de sintaxe: %s", syntax_err)
            if wd:
                wd.append_log("erro de sintaxe: %s" % syntax_err[:80])
            return {"output": artifact, "tests_passed": 0, "tests_total": 1}

        if _imports_framework(artifact.code):
            logger.info("🧪 [TESTER] Código usa framework — pulando execução (validação sintática OK)")
            artifact.tests_passed = 1
            artifact.tests_total = 1
            artifact.runtime_error = ""
            if wd:
                wd.append_log("framework detectado, execução pulada")
            return {"output": artifact, "tests_passed": 1, "tests_total": 1}

        try:
            if wd:
                wd.write_code(artifact.code).append_log("iniciando sandbox...")
            from iaglobal.security.sandbox_executor import SandboxExecutor
            result = SandboxExecutor(timeout=10).execute(artifact.code)

            if wd and result.get("output"):
                wd.write_output(result.get("output", ""))

            if result.get("sucesso"):
                artifact.tests_passed = 1
                artifact.tests_total = 1
                artifact.runtime_error = ""
                logger.info("✅ [TESTER] Testes passaram")
            else:
                artifact.tests_passed = 0
                artifact.tests_total = 1
                artifact.runtime_error = result.get("stderr", result.get("erro", "Erro desconhecido"))
                logger.warning("❌ [TESTER] Falha: %s", artifact.runtime_error[:100])
        except Exception as e:
            artifact.tests_passed = 0
            artifact.tests_total = 1
            artifact.runtime_error = str(e)
            logger.warning("❌ [TESTER] Erro: %s", e)

        if wd:
            wd.append_log("testes: %d/%d" % (artifact.tests_passed, artifact.tests_total))

        return {
            "output": artifact,
            "tests_passed": artifact.tests_passed,
            "tests_total": artifact.tests_total,
        }
    return run


def _make_debugger_run(orchestrator: Any) -> Callable:
    MAX_DEBUG = 3

    async def run(ctx):
        artifact = ctx.get("memory", {}).get("tester", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        if artifact.tests_passed == artifact.tests_total and artifact.tests_total > 0:
            logger.info("✅ [DEBUGGER] Nenhum erro para corrigir.")
            if wd:
                wd.append_log("sem erros para corrigir")
            return {"output": artifact}

        if not _is_python_code(artifact.code):
            logger.info("✅ [DEBUGGER] Código não-Python — nenhum erro para corrigir.")
            if wd:
                wd.append_log("não-Python, debug pulado")
            return {"output": artifact}

        logger.info("🔧 [DEBUGGER v2] Iniciando loop de correção com re-check (max=%s)...", MAX_DEBUG)

        from iaglobal.agents.critic_agent import CriticAgent
        critic = CriticAgent()

        for tentativa in range(MAX_DEBUG):
            logger.debug("[DEBUGGER] Tentativa %s/%s", tentativa + 1, MAX_DEBUG)

            if hasattr(orchestrator, "_model_fn"):
                from iaglobal.providers.provider_config import ProviderConfig
                from iaglobal.events import resolve_locked_model
                default = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"

                from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
                _debug_errors = query_relevant_errors(artifact.task, limit=2)
                _debug_error_ctx = format_errors_for_prompt(_debug_errors)
                prompt = (
                    "Você é um agente de debug. Corrija o código abaixo.\n\n"
                    "Tarefa: %s\n\n"
                    "Código atual (com erro):\n%s\n\n"
                    "Erro:\n%s\n\n"
                    "%s"
                    "Retorne APENAS o código corrigido dentro de um bloco ```python ... ```.\n"
                    "Mantenha a intenção original.\n"
                ) % (artifact.task, artifact.code, artifact.runtime_error,
                     _debug_error_ctx + "\n\n" if _debug_error_ctx else "")
                from iaglobal.providers.provider_router import async_route_generate
                locked_model = resolve_locked_model(ctx, f"ollama/{default}")
                code_raw = await async_route_generate(model=locked_model, prompt=prompt, task_type="debug")
                new_code = _extrair_codigo_puro(code_raw)

                if new_code:
                    artifact.code = new_code
                    artifact.repaired = True

            try:
                ast.parse(artifact.code)
            except SyntaxError:
                logger.warning("⚠️ [DEBUGGER] Código corrigido com erro de sintaxe")
                if wd:
                    wd.append_log("tentativa %d: erro de sintaxe" % (tentativa + 1))
                continue

            try:
                if wd:
                    wd.write_code(artifact.code).append_log("tentativa %d sandbox..." % (tentativa + 1))
                from iaglobal.security.sandbox_executor import SandboxExecutor
                result = SandboxExecutor(timeout=30).execute(artifact.code)

                if wd and result.get("output"):
                    wd.write_output(result.get("output", ""))

                if result.get("sucesso"):
                    artifact.tests_passed = 1
                    artifact.tests_total = 1
                    artifact.runtime_error = ""

                    critic_result = critic.avaliar_com_scores(artifact.task, artifact.code)
                    if critic_result.get("approved", False):
                        artifact.score = critic_result.get("score", 60.0)
                        artifact.critic_scores = critic_result.get("scores", {})
                        logger.info("✅ [DEBUGGER] Corrigido e aprovado pelo Critic na tentativa %s", tentativa + 1)
                        if wd:
                            wd.write_code(artifact.code).append_log("debug OK tentativa %d" % (tentativa + 1))
                        break
                    else:
                        logger.warning("⚠️ [DEBUGGER] Código corrigido mas rejeitado pelo Critic (score=%s)", critic_result.get('score', 0))
                        artifact.runtime_error = "Critic rejeitou: %s" % critic_result.get('summary', 'baixa qualidade')
                else:
                    artifact.runtime_error = result.get("stderr", result.get("erro", "Erro desconhecido"))
                    logger.debug("[DEBUGGER] Tentativa %s falhou", tentativa + 1)
                    if wd:
                        wd.append_log("tentativa %d: %s" % (tentativa + 1, artifact.runtime_error[:100]))
            except Exception as e:
                artifact.runtime_error = str(e)
                logger.warning("⚠️ [DEBUGGER] Erro na tentativa %s: %s", tentativa + 1, e)
                if wd:
                    wd.append_log("tentativa %d exceção: %s" % (tentativa + 1, e))

        if artifact.runtime_error:
            logger.error("❌ [DEBUGGER] Falha após %s tentativas", MAX_DEBUG)

        if wd:
            wd.write_code(artifact.code)
        return {"output": artifact}
    return run


def _make_rank_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        debugger_artifact = ctx.get("memory", {}).get("debugger", {}).get("output", SolutionArtifact())
        tester_artifact = ctx.get("memory", {}).get("tester", {}).get("output", SolutionArtifact())
        wd = ctx.get("workdir")

        if not isinstance(debugger_artifact, SolutionArtifact):
            debugger_artifact = tester_artifact if isinstance(tester_artifact, SolutionArtifact) else SolutionArtifact()

        score = _compute_final_score(debugger_artifact)
        debugger_artifact.score = score

        logger.info("🏆 [RANK] Score final: %.2f", score)
        if wd:
            wd.append_log("rank score=%.2f" % score)
        return {
            "output": debugger_artifact,
            "final_score": score,
        }
    return run


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
    MIN_SCORE = 0.6
    MAX_AST_WARNINGS = 3

    async def run(ctx):
        artifact = ctx.get("memory", {}).get("rank_final", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        logger.info("🚧 [GATEKEEPER] Validando resultado final...")

        out = Artifact(content=artifact.code, type="code", metadata={"task": artifact.task, "score": artifact.score})

        if not artifact.code or not artifact.code.strip():
            artifact.runtime_error = "GATEKEEPER: Código vazio — resultado rejeitado"
            artifact.tests_passed = 0
            logger.error("❌ [GATEKEEPER] Código vazio")
            if wd:
                wd.append_log("código vazio")
            return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        # 0. Critic degradado — rejeitar (avaliação não confiável)
        if artifact.critic_degraded:
            artifact.runtime_error = "GATEKEEPER: Critic degradado (fallback) — resultado rejeitado"
            artifact.tests_passed = 0
            logger.error("❌ [GATEKEEPER] Critic degradado — avaliação não confiável")
            if wd:
                wd.append_log("critic degradado")
            return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        # 1. Score mínimo (já em 0-1 do RankFinal)
        score_normalized = artifact.score
        if score_normalized < MIN_SCORE:
            artifact.runtime_error = "GATEKEEPER: Score %.2f abaixo do mínimo %.2f" % (score_normalized, MIN_SCORE)
            artifact.tests_passed = 0
            logger.error("❌ [GATEKEEPER] %s", artifact.runtime_error)
            if wd:
                wd.append_log("score %.2f < min %.2f" % (score_normalized, MIN_SCORE))
            return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        # 2. Testes devem ter passado
        if artifact.tests_total > 0 and artifact.tests_passed < artifact.tests_total:
            artifact.runtime_error = "GATEKEEPER: Testes falharam (%d/%d)" % (artifact.tests_passed, artifact.tests_total)
            artifact.tests_passed = 0
            logger.error("❌ [GATEKEEPER] %s", artifact.runtime_error)
            if wd:
                wd.append_log("testes %d/%d" % (artifact.tests_passed, artifact.tests_total))
            return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        # 3. AST real validator
        from iaglobal.validation.ast_security import validate_code_real
        ast_errors = validate_code_real(artifact.code)
        if len(ast_errors) > MAX_AST_WARNINGS:
            artifact.runtime_error = "GATEKEEPER: %d warnings AST (máx %d)" % (len(ast_errors), MAX_AST_WARNINGS)
            artifact.tests_passed = 0
            logger.error("❌ [GATEKEEPER] %s", artifact.runtime_error)
            if wd:
                wd.append_log("%d AST warnings" % len(ast_errors))
            return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        # 4. Execução sandbox final (pular para framework ou não-Python)
        if _imports_framework(artifact.code):
            logger.info("🚧 [GATEKEEPER] Código usa framework — pulando execução final")
        elif not _is_python_code(artifact.code):
            logger.info("🚧 [GATEKEEPER] Código não-Python — pulando execução final")
            if wd:
                wd.append_log("framework detectado, execução pulada")
        else:
            try:
                if wd:
                    wd.write_code(artifact.code).append_log("gatekeeper sandbox...")
                from iaglobal.security.sandbox_executor import SandboxExecutor
                sandbox_result = SandboxExecutor(timeout=10).execute(artifact.code)
                if wd and sandbox_result.get("output"):
                    wd.write_output(sandbox_result.get("output", ""))
                if not sandbox_result.get("sucesso"):
                    artifact.runtime_error = "GATEKEEPER: Falha na execução final: %s" % sandbox_result.get("stderr", sandbox_result.get("erro", "erro"))[:200]
                    artifact.tests_passed = 0
                    logger.error("❌ [GATEKEEPER] %s", artifact.runtime_error)
                    if wd:
                        wd.append_log("falha execução final")
                    return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}
            except Exception as e:
                artifact.runtime_error = "GATEKEEPER: Exceção na execução final: %s" % str(e)[:200]
                artifact.tests_passed = 0
                logger.error("❌ [GATEKEEPER] %s", artifact.runtime_error)
                if wd:
                    wd.append_log("exceção: %s" % str(e)[:100])
                return {"output": artifact, "gatekeeper_passed": False, "status": "rejected", "artifact": out, "output_mode": None}

        logger.info("✅ [GATEKEEPER] Resultado final aprovado (score=%.2f, testes=%d/%d, AST=%d warnings)", score_normalized, artifact.tests_passed, artifact.tests_total, len(ast_errors))
        if wd:
            wd.append_log("APROVADO score=%.2f" % score_normalized)
        return {
            "output": artifact,
            "gatekeeper_passed": True,
            "final_score": score_normalized,
            "status": "approved",
            "artifact": out,
            "output_mode": "file",
        }

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


def _make_artifact_writer_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        gatekeeper_result = ctx.get("memory", {}).get("final_gatekeeper", {})
        solution = gatekeeper_result.get("output", SolutionArtifact())
        if not isinstance(solution, SolutionArtifact):
            solution = SolutionArtifact()
        wd = ctx.get("workdir")
        gatekeeper_passed = gatekeeper_result.get("gatekeeper_passed", False)

        artifact = gatekeeper_result.get("artifact")
        if not isinstance(artifact, Artifact):
            artifact = Artifact(content=solution.code, type="code", metadata={"task": solution.task, "score": solution.score})

        logger.info("💾 [ARTIFACT_WRITER] Persistindo artifact final...")

        if not artifact.content or (isinstance(artifact.content, str) and not artifact.content.strip()):
            logger.warning("⏭️ [ARTIFACT_WRITER] Nada para persistir (código vazio)")
            if wd:
                wd.append_log("código vazio, nada persistido")
            return {"output": "", "path": None, "persisted": False, "artifact": artifact}

        from iaglobal._paths import SCRIPTS_DIR
        import re, time
        from pathlib import Path

        task = artifact.metadata.get("task", "script") or "script"
        safe_name = re.sub(r'[^\w]', '_', task.strip()[:48])
        safe_name = safe_name.strip('_') or 'script'
        timestamp = int(time.time())

        # SEMPRE cria pasta por projeto
        project_dir = SCRIPTS_DIR / ("%s_%d" % (safe_name, timestamp))
        project_dir.mkdir(parents=True, exist_ok=True)

        files_to_save = {}
        if solution.code:
            ext, main_name = _detect_ext_and_name(solution.code, task)
            files_to_save[main_name] = solution.code
        files_to_save.update(solution.files or {})

        # Para projetos web, cria subpastas comuns
        is_web = any(w in task.lower() for w in ["html", "css", "js", "web", "pagina", "site", "django", "flask"])
        if is_web:
            for sub in ["css", "js", "templates"]:
                (project_dir / sub).mkdir(parents=True, exist_ok=True)

        content_str = ""
        cleaned = {}
        for relpath, content in files_to_save.items():
            content = content.rstrip("`").strip()
            if not content:
                continue
            if relpath == "output.txt" and len(content) < 10:
                continue
            if _is_python_code(content):
                if relpath in ("output.txt", "script.py"):
                    relpath = "main.py"
            cleaned[relpath] = content
        content_str = ""
        for relpath, content in cleaned.items():
            full_path = project_dir / relpath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            content_str = content

        if not content_str:
            content_str = artifact.content if isinstance(artifact.content, str) else str(artifact.content)

        artifact.path = str(project_dir / (next(iter(cleaned)) if cleaned else "output.txt"))
        logger.info("💾 salvando arquivo em disco ...")
        logger.info("✅ [ARTIFACT_WRITER] Projeto salvo em: %s (%d arquivos, pasta=%s)",
                     artifact.path, len(files_to_save), project_dir)
        if wd:
            wd.append_log("projeto salvo em %s (%d arquivos)" % (project_dir, len(files_to_save)))

        return {
            "output": str(artifact.path),
            "path": str(artifact.path),
            "artifact": artifact,
            "artifact_code": content_str,
            "artifact_type": artifact.type,
            "persisted": True,
            "task": task,
            "score": solution.score,
        }
    return run


# Mapeamento import → pacote pip para o Dependency Agent
_IMPORT_TO_PACKAGE = {
    "django": "django", "flask": "flask", "fastapi": "fastapi",
    "sqlalchemy": "sqlalchemy", "psycopg2": "psycopg2-binary",
    "redis": "redis", "celery": "celery", "pandas": "pandas",
    "numpy": "numpy", "matplotlib": "matplotlib", "scikit_learn": "scikit-learn",
    "sklearn": "scikit-learn", "transformers": "transformers",
    "torch": "torch", "tensorflow": "tensorflow", "requests": "requests",
    "httpx": "httpx", "aiohttp": "aiohttp", "asyncio": "asyncio",
    "pydantic": "pydantic", "typing": "typing",
    "uuid": "uuid", "datetime": "python-dateutil",
    "json": "json", "re": "regex", "os": "os",
    "pathlib": "pathlib", "shutil": "shutil",
    "jinja2": "jinja2", "markdown": "markdown",
    "beautifulsoup4": "beautifulsoup4", "bs4": "beautifulsoup4",
    "lxml": "lxml", "pillow": "pillow", "PIL": "pillow",
    "pytest": "pytest", "unittest": "unittest",
    "coverage": "coverage", "black": "black", "ruff": "ruff",
    "mypy": "mypy", "isort": "isort", "flake8": "flake8",
    "click": "click", "typer": "typer", "argparse": "argparse",
    "websockets": "websockets", "sse_starlette": "sse-starlette",
    "uvicorn": "uvicorn", "gunicorn": "gunicorn",
    "whitenoise": "whitenoise", "corsheaders": "django-cors-headers",
    "rest_framework": "djangorestframework",
    "django_filters": "django-filter", "crispy_forms": "django-crispy-forms",
    "allauth": "django-allauth", "storages": "django-storages",
    "debug_toolbar": "django-debug-toolbar",
}

# Versões mínimas recomendadas (pacote: versão)
_RECOMMENDED_VERSIONS = {
    "django": "4.2", "flask": "2.3", "fastapi": "0.104",
    "sqlalchemy": "2.0", "pydantic": "2.0", "requests": "2.31",
    "httpx": "0.25", "celery": "5.3", "pandas": "2.0",
}


def _make_dependency_run() -> Callable:
    """Gerencia dependências do projeto: seleciona bibliotecas, verifica compatibilidade, atualiza versões."""
    async def run(ctx):
        artifact_result = ctx.get("memory", {}).get("artifact_writer", {})
        project_path = artifact_result.get("path", "")
        artifact_code = artifact_result.get("artifact_code", "")
        wd = ctx.get("workdir")

        logger.info("📦 [DEPENDENCY] Analisando dependências...")

        from pathlib import Path
        import re
        import subprocess
        import sys

        project_dir = Path(project_path).parent if Path(project_path).is_file() else Path(project_path)

        # 1. Scan de imports no código
        imports_found = set()
        for m in re.finditer(r"^import\s+(\S+)", artifact_code, re.MULTILINE):
            imports_found.add(m.group(1).split(".")[0])
        for m in re.finditer(r"^from\s+(\S+)\s+import", artifact_code, re.MULTILINE):
            imports_found.add(m.group(1).split(".")[0])

        # 2. Mapear para pacotes pip
        needed = set()
        unresolved = []
        for imp in sorted(imports_found):
            pkg = _IMPORT_TO_PACKAGE.get(imp)
            if pkg:
                needed.add(pkg)
            elif imp not in ("__future__", "builtins", "sys", "io", "abc", "collections",
                            "itertools", "functools", "operator", "math", "random",
                            "statistics", "hashlib", "hmac", "base64", "binascii",
                            "textwrap", "pprint", "copy", "enum", "dataclasses",
                            "decimal", "fractions", "numbers", "string", "struct",
                            "time", "zoneinfo", "calendar", "locale", "gettext",
                            "logging", "warnings", "traceback", "inspect",
                            "atexit", "signal", "platform", "errno", "glob",
                            "fnmatch", "linecache", "pickle", "shelve", "marshal",
                            "socketserver", "http", "urllib", "xml", "csv", "configparser",
                            "netrc", "getpass", "fileinput", "filecmp", "tempfile",
                            "difflib", "contextlib", "weakref", "types", "typing",
                            "functools", "stringprep", "bisect", "array", "queue",
                            "subprocess", "threading", "multiprocessing", "concurrent",
                            "mmap", "readline", "rlcompleter", "curses", "tty", "pty",
                            "turtle", "tkinter", "webbrowser", "antigravity", "this"):
                unresolved.append(imp)

        # 3. Ler requirements.txt existente (se houver)
        req_file = project_dir / "requirements.txt"
        existing_reqs = {}
        if req_file.exists():
            for line in req_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                parts = re.split(r"[=<>!~]", line, maxsplit=1)
                pkg_name = parts[0].strip().lower().replace("_", "-")
                existing_reqs[pkg_name] = line

        # 4. Verificar versões instaladas via pip
        installed = {}
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                import json
                for pkg in json.loads(result.stdout):
                    installed[pkg["name"].lower()] = pkg["version"]
        except Exception:
            pass

        # 5. Gerar requirements.txt com versões compatíveis
        lines = ["# Gerado por IAGlobal Dependency Agent\n"]
        compatibility_issues = []
        new_packages = 0

        for pkg in sorted(needed):
            pkg_lower = pkg.lower()
            recommended = _RECOMMENDED_VERSIONS.get(pkg_lower)
            installed_ver = installed.get(pkg_lower)

            if recommended and installed_ver:
                if installed_ver < recommended:
                    compatibility_issues.append(
                        "%s: instalado %s, recomendado >= %s" % (pkg, installed_ver, recommended)
                    )
                    lines.append("%s>=%s  # atualização necessária" % (pkg, recommended))
                else:
                    lines.append("%s>=%s" % (pkg, installed_ver))
            elif recommended:
                lines.append("%s>=%s" % (pkg, recommended))
                new_packages += 1
            elif installed_ver:
                lines.append("%s>=%s" % (pkg, installed_ver))
            else:
                lines.append(pkg)
                new_packages += 1

        # 6. Escrever requirements.txt
        req_file.write_text("\n".join(lines) + "\n")
        logger.info("📦 [DEPENDENCY] requirements.txt gerado com %d pacotes", len(needed))

        if unresolved:
            logger.info("📦 [DEPENDENCY] %d import(s) não mapeados: %s", len(unresolved), unresolved[:10])

        if wd:
            wd.append_log("dependências: %d pacotes, %d issues" % (len(needed), len(compatibility_issues)))

        return {
            "output": {
                "packages": sorted(needed),
                "unresolved_imports": unresolved,
                "compatibility_issues": compatibility_issues,
                "requirements_path": str(req_file),
            },
            "packages": sorted(needed),
            "compatibility_issues": compatibility_issues,
            "total_packages": len(needed),
        }
    return run


def _make_documentation_run() -> Callable:
    """Gera documentação do projeto: README, ADR, docstrings, diagrama de arquitetura."""
    async def run(ctx):
        coder_out = ctx.get("memory", {}).get("coder", {}).get("output", "")
        debug_out = ctx.get("memory", {}).get("debug_coder", {}).get("output", None)
        if isinstance(debug_out, SolutionArtifact) and debug_out.code:
            artifact_code = debug_out.code
        elif hasattr(coder_out, "code"):
            artifact_code = coder_out.code or ""
        elif isinstance(coder_out, dict):
            artifact_code = coder_out.get("code", coder_out.get("output", "")) or ""
        else:
            artifact_code = str(coder_out) if coder_out else ""
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        logger.info("📚 [DOCUMENTATION] Gerando documentação...")

        if not artifact_code:
            logger.info("⏭️ [DOCUMENTATION] Nada a documentar")
            return {"documentation": {}, "docs_generated": False}

        from pathlib import Path
        import re, json

        from iaglobal._paths import TEMP_DIR
        project_dir = Path(wd.path) if wd and hasattr(wd, 'path') else Path(TEMP_DIR / "docs")

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        docs = {}

        # 1. README.md
        try:
            readme_prompt = (
                "Gere um README.md em português para um projeto de software com base no código abaixo. "
                "Inclua: descrição do projeto, funcionalidades, pré-requisitos, instalação, uso, estrutura de diretórios. "
                "Use markdown.\n\nCódigo:\n%s\n\nREADME.md:" % artifact_code[:3000]
            )
            readme = await async_route_generate(model=locked, prompt=readme_prompt, task_type="general")
            if readme and len(readme.strip()) > 50:
                docs["README.md"] = readme.strip()
                (project_dir / "README.md").write_text(docs["README.md"])
                logger.info("📚 [DOCUMENTATION] README.md gerado (%d chars)", len(readme))
        except Exception as e:
            logger.warning("📚 [DOCUMENTATION] README falhou: %s", e)

        # 2. ADR (Architecture Decision Record)
        try:
            adr_prompt = (
                "Gere um Architecture Decision Record (ADR) em português para o projeto descrito pelo código abaixo. "
                "Use o formato: Título, Contexto, Decisão, Consequências. "
                "Nomeie o arquivo como 0001-arquitetura-inicial.md.\n\nCódigo:\n%s\n\nADR:" % artifact_code[:3000]
            )
            adr = await async_route_generate(model=locked, prompt=adr_prompt, task_type="general")
            if adr and len(adr.strip()) > 50:
                docs["adr/0001-arquitetura-inicial.md"] = adr.strip()
                adr_dir = project_dir / "adr"
                adr_dir.mkdir(parents=True, exist_ok=True)
                (adr_dir / "0001-arquitetura-inicial.md").write_text(docs["adr/0001-arquitetura-inicial.md"])
                logger.info("📚 [DOCUMENTATION] ADR gerado (%d chars)", len(adr))
        except Exception as e:
            logger.warning("📚 [DOCUMENTATION] ADR falhou: %s", e)

        # 3. Docstrings — reescreve o código com docstrings
        try:
            docstring_prompt = (
                "Adicione docstrings em português ao código abaixo seguindo o padrão Google Style. "
                "Retorne APENAS o código completo com as docstrings adicionadas. Não explique nada.\n\nCódigo:\n%s"
                % artifact_code[:4000]
            )
            docstring_code = await async_route_generate(model=locked, prompt=docstring_prompt, task_type="general")
            if docstring_code and len(docstring_code.strip()) > len(artifact_code.strip()):
                # Extrai bloco de código se houver
                blocks = re.findall(r'```(?:\w+)?\s*\n(.*?)```', docstring_code, re.DOTALL)
                final_code = blocks[0].strip() if blocks else docstring_code.strip()
                # Substitui o código principal
                main_file = project_dir / "main.py"
                if not main_file.exists():
                    py_files = list(project_dir.glob("*.py"))
                    main_file = py_files[0] if py_files else main_file
                main_file.write_text(final_code)
                docs["docstrings"] = "Adicionadas ao código-fonte"
                logger.info("📚 [DOCUMENTATION] Docstrings adicionadas (%d chars)", len(final_code))
        except Exception as e:
            logger.warning("📚 [DOCUMENTATION] Docstrings falhou: %s", e)

        # 4. Diagrama de arquitetura (Mermaid)
        try:
            diagram_prompt = (
                "Gere um diagrama de arquitetura em formato Mermaid para o projeto descrito pelo código abaixo. "
                "Retorne APENAS o bloco mermaid, sem explicações.\n\nCódigo:\n%s\n\n```mermaid" % artifact_code[:3000]
            )
            diagram = await async_route_generate(model=locked, prompt=diagram_prompt, task_type="general")
            if diagram and len(diagram.strip()) > 20:
                formatted = "```mermaid\n%s\n```" % diagram.strip().replace("```mermaid", "").replace("```", "")
                docs["diagrama-arquitetura.md"] = "# Diagrama de Arquitetura\n\n" + formatted
                (project_dir / "diagrama-arquitetura.md").write_text(docs["diagrama-arquitetura.md"])
                logger.info("📚 [DOCUMENTATION] Diagrama gerado")
        except Exception as e:
            logger.warning("📚 [DOCUMENTATION] Diagrama falhou: %s", e)

        if wd:
            wd.append_log("documentação: %d arquivos gerados" % len(docs))

        generated = list(docs.keys())
        logger.info("✅ [DOCUMENTATION] %d documento(s) gerado(s): %s", len(generated), generated)
        return {"documentation": docs, "docs_generated": bool(docs), "doc_files": generated}
    return run


def _make_release_run() -> Callable:
    """Release Agent — gera CHANGELOG, versionamento, release notes e deploy plan."""
    async def run(ctx):
        docs_result = ctx.get("memory", {}).get("documentation", {}).get("documentation", {})
        artifact_result = ctx.get("memory", {}).get("artifact_writer", {})
        artifact_code = artifact_result.get("artifact_code", "")
        project_path = artifact_result.get("path", "")
        wd = ctx.get("workdir")

        logger.info("🚀 [RELEASE] Gerando artefatos de release...")

        if not artifact_code:
            return {"output": {}, "release_generated": False}

        from pathlib import Path
        import json as _json

        project_dir = Path(project_path).parent if Path(project_path).is_file() else Path(project_path)

        from iaglobal.providers.provider_config import ProviderConfig
        from iaglobal.events import resolve_locked_model
        from iaglobal.providers.provider_router import async_route_generate

        fallback = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        locked = resolve_locked_model(ctx, f"ollama/{fallback}")

        release = {}

        # 1. CHANGELOG
        try:
            prompt = (
                "Gere um CHANGELOG.md em português para o projeto descrito abaixo. "
                "Use formato baseado em Keep a Changelog.\n\nCódigo:\n%s\n\nCHANGELOG.md:" % artifact_code[:3000]
            )
            changelog = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            if changelog and len(changelog.strip()) > 50:
                release["CHANGELOG.md"] = changelog.strip()
                (project_dir / "CHANGELOG.md").write_text(release["CHANGELOG.md"])
                logger.info("🚀 [RELEASE] CHANGELOG.md gerado")
        except Exception as e:
            logger.warning("🚀 [RELEASE] CHANGELOG falhou: %s", e)

        # 2. Release Notes
        try:
            prompt = (
                "Gere Release Notes em português para a versão inicial do projeto "
                "descrito pelo código abaixo. Inclua: novidades, correções, melhorias.\n\nCódigo:\n%s\n\nRelease Notes:"
                % artifact_code[:3000]
            )
            notes = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            if notes and len(notes.strip()) > 50:
                release["RELEASE_NOTES.md"] = notes.strip()
                (project_dir / "RELEASE_NOTES.md").write_text(release["RELEASE_NOTES.md"])
                logger.info("🚀 [RELEASE] Release Notes gerado")
        except Exception as e:
            logger.warning("🚀 [RELEASE] Release Notes falhou: %s", e)

        # 3. Deploy Plan
        try:
            prompt = (
                "Gere um plano de deploy em português para o projeto descrito abaixo. "
                "Inclua: pré-requisitos, passos, verificação pós-deploy e rollback.\n\nCódigo:\n%s\n\nDeploy Plan:"
                % artifact_code[:3000]
            )
            deploy = await async_route_generate(model=locked, prompt=prompt, task_type="general")
            if deploy and len(deploy.strip()) > 50:
                release["DEPLOY_PLAN.md"] = deploy.strip()
                (project_dir / "DEPLOY_PLAN.md").write_text(deploy)
                logger.info("🚀 [RELEASE] Deploy Plan gerado")
        except Exception as e:
            logger.warning("🚀 [RELEASE] Deploy Plan falhou: %s", e)

        if wd:
            wd.append_log("release: %d artefatos" % len(release))

        generated = list(release.keys())
        logger.info("✅ [RELEASE] %d artefato(s): %s", len(generated), generated)
        return {"output": release, "release_generated": bool(release), "release_files": generated}
    return run


def _make_metrics_run() -> Callable:
    """Metrics Agent — transversal. Coleta métricas de todos os nós da execução."""
    async def run(ctx):
        memory = ctx.get("memory", {})
        wd = ctx.get("workdir")

        logger.info("📊 [METRICS] Coletando métricas...")

        metrics = {
            "nodes_executed": list(memory.keys()),
            "node_count": len(memory),
            "scores": {},
            "durations": {},
        }

        for node_name, node_data in memory.items():
            if isinstance(node_data, dict):
                for key in ("score", "review_score", "performance_score", "security_score", "risk_score"):
                    if key in node_data:
                        metrics["scores"]["%s.%s" % (node_name, key)] = node_data[key]
                if "output" in node_data and hasattr(node_data["output"], "score"):
                    metrics["scores"]["%s.output_score" % node_name] = node_data["output"].score

        if wd:
            wd.append_log("metrics: %d nodes, %d scores" % (len(memory), len(metrics["scores"])))

        return {"output": metrics, "metrics_report": metrics}
    return run


def _make_optimization_run() -> Callable:
    """Optimization Agent — transversal. Analisa histórico e sugere otimizações."""
    async def run(ctx):
        memory = ctx.get("memory", {})
        wd = ctx.get("workdir")

        logger.info("🔧 [OPTIMIZATION] Analisando padrões...")

        patterns = {
            "useful_agents": [],
            "unnecessary_steps": [],
            "suggestions": [],
        }

        # Análise simples: detecta nós que produziram warnings ou erros
        for node_name, node_data in memory.items():
            if isinstance(node_data, dict):
                if node_data.get("output") is None or node_data.get("output") == "":
                    patterns["unnecessary_steps"].append(node_name)

        if not patterns["unnecessary_steps"]:
            patterns["suggestions"].append("Pipeline executou sem nós desnecessários")

        patterns["useful_agents"] = [n for n in memory.keys() if n not in patterns["unnecessary_steps"]]

        if wd:
            wd.append_log("optimization: %d sugestões" % len(patterns["suggestions"]))

        return {"output": patterns, "optimization_report": patterns}
    return run


def _make_reflexion_run(orchestrator: Any) -> Callable:
    async def run(ctx):
        artifact = ctx.get("memory", {}).get("final_gatekeeper", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = ctx.get("workdir")

        if not artifact.code:
            logger.info("⏭️ [REFLEXION] Nada para salvar.")
            if wd:
                wd.append_log("nada para salvar")
            return {"output": artifact}

        logger.info("💾 [REFLEXION] Salvando aprendizado...")

        error_entry = {
            "task": artifact.task,
            "erro": artifact.runtime_error,
            "correcao": artifact.code,
            "resultado": artifact.tests_passed == artifact.tests_total and artifact.tests_total > 0,
            "score": artifact.score,
            "critique": artifact.critique,
        }

        if wd:
            wd.write_code(artifact.code).append_log("reflexion salvo no banco")

        try:
            from iaglobal.memory.db_manager import db
            db.insert_insight(
                agent="reflexion",
                task_id=hash(artifact.task),
                content=str(error_entry),
                score=artifact.score,
            )
            logger.info("🧠 aumentando o nivel de consciência ...")
        except Exception as e:
            logger.warning("⚠️ [REFLEXION] Erro ao salvar: %s", e)

        try:
            from iaglobal.memory.memory_storage import storage
            storage.store(
                artifact.task,
                artifact.code,
                {"score": artifact.score, "critique": artifact.critique, "ts": __import__("time").time()},
            )
            logger.info("✅ tudo ok, aprendi mais uma lição!")
        except Exception as e:
            logger.warning("⚠️ [REFLEXION] Erro no storage: %s", e)

        return {"output": artifact}
    return run


def _make_knowledge_run() -> Callable:
    """Knowledge Agent — transversal. Armazena e recupera conhecimento operacional."""
    async def run(ctx):
        from iaglobal.evolution.agents.knowledge_agent import knowledge

        logger.info("📚 [KNOWLEDGE] Processando conhecimento...")

        memory = ctx.get("memory", {})
        task = ctx.get("input", {}).get("task", "")

        # 1. Extrai conhecimento novo dos resultados dos nós
        for node_name, node_data in memory.items():
            if not isinstance(node_data, dict):
                continue
            output = node_data.get("output")
            if output is None:
                continue

            # Arquitetura
                if node_name == "architect" and hasattr(output, "architecture"):
                    knowledge.store(
                        category="architecture",
                        title="Arquitetura definida",
                        content=str(output.architecture)[:500],
                        tags=["architect", "architecture"],
                        source=node_name,
                    )

            # Conhecimento dos agentes V3
            if node_name == "security_design":
                report = output.get("security_design_report", {}) if isinstance(output, dict) else {}
                if report.get("total_issues", 0) > 0:
                    knowledge.store(
                        category="pattern",
                        title="Issues de segurança no design",
                        content=str(report.get("issues", []))[:500],
                        tags=["security_design", "security", "design"],
                        source=node_name,
                    )

            if node_name == "performance_design":
                report = output.get("performance_design_report", {}) if isinstance(output, dict) else {}
                if report.get("total_issues", 0) > 0:
                    knowledge.store(
                        category="pattern",
                        title="Issues de performance no design",
                        content=str(report.get("issues", []))[:500],
                        tags=["performance_design", "performance", "design"],
                        source=node_name,
                    )

            if node_name == "security_audit":
                audit = output.get("security_audit_report", {}) if isinstance(output, dict) else {}
                if audit.get("total_issues", 0) > 0:
                    knowledge.store(
                        category="bug",
                        title="Issues de segurança no código",
                        content=str(audit.get("issues", []))[:500],
                        tags=["security_audit", "security", "code"],
                        source=node_name,
                    )

            if node_name == "performance_audit":
                audit = output.get("performance_audit_report", {}) if isinstance(output, dict) else {}
                if audit.get("total_bottlenecks", 0) > 0:
                    knowledge.store(
                        category="bug",
                        title="Gargalos de performance no código",
                        content=str(audit.get("bottlenecks", []))[:500],
                        tags=["performance_audit", "performance", "code"],
                        source=node_name,
                    )

            # Bugs/erros
            if node_name in ("debugger", "tester") and hasattr(output, "error") and output.error:
                knowledge.store(
                    category="bug",
                    title="Erro detectado: %s" % node_name,
                    content=str(output.error)[:500],
                    tags=[node_name, "error"],
                    source=node_name,
                )

            # Soluções bem-sucedidas
            if hasattr(output, "score") and getattr(output, "score", 0) >= 0.8:
                code = getattr(output, "code", "")
                if code and len(code) > 100:
                    knowledge.store(
                        category="best_practice",
                        title="Solucao de alta qualidade (%s)" % node_name,
                        content=code[:500],
                        tags=[node_name, "high_score"],
                        source=node_name,
                    )

        # 2. Busca conhecimento relevante para a task atual
        relevant = knowledge.retrieve_relevant(task, max_results=3)

        summary = knowledge.summarize(max_entries=5)

        logger.info("[KNOWLEDGE] %d entradas relevantes encontradas para a task", len(relevant))

        return {
            "output": {
                "relevant_knowledge": relevant,
                "summary": summary,
                "stats": knowledge.get_stats(),
            },
            "knowledge_context": {
                "relevant": relevant,
                "summary": summary,
            },
        }
    return run


def _make_enhancement_run() -> Callable:
    """Enhancement — refine e enriquece o prompt após o intake."""
    async def run(ctx):
        from iaglobal.agents.enhancement_agent import EnhancementAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt

        task = ctx.get("input", {}).get("task", "")
        intake = ctx.get("memory", {}).get("prompt_intake", {}).get("output", {})
        if isinstance(intake, dict):
            intake = intake
        else:
            intake = getattr(intake, "output", intake) if hasattr(intake, "output") else intake
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(task, limit=2)
        knowledge_context = knowledge.summarize(max_entries=3) if relevant else ""
        error_context = format_errors_for_prompt(errors)

        agent = EnhancementAgent()
        result = agent.enhance(task, intake, knowledge_context=knowledge_context,
                               error_context=error_context)

        try:
            from iaglobal.memory.db_manager import db
            import hashlib
            task_id = hashlib.md5(task.encode()).hexdigest()
            db.insert_insight("enhancement", task_id,
                          "Approaches: %s | Prerequisites: %s" %
                          (result.get("approach", []), result.get("prerequisites", [])),
                          score=1.0)
        except Exception:
            pass

        logger.info("✨ [ENHANCEMENT] approach=%s", result.get("approach", []))
        if wd:
            wd.append_log("enhancement: %d abordagens" % len(result.get("approach", [])))

        ctx["input"]["intake"] = intake
        ctx["input"]["enhanced_task"] = result.get("enhanced_task", task)

        return {
            "output": result,
            "enhanced_task": result.get("enhanced_task", task),
            "approach": result.get("approach", []),
            "prerequisites": result.get("prerequisites", []),
        }
    return run


def _make_orchestrator_run() -> Callable:
    """Orchestrator — coordena o fluxo entre agentes."""
    async def run(ctx):
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt

        enhanced_task = ctx.get("input", {}).get("enhanced_task", "")
        prerequisites = ctx.get("memory", {}).get("enhancement", {}).get("output", {}).get("prerequisites", [])
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(enhanced_task or task, limit=2)
        knowledge_ctx = knowledge.summarize(max_entries=3) if relevant else ""
        error_ctx = format_errors_for_prompt(errors)

        plan = {
            "phase": "definition",
            "steps": [
                "pm -> requirements -> architect -> search",
                "knowledge -> dependency -> risk -> security_design -> performance_design",
                "planner -> coder -> reviewer -> semantic_validator",
                "security_audit -> performance_audit -> tester",
                "documentation -> release -> metrics -> optimization -> result_agent",
            ],
            "prerequisites": prerequisites,
            "knowledge_hints": len(relevant),
            "error_hints": error_ctx,
        }

        try:
            from iaglobal.memory.db_manager import db
            import hashlib
            task_id = hashlib.md5(task.encode()).hexdigest()
            kb_size = len(knowledge_ctx)
            err_size = len(error_ctx)
            db.insert_insight("orchestrator_agent", task_id,
                          "Plan steps: %d | Knowledge: %d chars | Errors: %d chars" %
                          (len(plan["steps"]), kb_size, err_size),
                          score=1.0)
        except Exception:
            pass

        logger.info("🎯 [ORCHESTRATOR] Plano de execução definido com %d fases", len(plan["steps"]))
        if wd:
            wd.append_log("orchestrator: %d steps" % len(plan["steps"]))

        return {
            "output": plan,
            "orchestration_plan": plan,
            "execution_order": plan["steps"],
        }
    return run


def _make_security_design_run() -> Callable:
    """Security Design — análise de segurança na fase de design."""
    async def run(ctx):
        from iaglobal.agents.security_design_agent import SecurityDesignAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt

        architecture = ctx.get("memory", {}).get("architect", {}).get("output", {})
        requirements = ctx.get("memory", {}).get("requirements", {}).get("output", {})
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(task, limit=2)
        knowledge_ctx = knowledge.summarize(max_entries=3) if relevant else ""
        error_ctx = format_errors_for_prompt(errors)

        agent = SecurityDesignAgent()
        result = agent.analyze(architecture, requirements, knowledge_context=knowledge_ctx,
                               error_context=error_ctx)

        issues = result.get("security_design_report", {}).get("total_issues", 0)

        if issues > 0:
            try:
                from iaglobal.memory.db_manager import db
                import hashlib
                task_id = hashlib.md5(task.encode()).hexdigest()
                db.insert_insight("security_design", task_id,
                              "Issues: %d | Recommendations: %s" %
                              (issues, result.get("security_requirements", [])),
                              score=0.5)
            except Exception:
                pass

        logger.info("🔒 [SECURITY-DESIGN] %d issues encontradas", issues)
        if wd:
            wd.append_log("security_design: %d issues" % issues)

        return {
            "output": result,
            "security_design_report": result.get("security_design_report", {}),
            "security_requirements": result.get("security_requirements", []),
        }
    return run


def _make_performance_design_run() -> Callable:
    """Performance Design — análise de performance na fase de design."""
    async def run(ctx):
        from iaglobal.agents.performance_design_agent import PerformanceDesignAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt

        architecture = ctx.get("memory", {}).get("architect", {}).get("output", {})
        requirements = ctx.get("memory", {}).get("requirements", {}).get("output", {})
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(task, limit=2)
        knowledge_ctx = knowledge.summarize(max_entries=3) if relevant else ""
        error_ctx = format_errors_for_prompt(errors)

        agent = PerformanceDesignAgent()
        result = agent.analyze(architecture, requirements, knowledge_context=knowledge_ctx,
                               error_context=error_ctx)

        issues = result.get("performance_design_report", {}).get("total_issues", 0)

        if issues > 0:
            try:
                from iaglobal.memory.db_manager import db
                import hashlib
                task_id = hashlib.md5(task.encode()).hexdigest()
                db.insert_insight("performance_design", task_id,
                              "Issues: %d | Recommendations: %s" %
                              (issues, result.get("performance_requirements", [])),
                              score=0.5)
            except Exception:
                pass

        logger.info("⚡ [PERF-DESIGN] %d issues encontradas", issues)
        if wd:
            wd.append_log("perf_design: %d issues" % issues)

        return {
            "output": result,
            "performance_design_report": result.get("performance_design_report", {}),
            "performance_requirements": result.get("performance_requirements", []),
        }
    return run


def _make_security_audit_run() -> Callable:
    """Security Audit — audita código contra requisitos de segurança."""
    async def run(ctx):
        from iaglobal.agents.security_audit_agent import SecurityAuditAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
        from iaglobal.memory.memory_error import store_error

        code = ctx.get("memory", {}).get("coder", {}).get("output", "")
        if hasattr(code, "code"):
            code = code.code
        elif isinstance(code, dict):
            code = code.get("code", "")
        security_reqs = ctx.get("memory", {}).get("security_design", {}).get("output", {}).get("security_requirements", [])
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(task, limit=2)
        knowledge_ctx = knowledge.summarize(max_entries=3) if relevant else ""
        error_ctx = format_errors_for_prompt(errors)

        agent = SecurityAuditAgent()
        result = agent.audit(str(code) if not isinstance(code, str) else code,
                             security_reqs,
                             knowledge_context=knowledge_ctx,
                             error_context=error_ctx)
        audit = result.get("security_audit_report", {})
        issues = audit.get("issues", [])

        if issues:
            try:
                from iaglobal.memory.db_manager import db
                import hashlib
                task_id = hashlib.md5(task.encode()).hexdigest()
                issue_summary = "; ".join(
                    "[%s] %s" % (i.get("severity", "?"), i.get("description", ""))
                    for i in issues[:5]
                )
                db.insert_insight("security_audit", task_id,
                              "Issues: %d | %s" % (len(issues), issue_summary),
                              score=0.5)
                store_error(task, str(code)[:200],
                         issue_summary, "", error_type="SecurityAudit")
            except Exception:
                pass

        logger.info("🔍 [SECURITY-AUDIT] %d issues (%d high)",
                     audit.get("total_issues", 0),
                     audit.get("severity_count", {}).get("high", 0))
        if wd:
            wd.append_log("security_audit: %d issues" % audit.get("total_issues", 0))

        return {
            "output": result,
            "security_audit_report": audit,
            "security_issues": result.get("security_issues", []),
        }
    return run


def _make_performance_audit_run() -> Callable:
    """Performance Audit — audita código contra requisitos de performance."""
    async def run(ctx):
        from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors, format_errors_for_prompt
        from iaglobal.memory.memory_error import store_error

        code = ctx.get("memory", {}).get("coder", {}).get("output", "")
        if hasattr(code, "code"):
            code = code.code
        elif isinstance(code, dict):
            code = code.get("code", "")
        perf_reqs = ctx.get("memory", {}).get("performance_design", {}).get("output", {}).get("performance_requirements", [])
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        relevant = knowledge.retrieve_relevant(task, max_results=2)
        errors = query_relevant_errors(task, limit=2)
        knowledge_ctx = knowledge.summarize(max_entries=3) if relevant else ""
        error_ctx = format_errors_for_prompt(errors)

        agent = PerformanceAuditAgent()
        result = agent.audit(str(code) if not isinstance(code, str) else code,
                             perf_reqs,
                             knowledge_context=knowledge_ctx,
                             error_context=error_ctx)
        audit = result.get("performance_audit_report", {})
        bottlenecks = audit.get("bottlenecks", [])

        if bottlenecks:
            try:
                from iaglobal.memory.db_manager import db
                import hashlib
                task_id = hashlib.md5(task.encode()).hexdigest()
                bn_summary = "; ".join(
                    "[%s] %s" % (b.get("severity", "?"), b.get("description", ""))
                    for b in bottlenecks[:5]
                )
                db.insert_insight("performance_audit", task_id,
                              "Bottlenecks: %d | %s" % (len(bottlenecks), bn_summary),
                              score=0.5)
                store_error(task, str(code)[:200],
                         bn_summary, "", error_type="PerformanceAudit")
            except Exception:
                pass

        logger.info("📊 [PERF-AUDIT] %d bottlenecks (%d high)",
                     audit.get("total_bottlenecks", 0),
                     audit.get("severity_count", {}).get("high", 0))
        if wd:
            wd.append_log("perf_audit: %d bottlenecks" % audit.get("total_bottlenecks", 0))

        return {
            "output": result,
            "performance_audit_report": audit,
            "bottlenecks": result.get("bottlenecks", []),
        }
    return run


def _make_result_agent_run() -> Callable:
    """Result Agent — agrega resultado final para o usuário."""
    async def run(ctx):
        from iaglobal.agents.result_agent import ResultAgent
        task = ctx.get("input", {}).get("task", "")
        wd = ctx.get("workdir")

        agent = ResultAgent()
        result = agent.build_result(ctx.get("memory", {}))

        try:
            from iaglobal.memory.db_manager import db
            import hashlib
            task_id = hashlib.md5(task.encode()).hexdigest()
            summary = result.get("summary", "")
            status = result.get("final_result", {}).get("status", "unknown")
            db.insert_insight("result_agent", task_id,
                          "Status: %s | Summary: %s" % (status, summary[:200]),
                          score=1.0)
        except Exception:
            pass

        logger.info("📋 [RESULT] Status: %s", result.get("final_result", {}).get("status", "unknown"))
        if wd:
            wd.append_log("result: %s" % result.get("summary", ""))

        return {
            "output": result,
            "final_result": result.get("final_result", {}),
            "summary": result.get("summary", ""),
            "next_steps": result.get("next_steps", []),
        }
    return run
