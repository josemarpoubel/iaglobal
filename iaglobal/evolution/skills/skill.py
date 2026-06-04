# iaglobal/evolution/skills/skill.py

"""
🎯 Skill — unidade executável + contrato + constraints + identidade

Skill NÃO é prompt. Skill encapsula:
- Um contrato de entrada/saída
- Constraints de execução (algoritmo, segurança)
- Política de execução (single-run, repeatable, etc.)
- Identidade versionada
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from enum import Enum


class ExecutionPolicy(Enum):
    SINGLE_RUN = "single-run"          # Executa uma vez por task
    REPEATABLE = "repeatable"          # Pode executar múltiplas vezes
    ON_DEMAND = "on-demand"            # Executa apenas quando requisitado
    ALWAYS = "always"                  # Executa sempre, mesmo em cache


@dataclass(frozen=True)
class Skill:
    """
    Skill — contrato executável versionado.

    Frozen=True garante imutabilidade: uma vez definida, a skill
    não pode ser alterada (apenas versionada).
    """

    name: str
    description: str = ""

    # Contrato
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    # Constraints
    constraints: List[str] = field(default_factory=list)

    # Política
    execution_policy: ExecutionPolicy = ExecutionPolicy.SINGLE_RUN

    # Execução
    run_fn: Optional[Callable] = None

    # Metadados
    version: str = "v1"
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Skill.name é obrigatório")

    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Verifica se todos os inputs necessários estão disponíveis."""
        for inp in self.inputs:
            if inp not in context:
                return False
        return True

    def validate_output(self, output: Any) -> bool:
        """Valida se a saída atende ao contrato (verificação básica)."""
        return output is not None

    def to_node(
        self,
        depends_on: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        critical: bool = False,
        model_hint: Optional[str] = None,
        name: Optional[str] = None,
    ) -> "Node":
        """
        Cria um Node a partir da Skill.

        O node herda:
        - name: skill.name (ou name se fornecido)
        - run: skill.run_fn
        - node_type: skill.name (identidade determinística)
        - seed_id: skill.name
        - mutation_id: ''
        - version: skill.version
        - strategy: da skill ou do parâmetro
        - critical: policy SINGLE_RUN é crítico por padrão
        - model_hint: opcional

        O parâmetro `name` permite sobrescrever o nome do node
        (útil para compatibilidade com DAG existente).
        """
        from iaglobal.graphs.node import Node

        node_name = name if name is not None else self.name

        return Node(
            name=node_name,
            run=self.run_fn or (lambda ctx: {"output": ""}),
            depends_on=depends_on or [],
            node_type=self.name,       # identidade = skill name
            seed_id=self.name,
            mutation_id="",
            version=self.version,
            strategy=strategy or self.name,
            critical=critical,
            model_hint=model_hint,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "constraints": list(self.constraints),
            "execution_policy": self.execution_policy.value,
            "version": self.version,
            "author": self.author,
            "tags": list(self.tags),
        }


# Skills pré-definidas do sistema
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
    tags=["core", "security"],
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
    tags=["core", "performance"],
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

SKILL_DEPENDENCY = Skill(
    name="dependency",
    description="Gerencia dependências do projeto: seleciona bibliotecas, "
                "verifica compatibilidade e atualiza versões",
    inputs=["code", "path", "requirements"],
    outputs=["requirements", "compatibility_report", "missing_deps"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "dependency"],
)

SKILL_REQUIREMENTS = Skill(
    name="requirements",
    description="Converte intenção em requisitos formais: funcionais, não funcionais "
                "e critérios de aceite",
    inputs=["task", "refined_task"],
    outputs=["rf", "rnf", "acceptance_criteria", "use_cases"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "requirements"],
)

SKILL_PRODUCT_MANAGER = Skill(
    name="pm",
    description="Product Manager — a partir de requisitos estruturados, cria "
                "Epics, Features, Stories e Backlog para o planner",
    inputs=["requirements"],
    outputs=["epics", "features", "stories", "backlog"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "pm", "product_manager"],
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
    description="Corrige código com base em erros",
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
    constraints=["llm"],
    execution_policy=ExecutionPolicy.ALWAYS,
    version="v1",
    tags=["core", "reflection"],
)

