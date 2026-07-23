# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de distribuição dos papéis cognitivos (Juiz, Operário, Sentinela).

Garante que os 3 modelos Ollama locais estão configurados e roteados
corretamente, e que nenhum path hardcoded quebra a distribuição.
"""

import os
import pytest

from iaglobal.providers.provider_config import (
    CognitiveRole,
    COGNITIVE_MODELS,
    get_model_config,
    get_all_active_models,
)
from iaglobal.providers.provider_router import (
    CognitiveRouter,
    GLM4_MODEL_ID,
    LFM_MODEL_ID,
    QWEN_MODEL_ID,
)
from iaglobal.agents.agent_base import AgentBase


# ── 1. COGNITIVE_MODELS ──────────────────────────────────────────────────────

EXPECTED_ROLES = {
    CognitiveRole.JUIZ: {
        "model_id": "yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest",
        "node_example": "critic",
    },
    CognitiveRole.OPERARIO: {
        "model_id": "qwen2.5:0.5b",
        "node_example": "coder",
    },
    CognitiveRole.SENTINELA: {
        "model_id": "oamazonasgabriel/lfm2.5-230m:bf16-8gbRAM",
        "node_example": "sandbox_validator",
    },
}


def test_all_cognitive_roles_present():
    """Os 3 papéis cognitivos devem estar definidos."""
    assert CognitiveRole.JUIZ in COGNITIVE_MODELS
    assert CognitiveRole.OPERARIO in COGNITIVE_MODELS
    assert CognitiveRole.SENTINELA in COGNITIVE_MODELS


def test_each_role_has_required_fields():
    """Cada papel deve ter os campos obrigatórios de configuração."""
    required = {"model_id", "type", "max_concurrent_requests", "timeout_seconds"}
    for role, config in COGNITIVE_MODELS.items():
        missing = required - set(config.keys())
        assert not missing, f"{role} missing fields: {missing}"


def test_each_role_has_correct_model_id():
    """Os model_ids devem corresponder aos esperados."""
    for role, expected in EXPECTED_ROLES.items():
        cfg = get_model_config(role)
        assert cfg is not None, f"{role} not found in COGNITIVE_MODELS"
        assert cfg["model_id"] == expected["model_id"], (
            f"{role}: esperado {expected['model_id']}, obtido {cfg['model_id']}"
        )
        assert cfg["type"] == "ollama", f"{role} deve ser ollama"


def test_all_active_models_returns_three():
    """get_all_active_models() deve retornar exatamente 3 modelos."""
    models = get_all_active_models()
    assert len(models) == 3
    for role, expected in EXPECTED_ROLES.items():
        assert expected["model_id"] in models, (
            f"{expected['model_id']} ausente em get_all_active_models()"
        )


# ── 2. COGNITIVE ROUTER ──────────────────────────────────────────────────────


def test_router_has_three_routes():
    """ROUTE_TO_MODEL deve conter as 3 rotas cognitivas."""
    assert "ollama" in CognitiveRouter.ROUTE_TO_MODEL
    assert "ollama_glm4" in CognitiveRouter.ROUTE_TO_MODEL
    assert "ollama_lfm" in CognitiveRouter.ROUTE_TO_MODEL


def test_router_resolves_model_ids():
    """Cada rota deve resolver para o model_id correto."""
    assert CognitiveRouter.resolve_model_id("ollama") == QWEN_MODEL_ID
    assert CognitiveRouter.resolve_model_id("ollama_glm4") == GLM4_MODEL_ID
    assert CognitiveRouter.resolve_model_id("ollama_lfm") == LFM_MODEL_ID


def test_glm4_model_id_matches_juiz():
    assert GLM4_MODEL_ID == get_model_config(CognitiveRole.JUIZ)["model_id"]


def test_lfm_model_id_matches_sentinela():
    assert LFM_MODEL_ID == get_model_config(CognitiveRole.SENTINELA)["model_id"]


def test_qwen_model_id_matches_operario():
    assert QWEN_MODEL_ID == get_model_config(CognitiveRole.OPERARIO)["model_id"]


def test_router_route_map_has_juiz_nodes():
    """Nós críticos devem rotear para ollama_glm4 (Juiz)."""
    for node in ["critic", "failure_analysis", "system_design"]:
        route = CognitiveRouter.resolve_route(node)
        assert route == "ollama_glm4", (
            f"{node} deveria rotear para ollama_glm4, roteou para {route}"
        )


def test_router_route_map_has_operario_nodes():
    """Nós de geração devem rotear para ollama (Operário)."""
    for node in [
        "coder",
        "planner",
        "frontend_builder",
        "backend_builder",
        "api_builder",
        "database_builder",
        "multi_coder",
    ]:
        route = CognitiveRouter.resolve_route(node)
        assert route == "ollama", (
            f"{node} deveria rotear para ollama, roteou para {route}"
        )


def test_router_route_map_has_sentinela_nodes():
    """Nós de validação devem rotear para ollama_lfm (Sentinela)."""
    for node in [
        "sandbox_validator",
        "lsp_validator",
        "semantic_validator",
        "fix_validator",
        "security_audit",
        "performance_audit",
        "compliance_audit",
        "evaluator",
    ]:
        route = CognitiveRouter.resolve_route(node)
        assert route == "ollama_lfm", (
            f"{node} deveria rotear para ollama_lfm, roteou para {route}"
        )


def test_router_unknown_node_falls_to_ollama():
    """Nós não mapeados devem cair no Operário (ollama)."""
    route = CognitiveRouter.resolve_route("unknown_random_node")
    assert route == "ollama"


def test_router_validation_heuristic():
    """Task_type 'validation'/'audit' deve rotear para Sentinela."""
    route = CognitiveRouter.resolve_route("some_node", task_type="code_audit")
    assert route == "ollama_lfm"


def test_router_get_route_config_returns_config():
    """get_route_config deve retornar a config do CognitiveRole correto."""
    juiz_config = CognitiveRouter.get_route_config("ollama_glm4")
    assert juiz_config is not None
    assert juiz_config["model_id"] == GLM4_MODEL_ID

    operario_config = CognitiveRouter.get_route_config("ollama")
    assert operario_config is not None
    assert operario_config["model_id"] == QWEN_MODEL_ID

    sentinela_config = CognitiveRouter.get_route_config("ollama_lfm")
    assert sentinela_config is not None
    assert sentinela_config["model_id"] == LFM_MODEL_ID


# ── 3. AGENTBASE DEFAULT CANDIDATES ──────────────────────────────────────────


def test_default_candidates_contains_all_three_ollama_models():
    """AgentBase.DEFAULT_CANDIDATES deve incluir os 3 modelos Ollama."""
    candidates = AgentBase.DEFAULT_CANDIDATES
    for role, expected in EXPECTED_ROLES.items():
        model_uri = f"ollama/{expected['model_id']}"
        assert model_uri in candidates, (
            f"{model_uri} ausente em AgentBase.DEFAULT_CANDIDATES"
        )


def test_default_candidates_no_hardcoded_duplicates():
    """AgentBase.DEFAULT_CANDIDATES não deve ter entradas duplicadas."""
    candidates = AgentBase.DEFAULT_CANDIDATES
    assert len(candidates) == len(set(candidates)), (
        f"Candidatos duplicados: {candidates}"
    )


# ── 4. PROVIDER ROUTER — OLLAMA_ONLY PATH ────────────────────────────────────


@pytest.mark.asyncio
async def test_ollama_only_respects_model_param(monkeypatch):
    """Quando OLLAMA_ONLY=true, async_route_generate deve usar o model
    passado, não hardcodar qwen2.5:0.5b."""
    monkeypatch.setenv("OLLAMA_ONLY", "true")
    import iaglobal.providers.provider_router as pr

    captured = []

    async def fake_safe_call(provider, func, prompt, model, task_type, **kw):
        captured.append(model)
        return "fake response"

    async def fake_enrich(p, t):
        return p

    monkeypatch.setattr(pr, "_async_safe_call", fake_safe_call)
    monkeypatch.setattr(pr, "_enrich_prompt_with_learned_knowledge", fake_enrich)

    result = await pr.async_route_generate(
        model="ollama/yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest",
        prompt="test",
        node_id="critic",
    )
    assert result == "fake response"
    assert len(captured) == 1
    assert "GLM4" in captured[0], f"Esperava GLM4 no model, obtido: {captured[0]}"


@pytest.mark.asyncio
async def test_ollama_only_fallback_to_qwen_when_model_empty(monkeypatch):
    """Quando OLLAMA_ONLY=true e model='', deve cair para qwen2.5:0.5b."""
    monkeypatch.setenv("OLLAMA_ONLY", "true")
    import iaglobal.providers.provider_router as pr

    captured = []

    async def fake_safe_call(provider, func, prompt, model, task_type, **kw):
        captured.append(model)
        return "fake response"

    async def fake_enrich(p, t):
        return p

    monkeypatch.setattr(pr, "_async_safe_call", fake_safe_call)
    monkeypatch.setattr(pr, "_enrich_prompt_with_learned_knowledge", fake_enrich)

    result = await pr.async_route_generate(model="", prompt="test", node_id="some_node")
    assert result == "fake response"
    assert len(captured) == 1
    assert "qwen2.5" in captured[0], (
        f"Esperava qwen2.5 como fallback, obtido: {captured[0]}"
    )


# ── 5. MEMBRANE REDIRECT PATH ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_psc_redirects_non_ollama_to_ollama_preserving_model(monkeypatch):
    """PSC deve redirecionar modelo cloud para ollama preservando o
    model_id (ex: groq/llama → ollama/llama)."""
    monkeypatch.setenv("OLLAMA_ONLY", "false")
    import iaglobal.providers.provider_router as pr

    captured = []

    async def fake_safe_call(provider, func, prompt, model, task_type, **kw):
        captured.append(model)
        return "fake response"

    async def fake_enrich(p, t):
        return p

    monkeypatch.setattr(pr, "_async_safe_call", fake_safe_call)
    monkeypatch.setattr(pr, "_enrich_prompt_with_learned_knowledge", fake_enrich)

    result = await pr.async_route_generate(
        model="groq/llama-3.3-70b-versatile",
        prompt="test",
        node_id="coder",
    )
    assert result == "fake response"
    assert len(captured) == 1
    # PSC reescreveu: groq/llama-3.3-70b-versatile → ollama/llama-3.3-70b-versatile
    assert captured[0].startswith("ollama/"), (
        f"PSC deveria prefixar ollama/, obtido: {captured[0]}"
    )
    assert "llama-3.3" in captured[0], (
        f"Deveria preservar o model_id, obtido: {captured[0]}"
    )


# ── 6. INTEGRITY: NO HARDCODED qwen2.5:0.5b IN CRITICAL PATHS ───────────────


@pytest.mark.asyncio
async def test_async_route_generate_no_hardcoded_strings(monkeypatch):
    """Verifica se async_route_generate usa o parâmetro model em vez de
    string literal 'qwen2.5:0.5b'."""
    monkeypatch.setenv("OLLAMA_ONLY", "false")
    import iaglobal.providers.provider_router as pr

    captured = []

    async def fake_safe_call(provider, func, prompt, model, task_type, **kw):
        captured.append(model)
        return "fake"

    monkeypatch.setattr(pr, "_async_safe_call", fake_safe_call)
    monkeypatch.setattr(
        pr,
        "_async_fallback_chain",
        lambda prompt, exclude=None, task_type="general", node_id="": "fake fallback",
    )

    result = await pr.async_route_generate(
        model="ollama/oamazonasgabriel/lfm2.5-230m:bf16-8gbRAM",
        prompt="test",
        node_id="sandbox_validator",
    )
    assert result
    assert captured and "lfm2.5" in captured[0].lower(), (
        f"Esperava lfm2.5 no model, obtido: {captured}"
    )


# ── 7. CRITIC AGENT DEFAULT CANDIDATES ───────────────────────────────────────


def test_critic_agent_inherits_default_candidates():
    """CriticAgent (que estende AgentBase) deve herdar DEFAULT_CANDIDATES
    com os 3 modelos."""
    from iaglobal.agents.critic_agent import CriticAgent

    candidates = getattr(CriticAgent, "DEFAULT_CANDIDATES", None)
    assert candidates is not None, "CriticAgent não tem DEFAULT_CANDIDATES"
    for role, expected in EXPECTED_ROLES.items():
        model_uri = f"ollama/{expected['model_id']}"
        assert model_uri in candidates, (
            f"{model_uri} ausente em CriticAgent.DEFAULT_CANDIDATES"
        )


# ── 8. SEMAPHORE CONCURRENCY PER ROLE ────────────────────────────────────────


def test_model_semaphore_concurrency_matches_provider_config():
    """_resolve_local_concurrency deve retornar max_concurrent_requests
    do provider_config.py para cada papel cognitivo."""
    from iaglobal.graphs.bandit import BanditPolicy

    bp = BanditPolicy()

    for role, expected in EXPECTED_ROLES.items():
        cfg = get_model_config(role)
        expected_concurrency = cfg["max_concurrent_requests"]
        model_uri = f"ollama/{expected['model_id']}"
        actual = bp._resolve_local_concurrency(model_uri)
        assert actual == expected_concurrency, (
            f"{role} ({expected['model_id']}): "
            f"esperado concurrency={expected_concurrency}, "
            f"obtido {actual}"
        )


def test_semaphore_created_with_correct_concurrency():
    """O semáforo criado para cada modelo deve usar a concorrência
    definida em provider_config.py."""
    import asyncio
    from iaglobal.graphs.bandit import BanditPolicy

    # Limpa semáforos compartilhados para teste
    for role, expected in EXPECTED_ROLES.items():
        BanditPolicy.MODEL_SEMAPHORES.clear()
        bp = BanditPolicy()
        model_uri = f"ollama/{expected['model_id']}"
        sem = asyncio.run(bp._get_model_semaphore(model_uri))
        cfg = get_model_config(role)
        # Semaphore._value é o valor inicial (concorrência máxima)
        assert sem._value == cfg["max_concurrent_requests"], (
            f"{role}: esperado semaphore={cfg['max_concurrent_requests']}, "
            f"obtido {sem._value}"
        )


def test_ollama_provider_no_dead_semaphores():
    """ollama_provider.py não deve conter os semáforos mortos
    _OLLAMA_CPU_LOCK e _ollama_semaphore."""
    import iaglobal.providers.ollama_provider as op

    assert not hasattr(op, "_OLLAMA_CPU_LOCK"), (
        "_OLLAMA_CPU_LOCK morto ainda existe em ollama_provider.py"
    )
    assert not hasattr(op, "OLLAMA_CPU_LOCK"), (
        "OLLAMA_CPU_LOCK morto ainda existe em ollama_provider.py"
    )
    assert not hasattr(op, "_ollama_semaphore"), (
        "_ollama_semaphore morto ainda existe em ollama_provider.py"
    )


# ── 9. STARVATION TRACKING ──────────────────────────────────────────────────


def test_semaphore_tracker_starvation_increments_counter():
    """record_starvation deve incrementar o contador de starvations."""
    from iaglobal.observability.semaphore_tracker import SemaphoreTracker

    st = SemaphoreTracker()
    st.record_starvation(
        node_id="test",
        candidates=["ollama/qwen2.5:0.5b"],
        retry_rounds=3,
    )
    mm = st.get_metrics("ollama/qwen2.5:0.5b")
    assert mm.starvations == 1, f"Esperado 1 starvation, obtido {mm.starvations}"


def test_semaphore_tracker_health_report_includes_starvations():
    """health_report deve incluir o campo starvations."""
    from iaglobal.observability.semaphore_tracker import SemaphoreTracker

    st = SemaphoreTracker()
    st.record_starvation(
        node_id="test",
        candidates=["ollama/qwen2.5:0.5b"],
        retry_rounds=3,
    )
    report = st.health_report()
    assert "ollama/qwen2.5:0.5b" in report
    assert "starvations" in report["ollama/qwen2.5:0.5b"], (
        "health_report deve incluir 'starvations'"
    )
    assert report["ollama/qwen2.5:0.5b"]["starvations"] == 1
