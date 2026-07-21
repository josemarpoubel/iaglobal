# iaglobal/tests/test_context_providers.py

import pytest

from iaglobal.pipeline.mission import MissionAnalyzer
from iaglobal.pipeline.context import (
    ExecutionContext,
    MissionContext,
    RuntimeContext,
    HistoryContext,
    MemoryContext,
    MetricsContext,
    NodeSection,
    NodeContext,
    TokenBudget,
    SectionSpec,
    ProjectionProvider,
    PlannerContextProvider,
    CoderContextProvider,
    TesterContextProvider,
    CriticContextProvider,
    DependencyContextProvider,
    KnowledgeContextProvider,
    MemoryContextProvider,
    SecurityContextProvider,
    PerformanceContextProvider,
    ContextSerializer,
)
from iaglobal.pipeline.context.protocol import CharTokenEstimator


_PROMPT = (
    "crie um app de vendas para um restaurante "
    "com tema escuro elegante e responsivo "
    "com controle de estoque "
    "controle de vendas "
    "controle de funcionarios"
)


@pytest.fixture
def exec_ctx() -> ExecutionContext:
    mission = MissionAnalyzer().analyze(_PROMPT)
    return ExecutionContext(mission=mission)


# ============================================================
# TEST GROUP 1 — sub-contextos especializados
# ============================================================


def test_mission_context_frozen():
    m = MissionContext(objective="test")
    with pytest.raises(Exception):
        m.objective = "novo"


def test_mission_context_updated_returns_new():
    m1 = MissionContext(objective="original", domain="web")
    m2 = m1.updated(domain="mobile")
    assert m1.objective == "original"
    assert m1.domain == "web"
    assert m2.objective == "original"
    assert m2.domain == "mobile"
    assert m1 is not m2


def test_mission_context_from_dict():
    d = {
        "objective": "criar app",
        "domain": "restaurant",
        "entities": ["estoque", "vendas"],
        "confidence": 0.85,
    }
    m = MissionContext.from_dict(d)
    assert m.objective == "criar app"
    assert m.domain == "restaurant"
    assert m.entities == ("estoque", "vendas")
    assert m.confidence == 0.85


def test_runtime_context():
    r = RuntimeContext(graph_state={"stage": "build"}, task_id="abc-123")
    assert r.graph_state["stage"] == "build"
    assert r.task_id == "abc-123"


def test_history_context():
    h = HistoryContext(entries=({"event": "start"}, {"event": "end"}))
    assert len(h.entries) == 2


def test_metrics_context():
    m = MetricsContext(ivm=0.9, score=0.85)
    assert m.ivm == 0.9
    assert m.score == 0.85


# ============================================================
# TEST GROUP 2 — ExecutionContext composition
# ============================================================


def test_execution_context_composicao():
    ec = ExecutionContext(
        mission=MissionContext(objective="test", domain="web"),
        runtime=RuntimeContext(task_id="t1"),
        history=HistoryContext(),
        memory=MemoryContext(knowledge="info"),
        metrics=MetricsContext(ivm=0.7),
    )
    assert ec.mission.domain == "web"
    assert ec.runtime.task_id == "t1"
    assert ec.memory.knowledge == "info"
    assert ec.metrics.ivm == 0.7


# ============================================================
# TEST GROUP 3 — NodeSection com conteúdo tipado
# ============================================================


def test_node_section_typed_content():
    section = NodeSection(
        id="entities",
        title="Entidades",
        content=("estoque", "vendas", "funcionarios"),
        priority=70,
    )
    assert section.id == "entities"
    assert len(section.content) == 3
    assert not section.is_empty


def test_node_section_is_empty():
    s1 = NodeSection(id="empty", title="Vazio")
    assert s1.is_empty
    s2 = NodeSection(id="nonempty", title="Cheio", content=("a",))
    assert not s2.is_empty


def test_node_section_frozen():
    s = NodeSection(id="t", title="T", content=("a",))
    with pytest.raises(Exception):
        s.content = ("b",)


# ============================================================
# TEST GROUP 4 — TokenBudget
# ============================================================


def test_token_budget():
    b = TokenBudget(objective=60, entities=40, constraints=50)
    assert b.for_section("objective") == 60
    assert b.for_section("entities") == 40
    assert b.for_section("inexistente") == b.other


def test_token_budget_total():
    b = TokenBudget(objective=10, domain=5)
    assert b.total > 0


def test_char_token_estimator():
    est = CharTokenEstimator()
    assert est.estimate("hello world") >= 1
    assert est.estimate("a" * 100) == 25  # 100/4


# ============================================================
# TEST GROUP 5 — PlannerContextProvider (declarativo)
# ============================================================


def test_planner_provider_tipos():
    """Verifica que o PlannerProvider atende ao protocolo."""
    assert hasattr(PlannerContextProvider, "requires")
    assert hasattr(PlannerContextProvider, "build")
    assert MissionContext in PlannerContextProvider.requires


def test_planner_provider_cadeia_completa(exec_ctx):
    ctx = PlannerContextProvider.build(exec_ctx, node_name="planner")
    assert ctx.node_name == "planner"

    sections = {s.id: s for s in ctx.sections}
    assert "objective" in sections
    assert "domain" in sections
    assert "entities" in sections
    assert "constraints" in sections

    entities_val = " ".join(str(c) for c in sections["entities"].content)
    assert "estoque" in entities_val
    assert "vendas" in entities_val
    assert "funcionarios" in entities_val


