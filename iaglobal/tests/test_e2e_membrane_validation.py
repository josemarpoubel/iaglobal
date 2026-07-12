# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# tests/temp/test_e2e_membrane_validation.py
"""Guarda de regressão E2E da membrana seletiva + gate de busca + IVM.

Princípio metabólico (ATP 10:1): a validação NÃO dispara um `iaglobal run` real
por padrão (consumiria nuvem/Ollama a cada `pytest`). Em vez disso, exercita a
camada de DECISÃO da membrana — `_policy_candidates` / `_is_external_authorized`
— que é pura, determinística e sem rede, e prova os dois ramos (Ollama OK x
Ollama indisponível) pela *composição de candidatos*:

  • não-crítico -> candidatos == {ollama} SOMENTE. Se Ollama cair, NÃO há
    fallback cloud (membrana negou) -> o pipeline falha de forma segura.
  • crítico     -> candidatos incluem cloud. Se Ollama cair, escala para nuvem.

Isso é exatamente o comportamento crítico em produção, testado em milissegundos.

Pontos cobertos:
  1. Assert programático (não grep manual): captura o log `[MEMBRANA]` e o
     skip-list de busca; grava resumo estruturado em JSON.
  2. Dois ramos: confinamento local (feliz) x reação a falha (Ollama down).
  3. Resumo estruturado em /tmp/iaglobal_e2e_summary.json com campos tipados.
  4. Baseline de ambiente ANTES de validar (playwright/yacy reais).

O ramo ao vivo (`IAGLOBAL_E2E_LIVE=1`) roda o pipeline real e faz grep de log —
opt-in para não queimar ATP no CI.
"""
import os
import json
import asyncio
import logging
import pytest

from iaglobal.providers import provider_router as pr
from iaglobal.graphs.nodes import _search_capabilities as cap


# Node_ids representativos da colônia (não-críticos vs crítico)
_NON_CRITIC_NODES = ["coder", "debugger_agent", "planner", "pm", "tester", "architect"]
_CRITIC_NODES = ["critic", "critic_agent", "no_critic"]


@pytest.fixture
def membrane_log_records():
    """Captura registros do logger 'iaglobal' para assert do padrão [MEMBRANA]."""
    records = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r)
    logger = logging.getLogger("iaglobal")
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


@pytest.fixture(autouse=True)
def _force_membrane_on(monkeypatch):
    """A membrana seletiva DEVE estar ativa para a guarda ser significativa."""
    monkeypatch.setenv("EXTERNAL_ACCESS_ONLY_CRITIC", "true")
    # Garante que flags epigenéticas não interfiram
    monkeypatch.delenv("EXTERNAL_AUTHORIZED_AGENTS", raising=False)
    yield


def _has_membrana_log(records) -> bool:
    return any("[MEMBRANA]" in records[i].getMessage() for i in range(len(records)))


# ---------------------------------------------------------------------------
# PONTO 4 — Baseline de ambiente (independente do pipeline)
# ---------------------------------------------------------------------------
def test_env_baseline_capability_gate():
    """Sabe de antemão o que o skip-list DEVE conter neste ambiente."""
    baseline = {
        "playwright": cap.is_playwright_available(),
        "yacy": asyncio.run(cap.is_yacy_available()),
    }
    skip = asyncio.run(cap.get_search_skip_list())

    # Playwright ausente -> fontes pesadas puladas; presente -> nunca puladas
    if baseline["playwright"]:
        assert cap._PLAYWRIGHT_SOURCES.isdisjoint(skip)
    else:
        assert cap._PLAYWRIGHT_SOURCES.issubset(skip)

    # YaCy ausente -> 'yacy' pulado; presente -> nunca pulado
    if baseline["yacy"]:
        assert "yacy" not in skip
    else:
        assert "yacy" in skip

    # Baseline é determinístico e consistente com as fontes conhecidas
    assert skip <= (cap._PLAYWRIGHT_SOURCES | cap._YACY_SOURCES)


