# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes específicos do sistema de semáforos para os 3 modelos Ollama.

Cobre:
  - Criação com concorrência correta por papel cognitivo
  - Ciclo acquire/release sem vazamento
  - Limite de concorrência respeitado (Juiz=1, Operário=3, Sentinela=5)
  - Timeout no acquire libera recursos corretamente
  - Starvation contabilizada no SemaphoreTracker
  - Semáforos compartilhados entre instâncias do BanditPolicy
"""

import asyncio
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")

# Modelos Ollama sob teste (extraídos do provider_config.py)
GLM4 = "ollama/yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest"
QWEN = "ollama/qwen2.5:0.5b"
LFM = "ollama/oamazonasgabriel/lfm2.5-230m:bf16-8gbRAM"

CONCURRENCY = {GLM4: 1, QWEN: 3, LFM: 5}


@pytest.fixture(autouse=True)
def reset_bandit():
    from iaglobal.graphs.bandit import BanditPolicy

    BanditPolicy.MODEL_SEMAPHORES.clear()
    BanditPolicy.SEMAPHORE_LOCK = asyncio.Lock()
    try:
        bp = BanditPolicy._instance if hasattr(BanditPolicy, "_instance") else None
        if bp is not None:
            bp._model_in_use.clear()
            bp.weights.clear()
            bp.rewards.clear()
            bp.circuit_breakers.clear()
    except Exception:
        pass


# ── 1. CRIAÇÃO DE SEMÁFOROS ──────────────────────────────────────────────────


async def _get_bp():
    from iaglobal.graphs.bandit import BanditPolicy

    return BanditPolicy()


async def test_cada_modelo_tem_semaphore_proprio():
    bp = await _get_bp()
    for model in [GLM4, QWEN, LFM]:
        sem = await bp._get_model_semaphore(model)
        assert sem is not None, f"Semáforo não criado para {model}"
        assert isinstance(sem, asyncio.Semaphore)


async def test_concurrency_respeita_provider_config():
    bp = await _get_bp()
    for model, expected in CONCURRENCY.items():
        sem = await bp._get_model_semaphore(model)
        assert sem._value == expected, (
            f"{model}: esperado concurrency={expected}, obtido {sem._value}"
        )


async def test_mesmo_semaphore_retornado_em_chamadas_repetidas():
    bp = await _get_bp()
    s1 = await bp._get_model_semaphore(QWEN)
    s2 = await bp._get_model_semaphore(QWEN)
    assert s1 is s2, "Deveria retornar o mesmo objeto Semaphore"


async def test_glm4_concurrency_um():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(GLM4)
    assert sem._value == 1, "GLM4 (Juiz) deve ter concurrency=1"


async def test_qwen_concurrency_tres():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(QWEN)
    assert sem._value == 3, "QWEN (Operário) deve ter concurrency=3"


async def test_lfm_concurrency_cinco():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(LFM)
    assert sem._value == 5, "LFM (Sentinela) deve ter concurrency=5"


# ── 2. ACQUIRE / RELEASE ─────────────────────────────────────────────────────


async def test_acquire_retorna_true_quando_slot_disponivel():
    bp = await _get_bp()
    acquired = await bp.acquire_model(QWEN, node_id="test")
    assert acquired is True
    bp.release_model(QWEN, node_id="test")


async def test_release_restaura_semaphore():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(QWEN)
    initial = sem._value
    await bp.acquire_model(QWEN, node_id="test")
    assert sem._value == initial - 1
    bp.release_model(QWEN, node_id="test")
    assert sem._value == initial


async def test_acquire_e_release_multiplos():
    bp = await _get_bp()
    n = 3
    for i in range(n):
        ok = await bp.acquire_model(QWEN, node_id=f"test-{i}")
        assert ok, f"acquire {i} falhou"
    sem = await bp._get_model_semaphore(QWEN)
    assert sem._value == 0, "Todos os slots ocupados"
    for i in range(n):
        bp.release_model(QWEN, node_id=f"test-{i}")
    assert sem._value == 3, "Todos os slots liberados"


async def test_release_sem_acquire_nao_quebra():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(QWEN)
    initial = sem._value
    bp.release_model(QWEN, node_id="orphan")
    assert sem._value == initial + 1, "release sem acquire infla o semáforo"


# ── 3. LIMITE DE CONCORRÊNCIA POR PAPEL ──────────────────────────────────────
# NOTA: Testamos no nível do Semaphore (não acquire_model) porque
# acquire_model tem timeout=15s interno para modelos locais.
# A validação de acquire_model é feita nos testes de acquire/release acima.


async def test_glm4_semaphore_limite_um():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(GLM4)
    assert sem._value == 1
    await sem.acquire()
    assert sem._value == 0
    acquired = sem.acquire()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquired, timeout=0.1)
    sem.release()
    assert sem._value == 1


async def test_qwen_semaphore_limite_tres():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(QWEN)
    for _ in range(3):
        await sem.acquire()
    assert sem._value == 0
    acquired = sem.acquire()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquired, timeout=0.1)
    for _ in range(3):
        sem.release()
    assert sem._value == 3


async def test_lfm_semaphore_limite_cinco():
    bp = await _get_bp()
    sem = await bp._get_model_semaphore(LFM)
    for _ in range(5):
        await sem.acquire()
    assert sem._value == 0
    acquired = sem.acquire()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(acquired, timeout=0.1)
    for _ in range(5):
        sem.release()
    assert sem._value == 5


async def test_semaphore_independente_entre_modelos():
    bp = await _get_bp()
    sg = await bp._get_model_semaphore(GLM4)
    sq = await bp._get_model_semaphore(QWEN)
    sl = await bp._get_model_semaphore(LFM)
    await sg.acquire()
    await sq.acquire()
    assert sg._value == 0
    assert sq._value == 2
    assert sl._value == 5
    sg.release()
    sq.release()
    assert sg._value == 1
    assert sq._value == 3


# ── 4. RESOLVE LOCAL CONCURRENCY ─────────────────────────────────────────────


async def test_resolve_local_concurrency_para_cada_modelo():
    from iaglobal.graphs.bandit import BanditPolicy

    bp = BanditPolicy()
    for model, expected in CONCURRENCY.items():
        actual = bp._resolve_local_concurrency(model)
        assert actual == expected, f"{model}: esperado {expected}, obtido {actual}"


async def test_resolve_local_concurrency_para_modelo_desconhecido():
    from iaglobal.graphs.bandit import BanditPolicy

    bp = BanditPolicy()
    actual = bp._resolve_local_concurrency("ollama/modelo:inexistente")
    assert actual == bp.LOCAL_MODEL_CONCURRENCY, (
        "Modelo desconhecido deve usar LOCAL_MODEL_CONCURRENCY"
    )


# ── 5. SEMAPHORE TRACKER — STARVATION ────────────────────────────────────────


_STARVATION_MODEL = "ollama/test-starvation-model:latest"


async def test_starvation_contabilizada_no_tracker():
    from iaglobal.observability.semaphore_tracker import get_semaphore_tracker

    st = get_semaphore_tracker()
    st.record_starvation(
        node_id="test",
        candidates=[_STARVATION_MODEL],
        retry_rounds=3,
    )
    mm = st.get_metrics(_STARVATION_MODEL)
    assert mm.starvations == 1


async def test_starvation_multiplas_chamadas_acumulam():
    from iaglobal.observability.semaphore_tracker import get_semaphore_tracker

    st = get_semaphore_tracker()
    model = "ollama/test-starvation-accum:latest"
    for i in range(5):
        st.record_starvation(
            node_id=f"test-{i}",
            candidates=[model],
            retry_rounds=3,
        )
    mm = st.get_metrics(model)
    assert mm.starvations == 5


async def test_starvation_health_report_expoe_contador():
    from iaglobal.observability.semaphore_tracker import get_semaphore_tracker

    st = get_semaphore_tracker()
    model = "ollama/test-starvation-report:latest"
    st.record_starvation(node_id="test", candidates=[model], retry_rounds=3)
    report = st.health_report()
    assert model in report
    assert report[model]["starvations"] == 1


# ── 6. INTEGRAÇÃO — BANDIT GENERATE COM SEMÁFOROS ────────────────────────────


async def _fake_route(
    model=None, prompt=None, task_type="general", node_id="provider_router"
):
    await asyncio.sleep(0.01)
    return "ok"


async def test_generate_com_semaphore_ollama(monkeypatch):
    import iaglobal.providers.provider_router as pr

    monkeypatch.setattr(pr, "async_route_generate", _fake_route)
    from iaglobal.graphs.bandit import _get_bandit

    bp = _get_bandit()
    result = await bp.generate(
        node_id="critic",
        prompt="test",
        candidates=[QWEN],
        task_type="general",
    )
    assert result == "ok"


async def test_generate_mantem_semaphore_integrity_apos_uso(monkeypatch):
    import iaglobal.providers.provider_router as pr

    monkeypatch.setattr(pr, "async_route_generate", _fake_route)
    from iaglobal.graphs.bandit import _get_bandit

    bp = _get_bandit()
    sem = await bp._get_model_semaphore(QWEN)
    initial = sem._value

    for i in range(10):
        result = await bp.generate(
            node_id="critic",
            prompt=f"test-{i}",
            candidates=[QWEN],
            task_type="general",
        )
        assert result == "ok"
    assert sem._value == initial, f"Semaphore vazou: {sem._value} != {initial}"


# ── 7. SEMÁFOROS COMPARTILHADOS (SINGLETON) ──────────────────────────────────


async def test_semaphore_compartilhado_entre_instancias():
    from iaglobal.graphs.bandit import BanditPolicy

    bp1 = BanditPolicy()
    bp2 = BanditPolicy()
    s1 = await bp1._get_model_semaphore(GLM4)
    s2 = await bp2._get_model_semaphore(GLM4)
    assert s1 is s2, "Semáforo deve ser compartilhado entre instâncias"