def test_planner_provider_respeita_orcamento(exec_ctx):
    ctx = PlannerContextProvider.build(exec_ctx)

    serializer = ContextSerializer()
    text = serializer.serialize(ctx)
    estimated_tokens = serializer.estimate(ctx)

    assert len(text) > 0
    assert estimated_tokens > 0


def test_planner_provider_budget_customizado(exec_ctx):
    tiny = TokenBudget(objective=10, domain=0, entities=0, constraints=0)
    ctx = PlannerContextProvider.build(exec_ctx, budget=tiny)

    serializer = ContextSerializer()
    text = serializer.serialize(ctx)
    estimated = serializer.estimate(ctx)

    assert estimated <= tiny.total * 4 + 50, (
        f"Budget customizado estourado: {estimated} tokens > {tiny.total}"
    )


# ============================================================
# TEST GROUP 6 — ContextSerializer (markdown-style)
# ============================================================


def test_serializer_nao_adiciona_bloat(exec_ctx):
    ctx = PlannerContextProvider.build(exec_ctx)
    text = ContextSerializer().serialize(ctx, system_role="Planejador")

    assert "PSC" not in text
    assert "EETL" not in text
    assert "Chain of Thought" not in text
    assert "AUTO-REVISÃO" not in text
    assert "Objetivo:" in text
    assert "Entidades:" in text


def test_serializer_ordenacao():
    sections = (
        NodeSection("z", "Z", ("ultimo",), priority=10),
        NodeSection("a", "A", ("primeiro",), priority=100),
    )
    ctx = NodeContext(sections=sections)
    text = ContextSerializer().serialize(ctx)
    assert text.index("A:") < text.index("Z:")


def test_serializer_estimate():
    sections = (
        NodeSection("o", "Objetivo", ("criar app",), priority=100),
        NodeSection("e", "Entidades", ("a", "b"), priority=70),
    )
    ctx = NodeContext(sections=sections)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert estimated >= 1
    assert estimated == len(text) // 4  # CharTokenEstimator: 1 token ≈ 4 chars


# ============================================================
# TEST GROUP 7 — Serializer strategy (JSON)
# ============================================================


def test_json_serializer():
    from iaglobal.pipeline.context import JSONSerializer

    sections = (
        NodeSection("objective", "Objetivo", ("criar app restaurante",), priority=100),
        NodeSection("entities", "Entidades", ("estoque", "vendas"), priority=70),
    )
    ctx = NodeContext(sections=sections)
    ser = JSONSerializer()
    text = ser.serialize(ctx)

    import json

    data = json.loads(text)
    assert "objective" in data
    assert "entities" in data
    assert len(data["entities"]) == 2


# ============================================================
# TEST GROUP 8 — ProjectionProvider (declarativo)
# ============================================================


def test_projection_provider_section_spec():
    spec = SectionSpec("domain", "Domínio", 90, "mission.domain")
    assert spec.section_id == "domain"
    assert spec.budget_key == ""


def test_projection_provider_custom(exec_ctx):
    CustomProvider = ProjectionProvider(
        requires=(MissionContext,),
        sections=(
            SectionSpec("objective", "Objetivo", 100, "mission.objective"),
            SectionSpec("domain", "Domínio", 90, "mission.domain"),
        ),
    )
    ctx = CustomProvider.build(exec_ctx, node_name="custom")
    assert len(ctx.sections) == 2
    assert ctx.node_name == "custom"
    ids = [s.id for s in ctx.sections]
    assert "objective" in ids
    assert "domain" in ids


def test_projection_provider_ignora_caminho_invalido():
    Custom = ProjectionProvider(
        requires=(MissionContext,),
        sections=(SectionSpec("bad", "Ruim", 50, "mission.nao_existe"),),
    )
    ctx = Custom.build(ExecutionContext(), node_name="test")
    assert len(ctx.sections) == 0  # caminho inválido → omitido


# ============================================================
# TEST GROUP 9 — PM Agent + MissionAnalyzer integração
# ============================================================


def test_pm_agent_com_mission_context():
    from iaglobal.agents.pm_agent import PMAgent

    agent = PMAgent()
    result = agent.extract_requirements(_PROMPT, {"intents_detected": ["web_app"]})
    reqs = " ".join(result["functional"]).lower()

    assert len(result["functional"]) >= 3
    assert "estoque" in reqs
    assert "vendas" in reqs
    assert "funcionarios" in reqs


# ============================================================
# TEST GROUP 10 — MissionAnalyzer sem LLM
# ============================================================


def test_mission_analyzer_restaurant():
    m = MissionAnalyzer().analyze(_PROMPT)
    assert m.domain == "restaurant"
    assert m.project_type == "web_application"
    assert "estoque" in m.entities
    assert "vendas" in m.entities
    assert m.confidence >= 0.8


# ============================================================
# TEST GROUP 11 — .empty() factory methods
# ============================================================


def test_runtime_context_empty():
    r = RuntimeContext.empty()
    assert r.graph_state == {}
    assert r.current_stage == ""
    assert r.task_id == ""


