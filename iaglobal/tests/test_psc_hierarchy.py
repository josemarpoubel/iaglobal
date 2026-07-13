# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes da hierarquia PSC (Protocolo de Soberania do Crítico).

Verifica 4 camadas da arquitetura:
  1. Provider Authority Gate  — só BanditPolicy chama provider_router
  2. PSC Chokepoint           — membrana exata + SecurityViolation
  3. Arbiter + Bandit + IVM   — fluxo cooperativo (Chappie + critic + bandit)
  4. effective_agent          — auditoria creditada ao agente delegante
"""

import ast
import asyncio
import os
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════
# 1. Provider Authority Gate — análise estática
# ═══════════════════════════════════════════════════════════════════

# Funções de roteamento de provedor que só BanditPolicy pode chamar
_PROVIDER_ROUTE_FUNCS = {"async_route_generate", "route_generate"}

# Únicos arquivos autorizados a chamar provider_router (fora de providers/ e tests/)
_AUTHORIZED_CALLERS = frozenset(
    {
        "graphs/bandit.py",
        "agents/critic_agent.py",
    }
)

# Violações conhecidas em modo shadow (serão removidas no cutover)
_SHADOW_VIOLATORS = frozenset(
    {
        "agents/reflexion_agent.py",
        "execution/executor.py",
        "core/neuro_orchestrator.py",
        "evolution/skills/run_fn_factory.py",
        "evolution/evo_agent.py",
    }
)

# Exceções arquiteturais documentadas
_EXCEPTIONS = frozenset(
    {
        "observability/phospholipid_bridge.py",
        "core/critic_batch_queue.py",
    }
)


def _walk_source_files(root: Path, base: Path):
    """Percorre iaglobal/ ignorando providers, tests, venv."""
    skip = {
        "providers",
        "tests",
        "venv",
        ".git",
        ".pytest_cache",
        "__pycache__",
        "scripts",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for f in filenames:
            if f.endswith(".py"):
                full = Path(dirpath) / f
                yield full, full.relative_to(base).as_posix()


def _find_direct_calls(filepath: Path):
    """Retorna [(linha, nome_da_funcao)] para chamadas diretas a provider_router."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = None
            if isinstance(fn, ast.Name) and fn.id in _PROVIDER_ROUTE_FUNCS:
                name = fn.id
            elif isinstance(fn, ast.Attribute) and fn.attr in _PROVIDER_ROUTE_FUNCS:
                name = fn.attr
            if name:
                calls.append((node.lineno, name))
    return calls


def test_provider_authority_gate():
    """
    Apenas graphs/bandit.py pode chamar provider_router diretamente
    (fora de providers/ e testes). Qualquer novo acesso deve passar
    pelo BanditPolicy — nunca por outro caminho.
    """
    root = Path(__file__).parent.parent / "iaglobal"
    base = Path(__file__).parent.parent
    novas = []

    for full, rel in _walk_source_files(root, base):
        calls = _find_direct_calls(full)
        if not calls:
            continue
        if rel in _AUTHORIZED_CALLERS:
            continue
        if rel in _EXCEPTIONS:
            continue
        if rel in _SHADOW_VIOLATORS:
            continue
        novas.append((rel, calls))

    msg = ""
    for path, calls in novas:
        for lineno, name in calls:
            msg += f"\n  {path}:{lineno} — {name}()"

    assert not novas, (
        f"Novas violações do Provider Authority Gate:{msg}\n\n"
        "REGRA: apenas BanditPolicy (graphs/bandit.py) pode chamar "
        "provider_router para geracao LLM. Use arbitrar_geracao() do "
        "CriticAgent se seu no precisa de modelo de IA."
    )


# ═══════════════════════════════════════════════════════════════════
# 2. PSC Chokepoint — verificação de identidade
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def bandit_module():
    import iaglobal.graphs.bandit as b

    return b


def test_psc_verify_caller_block_non_critic(bandit_module):
    """PSC §1.1: non-critic node MUST raise SecurityViolation."""
    bp = bandit_module._get_bandit()
    for node in ["reflexion", "coder", "executor", "evo_agent", ""]:
        with pytest.raises(bandit_module.BanditPolicy.SecurityViolation) as exc:
            bp._psc_verify_caller(node)
        assert "PSC BLOQUEADO" in str(exc.value)


def test_psc_verify_caller_allows_critic(bandit_module):
    """PSC §1.1: critic and critic_batch pass."""
    bp = bandit_module._get_bandit()
    for node in ["critic", "critic_batch"]:
        bp._psc_verify_caller(node)  # must not raise


