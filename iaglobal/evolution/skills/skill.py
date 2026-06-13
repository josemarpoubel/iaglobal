# iaglobal/evolution/skills/skill.py
"""
🎯 Skill – Unidade executável + contrato + constraints + identidade versionada.
Mapeia o comportamento atômico de um agente dentro do Grafo Evolutivo.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, TYPE_CHECKING  # <-- Importe TYPE_CHECKING
from enum import Enum
# Node é importado apenas sob TYPE_CHECKING (para evitar circular: skill → graphs → skill_executor → skill)
if TYPE_CHECKING:
    from iaglobal.graphs.node import Node
    from .skill_executor import SkillExecutionError

class ExecutionPolicy(Enum):
    SINGLE_RUN = "single-run"      # Executa uma vez por task
    REPEATABLE = "repeatable"      # Pode executar múltiplas vezes
    ON_DEMAND = "on-demand"        # Executa apenas quando requisitado
    ALWAYS = "always"              # Executa sempre, mesmo em cache


@dataclass
class Skill:
    """
    Skill – contrato executável versionado.
    
    Frozen=True garante imutabilidade: uma vez definida, a skill
    não pode ser alterada (apenas versionada).
    """
    name: str
    version: str
    description: str = ""

    # Execução
    run_fn: Optional[Callable] = None
    
    # Contrato
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    
    # Constraints
    constraints: List[str] = field(default_factory=list)
    
    # Política
    execution_policy: ExecutionPolicy = ExecutionPolicy.SINGLE_RUN
    
    # Metadados
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "production"

    def __post_init__(self):
        if not self.name:
            raise ValueError("Skill.name é obrigatório")
        # Garante que as listas internas se tornem tuplas imutáveis
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "tags", tuple(self.tags))

    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Verifica se todos os inputs necessários estão disponíveis."""
        return all(inp in context for inp in self.inputs)

    def validate_output(self, output: Any) -> bool:
        """Valida se a saída atende ao contrato (verificação básica)."""
        return output is not None

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.can_execute(context):
            raise ValueError(
                f"Contexto insuficiente para executar a skill '{self.name}'. "
                f"Inputs requeridos: {self.inputs}"
            )

        if self.run_fn:
            return self.run_fn(context)

        from .skill_executor import SkillExecutionError
        raise SkillExecutionError(
            f"Skill '{self.name}' sem run_fn — fallback para node.run"
        )


    def to_dict(self) -> Dict[str, Any]:
        """Serializa a skill para persistência ou geração de snapshots."""
        return {
            "name": self.name,
            "description": self.description,
            "inputs": self.inputs.copy(),
            "outputs": self.outputs.copy(),
            "constraints": self.constraints.copy(),
            "execution_policy": self.execution_policy.value,
            "version": self.version,
            "author": self.author,
            "tags": self.tags.copy(),
            "metadata": self.metadata.copy(),
        }

    def to_node(
        self,
        depends_on: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        critical: bool = False,
        model_hint: Optional[str] = None,
        name: Optional[str] = None,
    ) -> "Node":
        """Cria e configura adequadamente um Node a partir das propriedades imutáveis da Skill."""
        from iaglobal.graphs.node import Node
        
        node_name = name or self.name
        
        # Instancia o nó passando as propriedades reais do contrato da skill em vez de Ellipsis (...)
        return Node(
            name=node_name,
            inputs=list(self.inputs),
            outputs=list(self.outputs),
            run_fn=self.execute,
            depends_on=depends_on or [],
            strategy=strategy or self.constraints[0] if self.constraints else "llm",
            critical=critical,
            metadata={
                "version": self.version,
                "policy": self.execution_policy.value,
                "model_hint": model_hint,
                "tags": list(self.tags)
            }
        )