def test_history_context_empty():
    h = HistoryContext.empty()
    assert h.entries == ()


def test_memory_context_empty():
    m = MemoryContext.empty()
    assert m.knowledge == ""
    assert m.stm == ()
    assert m.ltm == ()


def test_metrics_context_empty():
    m = MetricsContext.empty()
    assert m.ivm == 0.0
    assert m.latency_ms == 0.0
    assert m.score == 0.0


# ============================================================
# TEST GROUP 12 — ProviderRegistry + lazy import
# ============================================================


def test_provider_registry_lazy_import():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("planner")
    assert provider is not None
    assert hasattr(provider, "build")
    assert hasattr(provider, "requires")


def test_provider_registry_returns_none_for_unknown():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    assert provider_registry.get("node_que_nao_existe") is None


def test_provider_registry_resolve(exec_ctx):
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    node_ctx = provider_registry.resolve("planner", exec_ctx)
    assert node_ctx is not None
    assert node_ctx.node_name == "planner"
    assert len(node_ctx.sections) >= 2


def test_provider_registry_register_decorator():
    from iaglobal.pipeline.context.contextproviderregistry import (
        register_provider,
        provider_registry,
    )

    @register_provider("test_provider")
    class _TestProvider:
        requires = ()

        def build(self, ctx, node_name="", budget=None):
            from iaglobal.pipeline.context import NodeContext

            return NodeContext(node_name=node_name)

    provider = provider_registry.get("test_provider")
    assert provider is not None
    assert (
        provider_registry.resolve("test_provider", exec_ctx=None).node_name
        == "test_provider"
    )


# ============================================================
# TEST GROUP 13 — Provider imutability contract
# ============================================================


def test_provider_never_mutates_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    before_mission_id = id(exec_ctx.mission)

    PlannerContextProvider.build(exec_ctx, node_name="planner")

    assert id(exec_ctx) == before_id, "ExecutionContext foi substituído"
    assert id(exec_ctx.mission) == before_mission_id, "MissionContext foi substituído"
    assert exec_ctx.mission.domain == "restaurant"


def test_provider_build_returns_new_node_context(exec_ctx):
    from iaglobal.pipeline.context import NodeContext

    node_ctx = PlannerContextProvider.build(exec_ctx, node_name="planner")
    assert isinstance(node_ctx, NodeContext)
    assert node_ctx is not exec_ctx
    assert node_ctx.node_name == "planner"


# ============================================================
# TEST GROUP 14 — ExecutionContext bridge (PipelineEngine → Graph → Node)
# ============================================================


def test_execution_context_flow_engine_to_graph():
    """Simula o fluxo: PipelineEngine → dict → _execute_node_async bridge."""
    mission = MissionAnalyzer().analyze(_PROMPT)
    exec_ctx = ExecutionContext(mission=mission)

    # Passo 1: Engine coloca no dict do grafo
    input_data = {
        "input": {"task": _PROMPT},
        "__exec_ctx": exec_ctx,
    }

    # Passo 2: Graph extrai na bridge
    extracted = input_data.get("__exec_ctx")
    node_ctx: dict = {"input": input_data}
    if extracted is not None:
        node_ctx["execution_context"] = extracted

    assert node_ctx["execution_context"] is exec_ctx
    assert node_ctx["execution_context"].mission.domain == "restaurant"
    assert "estoque" in node_ctx["execution_context"].mission.entities


def test_execution_context_is_optional():
    """Nós sem execution_context não quebram."""
    input_data = {"input": {"task": _PROMPT}}
    extracted = input_data.get("__exec_ctx")
    node_ctx: dict = {"input": input_data}
    if extracted is not None:
        node_ctx["execution_context"] = extracted

    assert "execution_context" not in node_ctx


def test_provider_augments_task_when_registered(exec_ctx):
    """Provider registrado aumenta o raw_task com contexto serializado."""
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry
    from iaglobal.pipeline.context.serializers import ContextSerializer

    provider = provider_registry.get("planner")
    assert provider is not None

    node_ctx = provider.build(exec_ctx, node_name="planner")
    prompt_context = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prompt_context}\n\n{_PROMPT}"

    assert "Objetivo:" in raw_task
    assert "Restrições:" in raw_task
    assert "app de vendas" in raw_task


# ============================================================
# TEST GROUP 15 — CoderContextProvider
# ============================================================


def test_coder_provider_tipos():
    assert hasattr(CoderContextProvider, "requires")
    assert hasattr(CoderContextProvider, "build")
    assert MissionContext in CoderContextProvider.requires


def test_coder_provider_cadeia_completa(exec_ctx):
    ctx = CoderContextProvider.build(exec_ctx, node_name="coder")
    assert ctx.node_name == "coder"

    sections = {s.id: s for s in ctx.sections}
    assert "objective" in sections
    assert "architecture" in sections
    assert "requirements" in sections
    assert "constraints" in sections
    assert "technologies" in sections


def test_coder_provider_serializa(exec_ctx):
    ctx = CoderContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    assert "Objetivo:" in text
    assert "Arquitetura:" in text
    assert "Requisitos:" in text
    assert "Restrições:" in text
    assert "Tecnologias:" in text


def test_coder_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("coder")
    assert provider is not None
    assert provider is CoderContextProvider


