# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de estresse de concorrência do BanditPolicy.

Valida que o invariante acquires == releases se mantém sob carga
concorrente, mesmo com timeouts e falhas de semáforo.
"""

import asyncio
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def reset_bandit():
    """Reseta estado global do BanditPolicy entre testes."""
    from iaglobal.graphs.bandit import BanditPolicy

    BanditPolicy.MODEL_SEMAPHORES.clear()
    BanditPolicy.SEMAPHORE_LOCK = asyncio.Lock()
    try:
        from iaglobal.graphs.bandit import _get_bandit

        bp = _get_bandit()
        bp._model_in_use.clear()
        bp.weights.clear()
        bp.rewards.clear()
        bp.circuit_breakers.clear()
        if bp.credit_engine is not None:
            try:
                bp.credit_engine.stats.clear()
            except Exception:
                pass
    except Exception:
        pass


async def _fake_route(
    model=None, prompt=None, task_type="general", node_id="provider_router"
):
    """Simula execução rápida de modelo (10ms)."""
    await asyncio.sleep(0.01)
    return "ok"


async def _slow_route(
    model=None, prompt=None, task_type="general", node_id="provider_router"
):
    """Simula execução lenta (200ms) para exercitar concorrência."""
    await asyncio.sleep(0.2)
    return "ok"


def _make_bandit(monkeypatch, route_fn=None):
    """Retorna BanditPolicy global com provider_router mockado."""
    import iaglobal.providers.provider_router as pr

    monkeypatch.setattr(pr, "async_route_generate", route_fn or _fake_route)

    from iaglobal.graphs.bandit import _get_bandit

    return _get_bandit()


async def test_semaphore_invariante_acquire_release(monkeypatch):
    """
    Valida o invariante central: acquires == releases após N chamadas
    concorrentes ao generate() com o mesmo modelo.

    Cria 20 tasks concorrentes disputando 4 slots de um modelo local.
    Após todas completarem, verifica que:
      - Nenhum semáforo está com _value > initial (leaked permit)
      - Nenhum modelo está marcado como _model_in_use
    """
    bp = _make_bandit(monkeypatch)

    candidates = ["ollama/qwen2.5:0.5b"]
    n_concurrent = 20

    async def _concurrent_call(idx: int):
        return await bp.generate(
            node_id="critic",
            prompt=f"test-{idx}",
            candidates=candidates,
            task_type="general",
        )

    tasks = [_concurrent_call(i) for i in range(n_concurrent)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r == "ok")
    failures = sum(1 for r in results if r == "")
    exceptions = sum(1 for r in results if isinstance(r, BaseException))

    print(
        f"  Total: {n_concurrent} | OK={successes} | empty={failures} | exc={exceptions}"
    )

    # Verifica semáforo: _value deve ser == initial (CLOUD_MODEL_CONCURRENCY ou LOCAL_MODEL_CONCURRENCY)
    sem = bp.MODEL_SEMAPHORES.get("ollama/qwen2.5:0.5b")
    if sem is not None:
        expected_initial = bp.LOCAL_MODEL_CONCURRENCY  # 4
        assert sem._value == expected_initial, (
            f"Semaphore leak: _value={sem._value}, expected={expected_initial}"
        )
        print(f"  Semaphore value: {sem._value}/{expected_initial} ✅")

    # Verifica _model_in_use: todos devem ser False
    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos como em uso: {stuck}"
    print(f"  Model in use: OK ✅")


async def test_semaphore_invariante_multiplos_modelos(monkeypatch):
    """
    Com múltiplos candidatos (cloud + local), verifica que cada semáforo
    individual mantém acquires == releases após carga concorrente.
    """
    bp = _make_bandit(monkeypatch)

    candidates = [
        "groq/llama-3.3-70b-versatile",
        "ollama/qwen2.5:0.5b",
    ]
    n_concurrent = 10

    async def _call(idx: int):
        return await bp.generate(
            node_id="critic",
            prompt=f"test-{idx}",
            candidates=candidates,
            task_type="general",
        )

    tasks = [_call(i) for i in range(n_concurrent)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r == "ok")
    print(f"  Total: {n_concurrent} | OK={successes}")

    for model_name in candidates:
        sem = bp.MODEL_SEMAPHORES.get(model_name)
        if sem is not None:
            expected = (
                bp.CLOUD_MODEL_CONCURRENCY
                if "groq/" in model_name
                else bp.LOCAL_MODEL_CONCURRENCY
            )
            assert sem._value == expected, (
                f"Semaphore leak em {model_name}: _value={sem._value}, expected={expected}"
            )
            print(f"  {model_name}: {sem._value}/{expected} ✅")

    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos: {stuck}"


async def test_semaphore_sem_vazamento_com_timeout(monkeypatch):
    """
    Cenário de estresse onde metade das chamadas sofre timeout de semáforo.

    Usa um modelo com concurrency=1 (cloud) e lança 10 chamadas concorrentes.
    Apenas 1 executa por vez; as demais devem timeout (3s cloud) e retornar "".
    Ao final, o semáforo deve estar íntegro.
    """
    bp = _make_bandit(monkeypatch, route_fn=_slow_route)

    candidates = ["groq/llama-3.3-70b-versatile"]
    n_concurrent = 10

    async def _call(idx: int):
        return await bp.generate(
            node_id="critic",
            prompt=f"test-{idx}",
            candidates=candidates,
            task_type="general",
            timeout=5.0,
        )

    tasks = [_call(i) for i in range(n_concurrent)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r == "ok")
    empty = sum(1 for r in results if r == "")
    print(
        f"  Cloud(concurrency=1): {n_concurrent} chamadas | OK={successes} | empty={empty}"
    )

    sem = bp.MODEL_SEMAPHORES.get("groq/llama-3.3-70b-versatile")
    if sem is not None:
        expected = bp.CLOUD_MODEL_CONCURRENCY  # 1
        assert sem._value == expected, (
            f"Semaphore leak cloud: _value={sem._value}, expected={expected}"
        )
        print(f"  Semaphore: {sem._value}/{expected} ✅")

    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos: {stuck}"


async def test_semaphore_sem_vazamento_apos_falha_total(monkeypatch):
    """
    Quando NENHUM semáforo pode ser adquirido (todos ocupados + retries
    esgotados), o sistema retorna "" sem vazar recursos.

    Configura um mock que faz o acquire sempre falhar (ex.: gate lotado).
    """
    from iaglobal.graphs.bandit import BanditPolicy

    bp = _make_bandit(monkeypatch)

    # Força acquire_model a sempre retornar False (simula gate cheio)
    orig_acquire = BanditPolicy.acquire_model

    async def _always_fail(self, model_name, node_id=""):
        return False

    monkeypatch.setattr(BanditPolicy, "acquire_model", _always_fail)

    candidates = ["ollama/qwen2.5:0.5b", "groq/llama-3.3-70b-versatile"]
    n_concurrent = 5

    async def _call(idx: int):
        return await bp.generate(
            node_id="critic",
            prompt=f"test-{idx}",
            candidates=candidates,
            task_type="general",
        )

    tasks = [_call(i) for i in range(n_concurrent)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_empty = all(r == "" for r in results)
    assert all_empty, f"Deveriam todas retornar vazio, obtido: {results}"

    # Nenhum semáforo foi adquirido → nenhum modelo deve estar marcado como em uso
    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos como em uso: {stuck}"

    # Nenhum semáforo deve ter sido corrompido (release sem acquire)
    for model_name in candidates:
        sem = bp.MODEL_SEMAPHORES.get(model_name)
        if sem is not None:
            expected = (
                bp.CLOUD_MODEL_CONCURRENCY
                if "groq/" in model_name
                else bp.LOCAL_MODEL_CONCURRENCY
            )
            assert sem._value == expected, (
                f"Semaphore corrompido em {model_name}: _value={sem._value}, expected={expected}"
            )

    print(f"  Falha total: todas {n_concurrent} retornaram vazio ✅")
    print(f"  Semáforos íntegros após falha ✅")


async def test_ciclo_completo_arbiter_bandit_sem_vazamento(monkeypatch):
    """
    Teste de integração: arbitrar_geracao → Bandit.generate() → provider_router.

    Simula o fluxo real onde o critic não resolve localmente e escala para
    o Bandit, que executa o modelo.  Após múltiplas chamadas, verifica
    que os semáforos estão íntegros.
    """
    monkeypatch.setenv("ARBITER_MODE", "enforce")

    import iaglobal.graphs.bandit as bm
    from iaglobal.agents.critic_agent import _get_critic

    # Mock tools + memory para NAO resolver localmente
    async def no_resolve(self, prompt, tags=None):
        return None

    class _StubResult:
        found = False
        content = ""
        confidence = 0.0

    async def no_memory(prompt, task_type):
        return _StubResult()

    monkeypatch.setattr(
        "iaglobal.agents.critic_agent.CriticAgent._resolve_with_tools",
        no_resolve,
    )
    monkeypatch.setattr(
        "iaglobal.agents.critic_agent._get_memory_router",
        lambda: type("R", (), {"route": no_memory})(),
    )

    # Mock provider_router
    import iaglobal.providers.provider_router as pr

    monkeypatch.setattr(pr, "async_route_generate", _slow_route)

    critic = _get_critic()
    # Garante que o bandit do critic está limpo
    # (testes anteriores podem ter substituído por FakeBandit, então recria)
    if not hasattr(critic.bandit, "weights"):
        import iaglobal.graphs.bandit as bm_

        critic.bandit = bm_.BanditPolicy()
    critic.bandit.weights.clear()
    critic.bandit.rewards.clear()
    critic.bandit.circuit_breakers.clear()

    n_calls = 8

    async def _call(i):
        return await critic.arbitrar_geracao(
            node_id="pipeline_updater",
            prompt=f"test-{i}",
            task_type="general",
        )

    tasks = [_call(i) for i in range(n_calls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r and len(str(r).strip()) > 0)
    empty = sum(1 for r in results if r == "")

    print(f"  Arbitrar geracao: {n_calls} chamadas | OK={successes} | empty={empty}")

    # Verifica semáforos
    bp = critic.bandit
    for model_name, sem in bp.MODEL_SEMAPHORES.items():
        is_cloud = any(
            p in model_name for p in ("groq/", "nvidia/", "openrouter/", "gemini/")
        )
        expected = (
            bp.CLOUD_MODEL_CONCURRENCY if is_cloud else bp.LOCAL_MODEL_CONCURRENCY
        )
        assert sem._value == expected, (
            f"Semaphore leak em {model_name}: _value={sem._value}, expected={expected}"
        )
        print(f"  {model_name}: {sem._value}/{expected} ✅")

    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos: {stuck}"


async def test_semaphore_resiliencia_apos_multiplos_timeouts(monkeypatch):
    """
    Estresse com múltiplos timeouts consecutivos no semáforo.

    Simula um modelo que às vezes falha (adquire semáforo mas o provider
    demora), verificando que após 50 chamadas nenhum recurso vazou.
    """
    call_count = 0

    async def _alternating_route(model=None, prompt=None, **kw):
        nonlocal call_count
        call_count += 1
        if call_count % 3 == 0:
            await asyncio.sleep(0.5)  # Lento — timeout parcial
        await asyncio.sleep(0.02)
        return "ok"

    bp = _make_bandit(monkeypatch, route_fn=_alternating_route)

    candidates = ["ollama/qwen2.5:0.5b"]
    n_calls = 50

    async def _call(idx: int):
        return await bp.generate(
            node_id="critic",
            prompt=f"test-{idx}",
            candidates=candidates,
            task_type="general",
            timeout=2.0,
        )

    tasks = [_call(i) for i in range(n_calls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r and len(str(r).strip()) > 0)
    empty = sum(1 for r in results if r == "")
    exceptions = sum(1 for r in results if isinstance(r, BaseException))
    print(
        f"  {n_calls} chamadas (1 local slot) | OK={successes} | empty={empty} | exc={exceptions}"
    )

    sem = bp.MODEL_SEMAPHORES.get("ollama/qwen2.5:0.5b")
    if sem is not None:
        assert sem._value == bp.LOCAL_MODEL_CONCURRENCY, (
            f"Semaphore leak apos {n_calls} chamadas: _value={sem._value}, expected={bp.LOCAL_MODEL_CONCURRENCY}"
        )
        print(f"  Semaphore: {sem._value}/{bp.LOCAL_MODEL_CONCURRENCY} ✅")

    stuck = [m for m, v in bp._model_in_use.items() if v]
    assert not stuck, f"Modelos presos: {stuck}"
