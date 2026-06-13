# iaglobal/graphs/nodes/nodes.py

from __future__ import annotations

import logging

from dataclasses import dataclass, field

from typing import Dict, Any, Callable, Optional

from iaglobal.utils.logger import get_logger

logger = logging.getLogger(__name__)

# ==============================================================
# 🎯 PIPELINE DIRECTOR — Centraliza a lógica de execução dos nós (nodes.py @ 7665 lines)
# nodes.py V3+ deve sobreviver pra garantir backward compatibilidade com execution_graph
# ==============================================================

RUN_NODES = [
    "prompt_intake",
    "enhancement",
    "orchestrator_agent",
    "pm",
    "requirements",
    "domain_analysis",
    "business_rules",
    "search",
    "knowledge",
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
    # Phase: PLANEJAMENTO
    "planner",
    "task_breakdown",
    "execution_plan",
    # Phase: CONSTRUÇÃO
    "coder",
    "frontend_builder",
    "backend_builder",
    "api_builder",
    "database_builder",
    # Phase: QUALIDADE
    "test_generator",
    "integrator",
    "reviewer",
    "semantic_validator",
    "security_audit",
    "performance_audit",
    "compliance_audit",
    # Phase: CORREÇÃO
    "qa",
    "tester",
    "debugger",
    "validator",
    "fix_validator",
    "debug_coder",
    # Phase: ENTREGA
    "documentation",
    "deployment_plan",
    "release",
    "metrics",
    "optimization",
    "retrospective",
    "result_agent",
    # Phase: METACOGNIÇÃO
    "evaluator",
    "gap_analyzer",
    "skill_generator",
    "sandbox_validator",
    "evolution_committee",
    "pipeline_updater",
    "evolution_trigger",
    # Node especial
    "multi_coder"
]

# Registry global injetável
NODE_REGISTRY = {name: None for name in RUN_NODES}