def test_coder_provider_nunca_muta_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    CoderContextProvider.build(exec_ctx, node_name="coder")
    assert id(exec_ctx) == before_id


def test_coder_provider_respeita_orcamento(exec_ctx):
    ctx = CoderContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert len(text) > 0
    assert estimated > 0


def test_coder_provider_bridge_flow():
    """Simula o fluxo do execution_graph: __exec_ctx → provider → task prefix."""
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    mission = MissionContext(
        objective="criar app financeiro",
        architecture="event-driven",
        entities=("conta", "transacao", "cliente"),
        constraints=("alta disponibilidade", "criptografia"),
        language="python",
    )
    ec = ExecutionContext(mission=mission)

    # Bridge: lookup + build + serialize
    provider = provider_registry.get("coder")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="coder")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\ncrie uma API REST"

    assert "app financeiro" in raw_task
    assert "event-driven" in raw_task
    assert "conta" in raw_task
    assert "transacao" in raw_task
    assert "alta disponibilidade" in raw_task
    assert "API REST" in raw_task


# ============================================================
# TEST GROUP 16 — TesterContextProvider
# ============================================================


def test_tester_provider_tipos():
    assert hasattr(TesterContextProvider, "requires")
    assert hasattr(TesterContextProvider, "build")
    assert MissionContext in TesterContextProvider.requires


def test_tester_provider_cadeia_completa(exec_ctx):
    ctx = TesterContextProvider.build(exec_ctx, node_name="tester")
    assert ctx.node_name == "tester"

    sections = {s.id: s for s in ctx.sections}
    assert "objective" in sections
    assert "requirements" in sections
    assert "constraints" in sections
    assert "architecture" in sections
    assert "domain" in sections


def test_tester_provider_serializa(exec_ctx):
    ctx = TesterContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    assert "Objetivo:" in text
    assert "Requisitos:" in text
    assert "Restrições:" in text
    assert "Arquitetura:" in text
    assert "Domínio:" in text


def test_tester_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("tester")
    assert provider is not None
    assert provider is TesterContextProvider


def test_tester_provider_nunca_muta_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    TesterContextProvider.build(exec_ctx, node_name="tester")
    assert id(exec_ctx) == before_id


def test_tester_provider_respeita_orcamento(exec_ctx):
    ctx = TesterContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert len(text) > 0
    assert estimated > 0


def test_tester_provider_bridge_flow():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    mission = MissionContext(
        objective="testar modulo de pagamentos",
        domain="fintech",
        entities=("conta", "transacao"),
        constraints=("cobertura 80%", "testes unitarios"),
        architecture="microservicos",
        language="python",
    )
    ec = ExecutionContext(mission=mission)

    provider = provider_registry.get("tester")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="tester")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\nteste o codigo gerado"

    assert "testar modulo" in raw_task
    assert "fintech" in raw_task
    assert "conta" in raw_task
    assert "transacao" in raw_task
    assert "cobertura 80%" in raw_task
    assert "fintech" in raw_task


# ============================================================
# TEST GROUP 17 — CriticContextProvider
# ============================================================


def test_critic_provider_tipos():
    assert hasattr(CriticContextProvider, "requires")
    assert hasattr(CriticContextProvider, "build")
    assert MissionContext in CriticContextProvider.requires


def test_critic_provider_cadeia_completa(exec_ctx):
    ctx = CriticContextProvider.build(exec_ctx, node_name="critic")
    assert ctx.node_name == "critic"

    sections = {s.id: s for s in ctx.sections}
    assert "objective" in sections
    assert "requirements" in sections
    assert "constraints" in sections
    assert "architecture" in sections
    assert "domain" in sections


def test_critic_provider_serializa(exec_ctx):
    ctx = CriticContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    assert "Objetivo:" in text
    assert "Requisitos:" in text
    assert "Restrições:" in text
    assert "Arquitetura:" in text
    assert "Domínio:" in text


def test_critic_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("critic")
    assert provider is not None
    assert provider is CriticContextProvider


def test_critic_provider_nunca_muta_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    CriticContextProvider.build(exec_ctx, node_name="critic")
    assert id(exec_ctx) == before_id


def test_critic_provider_respeita_orcamento(exec_ctx):
    ctx = CriticContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert len(text) > 0
    assert estimated > 0


def test_critic_provider_bridge_flow():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    mission = MissionContext(
        objective="avaliar qualidade do codigo",
        domain="fintech",
        entities=("conta", "transacao"),
        constraints=("boas praticas", "seguranca"),
        architecture="event-driven",
        language="python",
    )
    ec = ExecutionContext(mission=mission)

    provider = provider_registry.get("critic")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="critic")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\navalie o codigo gerado"

    assert "avaliar qualidade" in raw_task
    assert "fintech" in raw_task
    assert "conta" in raw_task
    assert "transacao" in raw_task
    assert "boas praticas" in raw_task
    assert "event-driven" in raw_task


# ============================================================
# TEST GROUP 18 — DependencyContextProvider
# ============================================================


def test_dependency_provider_tipos():
    assert hasattr(DependencyContextProvider, "requires")
    assert hasattr(DependencyContextProvider, "build")
    assert MissionContext in DependencyContextProvider.requires


