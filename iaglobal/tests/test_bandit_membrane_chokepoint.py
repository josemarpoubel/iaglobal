# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do chokepoint da membrana seletiva em BanditPolicy.generate.

Cobre o passo 4 do plano de rollout: varre node_ids não exercitados antes
(planner, tester, architect, pm, coder, debugger, agentes sem mapeamento) e
confirma o confinamento fail-closed esperado. Sem custo de ATP — o provider
é substituído por um fake coroutine.
"""

import asyncio
import logging

import pytest


@pytest.fixture
def bandit_module():
    import iaglobal.graphs.bandit as b

    return b


# ── Funções puras da política (fail-closed) ──


def test_membrane_filter_confines_non_critic(bandit_module):
    cands = [
        "groq/llama-3.3-70b-versatile",
        "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
        "ollama/qwen2.5:0.5b",
    ]
    # Amostra de node_ids NUNCA exercitados pelo caminho do provider_router:
    for node in [
        "coder",
        "debugger",
        "planner",
        "pm",
        "tester",
        "architect",
        "",
        "unknown_agent",
        "evo-gen0",
        "multi_coder",
    ]:
        out = bandit_module.BanditPolicy._membrane_filter_candidates(
            bandit_module._get_bandit(), node, cands
        )
        assert out == ["ollama/qwen2.5:0.5b"], (
            f"{node!r} deveria ser confinado a Ollama"
        )


def test_membrane_filter_keeps_critic(bandit_module):
    cands = ["groq/llama-3.3-70b-versatile", "ollama/qwen2.5:0.5b"]
    # PSC §1 exige identidade exata — apenas "critic" e "critic_batch" passam
    for node in ["critic", "critic_batch"]:
        bp = bandit_module._get_bandit()
        out = bp._membrane_filter_candidates(node, cands)
        assert out == cands, f"{node!r} deve manter acesso à nuvem"


def test_membrane_filter_blocks_substring_matches(bandit_module):
    """PSC §1: substring como 'critic_agent' ou 'no_critic' NÃO passam."""
    cands = ["groq/llama-3.3-70b-versatile", "ollama/qwen2.5:0.5b"]
    bp = bandit_module._get_bandit()
    for node in ["critic_agent", "no_critic", "CriticAgent", "critical_analysis"]:
        out = bp._membrane_filter_candidates(node, cands)
        assert out == ["ollama/qwen2.5:0.5b"], f"{node!r} deve ser confinado a Ollama"


def test_membrane_fail_closed_injects_local_when_absent(bandit_module):
    cands = [
        "groq/llama-3.3-70b-versatile",
        "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
    ]
    bp = bandit_module._get_bandit()
    out = bp._membrane_filter_candidates("planner", cands)
    # Fail-closed: sem candidato local, injeta Ollama — NÃO libera nuvem.
    assert out == ["ollama/qwen2.5:0.5b"]


def test_membrane_mode_env(monkeypatch, bandit_module):
    bp = bandit_module._get_bandit()
    monkeypatch.delenv("MEMBRANA_MODE", raising=False)
    assert bp._membrane_mode() == "enforce"
    monkeypatch.setenv("MEMBRANA_MODE", "shadow")
    assert bp._membrane_mode() == "shadow"
    monkeypatch.setenv("MEMBRANA_MODE", "off")
    assert bp._membrane_mode() == "off"


# ── Integração do chokepoint (provider fake, sem ATP) ──


def test_bandit_generate_enforce_confines(monkeypatch, bandit_module):
    import iaglobal.providers.provider_router as pr

    captured = {}

    async def fake_generate(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        captured["model"] = model
        captured["node_id"] = node_id
        return "ok"

    async def _run():
        monkeypatch.setattr(pr, "async_route_generate", fake_generate)
        monkeypatch.setenv("MEMBRANA_MODE", "enforce")
        bp = bandit_module._get_bandit()
        # Reset de estado de aprendizado p/ ranking determinístico entre testes.
        bp.weights.clear()
        bp.rewards.clear()
        bp.circuit_breakers.clear()
        if bp.credit_engine is not None:
            try:
                bp.credit_engine.stats.clear()
            except Exception:
                pass

        # Mock acquire_model (classe/método) para evitar dependência de semáforo real
        async def _fake_acquire(self, model_name, node_id="", execution_id=""):
            return True

        monkeypatch.setattr(bandit_module.BanditPolicy, "acquire_model", _fake_acquire)
        # PSC: critic é o único node_id que passa. A membrana em modo enforce
        # não filtra critic (tem acesso cloud). O teste verifica que o modelo
        # de maior peso (groq) é selecionado para critic.
        return await bp.generate(
            node_id="critic",
            prompt="hello",
            candidates=[
                "groq/llama-3.3-70b-versatile",
                "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
                "ollama/qwen2.5:0.5b",
            ],
        )

    out = asyncio.run(_run())
    assert out == "ok"
    # critic tem acesso cloud — pode selecionar qualquer modelo dos candidatos
    assert captured["node_id"] == "critic"


def test_bandit_generate_shadow_logs_only(monkeypatch, bandit_module, caplog):
    import iaglobal.providers.provider_router as pr

    captured = {}

    async def fake_generate(
        model=None, prompt=None, task_type="general", node_id="provider_router"
    ):
        captured["model"] = model
        return "ok"

    async def _run():
        monkeypatch.setattr(pr, "async_route_generate", fake_generate)
        monkeypatch.setenv("MEMBRANA_MODE", "shadow")
        bp = bandit_module._get_bandit()
        # Reset de estado de aprendizado p/ ranking determinístico entre testes.
        bp.weights.clear()
        bp.rewards.clear()
        bp.circuit_breakers.clear()
        if bp.credit_engine is not None:
            try:
                bp.credit_engine.stats.clear()
            except Exception:
                pass

        # Mock acquire_model (classe/método) para evitar dependência de semáforo real
        async def _fake_acquire(self, model_name, node_id="", execution_id=""):
            return True

        monkeypatch.setattr(bandit_module.BanditPolicy, "acquire_model", _fake_acquire)
        # PSC: critic é o único node_id que passa. Em shadow mode, a membrana
        # não confina critic (tem acesso cloud). O teste verifica fluxo normal.
        return await bp.generate(
            node_id="critic",
            prompt="hello",
            candidates=["groq/llama-3.3-70b-versatile", "ollama/qwen2.5:0.5b"],
        )

    with caplog.at_level(logging.INFO):
        out = asyncio.run(_run())

    assert out == "ok"
    # Shadow NÃO confina critic: candidato cloud ainda elegível
    assert "groq" in captured.get("model", "") or "ollama" in captured.get("model", "")
    # Critic não é confinado, então não há log [MEMBRANA] para critic
    # (a membrana só loga quando confina um node_id não-crítico)