# ---------------------------------------------------------------------------
# PONTO 1 + 2 — Membrana: confinamento local (ramo feliz) e reação a falha
# ---------------------------------------------------------------------------
def test_membrane_confines_non_critic_and_logs(membrane_log_records):
    """Não-crítico só enxerga Ollama e a membrana LOGA o confinamento."""
    # Limpa possível log prévio do fixture
    membrane_log_records.clear()

    for node_id in _NON_CRITIC_NODES:
        cands = pr._policy_candidates("general", node_id)
        providers = {p for p, _ in cands}
        # RAMO FELIZ: confinado a Ollama local
        assert providers == {"ollama"}, (
            f"node_id='{node_id}' deveria ficar restrito a Ollama, "
            f"mas recebeu {providers}"
        )

    # O confinamento emite o marcador [MEMBRANA] (prova que a membrana existe)
    assert _has_membrana_log(membrane_log_records), (
        "Esperado log [MEMBRANA] ao confinar agentes não-críticos"
    )


def test_membrane_authorizes_critic_with_cloud():
    """Crítico tem direito a modelo externo (cloud) — sem log de confinamento."""
    records = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r)
    logger = logging.getLogger("iaglobal")
    logger.addHandler(handler)
    try:
        for node_id in _CRITIC_NODES:
            assert pr._is_external_authorized(node_id) is True
            cands = pr._policy_candidates("general", node_id)
            providers = {p for p, _ in cands}
            # RAMO DE ESCALA: cloud presente entre os candidatos
            assert providers >= {"groq", "nvidia"}, (
                f"crítico '{node_id}' deveria poder alcançar cloud, "
                f"mas recebeu {providers}"
            )
        # Crítico NÃO é confinado -> NENHUM log [MEMBRANA]
        assert not _has_membrana_log(records), (
            "Crítico não deveria gerar log de confinamento de membrana"
        )
    finally:
        logger.removeHandler(handler)


def test_membrane_reacts_to_ollama_failure_two_branches():
    """Prova a REAÇÃO à falha (não só a existência) sem rede:

    • não-crítico: candidatos == {ollama} -> se Ollama cai, NÃO há cloud para
      escalar (membrana negou) -> pipeline falha de forma segura.
    • crítico: candidatos incluem cloud -> se Ollama cai, escala para nuvem.
    """
    non_critic_providers = {p for p, _ in pr._policy_candidates("general", "coder")}
    critic_providers = {p for p, _ in pr._policy_candidates("general", "critic")}

    # Ramo A (Ollama OK): não-crítico confinado local
    assert non_critic_providers == {"ollama"}

    # Ramo B (Ollama indisponível): a DIFERENÇA de composição é o que importa
    # Não-crítico não tem para onde escalar:
    assert non_critic_providers.isdisjoint({"groq", "nvidia", "openrouter"})
    # Crítico TEM para onde escalar:
    assert critic_providers >= {"groq", "nvidia"}

    # Sem Ollama, o não-crítico não sobrevive (falha segura); o crítico sim.
    assert "ollama" in non_critic_providers  # depende 100% de Ollama
    assert "ollama" in critic_providers and len(critic_providers) > 1  # tem redundância