SKILL_GENESIS = Skill(
    name="genesis_builder",
    description="Gera bloco genesis para blockchain SHA3-512",
    inputs=["blockchain_name", "author"],
    outputs=["block", "chain"],
    constraints=["sha3_512", "deterministic", "python"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["blockchain", "genesis"],
)

# ==============================================================
# 🎯 Skills da Pipeline V2
# ==============================================================

SKILL_PROMPT_INTAKE = Skill(
    name="prompt_intake",
    description="Primeiro contato com o usuário — extrai domínio, objetivo, "
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
    outputs=["risk_report", "risks"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "risk"],
)

SKILL_RELEASE = Skill(
    name="release",
    description="Gera artefatos de release: CHANGELOG, versionamento, "
                "release notes e deploy plan a partir do código final",
    inputs=["code", "path", "documentation"],
    outputs=["changelog", "version", "release_notes", "deploy_plan"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "release"],
)

SKILL_METRICS = Skill(
    name="metrics",
    description="Agente transversal — observa todos os nós e coleta métricas: "
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

# ==============================================================
# 🏗️ Skills de Infraestrutura
# ==============================================================

SKILL_INTERPRETER = Skill(
    name="interpreter",
    description="Interpreta e melhora o prompt do usuário: corrige gramática (PT/EN), "
                "estrutura a solicitação, e prepara para o pipeline",
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
)

SKILL_STYLE_VALIDATOR = Skill(
    name="style_validator",
    description="Valida e corrige estilo visual do código gerado: "
                "cores, tema escuro, consistência CSS, substitui Django por Flask quando inadequado",
    inputs=["code", "task"],
    outputs=["code"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "style", "validation"],
)

SKILL_SEMANTIC_VALIDATOR = Skill(
    name="semantic_validator",
    description="Valida requisitos semânticos do código gerado",
    inputs=["code", "task"],
    outputs=["semantic_score", "semantic_errors"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "validation"],
)

SKILL_AST_VALIDATOR = Skill(
    name="ast_validator",
    description="Valida sintaxe AST e análise estática do código",
    inputs=["code"],
    outputs=["security_report", "ast_warnings"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "validation"],
)

SKILL_RANK_FINAL = Skill(
    name="rank_final",
    description="Calcula score final multicritério do artefato",
    inputs=["artifact"],
    outputs=["final_score"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "ranking"],
)

SKILL_FINAL_GATEKEEPER = Skill(
    name="final_gatekeeper",
    description="Valida resultado final antes de aceitar",
    inputs=["artifact"],
    outputs=["approved", "final_score"],
    constraints=["deterministic", "security"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["infra", "gatekeeper"],
)

SKILL_ARTIFACT_WRITER = Skill(
    name="artifact_writer",
    description="Persiste o artifact final em disco e retorna caminho do arquivo",
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

# ==============================================================
# 🚀 Skills da Pipeline V3
# ==============================================================

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
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security", "design", "v3"],
)

SKILL_PERFORMANCE_DESIGN = Skill(
    name="performance_design",
    description="Analisa requisitos de performance na fase de design: "
                "escalabilidade, caching, concorrência, limites de recursos, "
                "SLOs e padrões de otimização",
    inputs=["architecture", "requirements"],
    outputs=["performance_design_report", "performance_requirements"],
    constraints=["llm"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "performance", "design", "v3"],
)

SKILL_SECURITY_AUDIT = Skill(
    name="security_audit",
    description="Audita o código gerado contra requisitos de segurança: "
                "verifica implementação de autenticação, sanitização de inputs, "
                "proteção contra SQLi/XSS/SSRF e secrets management",
    inputs=["code", "security_requirements"],
    outputs=["security_audit_report", "security_issues"],
    constraints=["deterministic", "fast"],
    execution_policy=ExecutionPolicy.SINGLE_RUN,
    version="v1",
    tags=["core", "security", "audit", "v3"],
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
    tags=["core", "performance", "audit", "v3"],
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
    tags=["core", "result", "v3"],
)