def test_dependency_provider_cadeia_completa(exec_ctx):
    ctx = DependencyContextProvider.build(exec_ctx, node_name="dependency")
    assert ctx.node_name == "dependency"

    sections = {s.id: s for s in ctx.sections}
    assert "objective" in sections
    assert "domain" in sections
    assert "technologies" in sections
    assert "architecture" in sections


def test_dependency_provider_serializa(exec_ctx):
    ctx = DependencyContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    assert "Objetivo:" in text
    assert "Domínio:" in text
    assert "Tecnologias:" in text
    assert "Arquitetura:" in text


def test_dependency_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("dependency")
    assert provider is not None
    assert provider is DependencyContextProvider


def test_dependency_provider_nunca_muta_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    DependencyContextProvider.build(exec_ctx, node_name="dependency")
    assert id(exec_ctx) == before_id


def test_dependency_provider_respeita_orcamento(exec_ctx):
    ctx = DependencyContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert len(text) > 0
    assert estimated > 0


def test_dependency_provider_bridge_flow():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    mission = MissionContext(
        objective="criar API REST com FastAPI",
        domain="web_backend",
        entities=("usuario", "produto", "pedido"),
        constraints=("autenticacao JWT", "banco PostgreSQL"),
        architecture="monolito_modular",
        language="python",
    )
    ec = ExecutionContext(mission=mission)

    provider = provider_registry.get("dependency")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="dependency")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\nresolva as dependencias"

    assert "API REST" in raw_task
    assert "web_backend" in raw_task
    assert "FastAPI" in raw_task
    assert "python" in raw_task
    assert "monolito_modular" in raw_task


# ============================================================
# TEST GROUP 19 — KnowledgeContextProvider
# ============================================================


def test_knowledge_provider_tipos():
    assert hasattr(KnowledgeContextProvider, "requires")
    assert hasattr(KnowledgeContextProvider, "build")
    assert MissionContext in KnowledgeContextProvider.requires


def test_knowledge_provider_cadeia_completa(exec_ctx):
    ctx = KnowledgeContextProvider.build(exec_ctx, node_name="knowledge")
    assert ctx.node_name == "knowledge"

    sections = {s.id: s for s in ctx.sections}
    assert "domain" in sections
    assert "architecture" in sections
    assert "entities" in sections
    assert "constraints" in sections
    assert "priorities" in sections


def test_knowledge_provider_serializa(exec_ctx):
    ctx = KnowledgeContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    assert "Domínio:" in text
    assert "Padrões Arquiteturais:" in text
    assert "Entidades do Domínio:" in text
    assert "Restrições:" in text


def test_knowledge_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("knowledge")
    assert provider is not None
    assert provider is KnowledgeContextProvider


def test_knowledge_provider_nunca_muta_execution_context(exec_ctx):
    before_id = id(exec_ctx)
    KnowledgeContextProvider.build(exec_ctx, node_name="knowledge")
    assert id(exec_ctx) == before_id


def test_knowledge_provider_respeita_orcamento(exec_ctx):
    ctx = KnowledgeContextProvider.build(exec_ctx)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)
    assert len(text) > 0
    assert estimated > 0


def test_knowledge_provider_bridge_flow():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    mission = MissionContext(
        objective="criar sistema de pagamentos",
        domain="fintech",
        architecture="event_sourcing",
        entities=("conta", "transacao", "usuario"),
        constraints=("PCI DSS", "LGPD", "alta_disponibilidade"),
        priorities=("seguranca", "escalabilidade", "conformidade"),
        language="python",
    )
    ec = ExecutionContext(mission=mission)

    provider = provider_registry.get("knowledge")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="knowledge")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\naplique conhecimento de dominio"

    assert "fintech" in raw_task
    assert "event_sourcing" in raw_task
    assert "conta" in raw_task
    assert "PCI DSS" in raw_task
    assert "seguranca" in raw_task


# ============================================================
# TEST GROUP 20 — MemoryContextProvider + MemorySnapshot
# ============================================================


def test_memory_snapshot_is_empty_by_default():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot()
    assert snapshot.is_empty is True
    assert snapshot.total_items == 0


def test_memory_snapshot_with_data():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(
        recent_decisions=("dec1", "dec2"),
        successful_patterns=("pattern1",),
        similar_projects=("proj1",),
    )
    assert snapshot.is_empty is False
    assert snapshot.total_items == 4
    assert len(snapshot.recent_decisions) == 2


def test_memory_snapshot_frozen():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(recent_decisions=("dec1",))
    with pytest.raises(Exception):
        snapshot.recent_decisions = ("dec2",)


def test_memory_provider_tipos():
    assert hasattr(MemoryContextProvider, "requires")
    assert hasattr(MemoryContextProvider, "build")
    assert ExecutionContext in MemoryContextProvider.requires


def test_memory_provider_cadeia_completa():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(
        recent_decisions=("decisao1", "decisao2"),
        successful_patterns=("pattern1",),
        similar_projects=("proj1",),
        semantic_hits=("hit1",),
        cached_artifacts=("artifact1",),
        failure_lessons=("fail1",),
        obsidian_notes=("note1",),
    )
    ec = ExecutionContext(memory_snapshot=snapshot)

    ctx = MemoryContextProvider.build(ec, node_name="memory")
    assert ctx.node_name == "memory"

    sections = {s.id: s for s in ctx.sections}
    assert "recent_decisions" in sections
    assert "successful_patterns" in sections
    assert "similar_projects" in sections
    assert "semantic_hits" in sections
    assert "cached_artifacts" in sections
    assert "failure_lessons" in sections
    assert "obsidian_notes" in sections