# ---------------------------------------------------------------------------
# PONTO 3 — Resumo estruturado (typed, machine-readable)
# ---------------------------------------------------------------------------
def test_structured_e2e_summary_emitted():
    """Coleta métricas observáveis e grava JSON tipado — validação sem grep."""
    summary = {
        "agents_confined_local": 0,
        "agents_escalated_cloud": 0,
        "search_skip_list": sorted(asyncio.run(cap.get_search_skip_list())),
        "ivm_ranked_count": 0,
    }

    all_providers = set()
    for node_id in _NON_CRITIC_NODES + _CRITIC_NODES:
        providers = {p for p, _ in pr._policy_candidates("general", node_id)}
        all_providers |= providers
        if providers == {"ollama"}:
            summary["agents_confined_local"] += 1
        if providers >= {"groq", "nvidia"}:
            summary["agents_escalated_cloud"] += 1

    summary["ivm_ranked_count"] = len(all_providers)

    # Sinal estruturado NÍVEL-INDEPENDENTE (não depende de WARNING/INFO no CLI)
    pr._MEMBRANE_DECISIONS.clear()
    for node_id in _NON_CRITIC_NODES + _CRITIC_NODES:
        pr._policy_candidates("general", node_id)
    decisions = [d for d in pr._MEMBRANE_DECISIONS]
    summary["membrane_decisions_structured"] = len(decisions)
    summary["membrane_confined_count"] = sum(1 for d in decisions if d["action"] == "confined_local")
    summary["membrane_authorized_count"] = sum(1 for d in decisions if d["action"] == "authorized_cloud")

    path = "/tmp/iaglobal_e2e_summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Releitura e asserts de schema (ponto 3: chaves conhecidas, não regex)
    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert isinstance(loaded["agents_confined_local"], int)
    assert isinstance(loaded["agents_escalated_cloud"], int)
    assert isinstance(loaded["search_skip_list"], list)
    assert isinstance(loaded["ivm_ranked_count"], int)

    # Invariantes do ambiente sob membrana ativa
    assert loaded["agents_confined_local"] >= len(_NON_CRITIC_NODES)
    assert loaded["agents_escalated_cloud"] >= len(_CRITIC_NODES)
    assert loaded["ivm_ranked_count"] >= 3  # ollama + ao menos 1 cloud
    # skip-list reflete o baseline real (playwright ausente NESTE ambiente)
    if cap.is_playwright_available():
        assert "google_pw" not in loaded["search_skip_list"]
    else:
        assert "google_pw" in loaded["search_skip_list"]

    # Sinal estruturado prova que a membrana é observável SEM depender de nível de log
    assert loaded["membrane_decisions_structured"] == len(_NON_CRITIC_NODES) + len(_CRITIC_NODES)
    assert loaded["membrane_confined_count"] == len(_NON_CRITIC_NODES)
    assert loaded["membrane_authorized_count"] == len(_CRITIC_NODES)


# ---------------------------------------------------------------------------
# PONTO 1 (live, opt-in) — `iaglobal run` real + grep de log
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.environ.get("IAGLOBAL_E2E_LIVE"),
    reason="Live E2E desligado (defina IAGLOBAL_E2E_LIVE=1 para rodar de verdade)",
)
def test_live_iaglobal_run_membrane_logs():
    """Live REAL: exercita o gateway provider_router com Ollama de verdade.

    Prova ponta-a-ponta que a membrana (a) confina não-crítico a Ollama e LOGA
    `[MEMBRANA]`, e (b) autoriza o crítico a enxergar cloud — tudo com IVM
    registrado. Rápido (~3s) e determinístico, diferente do CLI completo que
    depende de agentes chamarem o gateway (cobertura parcial — ver nota no
    relatório). Requer Ollama local em pé (default :11434).

    Para simular 'Ollama indisponível', aponte OLLAMA_BASE_URL para porta morta:
        OLLAMA_BASE_URL=http://127.0.0.1:9 IAGLOBAL_E2E_LIVE=1 pytest ...
    """
    records = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r)
    logger = logging.getLogger("iaglobal")
    prev_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        out_coder = asyncio.run(
            pr.async_route_generate_parallel("responda 'ok'", task_type="general", node_id="coder")
        )
        out_critic = asyncio.run(
            pr.async_route_generate_parallel("responda 'ok'", task_type="general", node_id="critic")
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)

    msgs = [records[i].getMessage() for i in range(len(records))]
    # Membrana confina o não-crítico e LOGA o marcador ao vivo
    assert any("[MEMBRANA]" in m and "node_id='coder'" in m for m in msgs), (
        "Live: membrana não logou confinamento do coder (Ollama indisponível ou gate off?)"
    )
    assert out_coder and out_coder.strip(), "Live: coder não retornou texto (Ollama indisponível?)"
    assert out_critic and out_critic.strip(), "Live: critic não retornou texto"


# ---------------------------------------------------------------------------
# Failover sem chaves de nuvem — simula o outro extremo do circuito (auth)
# ---------------------------------------------------------------------------
async def _fake_ok(prompt, **kw):
    return "ok-local"