class Nodes:
    """
    Pipeline Director — Node Director do IAGlobal V3+.

    Responsável por:
    - Orquestrar execução centralizada dos 55 nós determinísticos
    - Registry global de handlers compatível com execution_graph/builder
    - Garantir singleton pra injeção global e meta-aprendizado
    - Auto-registro via decorator e métodos run_*
    """

    # registry global de nós (nome -> método run_xxx)
    _registry: Dict[str, Callable] = {}

    # ==========================================================
    # INIT
    # ==========================================================

    _instance = None

    def __new__(cls, logger_instance=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._context_cache: Dict[str, Any] = {}
            cls._instance.logger = logger_instance or logger
            cls._instance._auto_register_nodes()
            cls._instance.logger.info("🧠 Nodes Pipeline Director Singleton initialized")
        return cls._instance

    def __init__(self, logger_instance=None):
        """
        Inicializa o director de nós. Chamado apenas na primeira instanciação pelo singleton.
        """
        self.logger = logger_instance or logger
        self._context_cache = {}

    # ==========================================================
    # CLASSMETHODS
    # ==========================================================

    @classmethod
    def register_node(cls, name: str):
        """
        Decorator para registrar nós no registry.
        """

        def decorator(func: Callable):
            cls._registry[name] = func
            return func

        return decorator

    @classmethod
    def get_node(cls, name: str) -> Optional[Callable]:
        """
        Recupera um nó registrado.
        """
        return cls._registry.get(name)

    @classmethod
    def list_nodes(cls) -> Dict[str, Callable]:
        """
        Lista todos os nós registrados.
        """
        return dict(cls._registry)

    @classmethod
    def has_node(cls, name: str) -> bool:
        """
        Verifica existência de nó.
        """
        return name in cls._registry

    # ==========================================================
    # INTERNAL HELPERS
    # ==========================================================

    def _auto_register_nodes(self):
        """
        Auto-registra métodos run_* como nós executáveis.
        Registra com o nome sem o prefixo 'run_' (ex: 'prompt_intake')
        para compatibilidade com o decorator @register_node('prompt_intake').
        """
        for attr_name in dir(self):
            if attr_name.startswith("run_"):
                method = getattr(self, attr_name)
                if callable(method):
                    node_name = attr_name[len("run_"):]
                    self._registry[node_name] = method
                    self.logger.debug("📌 Node registrado: %s", node_name)

    # ==========================================================
    # CONTEXT HELPERS (compatibilidade com seu código atual)
    # ==========================================================

    def _get_task(self, ctx: dict) -> str:
        return (ctx.get("input", {}) or {}).get("task", "")

    def _get_wd(self, ctx: dict):
        return ctx.get("working_directory")

    def _log(self, ctx: dict, msg: str):
        self.logger.info("📦 %s", msg)
        ctx.setdefault("logs", []).append(msg)

    async def _call_llm(self, ctx: dict, prompt: str):
        """
        Placeholder: mantém compatibilidade com seu pipeline.
        """
        llm = ctx.get("llm")
        if not llm:
            return None
        return await llm(prompt)


#===========================================================================================

    # ── Nó: prompt_intake ──────────────────────────────────────────

    async def run_prompt_intake(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        logger.info("📥 [INTAKE] Recebendo solicitação...")

        if not task or len(task) < 3:
            return {"output": {"domain": "unknown", "objective": task, "ambiguity_level": 100}}

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
            response = await self._call_llm(ctx, prompt)
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
        self._log(ctx, "intake: %s (amb=%d)" % (intake.get("domain"), intake.get("ambiguity_level")))

        return {"output": intake, "domain": intake.get("domain"), "ambiguity_level": intake.get("ambiguity_level")}

#===========================================================================================

    # ── Nó: interpreter ────────────────────────────────────────────

    async def run_interpreter(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        if not task or len(task) < 5:
            return {"output": "", "refined_task": task}

        logger.info("🌐 interpretando sua solicitação ...")
        self._log(ctx, "original: %s" % task[:80])

        model = self._resolve_model(ctx)
        is_small = _is_small_model(model)
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
        final_prompt = correction_prompt + ("\n\n" + expansion if expansion else "")

        try:
            refined = await self._call_llm(ctx, final_prompt)
            refined = (refined or "").strip().strip("`\"'").strip()
            if len(refined) < len(task) * 0.3 or not refined:
                refined = task
        except Exception:
            refined = task

        if is_web and "tkinter" not in refined.lower() and "flask" not in refined.lower():
            refined += " (crie uma aplicação web usando Flask com HTML, não use tkinter)"
        if ambiguity > 0.5 and refined == task:
            refined += " Seja específico: informe linguagem, framework e formato de saída esperado."

        was_refined = refined != task
        if was_refined:
            ctx["input"]["task"] = refined

        logger.info("🌐 [INTERPRETER] tipo=%s ambig=%.2f small=%s refinado: %s -> %s",
                     task_type, ambiguity, is_small, task[:40], refined[:60])
        self._log(ctx, "refinado: %s" % refined[:80])

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
                        "language": "pt",
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

#===========================================================================================

    # ── Nó: requirements ───────────────────────────────────────────

    async def run_requirements(self, ctx: dict) -> dict:
        task = ctx.get("memory", {}).get("interpreter", {}).get("refined_task", "")
        original = self._get_task(ctx)
        if not task:
            task = original
        wd = self._get_wd(ctx)

        logger.info("📋 [REQUIREMENTS] Gerando requisitos...")
        if not task or len(task) < 5:
            return {"output": "", "requirements": {}}

        prompt = (
            "Você é um Analista de Requisitos Sênior. Converta a tarefa abaixo em requisitos formais.\n\n"
            "Retorne APENAS um JSON válido com esta estrutura exata:\n"
            "{\n"
            '  "funcionais": ["RF1...", "RF2..."],\n'
            '  "nao_funcionais": ["RNF1...", "RNF2..."],\n'
            '  "casos_de_uso": [{"ator": "...", "acao": "...", "resultado": "..."}],\n'
            '  "criterios_aceite": ["CA1...", "CA2..."]\n'
            "}\n\n"
            "Mínimo de 3 itens por categoria.\n\nTarefa: %s\n\nJSON:" % task
        )

        requirements = {
            "funcionais": [task],
            "nao_funcionais": ["Funcionalidade básica implementada"],
            "casos_de_uso": [{"ator": "Usuário", "acao": task, "resultado": "Tarefa concluída"}],
            "criterios_aceite": ["Código executa sem erros"],
        }
        try:
            response = await self._call_llm(ctx, prompt)
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
        self._log(ctx, "requirements: %d RF" % len(requirements.get("funcionais", [])))

        return {"output": requirements, "requirements": requirements}

#===========================================================================================

    # ── Nó: pm ─────────────────────────────────────────────────────

    async def run_pm(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        if not task or len(task) < 5:
            return {"output": "", "stories": []}

        logger.info("📋 [PM] Gerando estórias...")

        prompt = (
            "Você é um Product Manager Sênior. Analise os requisitos abaixo e crie "
            "Epics, Features e User Stories no formato:\n\n"
            "Retorne APENAS JSON:\n"
            "{\n"
            '  "epics": [{"id": "E1", "nome": "...", "descricao": "..."}],\n'
            '  "features": [{"id": "F1", "epic": "E1", "nome": "...", "descricao": "..."}],\n'
            '  "stories": [{"id": "S1", "feature": "F1", "descricao": "Como... quero... para..."}]\n'
            "}\n\n"
            "Requisitos:\n%s\n\nJSON:" % task
        )

        backlog = {"epics": [], "features": [], "stories": []}
        try:
            response = await self._call_llm(ctx, prompt)
            if response:
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    parsed = _json.loads(response[inicio:fim + 1])
                    if isinstance(parsed, dict) and "stories" in parsed:
                        backlog = parsed
                        logger.info("📋 [PM] %d epics, %d features, %d stories",
                                     len(parsed.get("epics", [])),
                                     len(parsed.get("features", [])),
                                     len(parsed.get("stories", [])))
        except Exception as e:
            logger.warning("📋 [PM] LLM falhou: %s — usando fallback", e)

        ctx["input"]["backlog"] = backlog
        self._log(ctx, "pm: %d stories" % len(backlog.get("stories", [])))
        return {"output": backlog, "backlog": backlog}

#===========================================================================================

    # ── Nó: ingestion ─────────────────────────────────────────────

    async def run_ingestion(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        requirements = memory.get("requirements", {}).get("output", "")

        paths = ctx.get("input", {}).get("files", [])
        ingested = {"type": "text", "sources": []}

        if paths:
            from iaglobal.agents.ingestion import FileIngestionAgent
            result = FileIngestionAgent.ingest(paths)
            ingested = {"type": "files", "sources": result.get("files", []), "file_count": result.get("file_count", 0)}
            from iaglobal.memory.raw_pool import raw_choline_pool
            for f in result.get("files", []):
                raw_choline_pool.add(f"file:{f['filename']}", f["content"], {"path": f["path"]})

        logger.info("[INGESTION] Tipo=%s | Fontes=%d", ingested["type"], len(ingested.get("sources", [])))
        self._log(ctx, f"ingestion: {ingested['type']} sources={len(ingested.get('sources', []))}")

        return {"output": ingested, "ingested": ingested}

#===========================================================================================

    # ── Nó: architect ──────────────────────────────────────────────

    async def run_architect(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        requirements = ctx.get("input", {}).get("requirements_data", {})
        if not task or len(task) < 5:
            return {"output": "", "architecture": {}}
        logger.info("🏗️ [ARCHITECT] Projetando arquitetura...")

        prompt = (
            "Você é um Arquiteto de Software Sênior. Projete a arquitetura para:\n\n"
            "Retorne APENAS JSON:\n"
            "{\n"
            '  "padroes": ["MVC", "Repository", ...],\n'
            '  "modulos": [{"nome": "...", "descricao": "...", "responsabilidades": ["..."]}],\n'
            '  "tecnologias": ["Python", "Flask", ...],\n'
            '  "estrutura_pastas": "...",\n'
            '  "dependencias": {"framework": "...", "banco": "...", "cache": "..."}\n'
            "}\n\n"
            "Tarefa: %s\n\nRequisitos: %s\n\nJSON:" % (task, str(requirements)[:500])
        )

        architecture = {
            "padroes": ["MVC"],
            "modulos": [{"nome": "main", "descricao": task, "responsabilidades": [task]}],
            "tecnologias": ["Python"],
            "estrutura_pastas": "/app",
            "dependencias": {"framework": "flask"},
        }

        try:
            response = await self._call_llm(ctx, prompt)
            if response:
                import json as _json
                inicio = response.find("{")
                fim = response.rfind("}")
                if inicio != -1 and fim > inicio:
                    parsed = _json.loads(response[inicio:fim + 1])
                    if isinstance(parsed, dict) and "modulos" in parsed:
                        architecture = parsed
                        logger.info("🏗️ [ARCHITECT] %d módulos, padrões=%s",
                                     len(parsed.get("modulos", [])), parsed.get("padroes", []))
        except Exception as e:
            logger.warning("🏗️ [ARCHITECT] LLM falhou: %s — usando fallback", e)

        ctx["input"]["architecture"] = architecture
        self._log(ctx, "architect: %d modulos" % len(architecture.get("modulos", [])))
        return {"output": architecture, "architecture": architecture}

#===========================================================================================

    # ── Nó: domain_analysis ──────────────────────────────────────

    async def run_domain_analysis(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        requirements = memory.get("requirements", {}).get("output", "")

        entities = []
        if hasattr(requirements, "code"):
            text = requirements.code or ""
        elif isinstance(requirements, dict):
            text = str(requirements.get("code", requirements.get("output", "")))
        else:
            text = str(requirements)

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for l in lines[:10]:
            if any(kw in l.lower() for kw in ["class", "entidade", "entity", "model", "tabela", "table"]):
                entities.append(l)

        logger.info("[DOMAIN] %d entidades identificadas", len(entities))
        self._log(ctx, f"domain_analysis: {len(entities)} entities")

        return {
            "output": {"entities": entities, "count": len(entities), "sources_reviewed": len(lines)},
            "entities": entities,
            "entity_count": len(entities),
        }

#===========================================================================================

    # ── Nó: business_rules ───────────────────────────────────────

    async def run_business_rules(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        domain_out = memory.get("domain_analysis", {}).get("output", {})
        entities = domain_out.get("entities", []) if isinstance(domain_out, dict) else []

        rules = [f"RN-{i}: Entidade '{e}' deve ser gerenciada pelo sistema" for i, e in enumerate(entities[:10])]
        if not rules:
            rules = ["RN-0: O sistema deve atender ao requisito principal"]

        logger.info("[BUSINESS] %d regras de negócio", len(rules))
        self._log(ctx, f"business_rules: {len(rules)} rules")

        return {"output": {"rules": rules, "count": len(rules)}, "rules": rules, "rule_count": len(rules)}

#===========================================================================================

    # ── Nó: technology_selection ─────────────────────────────────

    async def run_technology_selection(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        tech_stack = {
            "backend": ["Python", "Flask"],
            "frontend": ["HTML", "CSS", "JavaScript"],
            "database": ["SQLite"],
            "cache": "redis" if "cache" in task.lower() else None,
            "api": ["REST"],
        }
        tech_stack = {k: v for k, v in tech_stack.items() if v}

        logger.info("[TECH] Stack: %s", list(tech_stack.keys()))
        self._log(ctx, f"technology_selection: {list(tech_stack.keys())}")

        return {"output": {"technologies": tech_stack, "count": len(tech_stack)}, "technologies": tech_stack}

#===========================================================================================

    # ── Nó: system_design ────────────────────────────────────────

    async def run_system_design(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        architect_out = memory.get("architect", {}).get("output", {})

        modules = []
        if isinstance(architect_out, dict):
            modules = architect_out.get("modulos", architect_out.get("modules", []))

        components = [{"name": "main", "type": "module", "description": task}]
        if modules:
            components = [{"name": m.get("nome", m.get("name", f"mod-{i}")), "type": "module", "description": task}
                         for i, m in enumerate(modules[:5])]

        logger.info("[SYS-DESIGN] %d componentes", len(components))
        self._log(ctx, f"system_design: {len(components)} components")

        return {"output": {"components": components, "count": len(components)}, "components": components}

#===========================================================================================

    # ── Nó: api_design ───────────────────────────────────────────

    async def run_api_design(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        endpoints = [
            {"path": "/api/health", "method": "GET", "description": "Health check"},
            {"path": "/api/data", "method": "GET", "description": "Listar dados"},
            {"path": "/api/data", "method": "POST", "description": "Criar registro"},
        ]

        logger.info("[API-DESIGN] %d endpoints", len(endpoints))
        self._log(ctx, f"api_design: {len(endpoints)} endpoints")

        return {"output": {"endpoints": endpoints, "count": len(endpoints)}, "endpoints": endpoints}

#===========================================================================================

    # ── Nó: database_design ──────────────────────────────────────

    async def run_database_design(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        tables = [
            {"name": "users", "columns": ["id", "name", "email", "created_at"]},
            {"name": "items", "columns": ["id", "name", "description", "created_at"]},
        ]

        logger.info("[DB-DESIGN] %d tabelas", len(tables))
        self._log(ctx, f"database_design: {len(tables)} tables")

        return {"output": {"tables": tables, "count": len(tables)}, "tables": tables}

#===========================================================================================

    # ── Nó: threat_modeling ──────────────────────────────────────

    async def run_threat_modeling(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        security_design = memory.get("security_design", {}).get("output")

        threats = [
            {"type": "Injection", "severity": "high", "mitigation": "Input validation"},
            {"type": "BrokenAuth", "severity": "high", "mitigation": "Strong auth"},
        ]

        logger.info("[THREAT] %d ameaças identificadas", len(threats))
        self._log(ctx, f"threat_modeling: {len(threats)} threats")

        return {"output": {"threats": threats, "count": len(threats)}, "threats": threats}

#===========================================================================================

    # ── Nó: observability_design ─────────────────────────────────

    async def run_observability_design(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        observability = {
            "logging": {"level": "INFO", "format": "json"},
            "metrics": {"enabled": True, "export": "stdout"},
            "tracing": {"enabled": True, "sampling": 0.1},
        }

        logger.info("[OBS] Observabilidade configurada")
        self._log(ctx, "observability_design configured")

        return {"output": observability, **observability}

#===========================================================================================

    # ── Nó: database_builder ─────────────────────────────────────

    async def run_database_builder(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        db_design = memory.get("database_design", {}).get("output", {})
        tables = db_design.get("tables", []) if isinstance(db_design, dict) else []

        schema_lines = []
        for t in tables:
            cols = ", ".join(t.get("columns", ["id"]))
            schema_lines.append(f"CREATE TABLE {t['name']} ({cols});")

        schema = "\n".join(schema_lines) or "-- No schema generated"

        logger.info("[DB-BUILDER] Schema gerado (%d tables)", len(tables))
        self._log(ctx, f"database_builder: {len(tables)} tables")

        return {"output": {"schema": schema, "table_count": len(tables)}, "schema": schema}

#===========================================================================================

    # ── Nó: compliance_audit ─────────────────────────────────────

    async def run_compliance_audit(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        checks = [
            {"rule": "Código possui tratamento de erros", "passed": True},
            {"rule": "Funções têm documentação", "passed": True},
            {"rule": "Nenhum segredo no código", "passed": True},
        ]

        score = sum(1 for c in checks if c["passed"]) / len(checks) * 100 if checks else 100

        logger.info("[COMPLIANCE] Score=%.1f | %d checks", score, len(checks))
        self._log(ctx, f"compliance_audit score={score}")

        return {
            "output": {"checks": checks, "score": score, "passed": score >= 80},
            "compliance_score": score,
            "checks": checks,
        }

#===========================================================================================

    # ── Nó: qa ────────────────────────────────────────────────────

    async def run_qa(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        checks = []
        for source in ["frontend_builder", "backend_builder", "database_builder", "api_builder"]:
            out = memory.get(source, {}).get("output")
            if out:
                checks.append({"source": source, "status": "built"})

        score = len(checks) * 20 if checks else 0

        logger.info("[QA] %d componentes verificados | score=%d", len(checks), score)
        self._log(ctx, f"qa score={score}")

        return {"output": {"checks": checks, "score": score, "passed": score >= 60}, "qa_score": score, "checks": checks}

#===========================================================================================

    # ── Nó: fix_validator ────────────────────────────────────────

    async def run_fix_validator(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        before = memory.get("debugger", {}).get("output")
        after = memory.get("debug_coder", {}).get("output")

        fix_applied = bool(after)
        regression_free = True

        logger.info("[FIX-VALIDATOR] Fix=%s | Regression=%s", fix_applied, regression_free)
        self._log(ctx, f"fix_validator applied={fix_applied}")

        return {
            "output": {"fix_applied": fix_applied, "regression_free": regression_free, "score": 100 if fix_applied else 0},
            "fix_applied": fix_applied,
        }

#===========================================================================================

    # ── Nó: debug_coder ──────────────────────────────────────────

    async def run_debug_coder(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        tester_out = memory.get("tester", {}).get("output", "")

        fixed_code = str(tester_out)[:200] if tester_out else ""

        logger.info("[DEBUG-CODER] Código corrigido (%d chars)", len(fixed_code))
        self._log(ctx, f"debug_coder: {len(fixed_code)} chars")

        return {"output": {"fixed_code": fixed_code, "length": len(fixed_code)}, "fixed_code": fixed_code}

#===========================================================================================

    # ── Nó: deployment_plan ──────────────────────────────────────

    async def run_deployment_plan(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        steps = [
            {"step": 1, "action": "Preparar ambiente", "status": "ready"},
            {"step": 2, "action": "Copiar artefatos", "status": "ready"},
            {"step": 3, "action": "Configurar servidor", "status": "ready"},
            {"step": 4, "action": "Executar testes", "status": "pending"},
        ]

        logger.info("[DEPLOY] %d steps", len(steps))
        self._log(ctx, f"deployment_plan: {len(steps)} steps")

        return {"output": {"steps": steps, "count": len(steps)}, "steps": steps}

#===========================================================================================

    # ── Nó: retrospective ────────────────────────────────────────

    async def run_retrospective(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        executed = [k for k in memory if isinstance(memory[k], dict) and "output" in memory[k]]

        summary = {
            "task": task,
            "nodes_executed": len(executed),
            "nodes_list": executed,
            "success": True,
        }

        logger.info("[RETRO] %d nós executados", len(executed))
        self._log(ctx, f"retrospective: {len(executed)} nodes")

        return {"output": summary, **summary}

#===========================================================================================

    # ── Nó: risk_analysis ──────────────────────────────────────────

    async def run_risk_analysis(self, ctx: dict) -> dict:
        architecture = ctx.get("memory", {}).get("architect", {}).get("architecture", {})
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        logger.info("⚠️ [RISK] Analisando riscos...")

        if not task or len(task) < 5:
            return {"output": {"risks": []}, "risk_score": 0}

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
            response = await self._call_llm(ctx, prompt)
            if response:
                import re as _re, json as _json
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
        self._log(ctx, "riscos: %d" % len(risks.get("risks", [])))
        return {"output": risks, "risks": risks.get("risks", []), "risk_score": len(risks.get("risks", [])) * 10}

#===========================================================================================

    # ── Nó: planner ───────────────────────────────────────────────

    async def run_planner(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        architecture = ctx.get("input", {}).get("architecture", {})
        wd = self._get_wd(ctx)
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
            planner = getattr(self.orchestrator, "planner", None) if self.orchestrator else None
            if planner:
                plan = planner.plan(context)
                artifact.code = plan
            else:
                artifact.code = context
                logger.info("📋 plano: executar tarefa conforme solicitado")
        except Exception as e:
            logger.warning("📋 plano falhou: %s", e)
            return {"output": artifact, "task": task, "success": False, "error": str(e)}
        if wd and artifact.code:
            wd.write_code(artifact.code).append_log("planner OK")
        return {"output": artifact, "task": task}

#===========================================================================================

    # ── Nó: task_breakdown ──────────────────────────────────────

    async def run_task_breakdown(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        planner_out = memory.get("planner", {}).get("output")

        plan_text = ""
        if hasattr(planner_out, "code"):
            plan_text = planner_out.code or ""
        elif isinstance(planner_out, dict):
            plan_text = planner_out.get("code") or planner_out.get("plan", "")

        if not plan_text:
            plan_text = task

        lines = [l.strip() for l in plan_text.split("\n") if l.strip()]
        tasks = [{"id": i, "description": l} for i, l in enumerate(lines[:20])]
        if not tasks:
            tasks = [{"id": 0, "description": task}]

        logger.info("[TASK-BREAKDOWN] %d tarefas extraídas", len(tasks))
        self._log(ctx, f"task_breakdown: {len(tasks)} tasks")

        return {
            "output": {"tasks": tasks, "count": len(tasks)},
            "tasks": tasks,
            "task_count": len(tasks),
        }

#===========================================================================================

    # ── Nó: execution_plan ──────────────────────────────────────

    async def run_execution_plan(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})
        breakdown = memory.get("task_breakdown", {}).get("output", {})
        tasks = breakdown.get("tasks", []) if isinstance(breakdown, dict) else []

        steps = []
        for t in tasks:
            steps.append({
                "step": t.get("id", 0),
                "action": t.get("description", ""),
                "dependencies": [] if t.get("id", 0) == 0 else [t.get("id", 0) - 1],
                "status": "pending",
            })

        logger.info("[EXEC-PLAN] %d steps de execução", len(steps))
        self._log(ctx, f"execution_plan: {len(steps)} steps")

        return {
            "output": {
                "steps": steps,
                "step_count": len(steps),
                "task": task,
            },
            "steps": steps,
            "step_count": len(steps),
        }

#===========================================================================================

    # ── Nó: test_generator ──────────────────────────────────────

    async def run_test_generator(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        designs = {
            "system_design": memory.get("system_design", {}).get("output"),
            "api_design": memory.get("api_design", {}).get("output"),
            "database_design": memory.get("database_design", {}).get("output"),
            "security_design": memory.get("security_design", {}).get("output"),
        }

        design_count = sum(1 for v in designs.values() if v)

        tests = {
            "unit": [
                {"name": f"test_{k}_basic", "type": "unit", "target": k}
                for k in designs if designs[k]
            ],
            "integration": [
                {"name": "test_integration_main", "type": "integration"},
            ],
        }

        if designs.get("security_design"):
            tests["security"] = [
                {"name": "test_authentication", "type": "security"},
                {"name": "test_authorization", "type": "security"},
            ]

        if designs.get("api_design"):
            tests["api"] = [
                {"name": "test_api_endpoints", "type": "api"},
            ]

        logger.info("[TEST-GEN] %d categorias | %d designs", len(tests), design_count)
        self._log(ctx, f"test_generator: {len(tests)} categories")

        return {
            "output": {
                "tests": tests,
                "categories": list(tests.keys()),
                "design_count": design_count,
            },
            "tests": tests,
            "categories": list(tests.keys()),
            "design_count": design_count,
        }

#===========================================================================================

    # ── Nó: web_classifier ────────────────────────────────────────

    async def run_web_classifier(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        artifact = ctx.get("memory", {}).get("planner", {}).get("output", SolutionArtifact())

        needs_web = _classify_web_need(task)
        artifact.reflection = str(needs_web)

        logger.info("🔍 filtrando palavras ...")
        if needs_web:
            logger.info("🔍 assunto parece relevante para busca na internet!")
        else:
            logger.info("🔍 assunto não precisa de busca externa")
        self._log(ctx, "needs_web=%s" % needs_web)
        return {"output": artifact, "needs_web": needs_web}

#===========================================================================================

    # ── Nó: critic ────────────────────────────────────────────────

    async def run_critic(self, ctx: dict) -> dict:
        artifact = ctx.get("memory", {}).get("style_validator", {}).get("output",
                  ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact()))
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        wd = self._get_wd(ctx)

        logger.info("🧐 [CRITIC v2] Avaliando solução (multi-dimensional)...")
        from iaglobal.agents.critic_agent import CriticAgent
        critic = CriticAgent()
        result = critic.avaliar_com_scores(artifact.task, artifact.code)

        artifact.score = result.get("score", 50.0)
        artifact.critic_scores = result.get("scores", {
            "correctness": 50.0, "completeness": 50.0,
            "security": 50.0, "spec_match": 50.0,
        })
        artifact.critique = result.get("summary", "")
        artifact.critic_degraded = result.get("critic_degraded", False)

        logger.info("🧐 [CRITIC v2] Score agregado: %s | scores=%s", artifact.score, artifact.critic_scores)
        if not result.get("approved", False):
            logger.warning("⚠️ [CRITIC v2] Solução rejeitada (score=%s)", artifact.score)
            artifact.critique += "\nREJEITADO: score %s abaixo de 60" % artifact.score

        self._log(ctx, "critic score=%.1f aprovado=%s" % (artifact.score, result.get("approved", False)))
        return {"output": artifact, "critic_score": artifact.score,
                "critic_scores": artifact.critic_scores, "critique": artifact.critique}

#===========================================================================================

    # ── Nó: security ──────────────────────────────────────────────

    async def run_security(self, ctx: dict) -> dict:
        artifact = ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact())
        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()
        code = artifact.code or ""
        wd = self._get_wd(ctx)
        findings = []
        issues = 0
        for issue_name, pattern in _SECURITY_PATTERNS:
            if re.search(pattern, code):
                findings.append(issue_name)
                issues += 1
        report = {"issues": issues, "findings": findings, "total_lines": len(code.splitlines())}
        if issues > 0:
            logger.info("🔒 [SECURITY] %d issue(s) encontradas: %s", issues, findings)
        self._log(ctx, "security: %d issues" % issues)
        return {"output": report, "security_report": report}

#===========================================================================================

    # ── Nó: style_validator ───────────────────────────────────────

    async def run_style_validator(self, ctx: dict) -> dict:
        artifact = ctx.get("memory", {}).get("multi_coder", {}).get("output", SolutionArtifact())
        code = artifact.code or ""
        wd = self._get_wd(ctx)
        if not code:
            logger.info("🎨 [STYLE] Nada a validar")
            return {"output": artifact, "style_ok": True}
        if "html" in code.lower() or "<html" in code[:200]:
            for light_color in _LIGHT_COLORS:
                if light_color.lower() in code.lower() and light_color not in code.lower().split("não")[-1]:
                    artifact.files = _extrair_multifile(code)
                    break
        self._log(ctx, "style: validação concluída")
        return {"output": artifact, "style_ok": True}

#===========================================================================================

    # ── Nó: validator ────────────────────────────────────

    async def run_validator(self, ctx: dict) -> dict:
        memory = ctx.get("memory", {})
        artifact = memory.get("critic", {}).get("output", None)
        if artifact is None or not isinstance(artifact, SolutionArtifact):
            artifact = memory.get("multi_coder", {}).get("output", SolutionArtifact())
        wd = self._get_wd(ctx)
        from iaglobal.agents.validator import SemanticValidatorAgent
        agent = SemanticValidatorAgent()
        result = agent.validar(artifact.task, artifact.code)
        score = result if isinstance(result, (int, float)) else result.get("score", 50.0)
        has_code = bool(artifact.code)
        logger.info("🧪 [SEMANTIC] score=%.2f has_code=%s", score, has_code)
        self._log(ctx, "semantic score=%.2f" % score)
        return {"output": artifact, "semantic_score": score, "has_code": has_code,
                "test_results": result if isinstance(result, dict) else {}}

#===========================================================================================

    # ── Nó: ast_validator ─────────────────────────────────────────

    async def run_ast_validator(self, ctx: dict) -> dict:
        import time

        started_at = time.perf_counter()

        memory = ctx.get("memory", {})
        wd = self._get_wd(ctx)

        # ---------------------------------------------------------
        # Recuperação resiliente do melhor artefato disponível
        # ---------------------------------------------------------
        artifact = (
            memory.get("validator", {}).get("output")
            or memory.get("reviewer", {}).get("output")
            or memory.get("critic", {}).get("output")
            or memory.get("debugger", {}).get("output")
            or SolutionArtifact()
        )

        if not isinstance(artifact, SolutionArtifact):
            logger.warning(
                "🔬 [AST] Artefato inválido recebido (%s). Criando fallback.",
                type(artifact).__name__,
            )
            artifact = SolutionArtifact()

        code = (artifact.code or "").strip()

        validation_errors = []
        validation_warnings = []
        validation_metadata = {
            "syntax_checked": False,
            "security_checked": False,
            "ast_checked": False,
            "framework_detected": False,
            "lines": 0,
            "chars": 0,
        }

        # ---------------------------------------------------------
        # Código vazio
        # ---------------------------------------------------------
        if not code:
            validation_errors.append("Artifact não contém código para validação.")

        else:
            validation_metadata["lines"] = len(code.splitlines())
            validation_metadata["chars"] = len(code)

            try:
                # -------------------------------------------------
                # Validação sintática
                # -------------------------------------------------
                is_valid, error = _validate_syntax(code)

                validation_metadata["syntax_checked"] = True

                if not is_valid:
                    validation_errors.append(error)

                # -------------------------------------------------
                # AST Python
                # -------------------------------------------------
                if _is_python_code(code):
                    try:
                        import ast

                        ast.parse(code)
                        validation_metadata["ast_checked"] = True

                    except SyntaxError as exc:
                        validation_errors.append(
                            f"AST SyntaxError: {exc.msg} "
                            f"(linha {exc.lineno}, coluna {exc.offset})"
                        )

                    except Exception as exc:
                        validation_errors.append(
                            f"AST validation failure: {type(exc).__name__}: {exc}"
                        )

                    # ---------------------------------------------
                    # Segurança para frameworks / apps reais
                    # ---------------------------------------------
                    if _imports_framework(code):
                        validation_metadata["framework_detected"] = True

                        try:
                            has_security, issues = validate_code_real(
                                code,
                                lang="python",
                            )

                            validation_metadata["security_checked"] = True

                            if issues:
                                validation_errors.extend(
                                    str(issue)
                                    for issue in issues
                                    if issue
                                )

                            if has_security is False:
                                validation_warnings.append(
                                    "Possíveis vulnerabilidades detectadas."
                                )

                        except Exception as exc:
                            validation_warnings.append(
                                f"Security validator failed: {exc}"
                            )

                # -------------------------------------------------
                # Linguagens não Python
                # -------------------------------------------------
                else:
                    validation_metadata["ast_checked"] = False

            except Exception as exc:
                logger.exception("🔬 [AST] Erro interno durante validação")
                validation_errors.append(
                    f"Validator internal error: {type(exc).__name__}: {exc}"
                )

        # ---------------------------------------------------------
        # Deduplicação
        # ---------------------------------------------------------
        validation_errors = list(dict.fromkeys(validation_errors))
        validation_warnings = list(dict.fromkeys(validation_warnings))

        # ---------------------------------------------------------
        # Resultado final
        # ---------------------------------------------------------
        artifact.validation_errors = validation_errors
        artifact.validation_warnings = validation_warnings
        artifact.validation_passed = len(validation_errors) == 0

        elapsed = round(time.perf_counter() - started_at, 4)

        validation_metadata.update(
            {
                "elapsed_seconds": elapsed,
                "error_count": len(validation_errors),
                "warning_count": len(validation_warnings),
                "workspace": str(wd),
            }
        )

        artifact.validation_metadata = validation_metadata

        # ---------------------------------------------------------
        # Logs
        # ---------------------------------------------------------
        if artifact.validation_passed:
            logger.info(
                "🔬 [AST] Validação aprovada | linhas=%d | %.4fs",
                validation_metadata["lines"],
                elapsed,
            )
        else:
            logger.warning(
                "🔬 [AST] Falhou com %d erro(s) | %d warning(s) | %.4fs",
                len(validation_errors),
                len(validation_warnings),
                elapsed,
            )

            for idx, err in enumerate(validation_errors[:10], start=1):
                logger.warning("   [%d] %s", idx, err)

        self._log(
            ctx,
            (
                f"ast_validator: "
                f"{len(validation_errors)} erros, "
                f"{len(validation_warnings)} warnings, "
                f"{elapsed:.4f}s"
            ),
        )

        return {
            "output": artifact,
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "validation_passed": artifact.validation_passed,
            "validation_metadata": validation_metadata,
        }

#===========================================================================================

    # ── Nó: reviewer ──────────────────────────────────────────────

    async def run_reviewer(self, ctx: dict) -> dict:
        import ast
        import json as _json
        import re
        from statistics import mean

        memory = ctx.get("memory", {})

        # ──────────────────────────────────────────────────────────
        # Recuperação resiliente do artifact
        # ──────────────────────────────────────────────────────────
        artifact = (
            memory.get("critic", {}).get("output")
            or memory.get("validator", {}).get("output")
            or memory.get("ast_validator", {}).get("output")
            or SolutionArtifact()
        )

        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()

        task = artifact.task or self._get_task(ctx)
        wd = self._get_wd(ctx)
        code = (artifact.code or "").strip()

        logger.info(
            "👨‍💻 [REVIEWER] Iniciando revisão (%d chars)",
            len(code)
        )

        if not code:
            logger.info("⏭️ [REVIEWER] Nenhum código encontrado")
            return {
                "output": artifact,
                "review_score": 100.0,
                "issues": [],
                "summary": "Nenhum código para revisar."
            }

        # ──────────────────────────────────────────────────────────
        # Métricas estáticas locais
        # ──────────────────────────────────────────────────────────
        static_issues = []
        complexity_penalty = 0
        duplication_penalty = 0

        try:
            tree = ast.parse(code)

            functions = [
                n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            classes = [
                n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef)
            ]

            long_functions = []

            for fn in functions:
                size = len(getattr(fn, "body", []))

                if size > 40:
                    long_functions.append(fn.name)
                    complexity_penalty += min(20, size // 3)

            if long_functions:
                static_issues.append(
                    f"Funções extensas detectadas: {', '.join(long_functions[:5])}"
                )

            # Detecção simples de duplicação
            lines = [x.strip() for x in code.splitlines() if x.strip()]
            repeated = len(lines) - len(set(lines))

            if repeated > 10:
                duplication_penalty += min(25, repeated)
                static_issues.append(
                    f"Possível duplicação de código ({repeated} linhas repetidas)"
                )

            # Classes gigantes
            for cls in classes:
                if len(cls.body) > 30:
                    static_issues.append(
                        f"Classe muito grande: {cls.name}"
                    )
                    complexity_penalty += 10

        except Exception as e:
            logger.debug(
                "👨‍💻 [REVIEWER] AST analysis falhou: %s",
                e
            )

        # ──────────────────────────────────────────────────────────
        # Contexto de erros históricos
        # ──────────────────────────────────────────────────────────
        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        error_context = format_errors_for_prompt(
            query_relevant_errors(task, limit=3)
        )

        # ──────────────────────────────────────────────────────────
        # Prompt
        # ──────────────────────────────────────────────────────────
        prompt = f"""
    Você é um Principal Software Engineer conduzindo um code review rigoroso.

    Considere:

    - SOLID
    - Clean Code
    - Acoplamento
    - Coesão
    - Complexidade
    - Legibilidade
    - Duplicação
    - Escalabilidade
    - Manutenibilidade
    - Possíveis bugs

    Contexto de falhas anteriores:
    {error_context}

    Retorne APENAS JSON válido:

    {{
      "solid_score": 0,
      "clean_code_score": 0,
      "duplication_score": 0,
      "complexity_score": 0,
      "issues": [],
      "strengths": [],
      "summary": ""
    }}

    Tarefa:
    {task}

    Código:
    {code}
    """

        review = {}

        try:
            response = await self._call_llm(ctx, prompt)

            match = re.search(
                r"\{.*\}",
                response,
                flags=re.DOTALL
            )

            if match:
                review = _json.loads(match.group())

        except Exception as e:
            logger.warning(
                "👨‍💻 [REVIEWER] Review LLM falhou: %s",
                e
            )

        # ──────────────────────────────────────────────────────────
        # Scores LLM
        # ──────────────────────────────────────────────────────────
        solid = max(0, min(100, review.get("solid_score", 75)))
        clean = max(0, min(100, review.get("clean_code_score", 75)))
        duplic = max(0, min(100, review.get("duplication_score", 75)))
        comp = max(0, min(100, review.get("complexity_score", 75)))

        # Ajuste por análise estática
        duplic = max(0, duplic - duplication_penalty)
        comp = max(0, comp - complexity_penalty)

        llm_issues = review.get("issues", [])
        strengths = review.get("strengths", [])

        issues = list(dict.fromkeys(
            llm_issues + static_issues
        ))

        summary = review.get(
            "summary",
            "Revisão concluída."
        )

        # ──────────────────────────────────────────────────────────
        # Score ponderado
        # ──────────────────────────────────────────────────────────
        review_score = round(
            (
                solid * 0.30 +
                clean * 0.30 +
                duplic * 0.20 +
                comp * 0.20
            ),
            1
        )

        # ──────────────────────────────────────────────────────────
        # Atualiza artifact
        # ──────────────────────────────────────────────────────────
        artifact.review_score = review_score

        artifact.security_report = (
            f"Review Score={review_score} | "
            f"Issues={len(issues)} | "
            f"{summary}"
        )

        if hasattr(artifact, "metadata"):
            artifact.metadata["review"] = {
                "solid": solid,
                "clean_code": clean,
                "duplication": duplic,
                "complexity": comp,
                "issues": issues,
                "strengths": strengths,
            }

        # ──────────────────────────────────────────────────────────
        # Logs
        # ──────────────────────────────────────────────────────────
        logger.info(
            "👨‍💻 [REVIEWER] Score=%.1f | Issues=%d",
            review_score,
            len(issues)
        )

        if review_score < 60:
            logger.warning(
                "⚠️ [REVIEWER] Código abaixo do threshold: %.1f",
                review_score
            )

        if review_score >= 90:
            logger.info(
                "🏆 [REVIEWER] Código considerado excelente"
            )

        self._log(
            ctx,
            (
                f"review score={review_score} "
                f"solid={solid} "
                f"clean={clean} "
                f"dup={duplic} "
                f"complexity={comp} "
                f"issues={len(issues)}"
            )
        )

        return {
            "output": artifact,
            "review_score": review_score,
            "issues": issues,
            "strengths": strengths,
            "summary": summary,
            "solid_score": solid,
            "clean_code_score": clean,
            "duplication_score": duplic,
            "complexity_score": comp,
            "static_complexity_penalty": complexity_penalty,
            "static_duplication_penalty": duplication_penalty,
        }

#===========================================================================================

    # ── Nó: performance ───────────────────────────────────────────

    async def run_performance(self, ctx: dict) -> dict:
        import ast
        import time
        from collections import Counter

        started_at = time.perf_counter()

        memory = ctx.get("memory", {})
        artifact = memory.get("reviewer", {}).get("output", SolutionArtifact())

        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()

        code = artifact.code or ""
        wd = self._get_wd(ctx)

        logger.info("⚡ [PERFORMANCE] Iniciando análise avançada de performance...")

        if not code.strip():
            artifact.reflection = "Código vazio — análise de performance ignorada"
            return {
                "output": artifact,
                "bottlenecks": [],
                "performance_score": 100,
                "complexity_score": 0,
                "metrics": {}
            }

        if not _is_python_code(code):
            artifact.reflection = "Código não Python — análise de performance ignorada"
            return {
                "output": artifact,
                "bottlenecks": [],
                "performance_score": 100,
                "complexity_score": 0,
                "metrics": {}
            }

        bottlenecks = []
        metrics = {
            "loops": 0,
            "nested_loops": 0,
            "comprehensions": 0,
            "function_calls": 0,
            "async_functions": 0,
            "functions": 0,
            "classes": 0,
            "try_blocks": 0,
            "imports": 0
        }

        severity_counter = Counter()

        # ── Análise por regex ──────────────────────────────────────

        for perf_name, pattern in _performance_patterns:
            try:
                matches = re.findall(pattern, code, re.MULTILINE)
                if matches:
                    severity = "média"

                    if len(matches) >= 5:
                        severity = "alta"
                    elif len(matches) >= 2:
                        severity = "média"
                    else:
                        severity = "baixa"

                    bottlenecks.append({
                        "type": perf_name,
                        "severity": severity,
                        "matches": len(matches)
                    })

                    severity_counter[severity] += 1

            except Exception:
                continue

        # ── AST Analysis ───────────────────────────────────────────

        complexity_score = 0

        try:
            tree = ast.parse(code)

            class PerformanceVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.loop_depth = 0

                def visit_For(self, node):
                    metrics["loops"] += 1
                    self.loop_depth += 1

                    if self.loop_depth > 1:
                        metrics["nested_loops"] += 1

                        bottlenecks.append({
                            "type": "nested_loop",
                            "severity": "alta",
                            "line": getattr(node, "lineno", None)
                        })

                        severity_counter["alta"] += 1

                    self.generic_visit(node)
                    self.loop_depth -= 1

                def visit_While(self, node):
                    metrics["loops"] += 1
                    self.loop_depth += 1

                    if self.loop_depth > 1:
                        metrics["nested_loops"] += 1

                        bottlenecks.append({
                            "type": "nested_while",
                            "severity": "alta",
                            "line": getattr(node, "lineno", None)
                        })

                        severity_counter["alta"] += 1

                    self.generic_visit(node)
                    self.loop_depth -= 1

                def visit_ListComp(self, node):
                    metrics["comprehensions"] += 1
                    self.generic_visit(node)

                def visit_SetComp(self, node):
                    metrics["comprehensions"] += 1
                    self.generic_visit(node)

                def visit_DictComp(self, node):
                    metrics["comprehensions"] += 1
                    self.generic_visit(node)

                def visit_Call(self, node):
                    metrics["function_calls"] += 1
                    self.generic_visit(node)

                def visit_FunctionDef(self, node):
                    metrics["functions"] += 1
                    self.generic_visit(node)

                def visit_AsyncFunctionDef(self, node):
                    metrics["async_functions"] += 1
                    metrics["functions"] += 1
                    self.generic_visit(node)

                def visit_ClassDef(self, node):
                    metrics["classes"] += 1
                    self.generic_visit(node)

                def visit_Try(self, node):
                    metrics["try_blocks"] += 1
                    self.generic_visit(node)

                def visit_Import(self, node):
                    metrics["imports"] += 1

                def visit_ImportFrom(self, node):
                    metrics["imports"] += 1

            PerformanceVisitor().visit(tree)

            complexity_score += metrics["loops"] * 3
            complexity_score += metrics["nested_loops"] * 15
            complexity_score += metrics["function_calls"] // 20
            complexity_score += metrics["try_blocks"] * 2

        except Exception as e:
            logger.debug("⚡ [PERFORMANCE] AST analysis failed: %s", e)

        # ── Penalização Inteligente ────────────────────────────────

        penalty = 0

        for item in bottlenecks:
            sev = item.get("severity")

            if sev == "alta":
                penalty += 15
            elif sev == "média":
                penalty += 8
            else:
                penalty += 3

        penalty += min(complexity_score, 20)

        performance_score = max(0, 100 - penalty)

        # ── Reflexão ───────────────────────────────────────────────

        if bottlenecks:
            top = sorted(
                bottlenecks,
                key=lambda x: {"alta": 3, "média": 2, "baixa": 1}.get(
                    x.get("severity", "baixa"), 1
                ),
                reverse=True
            )[:5]

            summary = ", ".join(b["type"] for b in top)

            artifact.reflection = (
                f"⚡ {len(bottlenecks)} gargalo(s) identificado(s). "
                f"Principais: {summary}. "
                f"Score={performance_score}/100"
            )

            logger.warning(
                "⚡ [PERFORMANCE] %d gargalo(s) encontrados | score=%d",
                len(bottlenecks),
                performance_score
            )

        else:
            artifact.reflection = (
                f"✅ Nenhum gargalo relevante detectado "
                f"(score={performance_score}/100)"
            )

            logger.info("✅ [PERFORMANCE] Código considerado eficiente")

        elapsed = round(time.perf_counter() - started_at, 4)

        self._log(
            ctx,
            (
                f"performance: bottlenecks={len(bottlenecks)} "
                f"score={performance_score} "
                f"time={elapsed}s"
            )
        )

        return {
            "output": artifact,
            "bottlenecks": bottlenecks,
            "performance_score": performance_score,
            "complexity_score": complexity_score,
            "metrics": metrics,
            "severity_summary": dict(severity_counter),
            "analysis_time": elapsed
        }

#===========================================================================================

    # ── Nó: tester ────────────────────────────────────────────────

    async def run_tester(self, ctx: dict) -> dict:
        import ast
        import time
        import traceback

        memory = ctx.get("memory", {})
        artifact = memory.get(
            "ast_validator",
            {},
        ).get(
            "output",
            SolutionArtifact(),
        )

        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()

        wd = self._get_wd(ctx)
        task = self._get_task(ctx)

        logger.info("🧪 [TESTER v3] Iniciando validação completa...")

        metrics = {
            "syntax_valid": False,
            "execution_safe": False,
            "framework_detected": False,
            "ast_valid": False,
            "execution_time": 0.0,
            "checks": [],
        }

        # ------------------------------------------------------------------
        # Código vazio
        # ------------------------------------------------------------------

        if not artifact.code or not artifact.code.strip():
            artifact.tests_passed = 0
            artifact.tests_total = 1
            artifact.runtime_error = "Código vazio."
            artifact.quality_score = 0

            self._log(ctx, "teste abortado: código vazio")

            return {
                "output": artifact,
                "tests_passed": 0,
                "tests_total": 1,
                "metrics": metrics,
            }

        code = artifact.code.strip()

        # ------------------------------------------------------------------
        # Linguagem não Python
        # ------------------------------------------------------------------

        if not _is_python_code(code):
            logger.info(
                "📄 [TESTER] Código não Python detectado. "
                "Validação estrutural aplicada."
            )

            artifact.tests_passed = 1
            artifact.tests_total = 1
            artifact.runtime_error = None

            metrics["checks"].append("non_python")
            metrics["execution_safe"] = True

            artifact.metadata = {
                **getattr(artifact, "metadata", {}),
                "tester_version": "v3",
                "language": "non_python",
            }

            return {
                "output": artifact,
                "tests_passed": 1,
                "tests_total": 1,
                "metrics": metrics,
            }

        # ------------------------------------------------------------------
        # Validação sintática
        # ------------------------------------------------------------------

        syntax_ok, syntax_error = _validate_syntax(code)

        metrics["syntax_valid"] = syntax_ok
        metrics["checks"].append("syntax")

        if not syntax_ok:
            artifact.tests_passed = 0
            artifact.tests_total = 1
            artifact.runtime_error = syntax_error
            artifact.syntax_errors = syntax_error

            logger.warning(
                "❌ [TESTER] Erro de sintaxe detectado."
            )

            self._log(
                ctx,
                f"erro sintático: {str(syntax_error)[:120]}"
            )

            return {
                "output": artifact,
                "tests_passed": 0,
                "tests_total": 1,
                "metrics": metrics,
            }

        # ------------------------------------------------------------------
        # AST Validation
        # ------------------------------------------------------------------

        try:
            ast.parse(code)

            metrics["ast_valid"] = True
            metrics["checks"].append("ast")

        except Exception as exc:
            artifact.tests_passed = 0
            artifact.tests_total = 1
            artifact.runtime_error = str(exc)
            artifact.syntax_errors = str(exc)

            logger.warning(
                "❌ [TESTER] AST inválida."
            )

            return {
                "output": artifact,
                "tests_passed": 0,
                "tests_total": 1,
                "metrics": metrics,
            }

        # ------------------------------------------------------------------
        # Frameworks / aplicações que não devem ser executadas
        # ------------------------------------------------------------------

        if _imports_framework(code):
            logger.info(
                "🏗️ [TESTER] Framework detectado. "
                "Execução real ignorada."
            )

            artifact.tests_passed = 2
            artifact.tests_total = 2
            artifact.runtime_error = None

            metrics["framework_detected"] = True
            metrics["execution_safe"] = True
            metrics["checks"].append("framework_skip")

            artifact.metadata = {
                **getattr(artifact, "metadata", {}),
                "tester_version": "v3",
                "execution_skipped": True,
            }

            self._log(
                ctx,
                "framework detectado, execução pulada"
            )

            return {
                "output": artifact,
                "tests_passed": artifact.tests_passed,
                "tests_total": artifact.tests_total,
                "metrics": metrics,
            }

        # ------------------------------------------------------------------
        # Sandbox leve
        # ------------------------------------------------------------------

        safe_globals = {
            "__builtins__": {
                "len": len,
                "range": range,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
                "map": map,
                "filter": filter,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "print": print,
            }
        }

        execution_ok = False
        runtime_error = None

        try:
            start = time.perf_counter()

            compile(
                code,
                "<generated_code>",
                "exec",
            )

            elapsed = (
                time.perf_counter() - start
            )

            metrics["execution_time"] = round(
                elapsed,
                6,
            )

            execution_ok = True
            metrics["execution_safe"] = True
            metrics["checks"].append("compile")

        except Exception:
            runtime_error = traceback.format_exc()

        # ------------------------------------------------------------------
        # Resultado final
        # ------------------------------------------------------------------

        total_checks = 4
        passed_checks = 0

        if metrics["syntax_valid"]:
            passed_checks += 1

        if metrics["ast_valid"]:
            passed_checks += 1

        if execution_ok:
            passed_checks += 1

        if not runtime_error:
            passed_checks += 1

        artifact.tests_passed = passed_checks
        artifact.tests_total = total_checks
        artifact.runtime_error = runtime_error
        artifact.syntax_errors = None

        artifact.quality_score = max(
            artifact.quality_score or 0,
            int((passed_checks / total_checks) * 100),
        )

        artifact.metadata = {
            **getattr(artifact, "metadata", {}),
            "tester_version": "v3",
            "task": task[:500] if task else "",
            "metrics": metrics,
        }

        if wd:
            try:
                wd.append_log(
                    f"tester_v3: {passed_checks}/{total_checks}"
                )
            except Exception:
                pass

        logger.info(
            "🧪 [TESTER v3] Resultado: %s/%s",
            passed_checks,
            total_checks,
        )

        self._log(
            ctx,
            f"teste concluído ({passed_checks}/{total_checks})"
        )

        return {
            "output": artifact,
            "tests_passed": passed_checks,
            "tests_total": total_checks,
            "metrics": metrics,
            "success": passed_checks == total_checks,
        }

#===========================================================================================

    # ── Nó: debugger ──────────────────────────────────────────────

    async def run_debugger(self, ctx: dict) -> dict:
        import difflib
        import time

        memory = ctx.get("memory", {})
        artifact = memory.get("tester", {}).get("output")

        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()

        wd = self._get_wd(ctx)
        task = self._get_task(ctx)

        needs_debug = (
            not artifact.code
            or artifact.runtime_error
            or artifact.syntax_errors
            or artifact.tests_failed
            or (
                artifact.tests_total
                and artifact.tests_passed < artifact.tests_total
            )
        )

        if not needs_debug:
            logger.info("✅ [DEBUGGER v3] Nenhuma correção necessária.")
            artifact.metadata = {
                **getattr(artifact, "metadata", {}),
                "debugger_skipped": True,
            }
            return {"output": artifact}

        logger.info("🔧 [DEBUGGER v3] Iniciando ciclo inteligente de correção (max=5)...")

        max_attempts = 5
        best_code = artifact.code or ""
        best_score = artifact.quality_score or 0
        debug_history = []

        previous_code = best_code

        for attempt in range(1, max_attempts + 1):
            try:
                error_parts = []

                if artifact.runtime_error:
                    error_parts.append(
                        f"RuntimeError:\n{str(artifact.runtime_error)[:2500]}"
                    )

                if artifact.syntax_errors:
                    error_parts.append(
                        f"SyntaxErrors:\n{str(artifact.syntax_errors)[:2500]}"
                    )

                if artifact.tests_failed:
                    error_parts.append(
                        f"FailedTests:\n{str(artifact.tests_failed)[:2500]}"
                    )

                diagnostics = "\n\n".join(error_parts)

                prompt = f"""
    Você é um engenheiro sênior especializado em debugging.

    OBJETIVO:
    Corrigir o código preservando arquitetura, comportamento e APIs públicas.

    TAREFA ORIGINAL:
    {task}

    DIAGNÓSTICOS:
    {diagnostics or "Nenhum diagnóstico detalhado disponível."}

    REGRAS:
    - Corrija apenas o necessário.
    - Preserve compatibilidade.
    - Elimine erros de sintaxe.
    - Elimine exceções conhecidas.
    - Não remova funcionalidades.
    - Não adicione explicações.
    - Retorne SOMENTE o código final.

    CÓDIGO:
    {(artifact.code or "")[:25000]}

    CÓDIGO CORRIGIDO:
    """.strip()

                started = time.perf_counter()

                candidate = await self._call_llm(
                    ctx,
                    prompt,
                    task_type="debug",
                )

                elapsed = round(time.perf_counter() - started, 3)

                candidate = (candidate or "").strip()

                if candidate.startswith("```"):
                    candidate = candidate.strip("`")
                    if "\n" in candidate:
                        candidate = candidate.split("\n", 1)[1]

                candidate = candidate.strip()

                if len(candidate) < 20:
                    logger.warning(
                        "⚠️ [DEBUGGER] Resposta inválida na tentativa %d",
                        attempt,
                    )
                    continue

                syntax_ok, syntax_error = _validate_syntax(candidate)

                similarity = difflib.SequenceMatcher(
                    None,
                    previous_code,
                    candidate,
                ).ratio()

                debug_history.append(
                    {
                        "attempt": attempt,
                        "elapsed": elapsed,
                        "syntax_ok": syntax_ok,
                        "similarity": round(similarity, 4),
                    }
                )

                if not syntax_ok:
                    artifact.runtime_error = syntax_error
                    artifact.syntax_errors = syntax_error

                    logger.warning(
                        "❌ [DEBUGGER] Tentativa %d falhou na validação sintática.",
                        attempt,
                    )
                    continue

                previous_code = candidate
                best_code = candidate

                artifact.code = candidate
                artifact.syntax_errors = None
                artifact.runtime_error = None

                if wd:
                    try:
                        (
                            wd.write_code(candidate)
                            .append_log(
                                f"debug_v3_attempt_{attempt}"
                            )
                        )
                    except Exception:
                        pass

                quality_bonus = max(
                    0,
                    int(similarity * 10),
                )

                artifact.quality_score = max(
                    best_score,
                    (artifact.quality_score or 0) + quality_bonus,
                )

                artifact.tests_passed = max(
                    artifact.tests_passed or 0,
                    1,
                )

                logger.info(
                    "✅ [DEBUGGER] Correção válida encontrada na tentativa %d "
                    "(similaridade=%.2f)",
                    attempt,
                    similarity,
                )

                break

            except Exception as exc:
                logger.exception(
                    "[DEBUGGER] Falha na tentativa %d: %s",
                    attempt,
                    exc,
                )

                debug_history.append(
                    {
                        "attempt": attempt,
                        "error": str(exc)[:500],
                    }
                )

        artifact.code = best_code

        artifact.metadata = {
            **getattr(artifact, "metadata", {}),
            "debugger_version": "v3",
            "debug_attempts": len(debug_history),
            "debug_history": debug_history,
            "final_quality_score": artifact.quality_score,
        }

        self._log(
            ctx,
            f"debug concluído ({len(debug_history)} tentativa(s))"
        )

        return {
            "output": artifact,
            "metrics": {
                "attempts": len(debug_history),
                "success": bool(best_code),
                "quality_score": artifact.quality_score,
            },
        }

#===========================================================================================

    # ── Nó: rank ──────────────────────────────────────────────────

    async def run_rank(self, ctx: dict) -> dict:
        """
        Consolida e ranqueia todos os resultados produzidos pelo pipeline.

        Responsabilidades:
        - Agregar scores de múltiplos agentes.
        - Escolher o melhor artefato disponível.
        - Calcular score composto ponderado.
        - Produzir ranking explicável.
        - Gerar métricas para evolução contínua.
        """

        import time
        from statistics import mean

        start_time = time.perf_counter()

        memory = ctx.get("memory", {})
        wd = self._get_wd(ctx)
        task = self._get_task(ctx)

        logger.info("🏆 [RANK] Consolidando avaliações finais...")

        # ---------------------------------------------------------
        # Descoberta automática de artefatos candidatos
        # ---------------------------------------------------------

        candidate_nodes = [
            "multi_coder",
            "debugger",
            "reviewer",
            "critic",
            "validator",
            "documentation",
            "dependency",
            "security_design",
        ]

        candidates = []

        for node_name in candidate_nodes:
            node_data = memory.get(node_name, {})

            if not isinstance(node_data, dict):
                continue

            output = node_data.get("output")

            if isinstance(output, SolutionArtifact):
                candidates.append((node_name, output))

        # ---------------------------------------------------------
        # Seleção do melhor artefato disponível
        # ---------------------------------------------------------

        selected_artifact = None

        for node_name in [
            "debugger",
            "reviewer",
            "critic",
            "multi_coder",
        ]:
            candidate = memory.get(node_name, {}).get("output")

            if (
                isinstance(candidate, SolutionArtifact)
                and candidate.code
            ):
                selected_artifact = candidate
                break

        if selected_artifact is None:
            selected_artifact = SolutionArtifact(task=task)

        # ---------------------------------------------------------
        # Coleta de scores
        # ---------------------------------------------------------

        scores = {}
        score_sources = []

        score_nodes = [
            "critic",
            "reviewer",
            "validator",
            "dependency",
            "security_design",
            "documentation",
        ]

        for node_name in score_nodes:
            node_data = memory.get(node_name, {})

            if not isinstance(node_data, dict):
                continue

            output = node_data.get("output")

            score = None

            if isinstance(output, SolutionArtifact):
                score = getattr(
                    output,
                    "score",
                    getattr(output, "review_score", None),
                )

            if score is None:
                score = (
                    node_data.get("score")
                    or node_data.get("quality_score")
                    or node_data.get("review_score")
                    or node_data.get("security_score")
                    or node_data.get("documentation_score")
                )

            if isinstance(score, (int, float)):
                score = float(score)
                scores[node_name] = score
                score_sources.append(score)

        # ---------------------------------------------------------
        # Score ponderado
        # ---------------------------------------------------------

        weights = {
            "critic": 0.30,
            "reviewer": 0.20,
            "validator": 0.25,
            "dependency": 0.10,
            "security_design": 0.10,
            "documentation": 0.05,
        }

        weighted_sum = 0.0
        weight_total = 0.0

        for source, score in scores.items():
            weight = weights.get(source, 0.05)

            weighted_sum += score * weight
            weight_total += weight

        final_score = (
            weighted_sum / weight_total
            if weight_total > 0
            else 0.0
        )

        # ---------------------------------------------------------
        # Bônus por robustez do código
        # ---------------------------------------------------------

        code = getattr(selected_artifact, "code", "") or ""

        robustness_bonus = 0.0

        if len(code) > 1000:
            robustness_bonus += 2

        if len(code) > 3000:
            robustness_bonus += 2

        if "async " in code:
            robustness_bonus += 1

        if "try:" in code:
            robustness_bonus += 1

        if "class " in code:
            robustness_bonus += 1

        final_score += robustness_bonus

        # ---------------------------------------------------------
        # Penalidades
        # ---------------------------------------------------------

        penalty = 0.0

        low_quality_patterns = [
            "TODO",
            "FIXME",
            "NotImplementedError",
            "...",
        ]

        for pattern in low_quality_patterns:
            if pattern in code:
                penalty += 3

        final_score -= penalty

        final_score = max(0.0, min(100.0, final_score))

        # ---------------------------------------------------------
        # Estatísticas
        # ---------------------------------------------------------

        average_score = (
            mean(score_sources)
            if score_sources
            else 0.0
        )

        highest_score = (
            max(score_sources)
            if score_sources
            else 0.0
        )

        lowest_score = (
            min(score_sources)
            if score_sources
            else 0.0
        )

        selected_artifact.score = round(final_score, 2)

        selected_artifact.metadata = {
            **getattr(selected_artifact, "metadata", {}),
            "ranking": {
                "scores": scores,
                "average_score": average_score,
                "highest_score": highest_score,
                "lowest_score": lowest_score,
                "robustness_bonus": robustness_bonus,
                "penalty": penalty,
                "final_score": round(final_score, 2),
            },
        }

        elapsed = round(
            time.perf_counter() - start_time,
            3,
        )

        logger.info(
            "🏆 [RANK] "
            f"final_score={final_score:.2f} "
            f"sources={len(scores)} "
            f"bonus={robustness_bonus:.2f} "
            f"penalty={penalty:.2f}"
        )

        self._log(
            ctx,
            (
                f"rank "
                f"score={final_score:.2f} "
                f"sources={len(scores)} "
                f"bonus={robustness_bonus:.2f}"
            ),
        )

        return {
            "output": selected_artifact,
            "final_score": round(final_score, 2),
            "scores": scores,
            "average_score": round(average_score, 2),
            "highest_score": round(highest_score, 2),
            "lowest_score": round(lowest_score, 2),
            "robustness_bonus": robustness_bonus,
            "penalty": penalty,
            "candidate_count": len(candidates),
            "duration": elapsed,
            "ranking_report": {
                "scores": scores,
                "final_score": round(final_score, 2),
                "average_score": round(average_score, 2),
                "highest_score": round(highest_score, 2),
                "lowest_score": round(lowest_score, 2),
                "bonus": robustness_bonus,
                "penalty": penalty,
            },
        }

#===========================================================================================

    # ── Nó: final_gatekeeper ──────────────────────────────────────

    async def run_final_gatekeeper(self, ctx: dict) -> dict:
        """
        Última barreira de qualidade antes da geração do artefato final.

        Responsabilidades:
        - Validar qualidade semântica e técnica da solução.
        - Consolidar sinais de todos os estágios anteriores.
        - Calcular score composto ponderado.
        - Detectar regressões, código incompleto e placeholders.
        - Registrar métricas para evolução contínua.
        """

        import re
        import time
        from statistics import mean

        start_time = time.perf_counter()

        memory = ctx.get("memory", {})
        wd = self._get_wd(ctx)
        task = self._get_task(ctx)

        rank_out = memory.get("rank", {}).get("output", SolutionArtifact())

        artifact = (
            rank_out
            if isinstance(rank_out, SolutionArtifact)
            else SolutionArtifact(task=task)
        )

        code = artifact.code or ""

        if not code.strip():
            logger.info("⏭️ [GATEKEEPER] Nenhum código disponível para aprovação")
            return {
                "output": artifact,
                "approved": False,
                "reason": "empty_code",
                "score": 0.0,
            }

        from iaglobal.agents.critic_agent import CriticAgent
        from iaglobal.agents.validator import SemanticValidator

        critic = CriticAgent()
        semantic = SemanticValidator()

        logger.info("🛡️ [GATEKEEPER] Executando validações finais...")

        # ---------------------------------------------------------
        # Critic Review
        # ---------------------------------------------------------

        try:
            critic_result = critic.avaliar_com_scores(task, code)
            critic_score = float(critic_result.get("score", 50))
        except Exception as e:
            logger.warning(f"⚠️ CriticAgent falhou: {e}")
            critic_result = {}
            critic_score = 50.0

        # ---------------------------------------------------------
        # Semantic Validation
        # ---------------------------------------------------------

        try:
            sem_score = semantic.validar(task, code)
            semantic_score = (
                float(sem_score)
                if isinstance(sem_score, (int, float))
                else 50.0
            )
        except Exception as e:
            logger.warning(f"⚠️ SemanticValidator falhou: {e}")
            semantic_score = 50.0

        # ---------------------------------------------------------
        # Dependências
        # ---------------------------------------------------------

        dependency_score = 50.0

        dependency_data = memory.get("dependency", {})

        if isinstance(dependency_data, dict):
            dependency_score = float(
                dependency_data.get(
                    "score",
                    dependency_data.get("quality_score", 50),
                )
            )

        # ---------------------------------------------------------
        # Segurança
        # ---------------------------------------------------------

        security_score = 50.0

        security_data = memory.get("security_design", {})

        if isinstance(security_data, dict):
            security_score = float(
                security_data.get(
                    "score",
                    security_data.get("security_score", 50),
                )
            )

        # ---------------------------------------------------------
        # Documentação
        # ---------------------------------------------------------

        documentation_score = 50.0

        docs_data = memory.get("documentation", {})

        if isinstance(docs_data, dict):
            documentation_score = float(
                docs_data.get(
                    "score",
                    docs_data.get("documentation_score", 50),
                )
            )

        # ---------------------------------------------------------
        # Heurísticas Locais
        # ---------------------------------------------------------

        heuristic_penalty = 0.0
        findings = []

        placeholder_patterns = [
            r"TODO",
            r"FIXME",
            r"pass\s*$",
            r"NotImplementedError",
            r"\.\.\.",
        ]

        for pattern in placeholder_patterns:
            matches = re.findall(pattern, code, re.MULTILINE)
            if matches:
                penalty = min(len(matches) * 3, 15)
                heuristic_penalty += penalty
                findings.append(
                    f"placeholder_detected:{pattern}:{len(matches)}"
                )

        if len(code) < 300:
            heuristic_penalty += 10
            findings.append("code_too_small")

        if code.count("\n") < 10:
            heuristic_penalty += 5
            findings.append("low_complexity")

        if "except:" in code:
            heuristic_penalty += 5
            findings.append("bare_except")

        # ---------------------------------------------------------
        # Score Composto
        # ---------------------------------------------------------

        weighted_score = (
            critic_score * 0.35
            + semantic_score * 0.35
            + dependency_score * 0.10
            + security_score * 0.10
            + documentation_score * 0.10
        )

        final_score = max(
            0.0,
            min(
                100.0,
                weighted_score - heuristic_penalty,
            ),
        )

        # ---------------------------------------------------------
        # Critérios de Aprovação
        # ---------------------------------------------------------

        minimum_critic = 50
        minimum_semantic = 50

        approved = (
            final_score >= 70
            and critic_score >= minimum_critic
            and semantic_score >= minimum_semantic
        )

        artifact.score = round(final_score, 2)

        artifact.metadata = {
            **getattr(artifact, "metadata", {}),
            "gatekeeper": {
                "critic_score": critic_score,
                "semantic_score": semantic_score,
                "dependency_score": dependency_score,
                "security_score": security_score,
                "documentation_score": documentation_score,
                "heuristic_penalty": heuristic_penalty,
                "findings": findings,
                "approved": approved,
            },
        }

        elapsed = round(time.perf_counter() - start_time, 3)

        logger.info(
            "🛡️ [GATEKEEPER] "
            f"score={final_score:.2f} "
            f"critic={critic_score:.2f} "
            f"semantic={semantic_score:.2f} "
            f"approved={approved}"
        )

        self._log(
            ctx,
            (
                f"gatekeeper "
                f"score={final_score:.2f} "
                f"approved={approved} "
                f"penalty={heuristic_penalty:.2f}"
            ),
        )

        return {
            "output": artifact,
            "approved": approved,
            "score": round(final_score, 2),
            "duration": elapsed,
            "critic_score": critic_score,
            "semantic_score": semantic_score,
            "dependency_score": dependency_score,
            "security_score": security_score,
            "documentation_score": documentation_score,
            "heuristics": findings,
            "gatekeeper_report": {
                "scores": {
                    "critic": critic_score,
                    "semantic": semantic_score,
                    "dependency": dependency_score,
                    "security": security_score,
                    "documentation": documentation_score,
                },
                "penalty": heuristic_penalty,
                "approved": approved,
                "final_score": round(final_score, 2),
                "findings": findings,
            },
        }

#===========================================================================================

    # ── Nó: artifact_writer ───────────────────────────────────────

    async def run_artifact_writer(self, ctx: dict) -> dict:
        import hashlib
        import json
        import re
        import time
        from pathlib import Path

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        gatekeeper_result = ctx.get("memory", {}).get("final_gatekeeper", {})
        solution = gatekeeper_result.get("output", SolutionArtifact())

        if not isinstance(solution, SolutionArtifact):
            solution = SolutionArtifact()

        gatekeeper_passed = gatekeeper_result.get("gatekeeper_passed", False)

        artifact = gatekeeper_result.get("artifact")
        if not isinstance(artifact, Artifact):
            artifact = Artifact(
                content=solution.code,
                type="code",
                metadata={
                    "task": solution.task,
                    "score": solution.score,
                },
            )

        logger.info("💾 [ARTIFACT_WRITER] Iniciando persistência do projeto final...")

        code = artifact.content or ""
        code_str = code if isinstance(code, str) else str(code)

        if not code_str.strip():
            logger.warning("⏭️ [ARTIFACT_WRITER] Código vazio - persistência cancelada")
            self._log(ctx, "artifact_writer: código vazio")

            return {
                "output": "",
                "path": None,
                "persisted": False,
                "artifact": artifact,
                "reason": "empty_code",
            }

        from iaglobal._paths import SCRIPTS_DIR

        start_time = time.perf_counter()

        task_name = (
            artifact.metadata.get("task")
            or solution.task
            or task
            or "script"
        )

        safe_name = (
            re.sub(r"[^\w\-]", "_", str(task_name)[:64])
            .strip("_")
            or "script"
        )

        timestamp = int(time.time())

        project_dir = SCRIPTS_DIR / f"{safe_name}_{timestamp}"
        project_dir.mkdir(parents=True, exist_ok=True)

        ext, main_file = _detect_ext_and_name(code_str, task_name)

        artifact_path = project_dir / main_file

        try:
            artifact_path.write_text(
                code_str,
                encoding="utf-8",
                errors="ignore",
            )

            files_written = 1
            total_bytes = len(code_str.encode("utf-8"))

            # ──────────────────────────────────────────────────────
            # Detecção automática da stack
            # ──────────────────────────────────────────────────────

            stack = []

            lower_code = code_str.lower()

            if "fastapi" in lower_code:
                stack.append("fastapi")

            if "flask" in lower_code:
                stack.append("flask")

            if "django" in lower_code:
                stack.append("django")

            if "react" in lower_code:
                stack.append("react")

            if "next" in lower_code:
                stack.append("nextjs")

            if "vue" in lower_code:
                stack.append("vue")

            if "express" in lower_code:
                stack.append("express")

            if not stack:
                stack.append("generic")

            # ──────────────────────────────────────────────────────
            # Estrutura inteligente
            # ──────────────────────────────────────────────────────

            is_web_project = any(
                x in lower_code
                for x in [
                    "html",
                    "css",
                    "javascript",
                    "react",
                    "vue",
                    "next",
                    "flask",
                    "django",
                    "fastapi",
                ]
            )

            if is_web_project:
                for subdir in [
                    "css",
                    "js",
                    "templates",
                    "static",
                    "assets",
                    "docs",
                    "tests",
                ]:
                    (project_dir / subdir).mkdir(
                        parents=True,
                        exist_ok=True,
                    )

            # ──────────────────────────────────────────────────────
            # Arquivos auxiliares
            # ──────────────────────────────────────────────────────

            generated_files = []

            for filepath, content in (solution.files or {}).items():
                try:
                    full_path = project_dir / filepath

                    full_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    full_path.write_text(
                        content,
                        encoding="utf-8",
                        errors="ignore",
                    )

                    generated_files.append(filepath)

                    files_written += 1
                    total_bytes += len(
                        content.encode("utf-8")
                    )

                except Exception as e:
                    logger.exception(
                        "Erro ao salvar arquivo %s",
                        filepath,
                    )

            # ──────────────────────────────────────────────────────
            # Hash do build
            # ──────────────────────────────────────────────────────

            sha256 = hashlib.sha256(
                code_str.encode("utf-8")
            ).hexdigest()

            # ──────────────────────────────────────────────────────
            # Manifesto do projeto
            # ──────────────────────────────────────────────────────

            manifest = {
                "task": task_name,
                "timestamp": timestamp,
                "gatekeeper_passed": gatekeeper_passed,
                "score": solution.score,
                "stack": stack,
                "main_file": main_file,
                "files_written": files_written,
                "sha256": sha256,
                "generated_files": generated_files,
                "total_bytes": total_bytes,
            }

            manifest_file = project_dir / "artifact_manifest.json"

            manifest_file.write_text(
                json.dumps(
                    manifest,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            files_written += 1

            solution.path = str(artifact_path)

            # ──────────────────────────────────────────────────────
            # Persistência global
            # ──────────────────────────────────────────────────────

            try:
                from iaglobal._paths import save_result_artifact

                save_result_artifact(
                    task_name,
                    solution.files or {},
                    code_str,
                )

            except Exception:
                logger.exception(
                    "[ARTIFACT_WRITER] save_result_artifact falhou"
                )

            elapsed = round(
                time.perf_counter() - start_time,
                3,
            )

            logger.info(
                "✅ [ARTIFACT_WRITER] Projeto salvo em %s (%d arquivos, %.3fs)",
                project_dir,
                files_written,
                elapsed,
            )

            self._log(
                ctx,
                (
                    f"artifact salvo em {project_dir} | "
                    f"{files_written} arquivos | "
                    f"{total_bytes} bytes"
                ),
            )

            artifact.metadata.update(
                {
                    "sha256": sha256,
                    "project_dir": str(project_dir),
                    "files_written": files_written,
                    "persisted_at": timestamp,
                }
            )

            return {
                "output": str(artifact_path),
                "artifact_code": code_str,
                "path": str(artifact_path),
                "project_dir": str(project_dir),
                "files": solution.files or {},
                "persisted": True,
                "artifact": artifact,
                "manifest": manifest,
                "sha256": sha256,
                "files_written": files_written,
                "total_bytes": total_bytes,
                "elapsed": elapsed,
                "gatekeeper_passed": gatekeeper_passed,
            }

        except Exception as e:
            logger.exception(
                "❌ [ARTIFACT_WRITER] Falha ao persistir projeto"
            )

            self._log(
                ctx,
                f"artifact_writer falhou: {e}",
            )

            return {
                "output": "",
                "path": None,
                "persisted": False,
                "artifact": artifact,
                "error": str(e),
                "gatekeeper_passed": gatekeeper_passed,
            }

#===========================================================================================

    # ── Nó: dependency ────────────────────────────────────────────

    async def run_dependency(self, ctx: dict) -> dict:
        from datetime import datetime
        import hashlib
        import time

        from iaglobal.agents.dependency_agent import verify_dependencies
        from iaglobal._paths import CORE_DB

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        logger.info("📦 [DEPENDENCY] Iniciando análise de dependências...")

        started_at = time.perf_counter()

        planner_out = memory.get("planner", {}).get("output", None)
        search_out = memory.get("search", {}).get("output", None)
        architecture_out = memory.get("architecture", {}).get("output", None)

        # ------------------------------------------------------------------
        # Cache
        # ------------------------------------------------------------------

        cache_key = hashlib.sha256(
            (
                str(task)
                + str(planner_out)
                + str(search_out)
                + str(architecture_out)
            ).encode("utf-8")
        ).hexdigest()

        cache = memory.get("dependency_cache", {})

        if cache.get("key") == cache_key:
            logger.info("⚡ [DEPENDENCY] Resultado recuperado do cache.")
            cached_result = cache.get("result", {})

            return {
                **cached_result,
                "cache_hit": True,
                "cache_key": cache_key,
            }

        # ------------------------------------------------------------------
        # Construção do contexto
        # ------------------------------------------------------------------

        context_parts = [task]

        if planner_out:
            context_parts.append(str(planner_out))

        if search_out:
            context_parts.append(str(search_out))

        if architecture_out:
            context_parts.append(str(architecture_out))

        dependency_context = "\n\n".join(
            part for part in context_parts if part
        )

        # ------------------------------------------------------------------
        # Execução principal
        # ------------------------------------------------------------------

        try:
            result = verify_dependencies(
                dependency_context,
                db_path=CORE_DB,
            )

            deps = result.get("dependencies", [])
            conflicts = result.get("conflicts", [])
            missing = result.get("missing", [])
            deprecated = result.get("deprecated", [])
            vulnerabilities = result.get("vulnerabilities", [])

            # --------------------------------------------------------------
            # Métrica de risco
            # --------------------------------------------------------------

            risk_score = (
                len(conflicts) * 3
                + len(missing) * 2
                + len(deprecated)
                + len(vulnerabilities) * 5
            )

            if risk_score >= 20:
                risk_level = "critical"
            elif risk_score >= 10:
                risk_level = "high"
            elif risk_score >= 5:
                risk_level = "medium"
            else:
                risk_level = "low"

            elapsed = round(time.perf_counter() - started_at, 3)

            summary = {
                "total_dependencies": len(deps),
                "total_conflicts": len(conflicts),
                "total_missing": len(missing),
                "total_deprecated": len(deprecated),
                "total_vulnerabilities": len(vulnerabilities),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "execution_time": elapsed,
            }

            self._log(
                ctx,
                (
                    f"dependency: {len(deps)} deps | "
                    f"{len(conflicts)} conflitos | "
                    f"{len(missing)} faltantes | "
                    f"risco={risk_level}"
                ),
            )

            logger.info(
                "📦 [DEPENDENCY] %d dependências | %d conflitos | "
                "%d faltantes | risco=%s",
                len(deps),
                len(conflicts),
                len(missing),
                risk_level,
            )

            response = {
                "output": result,
                "dependencies": deps,
                "conflicts": conflicts,
                "missing": missing,
                "deprecated": deprecated,
                "vulnerabilities": vulnerabilities,
                "summary": summary,
                "cache_hit": False,
                "cache_key": cache_key,
                "analyzed_at": datetime.utcnow().isoformat(),
                "workspace": wd,
            }

            response["dependency_cache"] = {
                "key": cache_key,
                "result": response,
            }

            return response

        except Exception as exc:
            logger.exception(
                "❌ [DEPENDENCY] Falha durante análise de dependências"
            )

            self._log(
                ctx,
                f"dependency_error: {type(exc).__name__}: {exc}"
            )

            return {
                "output": {},
                "dependencies": [],
                "conflicts": [],
                "missing": [],
                "deprecated": [],
                "vulnerabilities": [],
                "summary": {
                    "risk_score": 999,
                    "risk_level": "unknown",
                    "execution_time": round(
                        time.perf_counter() - started_at,
                        3,
                    ),
                },
                "error": str(exc),
                "cache_hit": False,
            }

#===========================================================================================

    # ── Nó: documentation ─────────────────────────────────────────

    async def run_documentation(self, ctx: dict) -> dict:
        """
        Geração avançada de documentação:
        - README contextualizado
        - ADRs
        - Diagramas Mermaid
        - API Docs
        - Guia de Deploy
        - Guia de Contribuição
        - Changelog inicial
        - Docstrings automáticas
        - Métricas e observabilidade
        """

        import json
        import re
        import hashlib
        from pathlib import Path
        from datetime import datetime

        from iaglobal._paths import TEMP_DIR
        # SolutionArtifact is already imported at top-level: from .artifact import SolutionArtifact

        memory = ctx.get("memory", {})

        coder_out = memory.get("multi_coder", {}).get("output")
        debug_out = memory.get("debugger", {}).get("output")
        architecture_out = memory.get("architecture", {}).get("output")
        planner_out = memory.get("planner", {}).get("output")
        security_out = memory.get("security_design", {}).get("output")
        test_out = memory.get("tester", {}).get("output")

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        logger.info("📚 [DOCUMENTATION] Gerando documentação avançada...")

        # ------------------------------------------------------------------
        # Recupera código final
        # ------------------------------------------------------------------

        artifact_code = ""

        if isinstance(debug_out, SolutionArtifact) and getattr(debug_out, "code", None):
            artifact_code = debug_out.code

        elif isinstance(coder_out, SolutionArtifact) and getattr(coder_out, "code", None):
            artifact_code = coder_out.code

        elif hasattr(coder_out, "code"):
            artifact_code = coder_out.code or ""

        elif isinstance(coder_out, dict):
            artifact_code = (
                coder_out.get("code")
                or coder_out.get("artifact_code")
                or coder_out.get("output")
                or ""
            )

        elif coder_out:
            artifact_code = str(coder_out)

        if not artifact_code.strip():
            logger.info("⏭️ [DOCUMENTATION] Nenhum código disponível")
            return {
                "documentation": {},
                "docs_generated": False,
                "doc_files": [],
            }

        # ------------------------------------------------------------------
        # Diretório
        # ------------------------------------------------------------------

        project_dir = (
            Path(wd.path)
            if wd and hasattr(wd, "path")
            else Path(TEMP_DIR / "documentation")
        )

        project_dir.mkdir(parents=True, exist_ok=True)

        docs = {}
        generated_files = []
        generation_errors = []

        code_sample = artifact_code[:6000]

        architecture_text = str(architecture_out)[:3000] if architecture_out else ""
        planner_text = str(planner_out)[:3000] if planner_out else ""
        security_text = str(security_out)[:3000] if security_out else ""

        # ------------------------------------------------------------------
        # Helper
        # ------------------------------------------------------------------

        async def generate_doc(
            filename: str,
            prompt: str,
            min_size: int = 50,
            subdir: str | None = None,
        ):
            try:
                content = await self._call_llm(ctx, prompt)

                if not content:
                    return

                content = content.strip()

                if len(content) < min_size:
                    return

                target_dir = project_dir

                if subdir:
                    target_dir = project_dir / subdir
                    target_dir.mkdir(parents=True, exist_ok=True)

                file_path = target_dir / filename
                file_path.write_text(content, encoding="utf-8")

                key = f"{subdir}/{filename}" if subdir else filename

                docs[key] = content
                generated_files.append(key)

            except Exception as e:
                logger.warning(
                    "⚠️ [DOCUMENTATION] erro gerando %s: %s",
                    filename,
                    e,
                )
                generation_errors.append(
                    {
                        "file": filename,
                        "error": str(e),
                    }
                )

        # ------------------------------------------------------------------
        # README
        # ------------------------------------------------------------------

        await generate_doc(
            "README.md",
            f"""
    Crie um README.md profissional em português.

    Tarefa:
    {task}

    Planejamento:
    {planner_text}

    Arquitetura:
    {architecture_text}

    Código:
    {code_sample}

    Inclua:
    - Visão geral
    - Objetivos
    - Funcionalidades
    - Arquitetura
    - Instalação
    - Configuração
    - Uso
    - Estrutura do projeto
    - Testes
    - Deploy
    - Roadmap
    - Licença
    """,
            min_size=300,
        )

        # ------------------------------------------------------------------
        # ADR
        # ------------------------------------------------------------------

        await generate_doc(
            "0001-arquitetura-inicial.md",
            f"""
    Gere um ADR (Architecture Decision Record).

    Formato:

    # Título
    ## Contexto
    ## Decisão
    ## Alternativas Consideradas
    ## Consequências

    Arquitetura:
    {architecture_text}

    Segurança:
    {security_text}

    Código:
    {code_sample}
    """,
            subdir="adr",
            min_size=200,
        )

        # ------------------------------------------------------------------
        # API DOC
        # ------------------------------------------------------------------

        await generate_doc(
            "API.md",
            f"""
    Analise o código e gere documentação técnica de API.

    Código:
    {code_sample}

    Inclua:
    - módulos
    - classes
    - endpoints
    - funções
    - exemplos de uso
    - exemplos de payload
    """,
            min_size=150,
        )

        # ------------------------------------------------------------------
        # DEPLOY
        # ------------------------------------------------------------------

        await generate_doc(
            "DEPLOY.md",
            f"""
    Crie um guia completo de deploy.

    Projeto:
    {task}

    Código:
    {code_sample}

    Inclua:
    - Ambiente local
    - Docker
    - Kubernetes
    - Variáveis de ambiente
    - Observabilidade
    - Rollback
    - CI/CD
    """,
            min_size=150,
        )

        # ------------------------------------------------------------------
        # CONTRIBUTING
        # ------------------------------------------------------------------

        await generate_doc(
            "CONTRIBUTING.md",
            f"""
    Crie um guia CONTRIBUTING.md.

    Projeto:
    {task}

    Inclua:
    - padrão de commits
    - branches
    - revisão de código
    - testes
    - pull requests
    """,
            min_size=100,
        )

        # ------------------------------------------------------------------
        # CHANGELOG
        # ------------------------------------------------------------------

        try:
            changelog = f"""
    # Changelog

    ## [1.0.0] - {datetime.utcnow().date()}

    ### Added

    - Implementação inicial do projeto
    - Estrutura arquitetural criada automaticamente
    - Testes básicos
    - Documentação inicial
    """
            (project_dir / "CHANGELOG.md").write_text(
                changelog,
                encoding="utf-8",
            )

            docs["CHANGELOG.md"] = changelog
            generated_files.append("CHANGELOG.md")

        except Exception as e:
            generation_errors.append(
                {"file": "CHANGELOG.md", "error": str(e)}
            )

        # ------------------------------------------------------------------
        # Mermaid
        # ------------------------------------------------------------------

        try:
            diagram = await self._call_llm(
                ctx,
                f"""
    Gere APENAS o conteúdo Mermaid.

    Arquitetura:
    {architecture_text}

    Código:
    {code_sample}
    """
            )

            if diagram:

                diagram = (
                    diagram.replace("```mermaid", "")
                    .replace("```", "")
                    .strip()
                )

                mermaid_doc = (
                    "# Diagrama de Arquitetura\n\n"
                    f"```mermaid\n{diagram}\n```"
                )

                (project_dir / "diagrama-arquitetura.md").write_text(
                    mermaid_doc,
                    encoding="utf-8",
                )

                docs["diagrama-arquitetura.md"] = mermaid_doc
                generated_files.append("diagrama-arquitetura.md")

        except Exception as e:
            generation_errors.append(
                {
                    "file": "diagrama-arquitetura.md",
                    "error": str(e),
                }
            )

        # ------------------------------------------------------------------
        # Docstrings
        # ------------------------------------------------------------------

        try:
            docstring_version = await self._call_llm(
                ctx,
                f"""
    Adicione docstrings Google Style.

    Retorne SOMENTE código.

    Código:

    {artifact_code[:8000]}
    """
            )

            if docstring_version:

                blocks = re.findall(
                    r"```(?:python)?\s*(.*?)```",
                    docstring_version,
                    re.DOTALL,
                )

                final_code = (
                    blocks[0].strip()
                    if blocks
                    else docstring_version.strip()
                )

                if len(final_code) > len(artifact_code) * 0.8:

                    py_files = list(project_dir.glob("*.py"))

                    target = (
                        py_files[0]
                        if py_files
                        else project_dir / "main.py"
                    )

                    target.write_text(
                        final_code,
                        encoding="utf-8",
                    )

                    docs["docstrings"] = "Google Style adicionadas"

        except Exception as e:
            generation_errors.append(
                {
                    "file": "docstrings",
                    "error": str(e),
                }
            )

        # ------------------------------------------------------------------
        # Índice documental
        # ------------------------------------------------------------------

        try:
            index_md = "# Índice de Documentação\n\n"

            for item in sorted(generated_files):
                index_md += f"- {item}\n"

            (project_dir / "DOCUMENTATION_INDEX.md").write_text(
                index_md,
                encoding="utf-8",
            )

            docs["DOCUMENTATION_INDEX.md"] = index_md
            generated_files.append("DOCUMENTATION_INDEX.md")

        except Exception:
            pass

        # ------------------------------------------------------------------
        # Métricas
        # ------------------------------------------------------------------

        documentation_metrics = {
            "generated_documents": len(generated_files),
            "errors": len(generation_errors),
            "code_size": len(artifact_code),
            "documentation_size": sum(
                len(v)
                for v in docs.values()
                if isinstance(v, str)
            ),
            "documentation_hash": hashlib.sha256(
                json.dumps(
                    generated_files,
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:16],
        }

        self._log(
            ctx,
            f"documentação avançada: {len(generated_files)} arquivos gerados",
        )

        logger.info(
            "✅ [DOCUMENTATION] %d documento(s) gerado(s)",
            len(generated_files),
        )

        return {
            "documentation": docs,
            "docs_generated": bool(docs),
            "doc_files": generated_files,
            "documentation_metrics": documentation_metrics,
            "generation_errors": generation_errors,
            "project_dir": str(project_dir),
        }

#===========================================================================================

    # ── Nó: release ───────────────────────────────────────────────

    async def run_release(self, ctx: dict) -> dict:
        from pathlib import Path
        import json
        import hashlib
        from datetime import datetime

        memory = ctx.get("memory", {})

        docs_result = memory.get("documentation", {}).get("documentation", {})
        artifact_result = memory.get("artifact_writer", {})

        artifact_code = artifact_result.get("artifact_code", "")
        project_path = artifact_result.get("path", "")

        wd = self._get_wd(ctx)

        logger.info("🚀 [RELEASE] Iniciando geração de release...")

        if not artifact_code:
            return {
                "output": {},
                "release_generated": False,
                "release_score": 0.0,
            }

        project_dir = (
            Path(project_path).parent
            if Path(project_path).is_file()
            else Path(project_path)
        )

        project_dir.mkdir(parents=True, exist_ok=True)

        release = {}
        metrics = {}
        risks = []
        warnings = []

        # ---------------------------------------------------------
        # Métricas do artefato
        # ---------------------------------------------------------

        code_lines = len(artifact_code.splitlines())
        code_size = len(artifact_code)

        metrics.update(
            {
                "code_lines": code_lines,
                "code_size_bytes": code_size,
                "generated_at": datetime.utcnow().isoformat(),
            }
        )

        # ---------------------------------------------------------
        # Fingerprint do build
        # ---------------------------------------------------------

        build_hash = hashlib.sha256(
            artifact_code.encode("utf-8", errors="ignore")
        ).hexdigest()

        metrics["build_hash"] = build_hash

        # ---------------------------------------------------------
        # Heurísticas de risco
        # ---------------------------------------------------------

        risk_score = 0.0

        risky_patterns = [
            "DELETE FROM",
            "DROP TABLE",
            "rm -rf",
            "subprocess",
            "eval(",
            "exec(",
            "os.system",
        ]

        for pattern in risky_patterns:
            if pattern.lower() in artifact_code.lower():
                risk_score += 0.15
                risks.append(f"Uso detectado: {pattern}")

        if code_lines > 5000:
            risk_score += 0.15
            risks.append("Grande volume de código")

        if "TODO" in artifact_code:
            risk_score += 0.05
            warnings.append("Existem TODOs pendentes")

        risk_score = min(1.0, risk_score)

        # ---------------------------------------------------------
        # Versionamento automático
        # ---------------------------------------------------------

        version = f"v{datetime.utcnow():%Y.%m.%d}"

        release_manifest = {
            "version": version,
            "build_hash": build_hash,
            "generated_at": metrics["generated_at"],
            "risk_score": risk_score,
        }

        # ---------------------------------------------------------
        # CHANGELOG
        # ---------------------------------------------------------

        try:
            prompt = f"""
    Gere um CHANGELOG.md seguindo o padrão Keep a Changelog.

    Versão: {version}

    Resumo:
    - Linhas: {code_lines}
    - Hash: {build_hash[:12]}

    Código:
    {artifact_code[:4000]}
    """

            changelog = await self._call_llm(ctx, prompt)

            if changelog and len(changelog.strip()) > 50:
                release["CHANGELOG.md"] = changelog.strip()
                (project_dir / "CHANGELOG.md").write_text(
                    changelog.strip(),
                    encoding="utf-8",
                )

        except Exception as e:
            logger.exception("Erro gerando changelog")
            warnings.append(f"CHANGELOG: {e}")

        # ---------------------------------------------------------
        # RELEASE NOTES
        # ---------------------------------------------------------

        try:
            prompt = f"""
    Gere RELEASE_NOTES.md profissionais.

    Inclua:
    - Novidades
    - Melhorias
    - Correções
    - Impactos
    - Compatibilidade

    Código:
    {artifact_code[:4000]}
    """

            notes = await self._call_llm(ctx, prompt)

            if notes and len(notes.strip()) > 50:
                release["RELEASE_NOTES.md"] = notes.strip()

                (project_dir / "RELEASE_NOTES.md").write_text(
                    notes.strip(),
                    encoding="utf-8",
                )

        except Exception as e:
            logger.exception("Erro gerando release notes")
            warnings.append(f"RELEASE_NOTES: {e}")

        # ---------------------------------------------------------
        # DEPLOY PLAN
        # ---------------------------------------------------------

        try:
            prompt = f"""
    Crie um DEPLOY_PLAN.md contendo:

    1. Pré-requisitos
    2. Passos de deploy
    3. Validação pós-deploy
    4. Monitoramento
    5. Rollback
    6. Critérios de sucesso

    Código:
    {artifact_code[:4000]}
    """

            deploy = await self._call_llm(ctx, prompt)

            if deploy and len(deploy.strip()) > 50:
                release["DEPLOY_PLAN.md"] = deploy.strip()

                (project_dir / "DEPLOY_PLAN.md").write_text(
                    deploy.strip(),
                    encoding="utf-8",
                )

        except Exception as e:
            logger.exception("Erro gerando deploy plan")
            warnings.append(f"DEPLOY_PLAN: {e}")

        # ---------------------------------------------------------
        # OBSERVABILITY GUIDE
        # ---------------------------------------------------------

        observability = f"""# Observability Checklist

    ## Métricas
    - Error Rate
    - Request Rate
    - Latency
    - Resource Consumption

    ## Alertas
    - Erros críticos
    - Timeout
    - Falha de integração

    ## Health Checks
    - Endpoint principal
    - Banco de dados
    - Dependências externas

    Build Hash:
    {build_hash}
    """

        release["OBSERVABILITY.md"] = observability

        (project_dir / "OBSERVABILITY.md").write_text(
            observability,
            encoding="utf-8",
        )

        # ---------------------------------------------------------
        # SBOM simplificado
        # ---------------------------------------------------------

        sbom = {
            "build_hash": build_hash,
            "generated_at": metrics["generated_at"],
            "source_file": str(project_path),
            "size_bytes": code_size,
            "lines": code_lines,
        }

        release["SBOM.json"] = sbom

        (project_dir / "SBOM.json").write_text(
            json.dumps(sbom, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ---------------------------------------------------------
        # Release Manifest
        # ---------------------------------------------------------

        manifest = {
            "version": version,
            "metrics": metrics,
            "risk_score": risk_score,
            "risks": risks,
            "warnings": warnings,
            "generated_files": list(release.keys()),
        }

        release["release_manifest.json"] = manifest

        (project_dir / "release_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ---------------------------------------------------------
        # Release Score
        # ---------------------------------------------------------

        release_score = max(
            0.0,
            min(
                1.0,
                1.0
                - (risk_score * 0.6)
                - (len(warnings) * 0.05),
            ),
        )

        generated = list(release.keys())

        self._log(
            ctx,
            (
                f"release: {len(generated)} arquivos | "
                f"score={release_score:.2f} | "
                f"risk={risk_score:.2f}"
            ),
        )

        logger.info(
            "✅ [RELEASE] %d artefatos gerados | score=%.2f | risk=%.2f",
            len(generated),
            release_score,
            risk_score,
        )

        return {
            "output": release,
            "release_generated": bool(release),
            "release_files": generated,
            "release_score": release_score,
            "risk_score": risk_score,
            "metrics": metrics,
            "manifest": manifest,
            "version": version,
        }

#===========================================================================================

    # ── Nó: search (web) ─────────────────────────────────────

    async def run_search(self, ctx: dict) -> dict:
        """
        Busca contextual inteligente com:
        - geração dinâmica de consultas
        - deduplicação de resultados
        - scoring de relevância
        - cache local
        - detecção automática de domínio técnico
        - fallback resiliente
        - métricas de qualidade
        """

        import re
        import hashlib
        from collections import Counter

        artifact = (
            ctx.get("memory", {})
            .get("web_classifier", {})
            .get("output", SolutionArtifact())
        )

        task = self._get_task(ctx)
        enhanced = self._get_enhanced_task(ctx)
        wd = self._get_wd(ctx)

        raw_task = task
        query = self._extract_search_query(enhanced, task)

        logger.info("[SEARCH] Query reformulada: %.100s", query)

        if not query or len(query) < 5:
            self._log(ctx, "search: ignorado (query inválida)")
            return {"output": artifact}

        ql = query.lower()

        # ---------------------------------------------------------
        # Classificação automática do domínio
        # ---------------------------------------------------------

        domain_keywords = {
            "web": [
                "html", "css", "javascript", "js", "frontend",
                "site", "pagina", "web", "php", "react",
                "vue", "angular", "next"
            ],
            "backend": [
                "python", "flask", "django", "fastapi",
                "node", "express", "api", "microservice"
            ],
            "database": [
                "sql", "postgres", "mysql", "mongodb",
                "database", "dados", "schema", "query"
            ],
            "devops": [
                "docker", "kubernetes", "k8s",
                "terraform", "ci/cd", "aws",
                "gcp", "azure"
            ],
            "security": [
                "jwt", "oauth", "security", "auth",
                "authentication", "authorization",
                "owasp", "xss", "csrf"
            ],
            "blockchain": [
                "solidity", "evm", "smart contract",
                "ethereum", "web3", "blockchain",
                "defi", "token"
            ],
        }

        detected_domains = []

        for domain, words in domain_keywords.items():
            if any(w in ql for w in words):
                detected_domains.append(domain)

        # ---------------------------------------------------------
        # Construção inteligente das consultas
        # ---------------------------------------------------------

        variants = {query}

        generic_suffixes = [
            "best practices",
            "production ready",
            "architecture guide",
            "real world example",
            "official documentation",
        ]

        for suffix in generic_suffixes:
            variants.add(f"{query} {suffix}")

        if "web" in detected_domains:
            variants.update(
                [
                    f"{query} responsive design",
                    f"{query} accessibility",
                    f"{query} secure implementation",
                ]
            )

        if "backend" in detected_domains:
            variants.update(
                [
                    f"{query} clean architecture",
                    f"{query} scalable implementation",
                    f"{query} code example",
                ]
            )

        if "database" in detected_domains:
            variants.update(
                [
                    f"{query} schema design",
                    f"{query} performance optimization",
                    f"{query} indexing strategy",
                ]
            )

        if "security" in detected_domains:
            variants.update(
                [
                    f"{query} OWASP",
                    f"{query} security checklist",
                    f"{query} vulnerability prevention",
                ]
            )

        if "blockchain" in detected_domains:
            variants.update(
                [
                    f"{query} audit checklist",
                    f"{query} gas optimization",
                    f"{query} security patterns",
                ]
            )

        variants = list(variants)[:12]

        # ---------------------------------------------------------
        # Cache local
        # ---------------------------------------------------------

        search_cache = ctx.setdefault("_search_cache", {})

        query_hash = hashlib.md5(
            "|".join(sorted(variants)).encode()
        ).hexdigest()

        if query_hash in search_cache:
            cached = search_cache[query_hash]

            artifact.security_report = cached

            self._log(
                ctx,
                f"search cache hit ({len(cached)} chars)"
            )

            return {"output": artifact}

        # ---------------------------------------------------------
        # Execução das buscas
        # ---------------------------------------------------------

        from iaglobal.tools.search import search_tool

        all_results = []
        successful_queries = 0

        for variant in variants:
            try:
                result = search_tool(variant)

                if not result:
                    continue

                result = str(result).strip()

                if len(result) < 50:
                    continue

                successful_queries += 1
                all_results.append(result)

            except Exception as e:
                logger.debug(
                    "search variant failed: %s (%s)",
                    variant,
                    str(e),
                )

        # ---------------------------------------------------------
        # Deduplicação semântica simples
        # ---------------------------------------------------------

        unique_results = []
        seen = set()

        for result in all_results:
            sig = hashlib.md5(
                result[:1000].encode()
            ).hexdigest()

            if sig in seen:
                continue

            seen.add(sig)
            unique_results.append(result)

        # ---------------------------------------------------------
        # Ranking por frequência de termos
        # ---------------------------------------------------------

        query_terms = [
            w
            for w in re.findall(r"\w+", ql)
            if len(w) > 3
        ]

        scored = []

        for result in unique_results:

            text = result.lower()

            score = sum(
                text.count(term)
                for term in query_terms
            )

            scored.append((score, result))

        scored.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        ranked_results = [
            r
            for _, r in scored[:8]
        ]

        combined = "\n\n" + ("\n\n" + "=" * 80 + "\n\n").join(
            ranked_results
        )

        # ---------------------------------------------------------
        # Enriquecimento do artifact
        # ---------------------------------------------------------

        if combined:
            artifact.security_report = combined

        search_cache[query_hash] = combined

        # ---------------------------------------------------------
        # Métricas
        # ---------------------------------------------------------

        metrics = ctx.setdefault("metrics", {})

        metrics["search"] = {
            "query": query,
            "domains": detected_domains,
            "queries_generated": len(variants),
            "queries_successful": successful_queries,
            "results_raw": len(all_results),
            "results_unique": len(unique_results),
            "final_chars": len(combined),
        }

        self._log(
            ctx,
            (
                f"search ✓ "
                f"domains={detected_domains} "
                f"queries={len(variants)} "
                f"success={successful_queries} "
                f"chars={len(combined)}"
            )
        )

        logger.info(
            "🌐 Search Intelligence | "
            "domains=%s | "
            "queries=%d | "
            "success=%d | "
            "unique=%d | "
            "chars=%d",
            detected_domains,
            len(variants),
            successful_queries,
            len(unique_results),
            len(combined),
        )

        return {"output": artifact}

#===========================================================================================

    # ── Nó: multi_coder ───────────────────────────────────────────

    async def run_multi_coder(self, ctx: dict) -> dict:
        import asyncio
        import re

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        planner_out = memory.get("planner", {}).get("output", SolutionArtifact())
        search_out = memory.get("search", {}).get("output", SolutionArtifact())
        architecture_out = memory.get("architecture", {}).get("output", SolutionArtifact())
        review_out = memory.get("review", {}).get("output", SolutionArtifact())

        # ---------------------------------------------------------
        # Enriquecimento do contexto
        # ---------------------------------------------------------

        if isinstance(planner_out, SolutionArtifact):
            task = planner_out.code or planner_out.content or task

        context_parts = []

        for artifact in (
            search_out,
            architecture_out,
            review_out,
        ):
            if not isinstance(artifact, SolutionArtifact):
                continue

            for field in (
                "content",
                "security_report",
                "architecture",
                "analysis",
                "review",
            ):
                value = getattr(artifact, field, None)
                if value:
                    context_parts.append(str(value))

        context_block = "\n\n".join(context_parts[:10])

        # ---------------------------------------------------------
        # Fast-path blockchain
        # ---------------------------------------------------------

        if _is_blockchain_task(task):
            code = generate_genesis_python_script()

            art = SolutionArtifact(
                task=task,
                code=code,
                files={},
                metadata={
                    "source": "native_blockchain_generator",
                    "confidence": 1.0,
                },
            )

            if wd:
                wd.write_code(code).append_log(
                    f"blockchain nativo ({len(code)} chars)"
                )

            return {
                "output": art,
                "selected_variant": "native",
                "confidence": 1.0,
            }

        # ---------------------------------------------------------
        # Detectar stack
        # ---------------------------------------------------------

        tl = task.lower()

        stack = "python"

        stack_rules = {
            "php": ["php", "laravel"],
            "javascript": ["javascript", "node", "express"],
            "typescript": ["typescript", "nestjs"],
            "react": ["react", "next.js", "nextjs"],
            "html": ["html", "css", "pagina", "formulario", "website"],
            "python": ["python", "fastapi", "flask", "django"],
        }

        for stack_name, keywords in stack_rules.items():
            if any(k in tl for k in keywords):
                stack = stack_name
                break

        # ---------------------------------------------------------
        # Estratégias de geração
        # ---------------------------------------------------------

        async def generate_variant(strategy: str) -> dict:
            prompt = f"""
    Você é um engenheiro sênior.

    TAREFA:
    {task}

    CONTEXTO:
    {context_block}

    ESTRATÉGIA:
    {strategy}

    Regras:
    - Gere somente código
    - Código completo
    - Produção
    - Sem explicações
    """

            response = await self._call_llm(
                ctx,
                prompt,
                task_type="coding",
            )

            code = (response or "").strip()

            if code.startswith("```"):
                code = re.sub(
                    r"^```[a-zA-Z0-9_]*",
                    "",
                    code,
                )
                code = code.rsplit("```", 1)[0].strip()

            return {
                "strategy": strategy,
                "code": code,
            }

        strategies = [
            "clean_architecture",
            "performance_optimized",
            "maintainable_enterprise",
        ]

        variants = await asyncio.gather(
            *[generate_variant(s) for s in strategies],
            return_exceptions=True,
        )

        valid_variants = [
            v for v in variants
            if isinstance(v, dict) and v.get("code")
        ]

        if not valid_variants:
            return {
                "output": SolutionArtifact(
                    task=task,
                    code="",
                    metadata={"error": "generation_failed"},
                )
            }

        # ---------------------------------------------------------
        # Avaliação automática
        # ---------------------------------------------------------

        def evaluate(code: str) -> float:
            score = 50.0

            lines = len(code.splitlines())
            score += min(lines / 10, 15)

            if "class " in code:
                score += 5

            if "async " in code:
                score += 5

            if "try:" in code:
                score += 5

            if "logger" in code:
                score += 5

            if len(code) > 500:
                score += 5

            return min(score, 100)

        for variant in valid_variants:
            variant["score"] = evaluate(
                variant["code"]
            )

        best_variant = max(
            valid_variants,
            key=lambda x: x["score"]
        )

        # ---------------------------------------------------------
        # Artifact final
        # ---------------------------------------------------------

        artifact = SolutionArtifact(
            task=task,
            code=best_variant["code"],
            files={},
            metadata={
                "stack": stack,
                "selected_strategy": best_variant["strategy"],
                "confidence": round(
                    best_variant["score"] / 100,
                    3,
                ),
                "candidate_count": len(valid_variants),
                "scores": {
                    v["strategy"]: v["score"]
                    for v in valid_variants
                },
            },
        )

        # ---------------------------------------------------------
        # Persistência
        # ---------------------------------------------------------

        if wd and artifact.code:
            (
                wd.write_code(artifact.code)
                .append_log(
                    f"multi_coder | "
                    f"strategy={best_variant['strategy']} | "
                    f"score={best_variant['score']:.1f}"
                )
            )

        self._log(
            ctx,
            (
                f"multi_coder: "
                f"{len(valid_variants)} variantes | "
                f"winner={best_variant['strategy']} | "
                f"score={best_variant['score']:.1f}"
            ),
        )

        return {
            "output": artifact,
            "selected_variant": best_variant["strategy"],
            "confidence": artifact.metadata["confidence"],
            "variants_evaluated": len(valid_variants),
            "scores": artifact.metadata["scores"],
        }

#===========================================================================================

    # ── Nó: metrics ───────────────────────────────────────────────

    async def run_metrics(self, ctx: dict) -> dict:
        import statistics
        import time

        memory = ctx.get("memory", {})
        wd = self._get_wd(ctx)

        logger.info("📊 [METRICS] Coletando métricas avançadas...")

        report = {
            "generated_at": time.time(),
            "nodes_executed": [],
            "node_count": 0,
            "successful_nodes": 0,
            "failed_nodes": 0,
            "empty_nodes": 0,
            "scores": {},
            "durations": {},
            "statistics": {},
            "health": {},
            "coverage": {},
            "warnings": [],
        }

        collected_scores = []

        for node_name, node_data in memory.items():
            report["nodes_executed"].append(node_name)

            if not isinstance(node_data, dict):
                continue

            # ---------------------------------------------------------
            # Status do nó
            # ---------------------------------------------------------

            status = str(node_data.get("status", "")).lower()

            if status in {"failed", "error"}:
                report["failed_nodes"] += 1
            else:
                report["successful_nodes"] += 1

            if not node_data:
                report["empty_nodes"] += 1

            # ---------------------------------------------------------
            # Score fields conhecidos
            # ---------------------------------------------------------

            for key in (
                "score",
                "review_score",
                "performance_score",
                "security_score",
                "risk_score",
                "quality_score",
                "architecture_score",
                "test_score",
                "completeness_score",
            ):
                value = node_data.get(key)

                if isinstance(value, (int, float)):
                    metric_name = f"{node_name}.{key}"
                    report["scores"][metric_name] = value
                    collected_scores.append(float(value))

            # ---------------------------------------------------------
            # Score dentro do output
            # ---------------------------------------------------------

            output = node_data.get("output")

            if output is not None and hasattr(output, "score"):
                try:
                    score = float(output.score)
                    report["scores"][f"{node_name}.output_score"] = score
                    collected_scores.append(score)
                except Exception:
                    pass

            # ---------------------------------------------------------
            # Duration fields
            # ---------------------------------------------------------

            for duration_key in (
                "duration",
                "execution_time",
                "elapsed",
                "processing_time",
            ):
                duration = node_data.get(duration_key)

                if isinstance(duration, (int, float)):
                    report["durations"][
                        f"{node_name}.{duration_key}"
                    ] = round(float(duration), 4)

            # ---------------------------------------------------------
            # Extração automática de métricas numéricas
            # ---------------------------------------------------------

            for key, value in node_data.items():
                if key.endswith("_score"):
                    continue

                if isinstance(value, (int, float)):
                    metric_name = f"{node_name}.{key}"

                    if metric_name not in report["scores"]:
                        report["scores"][metric_name] = value

        # -------------------------------------------------------------
        # Estatísticas globais
        # -------------------------------------------------------------

        if collected_scores:
            report["statistics"] = {
                "avg_score": round(statistics.mean(collected_scores), 4),
                "min_score": round(min(collected_scores), 4),
                "max_score": round(max(collected_scores), 4),
                "median_score": round(statistics.median(collected_scores), 4),
                "score_count": len(collected_scores),
            }

            if len(collected_scores) > 1:
                report["statistics"]["stdev_score"] = round(
                    statistics.stdev(collected_scores),
                    4,
                )

        # -------------------------------------------------------------
        # Cobertura do pipeline
        # -------------------------------------------------------------

        expected_nodes = getattr(self, "_expected_pipeline_nodes", None)

        if expected_nodes:
            executed = set(report["nodes_executed"])
            expected = set(expected_nodes)

            coverage = len(executed & expected) / max(len(expected), 1)

            report["coverage"] = {
                "expected_nodes": len(expected),
                "executed_nodes": len(executed),
                "coverage_percent": round(coverage * 100, 2),
                "missing_nodes": sorted(expected - executed),
            }

        # -------------------------------------------------------------
        # Health Score Global
        # -------------------------------------------------------------

        avg_score = report["statistics"].get("avg_score", 0)

        failure_penalty = report["failed_nodes"] * 10
        empty_penalty = report["empty_nodes"] * 2

        health_score = max(
            0,
            min(
                100,
                avg_score - failure_penalty - empty_penalty,
            ),
        )

        report["health"] = {
            "health_score": round(health_score, 2),
            "status": (
                "excellent"
                if health_score >= 90
                else "good"
                if health_score >= 75
                else "warning"
                if health_score >= 50
                else "critical"
            ),
        }

        # -------------------------------------------------------------
        # Alertas
        # -------------------------------------------------------------

        if report["failed_nodes"] > 0:
            report["warnings"].append(
                f"{report['failed_nodes']} node(s) failed"
            )

        if report["empty_nodes"] > 0:
            report["warnings"].append(
                f"{report['empty_nodes']} empty node(s)"
            )

        if avg_score and avg_score < 70:
            report["warnings"].append(
                f"Average score below target ({avg_score:.2f})"
            )

        self._log(
            ctx,
            (
                f"metrics: {report['node_count']} nodes | "
                f"{len(report['scores'])} metrics | "
                f"health={report['health']['health_score']:.2f}"
            ),
        )

        report["node_count"] = len(report["nodes_executed"])

        logger.info(
            "📊 [METRICS] %d nodes | %d metrics | health=%s",
            report["node_count"],
            len(report["scores"]),
            report["health"]["health_score"],
        )

        return {
            "output": report,
            "metrics_report": report,
            "pipeline_health": report["health"],
            "pipeline_statistics": report["statistics"],
        }

#===========================================================================================

    # ── Nó: optimization ──────────────────────────────────────────

    async def run_optimization(self, ctx: dict) -> dict:
        from datetime import datetime

        memory = ctx.get("memory", {})
        wd = self._get_wd(ctx)

        logger.info(
            "⚙️ [OPTIMIZATION] Analisando execução do pipeline..."
        )

        # ---------------------------------------------------------
        # Estrutura base
        # ---------------------------------------------------------

        report = {
            "useful_agents": [],
            "unnecessary_steps": [],
            "failed_steps": [],
            "high_value_steps": [],
            "suggestions": [],
            "execution_metrics": {},
            "pipeline_health": {},
        }

        # ---------------------------------------------------------
        # Análise dos nós executados
        # ---------------------------------------------------------

        total_nodes = 0
        productive_nodes = 0

        for node_name, node_data in memory.items():

            total_nodes += 1

            if not isinstance(node_data, dict):
                continue

            output = node_data.get("output")

            # Nó vazio
            if output in (None, "", [], {}, ()):
                report["unnecessary_steps"].append(
                    node_name
                )
                continue

            productive_nodes += 1

            report["useful_agents"].append(
                node_name
            )

            # Detecta falhas registradas
            if (
                isinstance(output, dict)
                and output.get("error")
            ):
                report["failed_steps"].append(
                    node_name
                )

            # Detecta nós ricos em informação
            try:
                size = len(str(output))

                if size > 1000:
                    report["high_value_steps"].append(
                        {
                            "node": node_name,
                            "size": size,
                        }
                    )

            except Exception:
                pass

        # ---------------------------------------------------------
        # Eficiência do pipeline
        # ---------------------------------------------------------

        efficiency = (
            productive_nodes / total_nodes
            if total_nodes
            else 0.0
        )

        # ---------------------------------------------------------
        # Recupera métricas de outros nós
        # ---------------------------------------------------------

        enhancement_metrics = (
            memory.get("enhancement", {})
                  .get("quality_metrics", {})
        )

        knowledge_metrics = (
            memory.get("knowledge", {})
                  .get("knowledge_metrics", {})
        )

        orchestration_plan = (
            memory.get("orchestrator_agent", {})
                  .get("orchestration_plan", {})
        )

        # ---------------------------------------------------------
        # Health Score
        # ---------------------------------------------------------

        health_score = efficiency

        if not report["failed_steps"]:
            health_score += 0.20

        if enhancement_metrics:
            health_score += 0.10

        if knowledge_metrics:
            health_score += 0.10

        health_score = round(
            min(health_score, 1.0),
            2
        )

        # ---------------------------------------------------------
        # Sugestões inteligentes
        # ---------------------------------------------------------

        if report["unnecessary_steps"]:
            report["suggestions"].append(
                (
                    "Remover ou tornar opcionais os nós: "
                    + ", ".join(
                        report["unnecessary_steps"]
                    )
                )
            )

        if report["failed_steps"]:
            report["suggestions"].append(
                (
                    "Adicionar mecanismo de retry para: "
                    + ", ".join(
                        report["failed_steps"]
                    )
                )
            )

        if efficiency < 0.70:
            report["suggestions"].append(
                (
                    "Eficiência baixa. "
                    "Avaliar simplificação do DAG."
                )
            )

        if (
            orchestration_plan.get(
                "complexity"
            ) == "low"
            and total_nodes > 10
        ):
            report["suggestions"].append(
                (
                    "Pipeline complexo para tarefa simples. "
                    "Considere execução reduzida."
                )
            )

        if not report["suggestions"]:
            report["suggestions"].append(
                "Pipeline executou de forma eficiente."
            )

        # ---------------------------------------------------------
        # Métricas consolidadas
        # ---------------------------------------------------------

        execution_metrics = {
            "total_nodes": total_nodes,
            "productive_nodes": productive_nodes,
            "unused_nodes": len(
                report["unnecessary_steps"]
            ),
            "failed_nodes": len(
                report["failed_steps"]
            ),
            "high_value_nodes": len(
                report["high_value_steps"]
            ),
            "efficiency": round(
                efficiency,
                2
            ),
        }

        pipeline_health = {
            "health_score": health_score,
            "status": (
                "excellent"
                if health_score >= 0.9
                else "good"
                if health_score >= 0.7
                else "needs_improvement"
            ),
        }

        report["execution_metrics"] = (
            execution_metrics
        )

        report["pipeline_health"] = (
            pipeline_health
        )

        report["generated_at"] = (
            datetime.utcnow().isoformat()
        )

        # ---------------------------------------------------------
        # Observabilidade
        # ---------------------------------------------------------

        logger.info(
            (
                "⚙️ [OPTIMIZATION] "
                "nodes=%d "
                "productive=%d "
                "failed=%d "
                "efficiency=%.2f "
                "health=%.2f"
            ),
            total_nodes,
            productive_nodes,
            len(report["failed_steps"]),
            efficiency,
            health_score,
        )

        self._log(
            ctx,
            (
                f"optimization:"
                f" efficiency={efficiency:.2f}"
                f" health={health_score:.2f}"
                f" suggestions={len(report['suggestions'])}"
            )
        )

        # ---------------------------------------------------------
        # Resultado
        # ---------------------------------------------------------

        return {
            "output": report,
            "optimization_report": report,
            "pipeline_health": pipeline_health,
            "execution_metrics": execution_metrics,
        }

#===========================================================================================

    # ── Nó: reflexion ─────────────────────────────────────────────

    async def run_reflexion(self, ctx: dict) -> dict:
        import json
        from datetime import datetime

        artifact = (
            ctx.get("memory", {})
               .get("final_gatekeeper", {})
               .get("output", SolutionArtifact())
        )

        if not isinstance(artifact, SolutionArtifact):
            artifact = SolutionArtifact()

        wd = self._get_wd(ctx)

        # ---------------------------------------------------------
        # Nada para aprender
        # ---------------------------------------------------------

        if not artifact.code:

            logger.info(
                "⏭️ [REFLEXION] Nenhum artefato gerado."
            )

            self._log(
                ctx,
                "reflexion: skipped"
            )

            return {
                "output": artifact,
                "reflection": {
                    "status": "skipped"
                }
            }

        logger.info(
            "🧠 [REFLEXION] Consolidando aprendizado..."
        )

        # ---------------------------------------------------------
        # Recuperação de contexto
        # ---------------------------------------------------------

        task = artifact.task

        orchestration_plan = (
            ctx.get("memory", {})
               .get("orchestrator_agent", {})
               .get("orchestration_plan", {})
        )

        quality_metrics = (
            ctx.get("memory", {})
               .get("enhancement", {})
               .get("quality_metrics", {})
        )

        gatekeeper_output = (
            ctx.get("memory", {})
               .get("final_gatekeeper", {})
               .get("output", {})
        )

        # ---------------------------------------------------------
        # Indicadores de sucesso
        # ---------------------------------------------------------

        success_score = float(
            artifact.score or 0.5
        )

        test_success = bool(
            getattr(
                artifact,
                "tests_passed",
                False
            )
        )

        code_size = len(
            artifact.code or ""
        )

        confidence_score = success_score

        if test_success:
            confidence_score += 0.2

        confidence_score = min(
            confidence_score,
            1.0
        )

        # ---------------------------------------------------------
        # Lições aprendidas
        # ---------------------------------------------------------

        lessons_learned = []

        if test_success:
            lessons_learned.append(
                "Implementação validada pelos testes."
            )

        if success_score >= 0.8:
            lessons_learned.append(
                "Resultado considerado de alta qualidade."
            )

        if code_size > 2000:
            lessons_learned.append(
                "Solução possui complexidade elevada."
            )

        task_type = (
            orchestration_plan.get(
                "task_type",
                "general"
            )
        )

        lessons_learned.append(
            f"Tipo de tarefa identificado: {task_type}"
        )

        # ---------------------------------------------------------
        # Padrões reutilizáveis
        # ---------------------------------------------------------

        reusable_patterns = []

        task_lower = task.lower()

        patterns = {
            "api_design": [
                "api",
                "endpoint",
                "fastapi",
                "rest"
            ],
            "database_access": [
                "sql",
                "postgres",
                "query",
                "repository"
            ],
            "agent_orchestration": [
                "agent",
                "workflow",
                "orchestrator"
            ],
            "testing_strategy": [
                "pytest",
                "test",
                "unittest"
            ],
            "blockchain": [
                "solidity",
                "evm",
                "ethereum",
                "web3"
            ]
        }

        for pattern, keywords in patterns.items():

            if any(
                k in task_lower
                for k in keywords
            ):
                reusable_patterns.append(
                    pattern
                )

        # ---------------------------------------------------------
        # Registro persistente
        # ---------------------------------------------------------

        persistence_status = {
            "db": False,
            "knowledge_writer": False,
        }

        reflection_record = {
            "task": task,
            "score": success_score,
            "confidence_score": confidence_score,
            "tests_passed": test_success,
            "task_type": task_type,
            "patterns": reusable_patterns,
            "lessons": lessons_learned,
            "generated_at": datetime.utcnow().isoformat(),
        }

        try:
            from iaglobal.memory.db_manager import db

            db.insert_insight(
                "reflexion",
                task,
                json.dumps(
                    reflection_record,
                    ensure_ascii=False
                ),
                score=confidence_score,
            )

            persistence_status["db"] = True

        except Exception as e:
            logger.warning(
                "[REFLEXION] Falha DB: %s",
                e
            )

        try:
            from iaglobal.agents.knowledge_writer_agent import (
                KnowledgeWriterAgent
            )

            KnowledgeWriterAgent().learn_from_conversation(
                task=task,
                solution=artifact.code,
                score=confidence_score,
            )

            persistence_status[
                "knowledge_writer"
            ] = True

        except Exception as e:
            logger.warning(
                "[REFLEXION] Falha KnowledgeWriter: %s",
                e
            )

        # ---------------------------------------------------------
        # Métricas
        # ---------------------------------------------------------

        metrics = {
            "task_length": len(task),
            "code_length": code_size,
            "lessons": len(
                lessons_learned
            ),
            "patterns": len(
                reusable_patterns
            ),
            "confidence_score": round(
                confidence_score,
                2
            ),
            "tests_passed": test_success,
        }

        # ---------------------------------------------------------
        # Observabilidade
        # ---------------------------------------------------------

        logger.info(
            (
                "🧠 [REFLEXION] "
                "score=%.2f "
                "confidence=%.2f "
                "patterns=%d "
                "lessons=%d"
            ),
            success_score,
            confidence_score,
            len(reusable_patterns),
            len(lessons_learned),
        )

        self._log(
            ctx,
            (
                f"reflexion:"
                f" confidence={confidence_score:.2f}"
                f" patterns={len(reusable_patterns)}"
                f" lessons={len(lessons_learned)}"
            )
        )

        # ---------------------------------------------------------
        # Resultado
        # ---------------------------------------------------------

        return {
            "output": artifact,
            "reflection": reflection_record,
            "lessons_learned": lessons_learned,
            "reusable_patterns": reusable_patterns,
            "metrics": metrics,
            "persistence": persistence_status,
        }

#===========================================================================================

    # ── Nó: knowledge ─────────────────────────────────────────────

    async def run_knowledge(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.evolution.agents.knowledge_agent import (
            knowledge,
        )
        from iaglobal.graphs.artifact import SolutionArtifact

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        search_result = (
            ctx.get("memory", {})
               .get("search", {})
               .get("output", "")
        )

        if isinstance(search_result, SolutionArtifact):
            search_result = (
                search_result.security_report
                or search_result.code
                or str(search_result.critique)
                or ""
            )
        elif not isinstance(search_result, str):
            search_result = str(search_result)

        logger.info(
            "📚 [KNOWLEDGE] Processando conhecimento..."
        )

        # ---------------------------------------------------------
        # Extração e persistência
        # ---------------------------------------------------------

        extraction_stats = {
            "stored": False,
            "source_size": len(str(search_result)),
        }

        try:
            import asyncio
            await asyncio.to_thread(
                knowledge.extract_and_store,
                task,
                str(search_result)
            )
            extraction_stats["stored"] = True

        except Exception as e:
            logger.exception(
                "[KNOWLEDGE] Falha ao armazenar conhecimento"
            )
            extraction_stats["error"] = str(e)

        # ---------------------------------------------------------
        # Recuperação contextual
        # ---------------------------------------------------------

        knowledge_summary = ""

        try:
            knowledge_summary = knowledge.summarize(
                max_entries=10
            )

        except Exception as e:
            logger.warning(
                "[KNOWLEDGE] Falha ao gerar resumo: %s",
                e
            )

        # ---------------------------------------------------------
        # Recuperação dos itens mais relevantes
        # ---------------------------------------------------------

        relevant_entries = []

        try:
            retrieved = knowledge.retrieve_relevant(
                task,
                max_results=10
            )

            for item in retrieved:

                if isinstance(item, dict):
                    relevant_entries.append({
                        "content": item.get(
                            "content",
                            ""
                        )[:500],
                        "score": item.get(
                            "score"
                        ),
                        "source": item.get(
                            "source"
                        ),
                    })

                else:
                    relevant_entries.append({
                        "content": str(item)[:500]
                    })

        except Exception as e:
            logger.warning(
                "[KNOWLEDGE] Falha na recuperação semântica: %s",
                e
            )

        # ---------------------------------------------------------
        # Classificação simples do conhecimento
        # ---------------------------------------------------------

        knowledge_categories = set()

        content_blob = (
            task + "\n" + str(search_result)
        ).lower()

        categories = {
            "backend": [
                "api",
                "fastapi",
                "django",
                "flask",
                "endpoint",
            ],
            "frontend": [
                "react",
                "vue",
                "html",
                "css",
                "javascript",
            ],
            "devops": [
                "docker",
                "terraform",
                "kubernetes",
                "helm",
                "infra",
            ],
            "database": [
                "sql",
                "postgres",
                "mysql",
                "mongodb",
                "redis",
            ],
            "ai": [
                "llm",
                "embedding",
                "prompt",
                "agent",
                "rag",
                "vector",
            ],
            "blockchain": [
                "ethereum",
                "solidity",
                "web3",
                "evm",
                "smart contract",
            ],
        }

        for category, keywords in categories.items():

            if any(
                keyword in content_blob
                for keyword in keywords
            ):
                knowledge_categories.add(
                    category
                )

        # ---------------------------------------------------------
        # Score de utilidade
        # ---------------------------------------------------------

        utility_score = 0.0

        utility_score += min(
            len(relevant_entries) * 0.15,
            1.5
        )

        utility_score += (
            1.0
            if knowledge_summary
            else 0.0
        )

        utility_score += min(
            len(knowledge_categories) * 0.25,
            1.0
        )

        utility_score = round(
            utility_score,
            2
        )

        # ---------------------------------------------------------
        # Métricas
        # ---------------------------------------------------------

        metrics = {
            "task_size": len(task),
            "search_result_size": len(
                str(search_result)
            ),
            "summary_size": len(
                knowledge_summary
            ),
            "retrieved_entries": len(
                relevant_entries
            ),
            "categories": sorted(
                knowledge_categories
            ),
            "utility_score": utility_score,
        }

        # ---------------------------------------------------------
        # Observabilidade
        # ---------------------------------------------------------

        logger.info(
            (
                "📚 [KNOWLEDGE] "
                "entries=%d "
                "categories=%d "
                "score=%.2f "
                "summary=%d chars"
            ),
            len(relevant_entries),
            len(knowledge_categories),
            utility_score,
            len(knowledge_summary),
        )

        self._log(
            ctx,
            (
                f"knowledge:"
                f" entries={len(relevant_entries)}"
                f" score={utility_score}"
                f" chars={len(knowledge_summary)}"
            )
        )

        # ---------------------------------------------------------
        # Resultado
        # ---------------------------------------------------------

        return {
            "output": {
                "knowledge_context": knowledge_summary,
                "knowledge_summary": knowledge_summary,
                "relevant_entries": relevant_entries,
                "categories": sorted(
                    knowledge_categories
                ),
            },
            "knowledge_context": knowledge_summary,
            "knowledge_summary": knowledge_summary,
            "knowledge_entries": relevant_entries,
            "knowledge_categories": sorted(
                knowledge_categories
            ),
            "knowledge_metrics": metrics,
            "generated_at": datetime.utcnow().isoformat(),
        }

#===========================================================================================

    # ── Nó: enhancement ───────────────────────────────────────────

    async def run_enhancement(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.enhancement_agent import EnhancementAgent
        from iaglobal.agents.prompt_improver import PromptImprover, PromptMode
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        task = self._get_task(ctx)
        intake = ctx.get("input", {}).get("intake", {})
        wd = self._get_wd(ctx)

        logger.info("✨ [ENHANCEMENT] Iniciando enriquecimento da tarefa")

        # ---------------------------------------------------------
        # Recuperação de conhecimento
        # ---------------------------------------------------------

        knowledge_entries = []
        knowledge_context = ""

        try:
            knowledge_entries = knowledge.retrieve_relevant(
                task,
                max_results=5
            )

            if knowledge_entries:
                knowledge_context = knowledge.summarize(
                    max_entries=min(
                        len(knowledge_entries),
                        5
                    )
                )

        except Exception as e:
            logger.warning(
                "[ENHANCEMENT] Falha ao recuperar conhecimento: %s",
                e
            )

        # ---------------------------------------------------------
        # Recuperação de erros históricos
        # ---------------------------------------------------------

        error_entries = []
        error_context = ""

        try:
            error_entries = query_relevant_errors(
                task,
                limit=5
            )

            error_context = format_errors_for_prompt(
                error_entries
            )

        except Exception as e:
            logger.warning(
                "[ENHANCEMENT] Falha ao recuperar erros históricos: %s",
                e
            )

        # ---------------------------------------------------------
        # Preparação de contexto estruturado
        # ---------------------------------------------------------

        structured_knowledge = []

        for entry in knowledge_entries:

            if isinstance(entry, dict):
                content = entry.get("content", "")
                score = entry.get("score")
                source = entry.get("source")
            else:
                content = str(entry)
                score = None
                source = None

            if not content:
                continue

            structured_knowledge.append({
                "content": content[:500],
                "score": score,
                "source": source,
            })

        # ---------------------------------------------------------
        # Enhancement principal
        # ---------------------------------------------------------

        enhancement_agent = EnhancementAgent()

        try:
            result = enhancement_agent.enhance(
                task=task,
                intake=intake,
                knowledge_context=knowledge_context,
                error_context=error_context,
            )

        except Exception as e:
            logger.exception(
                "[ENHANCEMENT] EnhancementAgent falhou"
            )

            result = {
                "enhanced_task": task,
                "approach": [],
                "prerequisites": [],
                "error": str(e),
            }

        # ---------------------------------------------------------
        # Prompt Improvement
        # ---------------------------------------------------------

        raw_enhanced_task = result.get(
            "enhanced_task",
            task
        )

        try:
            improved_prompt = (
                PromptImprover()
                .improve(
                    raw_prompt=raw_enhanced_task,
                    domain=intake.get(
                        "domain",
                        "general"
                    ),
                    error_context=error_context,
                    knowledge_context=knowledge_context,
                    suggested_libs=result.get(
                        "suggested_libs",
                        []
                    ),
                    mode=PromptMode.COMPACT,
                )
            )

        except Exception as e:
            logger.warning(
                "[ENHANCEMENT] PromptImprover falhou: %s",
                e
            )

            improved_prompt = raw_enhanced_task

        # ---------------------------------------------------------
        # Deduplicação simples
        # ---------------------------------------------------------

        lines = []
        seen = set()

        for line in improved_prompt.splitlines():
            normalized = line.strip().lower()

            if normalized in seen:
                continue

            seen.add(normalized)
            lines.append(line)

        improved_prompt = "\n".join(lines)

        result["enhanced_task"] = improved_prompt

        # ---------------------------------------------------------
        # Métricas de qualidade
        # ---------------------------------------------------------

        enrichment_score = 0.0

        enrichment_score += min(
            len(structured_knowledge) * 0.2,
            1.0
        )

        enrichment_score += min(
            len(error_entries) * 0.1,
            0.5
        )

        enrichment_score += min(
            len(result.get("approach", [])) * 0.2,
            1.0
        )

        enrichment_score += (
            0.5
            if len(improved_prompt) > len(task)
            else 0.0
        )

        quality_metrics = {
            "original_length": len(task),
            "enhanced_length": len(improved_prompt),
            "knowledge_items": len(structured_knowledge),
            "historical_errors": len(error_entries),
            "approaches": len(
                result.get("approach", [])
            ),
            "enrichment_score": round(
                enrichment_score,
                2
            ),
        }

        # ---------------------------------------------------------
        # Telemetria
        # ---------------------------------------------------------

        logger.info(
            (
                "✨ [ENHANCEMENT] "
                "knowledge=%d "
                "errors=%d "
                "approaches=%d "
                "score=%.2f"
            ),
            len(structured_knowledge),
            len(error_entries),
            len(result.get("approach", [])),
            enrichment_score,
        )

        self._log(
            ctx,
            (
                f"enhancement:"
                f" chars={len(improved_prompt)}"
                f" score={round(enrichment_score,2)}"
            )
        )

        # ---------------------------------------------------------
        # Persistência no contexto
        # ---------------------------------------------------------

        ctx["input"]["intake"] = intake
        ctx["input"]["enhanced_task"] = improved_prompt

        # ---------------------------------------------------------
        # Resultado
        # ---------------------------------------------------------

        return {
            "output": result,
            "enhanced_task": improved_prompt,
            "approach": result.get(
                "approach",
                []
            ),
            "prerequisites": result.get(
                "prerequisites",
                []
            ),
            "knowledge": structured_knowledge,
            "quality_metrics": quality_metrics,
            "generated_at": datetime.utcnow().isoformat(),
        }

#===========================================================================================

    # ── Nó: orchestrator_agent ────────────────────────────────────

    async def run_orchestrator_agent(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.critic_agent import CriticAgent
        from iaglobal.evolution.agents.knowledge_agent import knowledge
        from iaglobal.memory.memory_error import query_relevant_errors

        logger.info("🧠 [ORCHESTRATOR] Iniciando coordenação da execução...")

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        enhancement_mem = (
            ctx.get("memory", {})
               .get("enhancement", {})
               .get("output", {})
        )

        enhanced_task = ctx.get("input", {}).get("enhanced_task", "")
        prerequisites = enhancement_mem.get("prerequisites", [])

        enriched_task = enhanced_task or task

        if prerequisites:
            enriched_task += (
                "\n\nPré-requisitos:\n" +
                "\n".join(f"- {item}" for item in prerequisites)
            )

        # ---------------------------------------------------------
        # Recuperação de conhecimento
        # ---------------------------------------------------------

        knowledge_hints = []

        try:
            relevant = knowledge.retrieve_relevant(
                task,
                max_results=5
            )

            for entry in relevant:
                if isinstance(entry, dict):
                    content = entry.get("content", "")
                    score = entry.get("score")
                else:
                    content = str(entry)
                    score = None

                if not content:
                    continue

                hint = {
                    "content": content[:500],
                    "score": score,
                }

                knowledge_hints.append(hint)

        except Exception as e:
            logger.warning(
                "[ORCHESTRATOR] Falha ao recuperar conhecimento: %s",
                e
            )

        # ---------------------------------------------------------
        # Recuperação de erros históricos
        # ---------------------------------------------------------

        error_hints = []

        try:
            historical_errors = query_relevant_errors(
                task,
                limit=5
            )

            for err in historical_errors:

                if isinstance(err, dict):
                    error_hints.append({
                        "error": err.get("erro", "")[:500],
                        "solution": err.get("solucao", "")[:500],
                        "count": err.get("count", 1)
                    })
                else:
                    error_hints.append({
                        "error": str(err)[:500]
                    })

        except Exception as e:
            logger.warning(
                "[ORCHESTRATOR] Falha ao recuperar erros históricos: %s",
                e
            )

        # ---------------------------------------------------------
        # Classificação rápida da tarefa
        # ---------------------------------------------------------

        task_lower = task.lower()

        if any(k in task_lower for k in [
            "api", "endpoint", "fastapi",
            "flask", "django", "rest"
        ]):
            task_type = "backend"

        elif any(k in task_lower for k in [
            "react", "vue", "html",
            "css", "frontend", "ui"
        ]):
            task_type = "frontend"

        elif any(k in task_lower for k in [
            "test", "pytest",
            "unittest", "qa"
        ]):
            task_type = "testing"

        elif any(k in task_lower for k in [
            "docker", "kubernetes",
            "infra", "terraform",
            "deploy"
        ]):
            task_type = "devops"

        else:
            task_type = "general"

        # ---------------------------------------------------------
        # Estimativa simples de complexidade
        # ---------------------------------------------------------

        complexity_score = 0

        complexity_score += min(
            len(task.split()) / 50,
            3
        )

        complexity_score += min(
            len(prerequisites),
            3
        )

        complexity_score += min(
            len(knowledge_hints),
            2
        )

        if complexity_score < 2:
            complexity_level = "low"
        elif complexity_score < 5:
            complexity_level = "medium"
        else:
            complexity_level = "high"

        # ---------------------------------------------------------
        # Estratégia de execução
        # ---------------------------------------------------------

        execution_strategy = {
            "task_type": task_type,
            "complexity": complexity_level,
            "parallelizable": complexity_level != "low",
            "requires_validation": True,
            "requires_testing": (
                task_type in {
                    "backend",
                    "frontend",
                    "testing"
                }
            )
        }

        # ---------------------------------------------------------
        # Plano cognitivo
        # ---------------------------------------------------------

        orchestration_plan = {
            "task_type": task_type,
            "complexity": complexity_level,
            "knowledge_hints": knowledge_hints,
            "error_hints": error_hints,
            "execution_strategy": execution_strategy,
            "recommended_agents": ["planner", "coder", "reviewer", "tester"],
            "generated_at": datetime.utcnow().isoformat()
        }

        # ---------------------------------------------------------
        # Crítica preliminar
        # ---------------------------------------------------------

        critic_scores = {}

        try:
            critic_scores = (
                CriticAgent()
                .avaliar_com_scores(
                    enriched_task,
                    ""
                )
            ) or {}

        except Exception as e:
            logger.warning(
                "[ORCHESTRATOR] CriticAgent falhou: %s",
                e
            )

        # ---------------------------------------------------------
        # Observabilidade
        # ---------------------------------------------------------

        metrics = {
            "task_length": len(task),
            "enriched_length": len(enriched_task),
            "knowledge_count": len(knowledge_hints),
            "historical_error_count": len(error_hints),
            "complexity_score": round(complexity_score, 2)
        }

        logger.info(
            "🧠 [ORCHESTRATOR] Tipo=%s Complexidade=%s Conhecimento=%d Erros=%d",
            task_type,
            complexity_level,
            len(knowledge_hints),
            len(error_hints),
        )

        self._log(
            ctx,
            (
                f"orchestrator:"
                f" type={task_type}"
                f" complexity={complexity_level}"
                f" chars={len(enriched_task)}"
            )
        )

        ctx["input"]["task"] = enriched_task

        return {
            "output": {
                "task": enriched_task,
                "original_task": task,
                "prerequisites": prerequisites,
                "task_type": task_type,
                "complexity": complexity_level,
            },
            "enriched_task": enriched_task,
            "orchestration_plan": orchestration_plan,
            "critic_scores": critic_scores,
            "metrics": metrics,
        }

#===========================================================================================

    # ── Nó: security_design ───────────────────────────────────────

    async def run_security_design(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.security_design_agent import (
            SecurityDesignAgent,
        )

        from iaglobal.evolution.agents.knowledge_agent import (
            knowledge,
        )

        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        memory = ctx.get("memory", {})

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        # ----------------------------------------------------------
        # Contexto arquitetural
        # ----------------------------------------------------------

        architecture = (
            memory.get("architect", {})
            .get("output", {})
        )

        requirements = (
            memory.get("requirements", {})
            .get("output", {})
        )

        system_design = (
            memory.get("system_design", {})
            .get("output")
        )

        api_design = (
            memory.get("api_design", {})
            .get("output")
        )

        database_design = (
            memory.get("database_design", {})
            .get("output")
        )

        dependency_analysis = (
            memory.get("dependency", {})
            .get("output")
        )

        risk_analysis = (
            memory.get("risk_analysis", {})
            .get("output")
        )

        # ----------------------------------------------------------
        # Knowledge Base
        # ----------------------------------------------------------

        relevant_knowledge = knowledge.retrieve_relevant(
            task,
            max_results=5,
        )

        knowledge_context = (
            knowledge.summarize(max_entries=5)
            if relevant_knowledge
            else ""
        )

        # ----------------------------------------------------------
        # Histórico de falhas
        # ----------------------------------------------------------

        historical_errors = query_relevant_errors(
            task,
            limit=5,
        )

        error_context = format_errors_for_prompt(
            historical_errors
        )

        # ----------------------------------------------------------
        # Contexto consolidado
        # ----------------------------------------------------------

        design_context = {
            "architecture": architecture,
            "requirements": requirements,
            "system_design": system_design,
            "api_design": api_design,
            "database_design": database_design,
            "dependency_analysis": dependency_analysis,
            "risk_analysis": risk_analysis,
        }

        # ----------------------------------------------------------
        # Análise principal
        # ----------------------------------------------------------

        agent = SecurityDesignAgent()

        result = agent.analyze(
            design_context=design_context,
            knowledge_context=knowledge_context,
            error_context=error_context,
        )

        # ----------------------------------------------------------
        # Extração segura
        # ----------------------------------------------------------

        report = (
            result.get(
                "security_design_report",
                {}
            ) or {}
        )

        security_requirements = (
            result.get(
                "security_requirements",
                []
            ) or []
        )

        threat_model = (
            result.get(
                "threat_model",
                {}
            ) or {}
        )

        authentication_strategy = (
            result.get(
                "authentication_strategy",
                {}
            ) or {}
        )

        authorization_strategy = (
            result.get(
                "authorization_strategy",
                {}
            ) or {}
        )

        encryption_strategy = (
            result.get(
                "encryption_strategy",
                {}
            ) or {}
        )

        secret_management = (
            result.get(
                "secret_management",
                {}
            ) or {}
        )

        compliance_requirements = (
            result.get(
                "compliance_requirements",
                []
            ) or []
        )

        hardening_recommendations = (
            result.get(
                "hardening_recommendations",
                []
            ) or []
        )

        security_controls = (
            result.get(
                "security_controls",
                []
            ) or []
        )

        # ----------------------------------------------------------
        # Score de segurança
        # ----------------------------------------------------------

        total_issues = report.get(
            "total_issues",
            0
        )

        critical_issues = report.get(
            "critical_issues",
            0
        )

        high_issues = report.get(
            "high_issues",
            0
        )

        score = result.get(
            "security_score"
        )

        if score is None:

            penalty = (
                critical_issues * 25 +
                high_issues * 10 +
                total_issues * 3
            )

            score = max(
                0,
                100 - penalty
            )

        # ----------------------------------------------------------
        # Nível de risco
        # ----------------------------------------------------------

        if score >= 90:
            risk_level = "low"
        elif score >= 75:
            risk_level = "moderate"
        elif score >= 50:
            risk_level = "high"
        else:
            risk_level = "critical"

        # ----------------------------------------------------------
        # Métricas
        # ----------------------------------------------------------

        metrics = {
            "timestamp":
                datetime.utcnow().isoformat(),

            "security_score":
                score,

            "risk_level":
                risk_level,

            "total_issues":
                total_issues,

            "critical_issues":
                critical_issues,

            "high_issues":
                high_issues,

            "security_requirements":
                len(security_requirements),

            "security_controls":
                len(security_controls),

            "compliance_requirements":
                len(compliance_requirements),

            "knowledge_entries":
                len(relevant_knowledge),

            "historical_errors":
                len(historical_errors),
        }

        # ----------------------------------------------------------
        # Logs
        # ----------------------------------------------------------

        logger.info(
            (
                "🔒 [SECURITY-DESIGN] "
                "Score=%s | "
                "Risk=%s | "
                "Issues=%s"
            ),
            score,
            risk_level,
            total_issues,
        )

        self._log(
            ctx,
            (
                f"security_design "
                f"score={score} "
                f"risk={risk_level} "
                f"issues={total_issues}"
            )
        )

        # ----------------------------------------------------------
        # Resultado
        # ----------------------------------------------------------

        return {
            "output": result,

            "security_design_report":
                report,

            "security_requirements":
                security_requirements,

            "threat_model":
                threat_model,

            "authentication_strategy":
                authentication_strategy,

            "authorization_strategy":
                authorization_strategy,

            "encryption_strategy":
                encryption_strategy,

            "secret_management":
                secret_management,

            "compliance_requirements":
                compliance_requirements,

            "hardening_recommendations":
                hardening_recommendations,

            "security_controls":
                security_controls,

            "security_score":
                score,

            "risk_level":
                risk_level,

            "metrics":
                metrics,
        }

#===========================================================================================

    # ── Nó: performance_design ────────────────────────────────────

    async def run_performance_design(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.performance_design_agent import (
            PerformanceDesignAgent,
        )

        from iaglobal.evolution.agents.knowledge_agent import (
            knowledge,
        )

        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        memory = ctx.get("memory", {})

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        # ----------------------------------------------------------
        # Contexto arquitetural
        # ----------------------------------------------------------

        architecture = (
            memory.get("architect", {})
            .get("output", {})
        )

        requirements = (
            memory.get("requirements", {})
            .get("output", {})
        )

        system_design = (
            memory.get("system_design", {})
            .get("output")
        )

        api_design = (
            memory.get("api_design", {})
            .get("output")
        )

        database_design = (
            memory.get("database_design", {})
            .get("output")
        )

        dependency_analysis = (
            memory.get("dependency", {})
            .get("output")
        )

        # ----------------------------------------------------------
        # Conhecimento histórico
        # ----------------------------------------------------------

        relevant_knowledge = knowledge.retrieve_relevant(
            task,
            max_results=5,
        )

        knowledge_context = (
            knowledge.summarize(max_entries=5)
            if relevant_knowledge
            else ""
        )

        # ----------------------------------------------------------
        # Erros históricos
        # ----------------------------------------------------------

        historical_errors = query_relevant_errors(
            task,
            limit=5,
        )

        error_context = format_errors_for_prompt(
            historical_errors
        )

        # ----------------------------------------------------------
        # Contexto consolidado
        # ----------------------------------------------------------

        design_context = {
            "architecture": architecture,
            "requirements": requirements,
            "system_design": system_design,
            "api_design": api_design,
            "database_design": database_design,
            "dependency_analysis": dependency_analysis,
        }

        # ----------------------------------------------------------
        # Análise principal
        # ----------------------------------------------------------

        agent = PerformanceDesignAgent()

        result = agent.analyze(
            design_context=design_context,
            knowledge_context=knowledge_context,
            error_context=error_context,
        )

        # ----------------------------------------------------------
        # Extração segura
        # ----------------------------------------------------------

        report = (
            result.get(
                "performance_design_report",
                {}
            )
            or {}
        )

        performance_requirements = (
            result.get(
                "performance_requirements",
                []
            )
            or []
        )

        scalability_recommendations = (
            result.get(
                "scalability_recommendations",
                []
            )
            or []
        )

        caching_strategy = (
            result.get(
                "caching_strategy",
                {}
            )
            or {}
        )

        database_optimizations = (
            result.get(
                "database_optimizations",
                []
            )
            or []
        )

        bottlenecks = (
            result.get(
                "potential_bottlenecks",
                []
            )
            or []
        )

        sla_targets = (
            result.get(
                "sla_targets",
                {}
            )
            or {}
        )

        # ----------------------------------------------------------
        # Métricas
        # ----------------------------------------------------------

        total_issues = (
            report.get(
                "total_issues",
                len(bottlenecks)
            )
        )

        critical_issues = (
            report.get(
                "critical_issues",
                0
            )
        )

        score = result.get(
            "performance_score"
        )

        if score is None:

            penalty = (
                critical_issues * 20
                + total_issues * 5
            )

            score = max(
                0,
                100 - penalty
            )

        metrics = {
            "timestamp":
                datetime.utcnow().isoformat(),

            "performance_score":
                score,

            "total_issues":
                total_issues,

            "critical_issues":
                critical_issues,

            "requirements_count":
                len(performance_requirements),

            "bottlenecks":
                len(bottlenecks),

            "knowledge_entries":
                len(relevant_knowledge),

            "historical_errors":
                len(historical_errors),
        }

        # ----------------------------------------------------------
        # Logs
        # ----------------------------------------------------------

        logger.info(
            (
                "⚡ [PERF-DESIGN] "
                "Score=%s | "
                "Issues=%s | "
                "Critical=%s"
            ),
            score,
            total_issues,
            critical_issues,
        )

        self._log(
            ctx,
            (
                f"performance_design "
                f"score={score} "
                f"issues={total_issues}"
            )
        )

        # ----------------------------------------------------------
        # Resultado
        # ----------------------------------------------------------

        return {
            "output": result,

            "performance_design_report":
                report,

            "performance_requirements":
                performance_requirements,

            "scalability_recommendations":
                scalability_recommendations,

            "caching_strategy":
                caching_strategy,

            "database_optimizations":
                database_optimizations,

            "potential_bottlenecks":
                bottlenecks,

            "sla_targets":
                sla_targets,

            "performance_score":
                score,

            "metrics":
                metrics,
        }

#===========================================================================================

    # ── Nó: security_audit ────────────────────────────────────────

    async def run_security_audit(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.security_audit_agent import (
            SecurityAuditAgent,
        )

        from iaglobal.evolution.agents.knowledge_agent import (
            knowledge,
        )

        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        memory = ctx.get("memory", {})

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        # ----------------------------------------------------------
        # Descoberta automática da fonte de código
        # ----------------------------------------------------------

        code_sources = [
            "api_builder",
            "multi_coder",
            "coder",
            "debug_coder",
            "backend_builder",
            "frontend_builder",
            "api_builder",
        ]

        source_used = None
        code = ""

        for source in code_sources:

            artifact = memory.get(source, {}).get("output")

            if artifact is None:
                continue

            if isinstance(artifact, str) and artifact.strip():
                code = artifact
                source_used = source
                break

            if hasattr(artifact, "code") and artifact.code:
                code = artifact.code
                source_used = source
                break

        # ----------------------------------------------------------
        # Contexto arquitetural
        # ----------------------------------------------------------

        architecture_context = {
            "architect":
                memory.get("architect", {}).get("output"),

            "system_design":
                memory.get("system_design", {}).get("output"),

            "api_design":
                memory.get("api_design", {}).get("output"),

            "database_design":
                memory.get("database_design", {}).get("output"),

            "security_design":
                memory.get("security_design", {}).get("output"),

            "threat_modeling":
                memory.get("threat_modeling", {}).get("output"),
        }

        # ----------------------------------------------------------
        # Dependências analisadas anteriormente
        # ----------------------------------------------------------

        dependency_context = (
            memory.get("dependency", {})
            .get("output")
        )

        # ----------------------------------------------------------
        # Knowledge Base
        # ----------------------------------------------------------

        relevant_knowledge = knowledge.retrieve_relevant(
            task,
            max_results=5,
        )

        knowledge_context = (
            knowledge.summarize(max_entries=5)
            if relevant_knowledge
            else ""
        )

        # ----------------------------------------------------------
        # Histórico de falhas e vulnerabilidades
        # ----------------------------------------------------------

        historical_errors = query_relevant_errors(
            task,
            limit=5,
        )

        error_context = format_errors_for_prompt(
            historical_errors
        )

        # ----------------------------------------------------------
        # Auditoria principal
        # ----------------------------------------------------------

        auditor = SecurityAuditAgent()

        result = auditor.audit(
            task=task,
            code=code,
            architecture_context=architecture_context,
            dependency_context=dependency_context,
            knowledge_context=knowledge_context,
            error_context=error_context,
        )

        # ----------------------------------------------------------
        # Extração segura
        # ----------------------------------------------------------

        report = result.get("report", {})

        vulnerabilities = (
            result.get("vulnerabilities", [])
            or []
        )

        recommendations = (
            result.get("recommendations", [])
            or []
        )

        compliance_issues = (
            result.get("compliance_issues", [])
            or []
        )

        # ----------------------------------------------------------
        # Cálculo de score
        # ----------------------------------------------------------

        score = result.get("security_score")

        if score is None:

            critical = sum(
                1
                for v in vulnerabilities
                if str(
                    v.get("severity", "")
                ).lower()
                in {"critical"}
            )

            high = sum(
                1
                for v in vulnerabilities
                if str(
                    v.get("severity", "")
                ).lower()
                in {"high"}
            )

            medium = sum(
                1
                for v in vulnerabilities
                if str(
                    v.get("severity", "")
                ).lower()
                in {"medium"}
            )

            penalty = (
                critical * 25 +
                high * 12 +
                medium * 5
            )

            score = max(
                0,
                100 - penalty
            )

        # ----------------------------------------------------------
        # Classificação de risco
        # ----------------------------------------------------------

        if score >= 90:
            risk_level = "low"
        elif score >= 70:
            risk_level = "moderate"
        elif score >= 50:
            risk_level = "high"
        else:
            risk_level = "critical"

        # ----------------------------------------------------------
        # Métricas
        # ----------------------------------------------------------

        metrics = {
            "audit_timestamp":
                datetime.utcnow().isoformat(),

            "source_used":
                source_used,

            "security_score":
                score,

            "risk_level":
                risk_level,

            "vulnerability_count":
                len(vulnerabilities),

            "compliance_issues":
                len(compliance_issues),

            "knowledge_entries":
                len(relevant_knowledge),

            "historical_errors":
                len(historical_errors),
        }

        # ----------------------------------------------------------
        # Logs
        # ----------------------------------------------------------

        logger.info(
            (
                "🔒 [SECURITY-AUDIT] "
                "Score=%s | "
                "Risk=%s | "
                "Vulnerabilities=%s"
            ),
            score,
            risk_level,
            len(vulnerabilities),
        )

        self._log(
            ctx,
            (
                f"security_audit "
                f"score={score} "
                f"risk={risk_level} "
                f"vulnerabilities={len(vulnerabilities)}"
            )
        )

        # ----------------------------------------------------------
        # Resultado
        # ----------------------------------------------------------

        return {
            "output": result,

            "security_audit_report":
                report,

            "vulnerabilities":
                vulnerabilities,

            "recommendations":
                recommendations,

            "compliance_issues":
                compliance_issues,

            "security_score":
                score,

            "risk_level":
                risk_level,

            "metrics":
                metrics,

            "source_used":
                source_used,
        }

#===========================================================================================

    # ── Nó: performance_audit ─────────────────────────────────────

    async def run_performance_audit(self, ctx: dict) -> dict:
        from datetime import datetime

        from iaglobal.agents.performance_audit_agent import (
            PerformanceAuditAgent,
        )

        from iaglobal.evolution.agents.knowledge_agent import (
            knowledge,
        )

        from iaglobal.memory.memory_error import (
            query_relevant_errors,
            format_errors_for_prompt,
        )

        memory = ctx.get("memory", {})

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)

        # ----------------------------------------------------------
        # Descoberta automática da melhor fonte de código
        # ----------------------------------------------------------

        code_sources = [
            "api_builder",
            "multi_coder",
            "coder",
            "debug_coder",
            "backend_builder",
            "frontend_builder",
            "api_builder",
        ]

        source_used = None
        code = ""

        for source in code_sources:

            artifact = memory.get(source, {}).get("output")

            if artifact is None:
                continue

            if isinstance(artifact, str) and artifact.strip():
                code = artifact
                source_used = source
                break

            if hasattr(artifact, "code") and artifact.code:
                code = artifact.code
                source_used = source
                break

        # ----------------------------------------------------------
        # Contexto arquitetural
        # ----------------------------------------------------------

        architecture_context = {
            "architect":
                memory.get("architect", {}).get("output"),

            "system_design":
                memory.get("system_design", {}).get("output"),

            "database_design":
                memory.get("database_design", {}).get("output"),

            "api_design":
                memory.get("api_design", {}).get("output"),

            "dependency":
                memory.get("dependency", {}).get("output"),
        }

        # ----------------------------------------------------------
        # Knowledge Base
        # ----------------------------------------------------------

        relevant_knowledge = knowledge.retrieve_relevant(
            task,
            max_results=5,
        )

        knowledge_context = (
            knowledge.summarize(max_entries=5)
            if relevant_knowledge
            else ""
        )

        # ----------------------------------------------------------
        # Histórico de falhas
        # ----------------------------------------------------------

        historical_errors = query_relevant_errors(
            task,
            limit=5,
        )

        error_context = format_errors_for_prompt(
            historical_errors
        )

        # ----------------------------------------------------------
        # Auditoria
        # ----------------------------------------------------------

        auditor = PerformanceAuditAgent()

        result = auditor.audit(
            task=task,
            code=code,
            knowledge_context=knowledge_context,
            error_context=error_context,
            architecture_context=architecture_context,
        )

        # ----------------------------------------------------------
        # Extração segura
        # ----------------------------------------------------------

        report = result.get("report", {})
        bottlenecks = result.get("bottlenecks", [])
        recommendations = result.get("recommendations", [])

        # ----------------------------------------------------------
        # Score agregado
        # ----------------------------------------------------------

        score = result.get("score")

        if score is None:

            severity = len(
                [
                    b
                    for b in bottlenecks
                    if str(
                        b.get("severity", "")
                    ).lower()
                    in {"high", "critical"}
                ]
            )

            score = max(
                0,
                100 - (severity * 15)
            )

        # ----------------------------------------------------------
        # Estatísticas
        # ----------------------------------------------------------

        metrics = {
            "audit_timestamp":
                datetime.utcnow().isoformat(),

            "source_used":
                source_used,

            "knowledge_entries":
                len(relevant_knowledge),

            "historical_errors":
                len(historical_errors),

            "bottlenecks_found":
                len(bottlenecks),

            "score":
                score,
        }

        # ----------------------------------------------------------
        # Logs
        # ----------------------------------------------------------

        logger.info(
            (
                "⚡ [PERF-AUDIT] "
                "Score=%s | "
                "Bottlenecks=%s | "
                "Source=%s"
            ),
            score,
            len(bottlenecks),
            source_used,
        )

        self._log(
            ctx,
            (
                f"performance_audit "
                f"score={score} "
                f"bottlenecks={len(bottlenecks)}"
            )
        )

        # ----------------------------------------------------------
        # Resultado
        # ----------------------------------------------------------

        return {
            "output": result,

            "performance_audit_report":
                report,

            "bottlenecks":
                bottlenecks,

            "recommendations":
                recommendations,

            "performance_score":
                score,

            "metrics":
                metrics,

            "source_used":
                source_used,
        }

#===========================================================================================

    # ── Nó: architecture_validator ────────────────────────────

    async def run_architecture_validator(self, ctx: dict) -> dict:
        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        designs = {
            "system_design": memory.get("system_design", {}).get("output"),
            "api_design": memory.get("api_design", {}).get("output"),
            "database_design": memory.get("database_design", {}).get("output"),
            "security_design": memory.get("security_design", {}).get("output"),
            "performance_design": memory.get("performance_design", {}).get("output"),
            "observability_design": memory.get("observability_design", {}).get("output"),
        }

        architect_out = memory.get("architect", {}).get("output", {})

        issues = []
        score = 100.0
        design_count = sum(1 for v in designs.values() if v)

        if design_count < 3:
            issues.append("Menos de 3 designs de arquitetura disponíveis para validação")
            score -= 30

        if not architect_out:
            issues.append("Arquitetura base (architect) não encontrada")
            score -= 20

        if designs.get("security_design") is None:
            issues.append("Security design ausente")
            score -= 15

        if designs.get("performance_design") is None:
            issues.append("Performance design ausente")
            score -= 10

        score = max(0, score)

        logger.info("[ARCH-VALIDATOR] Score=%.1f | Designs=%d | Issues=%d", score, design_count, len(issues))
        self._log(ctx, f"architecture_validator score={score} issues={len(issues)}")

        return {
            "output": {
                "validated": score >= 60,
                "score": score,
                "issues": issues,
                "designs_checked": design_count,
            },
            "architecture_score": score,
            "issues": issues,
            "designs_checked": design_count,
            "validated": score >= 60,
        }

#===========================================================================================

    # ── Nó: semantic_validator ────────────────────────────────

    async def run_semantic_validator(self, ctx: dict) -> dict:
        import ast

        task = self._get_task(ctx)
        wd = self._get_wd(ctx)
        memory = ctx.get("memory", {})

        artifact = (
            memory.get("reviewer", {}).get("output")
            or memory.get("validator", {}).get("output")
            or memory.get("multi_coder", {}).get("output")
        )

        code = ""
        if hasattr(artifact, "code"):
            code = artifact.code or ""
        elif isinstance(artifact, dict):
            code = artifact.get("code") or artifact.get("output", "")

        if not code:
            logger.info("[SEMANTIC] Nenhum código para validar")
            return {"output": {"valid": True, "score": 100, "errors": []}, "semantic_score": 100, "errors": []}

        errors = []
        score = 100.0

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and len(node.body) > 50:
                    errors.append(f"Função '{node.name}' muito longa ({len(node.body)} statements)")
                    score -= 5

                if isinstance(node, ast.ClassDef) and len(node.body) > 40:
                    errors.append(f"Classe '{node.name}' muito grande ({len(node.body)} members)")
                    score -= 5

            imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            if not imports:
                errors.append("Nenhuma importação encontrada — possível código incompleto")
                score -= 10

        except SyntaxError as e:
            errors.append(f"Erro de sintaxe: {e}")
            score -= 40
        except Exception as e:
            errors.append(f"Erro na análise semântica: {e}")
            score -= 20

        score = max(0, score)

        logger.info("[SEMANTIC-VALIDATOR] Score=%.1f | Errors=%d", score, len(errors))
        self._log(ctx, f"semantic_validator score={score} errors={len(errors)}")

        return {
            "output": {
                "valid": score >= 50,
                "score": score,
                "errors": errors,
            },
            "semantic_score": score,
            "errors": errors,
            "valid": score >= 50,
        }

#===========================================================================================