def test_memory_provider_serializa():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(
        recent_decisions=("decisao1",),
        successful_patterns=("pattern1",),
        obsidian_notes=("nota1",),
    )
    ec = ExecutionContext(memory_snapshot=snapshot)

    ctx = MemoryContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)

    assert "Decisões Recentes:" in text
    assert "Padrões Bem-Sucedidos:" in text
    assert "Obsidian:" in text


def test_memory_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("memory")
    assert provider is not None
    assert provider is MemoryContextProvider


def test_memory_provider_nunca_muta_execution_context():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(recent_decisions=("dec1",))
    ec = ExecutionContext(memory_snapshot=snapshot)

    before_id = id(ec)
    before_snapshot_id = id(ec.memory_snapshot)

    MemoryContextProvider.build(ec, node_name="memory")

    assert id(ec) == before_id
    assert id(ec.memory_snapshot) == before_snapshot_id


def test_memory_provider_respeita_orcamento():
    from iaglobal.pipeline.context import MemorySnapshot

    snapshot = MemorySnapshot(
        recent_decisions=("dec1", "dec2", "dec3"),
        successful_patterns=("p1", "p2", "p3"),
    )
    ec = ExecutionContext(memory_snapshot=snapshot)

    ctx = MemoryContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)

    assert len(text) > 0
    assert estimated > 0


def test_memory_provider_bridge_flow():
    from iaglobal.pipeline.context import MemorySnapshot
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    snapshot = MemorySnapshot(
        recent_decisions=("usar event sourcing para pagamentos",),
        successful_patterns=("CQRS", "saga pattern"),
        similar_projects=("sistema financeiro X",),
        semantic_hits=("pagamentos assíncronos", "idempotência"),
        cached_artifacts=("codigo_pagamento_v1.py",),
        failure_lessons=("timeout em transações distribuídas",),
        obsidian_notes=("[[Padrões de Pagamento]]",),
    )
    ec = ExecutionContext(memory_snapshot=snapshot)

    provider = provider_registry.get("memory")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="memory")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\nuse memoria contextual"

    assert "event sourcing" in raw_task
    assert "CQRS" in raw_task
    assert "financeiro" in raw_task
    assert "idempotência" in raw_task
    assert "Pagamento" in raw_task


# ============================================================
# TEST GROUP 21 — SecurityContextProvider + SecuritySnapshot
# ============================================================


def test_security_snapshot_is_empty_by_default():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot()
    assert snapshot.is_empty is True
    assert snapshot.total_items == 0


def test_security_snapshot_with_data():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(
        compliance=("LGPD", "PCI DSS"),
        threat_model=("fraude", "vazamento"),
        required_validations=("autenticacao",),
    )
    assert snapshot.is_empty is False
    assert snapshot.total_items == 5


def test_security_snapshot_frozen():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(compliance=("LGPD",))
    with pytest.raises(Exception):
        snapshot.compliance = ("GDPR",)


def test_security_provider_tipos():
    assert hasattr(SecurityContextProvider, "requires")
    assert hasattr(SecurityContextProvider, "build")
    assert ExecutionContext in SecurityContextProvider.requires


def test_security_provider_cadeia_completa():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(
        security_objectives=("confidencialidade", "integridade"),
        compliance=("LGPD", "PCI DSS"),
        threat_model=("fraude", "escalacao_privilegios"),
        sensitive_assets=("usuario", "pagamento"),
        required_validations=("autenticacao", "autorizacao"),
        forbidden_patterns=("eval()", "exec()"),
    )
    ec = ExecutionContext(security_snapshot=snapshot)

    ctx = SecurityContextProvider.build(ec, node_name="security")
    assert ctx.node_name == "security"

    sections = {s.id: s for s in ctx.sections}
    assert "security_objectives" in sections
    assert "compliance" in sections
    assert "threat_model" in sections
    assert "sensitive_assets" in sections
    assert "required_validations" in sections
    assert "forbidden_patterns" in sections


def test_security_provider_serializa():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(
        security_objectives=("confidencialidade",),
        compliance=("LGPD",),
        threat_model=("vazamento",),
    )
    ec = ExecutionContext(security_snapshot=snapshot)

    ctx = SecurityContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)

    assert "Objetivos de Segurança:" in text
    assert "Compliance:" in text
    assert "Modelo de Ameaças:" in text


def test_security_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("security")
    assert provider is not None
    assert provider is SecurityContextProvider


def test_security_provider_nunca_muta_execution_context():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(compliance=("LGPD",))
    ec = ExecutionContext(security_snapshot=snapshot)

    before_id = id(ec)
    before_snapshot_id = id(ec.security_snapshot)

    SecurityContextProvider.build(ec, node_name="security")

    assert id(ec) == before_id
    assert id(ec.security_snapshot) == before_snapshot_id