async def _fake_auth_error(prompt, **kw):
    raise PermissionError("401 Unauthorized — API key ausente/inválida (simulado)")


async def _fake_down(prompt, **kw):
    raise ConnectionError("Ollama indisponível (porta morta simulada)")


def test_cloud_auth_failure_degrades_gracefully(monkeypatch):
    """Crítico com auth de nuvem falhando NÃO trava: degrada para Ollama.

    Equivalente à 'porta morta' no extremo oposto do circuito: sem chave real,
    o cliente cloud levanta erro de autenticação; o pipeline deve cair no
    fallback Ollama (graceful) e não pendurar nem quebrar.
    """
    monkeypatch.setitem(pr.ASYNC_PROVIDERS, "groq", _fake_auth_error)
    monkeypatch.setitem(pr.ASYNC_PROVIDERS, "nvidia", _fake_auth_error)
    monkeypatch.setattr(pr, "ollama_async_generate", _fake_ok)

    # Neutraliza o cache L1/L2 para isolar o failover real
    import iaglobal.memory.cache as _cache_mod
    monkeypatch.setattr(_cache_mod, "get", lambda p: None)
    monkeypatch.setattr(_cache_mod, "get_entry", lambda p: None)

    out = asyncio.run(
        pr.async_route_generate_parallel("auth-fail-probe-xyz", task_type="general", node_id="critic")
    )
    assert out and out.strip(), "Crítico deveria degradar para Ollama mesmo com nuvem em auth-failure"
    # Sinal estruturado registra a decisão (nível-independente)
    assert any(d["node_id"] == "critic" and d["action"] == "authorized_cloud"
               for d in pr._MEMBRANE_DECISIONS)


def test_non_critic_ollama_down_no_cloud_escalation(monkeypatch):
    """Não-crítico com Ollama morto NÃO escala para nuvem (fail-closed).

    Prova o ramo oposto ao 'Ollama morto -> escala nuvem': a membrana NEGA
    cloud ao não-crítico, então não há para onde escalar -> falha segura
    (RuntimeError), sem nunca invocar o provedor cloud.
    """
    pr._MEMBRANE_DECISIONS.clear()
    cloud_calls = {"groq": 0, "nvidia": 0}

    # Neutraliza o cache L1/L2 (SQLite aproximado) para isolar o failover real.
    # Se não isolasse, uma entrada L2 válida (cache hit) mascararia a queda do
    # Ollama e o teste passaria por engano — métrica de teste falsa. O teste
    # verifica o circuito fail-closed, não o cache, então ambos devem sumir.
    import iaglobal.memory.cache as _cache_mod
    monkeypatch.setattr(_cache_mod, "get", lambda p: None)
    monkeypatch.setattr(_cache_mod, "get_entry", lambda p: None)

    def _spy(provider):
        async def _inner(prompt, **kw):
            cloud_calls[provider] += 1
            return "leak"
        return _inner

    # Espiona cloud para garantir que NUNCA é chamado pelo não-crítico
    monkeypatch.setitem(pr.ASYNC_PROVIDERS, "groq", _spy("groq"))
    monkeypatch.setitem(pr.ASYNC_PROVIDERS, "nvidia", _spy("nvidia"))
    # Ollama "morto": a corrida usa ASYNC_PROVIDERS["ollama"]; o fallback final
    # (linha ~577) usa o global de módulo — patchia ambos.
    monkeypatch.setitem(pr.ASYNC_PROVIDERS, "ollama", _fake_down)
    monkeypatch.setattr(pr, "ollama_async_generate", _fake_down)

    with pytest.raises(RuntimeError):
        asyncio.run(
            pr.async_route_generate_parallel("ollama-down-probe-xyz", task_type="general", node_id="coder")
        )
    # Fail-closed: nenhum provedor cloud foi invocado para o não-crítico
    assert cloud_calls["groq"] == 0 and cloud_calls["nvidia"] == 0
    assert any(d["node_id"] == "coder" for d in pr._MEMBRANE_DECISIONS)