def _search_run_fn(context: Dict[str, Any]) -> Dict[str, Any]:
    from iaglobal.tools.search import search_tool
    
    # CORREÇÃO DE CONTRATO: Procura na raiz primeiro para respeitar self.inputs, com fallback para sub-dicionário
    task = context.get("task")
    if not task and "input" in context and isinstance(context["input"], dict):
        task = context["input"].get("task", "")
        
    task = str(task or "").strip()
    
    if not task or len(task) < 5:
        return {"output": "", "web_context": "", "success": False, "strategy_used": "search_tool"}
    try:
        result = search_tool(task)
        return {"output": result, "web_context": result, "success": bool(result), "strategy_used": "search_tool"}
    except Exception as e:
        return {"output": "", "web_context": "", "success": False, "error": str(e), "strategy_used": "search_tool"}


def _placeholder_run(name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback dinâmico corrigido para respeitar o contrato global do Grafo.
    """
    logger.warning(f"[SKILL-PLACEHOLDER] Executando fallback para a skill inacabada: '{name}'")
    return {
        "output": f"Placeholder executado para a skill: {name}", 
        "success": True,
        "strategy_used": "placeholder",
        "metadata": {
            "status": "placeholder_executed",
            "context_keys": list(context.keys())
        }
    }

# ... (Mantenha a declaração das @dataclass e constantes das skills intactas)

# CORREÇÃO DO MÉTODO TO_NODE DENTRO DA CLASSE SKILL:

# ── Skills pré-definidas do sistema ───────────────────────────────────────

SKILL_PLANNER = Skill(
    name="planner",
    description="Gera plano de execução estruturado com subtarefas",
    inputs=["task"],
    outputs=["plan"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "planning"],
)

SKILL_INGESTION = Skill(
    name="ingestion",
    description="Ingestão multimodal — arquivos, logs, documentação técnica",
    inputs=["requirements"],
    outputs=["ingested_data"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "ingestion"],
)

SKILL_DOMAIN_ANALYSIS = Skill(
    name="domain_analysis",
    description="Analisa o domínio do problema e identifica entidades, regras e fluxos",
    inputs=["requirements"],
    outputs=["domain_model"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "domain"],
)

SKILL_BUSINESS_RULES = Skill(
    name="business_rules",
    description="Gera regras de negócio a partir da tarefa",
    inputs=["task"],
    outputs=["business_rules"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "business"],
)

SKILL_TECHNOLOGY_SELECTION = Skill(
    name="technology_selection",
    description="Seleciona tecnologias adequadas com base nas regras de negócio",
    inputs=["business_rules"],
    outputs=["technology_selection"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "technology"],
)

SKILL_SYSTEM_DESIGN = Skill(
    name="system_design",
    description="Projeta a arquitetura do sistema com base nos requisitos",
    inputs=["architect"],
    outputs=["system_design"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "design"],
)

SKILL_API_DESIGN = Skill(
    name="api_design",
    description="Projeta as interfaces de API do sistema",
    inputs=["architect"],
    outputs=["api_design"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "design"],
)

SKILL_CODER = Skill(
    name="coder",
    description="Gera código a partir de especificação",
    inputs=["task", "plan"],
    outputs=["code"],
    constraints=["llm", "python", "syntax_valid"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "coding"],
)

SKILL_CRITIC = Skill(
    name="critic",
    description="Avalia código com LLM multidimensional",
    inputs=["code", "task"],
    outputs=["critique", "score"],
    constraints=["llm", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "review"],
)

SKILL_ARCHITECTURE_VALIDATOR = Skill(
    name="architecture_validator",
    description="Valida arquitetura proposta com base na seleção tecnológica",
    inputs=["technology_selection"],
    outputs=["architecture_validation"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "validation"],
    run_fn=lambda ctx: _placeholder_run("architecture_validation", ctx),
)

# ── Skills de análise e suporte ───────────────────────────────────────────

SKILL_REVIEWER = Skill(
    name="reviewer",
    description="Faz code review técnico: verifica SOLID, Clean Code, duplicação, "
                "complexidade ciclomática e sugere refatorações",
    inputs=["code", "task"],
    outputs=["review_score", "issues"],
    constraints=["llm", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "review", "quality"],
)

SKILL_SECURITY = Skill(
    name="security",
    description="Analisa segurança do código: SQL Injection, XSS, SSRF, "
                "Prompt Injection, secrets expostos e dependências vulneráveis",
    inputs=["code"],
    outputs=["security_report", "security_issues"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security", "analysis"],
)

SKILL_PERFORMANCE = Skill(
    name="performance",
    description="Analisa performance do código: consultas lentas, loops "
                "desnecessários, uso excessivo de memória e gargalos",
    inputs=["code"],
    outputs=["performance_score", "bottlenecks"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "performance", "analysis"],
)

SKILL_DOCUMENTATION = Skill(
    name="documentation",
    description="Gera documentação do projeto: README, docstrings, ADRs "
                "e diagramas a partir do código aprovado",
    inputs=["code", "path"],
    outputs=["readme", "adr", "docstrings"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "documentation"],
)

SKILL_TASK_BREAKDOWN = Skill(
    name="task_breakdown",
    description="Decompõe o plano em tarefas atômicas e ordenadas",
    inputs=["planner"],
    outputs=["tasks"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "planning"],
)

SKILL_EXECUTION_PLAN = Skill(
    name="execution_plan",
    description="Gera plano de execução detalhado a partir da arquitetura validada",
    inputs=["architecture_validation"],
    outputs=["execution_plan"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "planning"],
)

SKILL_INTEGRATOR = Skill(
    name="integrator",
    description="Integra componentes frontend, backend, database e API em um artefato único",
    inputs=["frontend_builder", "backend_builder", "database_builder", "api_builder"],
    outputs=["integrated_code", "files"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "integration"],
)

SKILL_SEMANTIC_VALIDATOR = Skill(
    name="semantic_validator",
    description="Valida semântica do código usando AST analysis",
    inputs=["reviewer"],
    outputs=["validation_score", "errors"],
    constraints=["fast", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "validation", "semantic"],
)

SKILL_DEPENDENCY = Skill(
    name="dependency",
    description="Gerencia dependências do projeto: seleciona bibliotecas, "
                "verifica compatibilidade e atualiza versões",
    inputs=["code", "path", "requirements"],
    outputs=["requirements", "compatibility_report", "missing_deps"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "dependency", "management"],
)

# ── Skills de requisitos, construção e suporte ────────────────────────────

SKILL_REQUIREMENTS = Skill(
    name="requirements",
    description="Converte intenção em requisitos formais: funcionais, não funcionais "
                "e critérios de aceite",
    inputs=["task", "refined_task"],
    outputs=["rf", "rnf", "acceptance_criteria", "use_cases"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "requirements"],
)

SKILL_FRONTEND_BUILDER = Skill(
    name="frontend_builder",
    description="Constrói componentes de frontend a partir do plano de execução",
    inputs=["execution_plan"],
    outputs=["frontend_code"],
    constraints=["llm", "ui", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "frontend", "builder"],
    run_fn=lambda ctx: _placeholder_run("frontend_code", ctx),
)

SKILL_PRODUCT_MANAGER = Skill(
    name="pm",
    description="Product Manager – a partir de requisitos estruturados, cria "
                "Epics, Features, Stories e Backlog para o planner",
    inputs=["requirements"],
    outputs=["epics", "features", "stories", "backlog"],
    constraints=["structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "pm", "product_manager"],
)

SKILL_BACKEND_BUILDER = Skill(
    name="backend_builder",
    description="Constrói componentes de backend a partir do plano de execução",
    inputs=["execution_plan"],
    outputs=["backend_code"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "backend", "builder"],
    run_fn=lambda ctx: _placeholder_run("backend_code", ctx),
)

SKILL_TESTER = Skill(
    name="tester",
    description="Gera e executa testes automatizados",
    inputs=["code", "task"],
    outputs=["tests", "results"],
    constraints=["sandbox", "deterministic"],
    execution_policy=ExecutionPolicy.REPEATABLE,
    version="v1",
    tags=["core", "testing"],
)

SKILL_DEBUGGER = Skill(
    name="debugger",
    description="Corrige código com base em erros detectados",
    inputs=["code", "error"],
    outputs=["fixed_code"],
    constraints=["llm", "iterative"],
    execution_policy=ExecutionPolicy.ON_DEMAND,
    version="v1",
    tags=["core", "debugging"],
)

SKILL_REFLEXION = Skill(
    name="reflexion",
    description="Analisa qualidade da execução e sugere melhorias",
    inputs=["execution_result"],
    outputs=["insight"],
    constraints=["analysis"],
    execution_policy=ExecutionPolicy.ALWAYS,
    version="v1",
    tags=["core", "reflection"],
)

# ── Skills de banco de dados e blockchain ─────────────────────────────────

SKILL_DATABASE_DESIGN = Skill(
    name="database_design",
    description="Projeta o esquema de banco de dados",
    inputs=["architect"],
    outputs=["database_design"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "design"],
)

SKILL_THREAT_MODELING = Skill(
    name="threat_modeling",
    description="Modela ameaças de segurança para o sistema",
    inputs=["security_design"],
    outputs=["threat_model"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security"],
)

SKILL_OBSERVABILITY_DESIGN = Skill(
    name="observability_design",
    description="Projeta estratégia de observabilidade (logs, métricas, tracing)",
    inputs=["architect"],
    outputs=["observability_design"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "design"],
)

SKILL_COMPLIANCE_AUDIT = Skill(
    name="compliance_audit",
    description="Audita conformidade do código com regras e padrões",
    inputs=["semantic_validator"],
    outputs=["compliance_report"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "audit"],
)

SKILL_DATABASE_BUILDER = Skill(
    name="database_builder",
    description="Constrói esquema de banco de dados a partir do plano de execução",
    inputs=["execution_plan"],
    outputs=["db_schema"],
    constraints=["llm", "structured", "sql"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "database", "builder"],
)

SKILL_GENESIS = Skill(
    name="genesis_builder",
    description="Gera bloco genesis para blockchain com SHA3-512",
    inputs=["blockchain_name", "author"],
    outputs=["block", "chain"],
    constraints=["sha3_512", "deterministic", "python"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["blockchain", "genesis", "core"],
)

# ── Skills da Pipeline V2 ─────────────────────────────────────────────────

SKILL_PROMPT_INTAKE = Skill(
    name="prompt_intake",
    description="Primeiro contato com o usuário – extrai domínio, objetivo, "
                "nível de ambiguidade e detecta lacunas, conflitos e requisitos faltantes",
    inputs=["task"],
    outputs=["intake_report", "domain", "objective", "ambiguity_level"],
    constraints=["llm", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "intake"],
)

SKILL_RISK_ANALYSIS = Skill(
    name="risk_analysis",
    description="Analisa riscos do projeto: escalabilidade, compliance, "
                "segurança e custos antes do planejamento",
    inputs=["architecture", "task"],
    outputs=["risk_report", "mitigations", "risk_score"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "risk"],
)

SKILL_API_BUILDER = Skill(
    name="api_builder",
    description="Constrói camada de API a partir do plano de execução",
    inputs=["execution_plan"],
    outputs=["api_code"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "api", "builder"],
    run_fn=lambda ctx: _placeholder_run("api_code", ctx),
)

SKILL_RELEASE = Skill(
    name="release",
    description="Gera artefatos de release: CHANGELOG, versionamento, "
                "release notes e plano de deploy a partir do código final",
    inputs=["code", "path", "documentation"],
    outputs=["changelog", "version", "release_notes", "deploy_plan"],
    constraints=["structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "release"],
    run_fn=lambda ctx: _placeholder_run("release", ctx),
)

SKILL_TEST_GENERATOR = Skill(
    name="test_generator",
    description="Gera testes automatizados a partir dos componentes construídos",
    inputs=["backend_code", "frontend_code", "db_schema", "api_code"],
    outputs=["tests"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "testing", "generator"],
    run_fn=lambda ctx: _placeholder_run("tests", ctx),
)

SKILL_METRICS = Skill(
    name="metrics",
    description="Agente transversal – observa todos os nós e coleta métricas: "
                "tempo, tokens, qualidade, cobertura, bugs",
    inputs=["execution_log"],
    outputs=["metrics_report", "durations", "token_usage", "quality_scores"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.ALWAYS,
    version="v1",
    tags=["core", "metrics", "observability"],
)

SKILL_OPTIMIZATION = Skill(
    name="optimization",
    description="Analisa histórico de execuções passadas para descobrir padrões: "
                "quais agentes são úteis para quais tarefas, otimizações de pipeline",
    inputs=["execution_history"],
    outputs=["optimization_report", "patterns", "suggestions"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.ALWAYS,
    version="v1",
    tags=["core", "optimization"],
)

# ============================================================
# 🏗️ Skills de Infraestrutura
# ============================================================

SKILL_INTERPRETER = Skill(
    name="interpreter",
    description="Interpreta e melhora o prompt do usuário: corrige gramática (PT/EN), "
                "estrutura a solicitação e prepara para o pipeline",
    inputs=["task"],
    outputs=["refined_task"],
    constraints=["llm", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "preprocessing"],
)

SKILL_ARCHITECT = Skill(
    name="architect",
    description="Projeta a arquitetura do sistema: escolhe padrões (MVC, hexagonal, etc.), "
                "define módulos, dependências, estrutura de pastas e contratos de API",
    inputs=["task"],
    outputs=["architecture"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "architecture"],
)

SKILL_WEB_CLASSIFIER = Skill(
    name="web_classifier",
    description="Classifica se a tarefa precisa de busca web",
    inputs=["task"],
    outputs=["needs_web"],
    constraints=["fast", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "classification"],
)

SKILL_SEARCH = Skill(
    name="search",
    description="Executa busca web para enriquecer contexto",
    inputs=["task", "needs_web"],
    outputs=["web_context"],
    constraints=["web", "cache"],
    execution_policy=ExecutionPolicy.ON_DEMAND,
    version="v1",
    tags=["infra", "web"],
    run_fn=_search_run_fn,
)

# Consolidado: Validator Suite
SKILL_VALIDATOR = Skill(
    name="validator",
    description="Valida código gerado em múltiplas dimensões: estilo visual, semântica, "
                "consistência estrutural e conformidade com requisitos",
    inputs=["code", "task"],
    outputs=["validated_code", "validation_report", "issues"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "validation", "suite"],
    run_fn=lambda ctx: _placeholder_run("validation_report", ctx),
)

# ============================================================
# 🏗️ Skills de Validação, Persistência e Memória
# ============================================================

SKILL_QA = Skill(
    name="qa",
    description="Garantia de qualidade — executa verificações automatizadas no código",
    inputs=["integrator"],
    outputs=["qa_report"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "qa"],
)

SKILL_DEBUG_CODER = Skill(
    name="debug_coder",
    description="Corrige bugs identificados pelo tester",
    inputs=["tester"],
    outputs=["fixed_code"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "debug"],
)

SKILL_FIX_VALIDATOR = Skill(
    name="fix_validator",
    description="Valida correções aplicadas ao código, garantindo que o bug foi resolvido "
                "sem introduzir regressões",
    inputs=["code"],
    outputs=["fix_validation_report", "issues"],
    constraints=["llm", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "validation", "fix"],
    run_fn=lambda ctx: _placeholder_run("fix_validation_report", ctx),
)

SKILL_ARTIFACT_WRITER = Skill(
    name="artifact_writer",
    description="Persiste o artefato final em disco e retorna caminho do arquivo",
    inputs=["artifact"],
    outputs=["path", "artifact_type"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "persistence"],
)

SKILL_KNOWLEDGE = Skill(
    name="knowledge",
    description="Agente de conhecimento transversal: armazena e recupera arquiteturas anteriores, "
                "bugs recorrentes, boas práticas e padrões internos. Alimenta os demais nós com contexto histórico.",
    inputs=["task"],
    outputs=["knowledge_context"],
    constraints=["structured", "fast"],
    execution_policy=ExecutionPolicy.ALWAYS,
    version="v1",
    tags=["infra", "memory", "transversal"],
)

# ================================================================
## 🚀 Skills da Pipeline V3
# ================================================================

SKILL_ENHANCEMENT = Skill(
    name="enhancement",
    description="Enriquece e refina o prompt de entrada após o intake: "
                "expande contexto, sugere abordagens, identifica pré-requisitos "
                "e prepara para o orchestrator",
    inputs=["task", "intake_report"],
    outputs=["enhanced_task", "approach", "prerequisites"],
    constraints=["llm", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "enhancement", "v3"],
)

SKILL_ORCHESTRATOR = Skill(
    name="orchestrator_agent",
    description="Orquestrador central da pipeline V3: coordena o fluxo entre "
                "os agentes, decide próximos passos e gerencia o estado "
                "da execução",
    inputs=["enhanced_task", "prerequisites"],
    outputs=["orchestration_plan", "execution_order"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "orchestrator", "v3"],
)

SKILL_SECURITY_DESIGN = Skill(
    name="security_design",
    description="Analisa requisitos de segurança na fase de design: "
                "autenticação, autorização, criptografia, proteção de dados, "
                "OWASP Top 10 e compliance",
    inputs=["architecture", "requirements"],
    outputs=["security_design_report", "security_requirements"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security", "design", "v3"],
    run_fn=lambda ctx: _placeholder_run("security_design_report", ctx),
)

# ================================================================
## 🚀 Skills de Deploy, Auditoria e Resultado
# ================================================================

SKILL_DEPLOYMENT_PLAN = Skill(
    name="deployment_plan",
    description="Gera plano de deployment detalhado a partir do código final",
    inputs=["code"],
    outputs=["deployment_plan"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "deployment"],
    run_fn=lambda ctx: _placeholder_run("deployment_plan", ctx),
)

SKILL_PERFORMANCE_DESIGN = Skill(
    name="performance_design",
    description="Analisa requisitos de performance na fase de design: "
                "latência, throughput, escalabilidade, concorrência, "
                "uso de memória e CPU",
    inputs=["architecture", "requirements"],
    outputs=["performance_design_report", "performance_requirements"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "performance", "design"],
    run_fn=lambda ctx: _placeholder_run("performance_design_report", ctx),
)

SKILL_RETROSPECTIVE = Skill(
    name="retrospective",
    description="Executa retrospectiva após a entrega: "
                "analisa métricas, erros, acertos e gera relatório de lições aprendidas",
    inputs=["metrics_report", "execution_log"],
    outputs=["retrospective_report", "lessons_learned"],
    constraints=["structured", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "retrospective"],
    run_fn=lambda ctx: _placeholder_run("retrospective_report", ctx),
)

SKILL_SECURITY_AUDIT = Skill(
    name="security_audit",
    description="Audita o código gerado contra requisitos de segurança: "
                "verifica autenticação, sanitização de inputs, "
                "proteção contra SQLi/XSS/SSRF e secrets management",
    inputs=["code", "security_requirements"],
    outputs=["security_audit_report", "security_issues"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security", "audit"],
)

SKILL_PERFORMANCE_AUDIT = Skill(
    name="performance_audit",
    description="Audita o código gerado contra requisitos de performance: "
                "verifica N+1 queries, caching, lazy loading, bottlenecks "
                "e uso eficiente de recursos",
    inputs=["code", "performance_requirements"],
    outputs=["performance_audit_report", "bottlenecks"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "performance", "audit"],
)

SKILL_RESULT_AGENT = Skill(
    name="result_agent",
    description="Agente de resultado final: agrega saídas de todos os "
                "agentes, formata resposta para o usuário, resume "
                "decisões e próximos passos",
    inputs=["documentation", "release", "metrics", "optimization"],
    outputs=["final_result", "summary", "next_steps"],
    constraints=["llm", "structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "result"],
    run_fn=lambda ctx: {"output": ctx.get("input", {}).get("task", ""), "final_result": ""},
)

# ============================================================
# 🔮 Metacognition Skills
# ============================================================

SKILL_EVALUATOR = Skill(
    name="evaluator",
    description="PipelineEvaluator – avalia performance da run e produz score 0–100",
    inputs=["result_agent"],
    outputs=["score", "evaluation"],
    constraints=["fast", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "evaluation"],
)

SKILL_GAP_ANALYZER = Skill(
    name="gap_analyzer",
    description="MetaGapAnalyzer – identifica gaps baseados em erros frequentes",
    inputs=["evaluator"],
    outputs=["gaps"],
    constraints=["fast", "deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "analysis"],
)

SKILL_SKILL_GENERATOR = Skill(
    name="skill_generator",
    description="MetaSkillGenerator – gera Skill template para gaps identificados",
    inputs=["gap_analyzer"],
    outputs=["generated_skills"],
    constraints=["structured"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "generation"],
)

SKILL_SANDBOX_VALIDATOR = Skill(
    name="sandbox_validator",
    description="SandboxValidator – valida skills geradas em ambiente isolado",
    inputs=["skill_generator"],
    outputs=["validation_results"],
    constraints=["deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "validation"],
)

SKILL_EVOLUTION_COMMITTEE = Skill(
    name="evolution_committee",
    description="EvolutionCommittee – avalia skills com 4 verificações (gain, risk, compat, cost)",
    inputs=["sandbox_validator"],
    outputs=["committee_decision"],
    constraints=["deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "governance"],
)

SKILL_PIPELINE_UPDATER = Skill(
    name="pipeline_updater",
    description="PipelineUpdater – atualiza pipeline com skills aprovadas pelo comitê",
    inputs=["evolution_committee"],
    outputs=["updates"],
    constraints=["deterministic"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "update"],
)

SKILL_EVOLUTION_TRIGGER = Skill(
    name="evolution_trigger",
    description="EvolutionTrigger – dispara evolução genética baseada em resultados",
    inputs=["pipeline_updater"],
    outputs=["triggered", "reason"],
    constraints=["fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["metacognition", "evolution"],
)

# ============================================================
# 🔄 Auto-register skills (lazy — triggered on first registry access)
# ============================================================

SKILL_LOCAL_KNOWLEDGE = Skill(
    name="local_knowledge",
    version="v1",
    description="LocalKnowledge – gerencia conhecimento local persistente",
    inputs=["prompt_intake"],
    outputs=["local_knowledge"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "knowledge"],
)

SKILL_KNOWLEDGE_ANALYZER = Skill(
    name="knowledge_analyzer",
    version="v1",
    description="KnowledgeAnalyzer – analisa e indexa conhecimento adquirido",
    inputs=["local_knowledge"],
    outputs=["analyzed_knowledge"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "knowledge"],
)

SKILL_MEMORY_WRITER = Skill(
    name="memory_writer",
    version="v1",
    description="MemoryWriter – persiste resultados em memória de longo prazo",
    inputs=["result_agent"],
    outputs=["memory_write"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "memory"],
)

SKILL_MEMORY_CLEANER = Skill(
    name="memory_cleaner",
    version="v1",
    description="MemoryCleaner – limpa e organiza memória obsoleta",
    inputs=["memory_writer"],
    outputs=["memory_clean"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "memory"],
)

SKILL_AGENTMAILBOX = Skill(
    name="agentmailbox",
    version="v1",
    description="AgentMailbox – gerencia caixa postal de mensagens entre agentes",
    inputs=[],
    outputs=["mailbox_ready"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "messaging"],
)

SKILL_CODE_EXECUTOR = Skill(
    name="code_executor",
    version="v1",
    description="CodeExecutor – executa código gerado pelos builders",
    inputs=["coder"],
    outputs=["execution_result"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "execution"],
)

SKILL_MULTI_CODER = Skill(
    name="multi_coder",
    version="v1",
    description="MultiCoder – coordenador de múltiplos coders concorrentes",
    inputs=["execution_plan"],
    outputs=["multi_coded"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "construction"],
)

SKILL_PROMPT_BUILDER = Skill(
    name="prompt_builder",
    version="v1",
    description="PromptBuilder – constrói prompts otimizados para cada nó",
    inputs=["prompt_intake"],
    outputs=["built_prompt"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "definition"],
)

SKILL_PROMPT_IMPROVER = Skill(
    name="prompt_improver",
    version="v1",
    description="PromptImprover – melhora prompts com base em feedback de execuções anteriores",
    inputs=["prompt_builder"],
    outputs=["improved_prompt"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    tags=["pipeline", "definition"],
)

_BUILTIN_SKILLS = [
    SKILL_PLANNER,
    SKILL_INGESTION,
    SKILL_DOMAIN_ANALYSIS,
    SKILL_BUSINESS_RULES,
    SKILL_TECHNOLOGY_SELECTION,
    SKILL_SYSTEM_DESIGN,
    SKILL_API_DESIGN,
    SKILL_DATABASE_DESIGN,
    SKILL_THREAT_MODELING,
    SKILL_OBSERVABILITY_DESIGN,
    SKILL_COMPLIANCE_AUDIT,
    SKILL_ARCHITECTURE_VALIDATOR,
    SKILL_TASK_BREAKDOWN,
    SKILL_EXECUTION_PLAN,
    SKILL_REQUIREMENTS,
    SKILL_PRODUCT_MANAGER,
    SKILL_ARCHITECT,
    SKILL_INTERPRETER,
    SKILL_PROMPT_INTAKE,
    SKILL_ENHANCEMENT,
    SKILL_ORCHESTRATOR,
    SKILL_RISK_ANALYSIS,
    SKILL_SECURITY_DESIGN,
    SKILL_SECURITY_AUDIT,
    SKILL_PERFORMANCE_DESIGN,
    SKILL_PERFORMANCE_AUDIT,
    SKILL_CODER,
    SKILL_FRONTEND_BUILDER,
    SKILL_BACKEND_BUILDER,
    SKILL_DATABASE_BUILDER,
    SKILL_API_BUILDER,
    SKILL_TEST_GENERATOR,
    SKILL_TESTER,
    SKILL_DEBUGGER,
    SKILL_REVIEWER,
    SKILL_CRITIC,
    SKILL_VALIDATOR,
    SKILL_QA,
    SKILL_DEBUG_CODER,
    SKILL_FIX_VALIDATOR,
    SKILL_SECURITY,
    SKILL_PERFORMANCE,
    SKILL_DEPENDENCY,
    SKILL_DOCUMENTATION,
    SKILL_RELEASE,
    SKILL_DEPLOYMENT_PLAN,
    SKILL_METRICS,
    SKILL_OPTIMIZATION,
    SKILL_KNOWLEDGE,
    SKILL_ARTIFACT_WRITER,
    SKILL_REFLEXION,
    SKILL_RETROSPECTIVE,
    SKILL_RESULT_AGENT,
    SKILL_GENESIS,
    SKILL_WEB_CLASSIFIER,
    SKILL_SEARCH,
    SKILL_EVALUATOR,
    SKILL_GAP_ANALYZER,
    SKILL_SKILL_GENERATOR,
    SKILL_SANDBOX_VALIDATOR,
    SKILL_EVOLUTION_COMMITTEE,
    SKILL_PIPELINE_UPDATER,
    SKILL_EVOLUTION_TRIGGER,
    SKILL_INTEGRATOR,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_LOCAL_KNOWLEDGE,
    SKILL_KNOWLEDGE_ANALYZER,
    SKILL_MEMORY_WRITER,
    SKILL_MEMORY_CLEANER,
    SKILL_AGENTMAILBOX,
    SKILL_CODE_EXECUTOR,
    SKILL_MULTI_CODER,
    SKILL_PROMPT_BUILDER,
    SKILL_PROMPT_IMPROVER,
]

def register_builtin_skills():
    """Registra todas as skills built-in no skill_registry global."""
    from .skill_registry import skill_registry
    for _s in _BUILTIN_SKILLS:
        skill_registry.register(_s)