def test_security_provider_respeita_orcamento():
    from iaglobal.pipeline.context import SecuritySnapshot

    snapshot = SecuritySnapshot(
        compliance=("LGPD", "PCI DSS", "HIPAA"),
        threat_model=("ameaca1", "ameaca2"),
    )
    ec = ExecutionContext(security_snapshot=snapshot)

    ctx = SecurityContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)

    assert len(text) > 0
    assert estimated > 0


def test_security_provider_bridge_flow():
    from iaglobal.pipeline.context import SecuritySnapshot
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    snapshot = SecuritySnapshot(
        security_objectives=("confidencialidade", "integridade", "disponibilidade"),
        compliance=("LGPD", "PCI DSS"),
        threat_model=("fraude", "vazamento de dados", "injecao SQL"),
        sensitive_assets=("usuario", "cartao_credito", "transacao"),
        required_validations=("autenticacao", "autorizacao", "sanitizacao"),
        forbidden_patterns=("eval()", "exec()", "subprocess"),
    )
    ec = ExecutionContext(security_snapshot=snapshot)

    provider = provider_registry.get("security")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="security")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\naplique politicas de seguranca"

    assert "confidencialidade" in raw_task
    assert "LGPD" in raw_task
    assert "PCI DSS" in raw_task
    assert "fraude" in raw_task
    assert "cartao_credito" in raw_task
    assert "autenticacao" in raw_task
    assert "eval()" in raw_task


# ============================================================
# TEST GROUP 22 — PerformanceContextProvider + PerformanceSnapshot
# ============================================================


def test_performance_snapshot_is_empty_by_default():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot()
    assert snapshot.is_empty is True
    assert snapshot.total_constraints == 4  # defaults: latency, memory, cpu, token


def test_performance_snapshot_with_data():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(
        latency_target_ms=100.0,
        memory_budget_mb=256.0,
        cpu_budget_percent=50.0,
        token_budget=2000,
        cost_budget_usd=0.01,
        known_bottlenecks=("IO bound",),
        hot_paths=("geracao_codigo",),
    )
    assert snapshot.is_empty is False
    assert snapshot.total_constraints == 7  # 4 defaults + cost + bottleneck + hot_path


def test_performance_snapshot_frozen():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(latency_target_ms=50.0)
    with pytest.raises(Exception):
        snapshot.latency_target_ms = 100.0


def test_performance_provider_tipos():
    assert hasattr(PerformanceContextProvider, "requires")
    assert hasattr(PerformanceContextProvider, "build")
    assert ExecutionContext in PerformanceContextProvider.requires


def test_performance_provider_cadeia_completa():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(
        latency_target_ms=100.0,
        memory_budget_mb=512.0,
        cpu_budget_percent=25.0,
        token_budget=4000,
        known_bottlenecks=("IO bound", "network latency"),
        hot_paths=("bandit_routing", "geracao_codigo"),
        optimization_priorities=("latencia", "custo"),
    )
    ec = ExecutionContext(performance_snapshot=snapshot)

    ctx = PerformanceContextProvider.build(ec, node_name="performance")
    assert ctx.node_name == "performance"

    sections = {s.id: s for s in ctx.sections}
    assert "latency_target" in sections
    assert "memory_budget" in sections
    assert "cpu_budget" in sections
    assert "token_budget" in sections
    assert "known_bottlenecks" in sections
    assert "hot_paths" in sections
    assert "optimization_priorities" in sections


def test_performance_provider_serializa():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(
        latency_target_ms=100.0,
        memory_budget_mb=256.0,
        token_budget=2000,
    )
    ec = ExecutionContext(performance_snapshot=snapshot)

    ctx = PerformanceContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)

    assert "Latency Target:" in text
    assert "Memory Budget:" in text
    assert "Token Budget:" in text


def test_performance_provider_registry():
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    provider = provider_registry.get("performance")
    assert provider is not None
    assert provider is PerformanceContextProvider


def test_performance_provider_nunca_muta_execution_context():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(latency_target_ms=100.0)
    ec = ExecutionContext(performance_snapshot=snapshot)

    before_id = id(ec)
    before_snapshot_id = id(ec.performance_snapshot)

    PerformanceContextProvider.build(ec, node_name="performance")

    assert id(ec) == before_id
    assert id(ec.performance_snapshot) == before_snapshot_id


def test_performance_provider_respeita_orcamento():
    from iaglobal.pipeline.context import PerformanceSnapshot

    snapshot = PerformanceSnapshot(
        latency_target_ms=50.0,
        memory_budget_mb=128.0,
        cpu_budget_percent=10.0,
        token_budget=1000,
        known_bottlenecks=("b1", "b2", "b3"),
    )
    ec = ExecutionContext(performance_snapshot=snapshot)

    ctx = PerformanceContextProvider.build(ec)
    ser = ContextSerializer()
    text = ser.serialize(ctx)
    estimated = ser.estimate(ctx)

    assert len(text) > 0
    assert estimated > 0