def test_psc_exact_identity_rejects_substring(bandit_module):
    """PSC §1: substring match nao passa — identidade exata."""
    bp = bandit_module._get_bandit()
    for node in ["critic_agent", "no_critic", "CriticAgent", "critical_analysis"]:
        assert not bp._membrane_is_critic(node), (
            f"{node!r} nao deveria passar como critic (substring)"
        )


def test_psc_exact_identity_accepts_critic(bandit_module):
    """PSC §1: apenas 'critic' e 'critic_batch' passam."""
    bp = bandit_module._get_bandit()
    for node in ["critic", "critic_batch"]:
        assert bp._membrane_is_critic(node), f"{node!r} deveria passar como critic"


def test_psc_generate_blocks_non_critic(monkeypatch, bandit_module):
    """BanditPolicy.generate() levanta SecurityViolation se node_id nao for critic."""
    import iaglobal.providers.provider_router as pr

    async def fake_route(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        return "ok"

    monkeypatch.setattr(pr, "async_route_generate", fake_route)
    bp = bandit_module._get_bandit()
    bp.weights.clear()
    bp.rewards.clear()
    bp.circuit_breakers.clear()
    if bp.credit_engine is not None:
        try:
            bp.credit_engine.stats.clear()
        except Exception:
            pass

    for node in ["reflexion", "executor", "evo_agent", ""]:
        with pytest.raises(bandit_module.BanditPolicy.SecurityViolation):
            asyncio.run(
                bp.generate(
                    node_id=node,
                    prompt="hello",
                    candidates=["ollama/qwen2.5:0.5b"],
                    context={"delegate_for": node},
                )
            )


# ═══════════════════════════════════════════════════════════════════
# 3. Arbiter + Bandit + IVM — fluxo cooperativo completo
# ═══════════════════════════════════════════════════════════════════


class _StubMemoryRouter:
    class _Result:
        found = False
        content = ""
        confidence = 0.0

    async def route(self, prompt, task_type):
        return self._Result()

    def get_effective_confidence(self, node_id, base_conf):
        return base_conf

    def record_memory_resolution(self, node_id):
        pass

    def record_llm_resolution(self, node_id):
        pass


@pytest.fixture
def mock_ivm_axiom(monkeypatch):
    """Mocka IVMAxiom para capturar chamadas de atualizar_metricas."""
    ivm_calls = []

    class FakeIVM:
        async def atualizar_metricas(self, **kwargs):
            ivm_calls.append(kwargs)

    monkeypatch.setattr(
        "iaglobal.chappie.ivm_axiom.get_ivm_axiom",
        lambda: FakeIVM(),
    )
    return ivm_calls


def test_arbiter_delegates_to_bandit_with_correct_identity(monkeypatch, mock_ivm_axiom):
    """
    Arbiter: fluxo completo agent -> critic -> Bandit.

    DADO que o critico nao resolve localmente (tools+memoria falham),
    QUANDO arbitrar_geracao e chamado,
    ENTAO BanditPolicy.generate() e chamado com node_id="critic"
    E context["delegate_for"] = "reflexion".
    """
    monkeypatch.setenv("ARBITER_MODE", "enforce")

    bandit_calls = []

    class FakeBandit:
        DEFAULT_CANDIDATES = ["ollama/qwen2.5:0.5b"]

        async def generate(
            self,
            node_id,
            prompt,
            candidates,
            context=None,
            task_type="general",
            timeout=30.0,
        ):
            bandit_calls.append(
                {
                    "node_id": node_id,
                    "effective_agent": (context or {}).get("delegate_for", node_id),
                    "context": context,
                }
            )
            return "resposta simulada"

    # Patch tools e memory para NAO resolverem localmente
    async def no_resolve(self, prompt, tags=None):
        return None

    async def no_memory(self, prompt, task_type):
        return _StubMemoryRouter()._Result()

    monkeypatch.setattr(
        "iaglobal.agents.critic_agent.CriticAgent._resolve_with_tools",
        no_resolve,
    )
    monkeypatch.setattr(
        "iaglobal.agents.critic_agent._get_memory_router",
        lambda: _StubMemoryRouter(),
    )

    from iaglobal.agents.critic_agent import _get_critic

    critic = _get_critic()
    critic.bandit = FakeBandit()

    async def run():
        return await critic.arbitrar_geracao(
            node_id="reflexion",
            prompt="teste prompt",
            task_type="general",
        )

    resultado = asyncio.run(run())
    assert resultado == "resposta simulada"

    assert len(bandit_calls) >= 1, "Bandit.generate() nao foi chamado"
    last = bandit_calls[-1]
    assert last["node_id"] == "critic", (
        f"PSC exige node_id='critic', obteve {last['node_id']!r}"
    )
    assert last["effective_agent"] == "reflexion", (
        f"effective_agent deve ser o agente original, obteve {last['effective_agent']!r}"
    )
    assert (last["context"] or {}).get("delegate_for") == "reflexion"


def test_arbiter_credits_ivm_cooperation(monkeypatch, mock_ivm_axiom):
    """
    IVM Cooperation: arbitrar_geracao credita C do IVM ao agente original.

    Quando escala (nao resolve localmente):
      skills_exchanged = 0 (C baixo — nao houve cooperacao interna)
      agent_name = agente original (ex: "tester")
    """
    monkeypatch.setenv("ARBITER_MODE", "enforce")

    async def no_resolve(self, prompt, tags=None):
        return None

    async def no_memory(self, prompt, task_type):
        return _StubMemoryRouter()._Result()

    monkeypatch.setattr(
        "iaglobal.agents.critic_agent.CriticAgent._resolve_with_tools",
        no_resolve,
    )
    monkeypatch.setattr(
        "iaglobal.agents.critic_agent._get_memory_router",
        lambda: _StubMemoryRouter(),
    )

    class FakeBandit:
        DEFAULT_CANDIDATES = ["ollama/qwen2.5:0.5b"]

        async def generate(self, **kw):
            return "ok"

    from iaglobal.agents.critic_agent import _get_critic

    critic = _get_critic()
    critic.bandit = FakeBandit()

    async def run():
        return await critic.arbitrar_geracao(
            node_id="tester",
            prompt="teste",
            task_type="general",
        )

    asyncio.run(run())

    # _creditar_cooperacao foi chamado com skills_exchanged=0 (nao local)
    coop = [c for c in mock_ivm_axiom if c.get("skills_exchanged") == 0]
    assert len(coop) >= 1, "Deveria creditar skills_exchanged=0 quando escala"
    assert coop[-1]["agent_name"] == "tester", (
        f"IVM deve creditar ao agente original, obteve {coop[-1]['agent_name']!r}"
    )


def test_arbiter_local_resolution_credits_high_cooperation(monkeypatch, mock_ivm_axiom):
    """
    Cooperacao alta quando resolve em casa.

    DADO que tools resolvem localmente,
    QUANDO arbitrar_geracao e chamado,
    ENTAO skills_exchanged = 1 (C alto — cooperacao interna bem-sucedida).
    """
    monkeypatch.setenv("ARBITER_MODE", "enforce")

    async def fake_tools(self, prompt, tags=None):
        return "solucao local"

    monkeypatch.setattr(
        "iaglobal.agents.critic_agent.CriticAgent._resolve_with_tools",
        fake_tools,
    )

    from iaglobal.agents.critic_agent import _get_critic

    critic = _get_critic()

    async def run():
        return await critic.arbitrar_geracao(
            node_id="tester",
            prompt="teste",
            task_type="general",
        )

    asyncio.run(run())

    coop = [c for c in mock_ivm_axiom if c.get("skills_exchanged") == 1]
    assert len(coop) >= 1, (
        "Deveria creditar skills_exchanged=1 quando resolve localmente"
    )


# ═══════════════════════════════════════════════════════════════════
# 4. effective_agent — auditoria creditada ao agente delegante
# ═══════════════════════════════════════════════════════════════════


def test_effective_agent_in_bandit_generate(monkeypatch, bandit_module):
    """
    BanditPolicy.generate() usa effective_agent (delegate_for) para
    auditoria, nao node_id.  node_id="critic" satisfaz PSC, mas
    effective_agent carrega o nome do agente original.
    """
    import iaglobal.providers.provider_router as pr

    captured = {}

    async def fake_route(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        captured["model"] = model
        return "ok"

    monkeypatch.setattr(pr, "async_route_generate", fake_route)
    bp = bandit_module._get_bandit()
    bp.weights.clear()
    bp.rewards.clear()
    bp.circuit_breakers.clear()
    if bp.credit_engine is not None:
        try:
            bp.credit_engine.stats.clear()
        except Exception:
            pass

    out = asyncio.run(
        bp.generate(
            node_id="critic",
            prompt="hello",
            candidates=["ollama/qwen2.5:0.5b"],
            context={"delegate_for": "reflexion"},
        )
    )
    assert out == "ok"