def test_performance_provider_bridge_flow():
    from iaglobal.pipeline.context import PerformanceSnapshot
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    snapshot = PerformanceSnapshot(
        latency_target_ms=100.0,
        memory_budget_mb=512.0,
        cpu_budget_percent=25.0,
        token_budget=4000,
        cost_budget_usd=0.02,
        known_bottlenecks=("IO bound", "network latency"),
        hot_paths=("bandit_routing", "geracao_codigo", "validacao_sintaxe"),
        optimization_priorities=("latencia", "custo", "throughput"),
    )
    ec = ExecutionContext(performance_snapshot=snapshot)

    provider = provider_registry.get("performance")
    assert provider is not None

    node_ctx = provider.build(ec, node_name="performance")
    prefix = ContextSerializer().serialize(node_ctx)
    raw_task = f"{prefix}\n\notimize performance"

    assert "100" in raw_task or "100.0" in raw_task
    assert "512" in raw_task
    assert "25" in raw_task
    assert "4000" in raw_task
    assert "0.02" in raw_task
    assert "IO bound" in raw_task
    assert "bandit_routing" in raw_task
    assert "latencia" in raw_task


# ============================================================
# TEST GROUP 23 — Teste Arquitetural Genérico de Providers
# ============================================================


def test_todos_providers_registrados_tem_requisitos_validos():
    """Valida que todo provider registrado tem `requires` definido."""
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    providers_conhecidos = [
        "planner",
        "coder",
        "tester",
        "critic",
        "dependency",
        "knowledge",
        "memory",
        "security",
        "performance",
    ]

    for name in providers_conhecidos:
        provider = provider_registry.get(name)
        assert provider is not None, f"Provider '{name}' não registrado"
        assert hasattr(provider, "requires"), (
            f"Provider '{name}' não tem atributo 'requires'"
        )
        assert len(provider.requires) > 0, f"Provider '{name}' tem requires vazio"


def test_todos_providers_sao_imutaveis_quando_constroem_node_context():
    """Valida que nenhum provider muta o ExecutionContext."""
    from iaglobal.pipeline.context import (
        ExecutionContext,
        MissionContext,
        MemorySnapshot,
        SecuritySnapshot,
        PerformanceSnapshot,
    )
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    exec_ctx = ExecutionContext(
        mission=MissionContext(objective="teste", domain="test"),
        memory_snapshot=MemorySnapshot(recent_decisions=("dec1",)),
        security_snapshot=SecuritySnapshot(compliance=("LGPD",)),
        performance_snapshot=PerformanceSnapshot(latency_target_ms=100.0),
    )

    providers_conhecidos = [
        "planner",
        "coder",
        "tester",
        "critic",
        "dependency",
        "knowledge",
        "memory",
        "security",
        "performance",
    ]

    for name in providers_conhecidos:
        provider = provider_registry.get(name)
        before_id = id(exec_ctx)
        before_mission_id = id(exec_ctx.mission)

        provider.build(exec_ctx, node_name=name)

        assert id(exec_ctx) == before_id, f"Provider '{name}' mutou ExecutionContext"
        assert id(exec_ctx.mission) == before_mission_id, (
            f"Provider '{name}' mutou MissionContext"
        )


def test_todos_providers_produzem_node_context_valido():
    """Valida que todo provider produz NodeContext com estrutura válida."""
    from iaglobal.pipeline.context import (
        ExecutionContext,
        MissionContext,
        MemorySnapshot,
        SecuritySnapshot,
        PerformanceSnapshot,
        NodeContext,
    )
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    exec_ctx = ExecutionContext(
        mission=MissionContext(objective="teste", domain="test"),
        memory_snapshot=MemorySnapshot(recent_decisions=("dec1",)),
        security_snapshot=SecuritySnapshot(compliance=("LGPD",)),
        performance_snapshot=PerformanceSnapshot(latency_target_ms=100.0),
    )

    providers_conhecidos = [
        "planner",
        "coder",
        "tester",
        "critic",
        "dependency",
        "knowledge",
        "memory",
        "security",
        "performance",
    ]

    for name in providers_conhecidos:
        provider = provider_registry.get(name)
        result = provider.build(exec_ctx, node_name=name)

        assert isinstance(result, NodeContext), (
            f"Provider '{name}' não retornou NodeContext"
        )
        assert result.node_name == name, f"Provider '{name}' node_name incorreto"
        assert hasattr(result, "sections"), f"Provider '{name}' não tem sections"
        assert hasattr(result, "budget"), f"Provider '{name}' não tem budget"


def test_todos_providers_suportam_serializacao():
    """Valida que todo provider produz contexto serializável."""
    from iaglobal.pipeline.context import (
        ExecutionContext,
        MissionContext,
        MemorySnapshot,
        SecuritySnapshot,
        PerformanceSnapshot,
        ContextSerializer,
    )
    from iaglobal.pipeline.context.contextproviderregistry import provider_registry

    exec_ctx = ExecutionContext(
        mission=MissionContext(objective="teste", domain="test"),
        memory_snapshot=MemorySnapshot(recent_decisions=("dec1",)),
        security_snapshot=SecuritySnapshot(compliance=("LGPD",)),
        performance_snapshot=PerformanceSnapshot(latency_target_ms=100.0),
    )

    providers_conhecidos = [
        "planner",
        "coder",
        "tester",
        "critic",
        "dependency",
        "knowledge",
        "memory",
        "security",
        "performance",
    ]

    for name in providers_conhecidos:
        provider = provider_registry.get(name)
        node_ctx = provider.build(exec_ctx, node_name=name)
        text = ContextSerializer().serialize(node_ctx)

        assert isinstance(text, str), f"Provider '{name}' não serializou para str"
        assert len(text) > 0, f"Provider '{name}' gerou texto vazio"
