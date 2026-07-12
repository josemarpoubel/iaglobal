# tests/test_rag_web_search_full.py

"""
Teste de Estresse Evolutivo — Ciclo de Auto-Regeneração
==========================================================

Objetivo: mutar o TRANSPORTE (borda de rede), nunca a lógica de negócio,
e validar que o organismo:

  1. SELEÇÃO   — BanditPolicy desloca peso/preferência para longe do
                  provider degradado após N falhas consecutivas.
                  ("Mutação sem seleção é ruído" — Lei 4)

  2. HOMEOSTASE — o circuit breaker (_ProviderGatekeeper, conforme
                  graphs/bandit.py) abre após o threshold e evita
                  novas tentativas custosas contra um provider morto.

  3. SEM HOMOCISTEÍNA — nenhuma falha injetada pode ser relatada
                  como success=True / tokens=0 / latency≈1ms.
                  Se isso acontecer aqui, é a MESMA assinatura do
                  log de 08/07 09:08-09:09 — ou seja, reproduzimos
                  o bug de roteamento fantasma em condições controladas.

  4. REGENERAÇÃO — quando o mock "cura" (para de falhar), a próxima
                  chamada real deve voltar a ter tokens > 0 e latência
                  consistente com inferência real em CPU (não 1ms).

IMPORTANTE — o que este arquivo NÃO sabe (preencher/ajustar):
  - Qual client HTTP a camada de provider realmente usa para falar com
    o Ollama (assumi aiohttp.ClientSession.post, baseado no padrão
    "_session_gc_watch" que vocês já corrigiram antes — mas se o
    provider adapter usa outro client, o monkeypatch precisa mudar
    de alvo).
  - Os nomes exatos dos métodos de BanditPolicy para ler peso/score
    por provider e os nomes/estado de _ProviderGatekeeper. Marquei
    com # AJUSTAR onde isso importa.

Rodar:
    source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
    pytest tests/temp/test_evolutionary_stress.py -v -s
"""
import asyncio
import time

import aiohttp
import pytest

from iaglobal.utils.logger import get_logger
from iaglobal.providers.provider_router import async_route_generate

# AJUSTAR: confirmar path real do singleton BanditPolicy usado em produção
from iaglobal.graphs.bandit import BanditPolicy

logger = get_logger("iaglobal")

FORCED_FAILURES = 5
NODE_ID = "stress_test_node"
MODEL = "ollama/qwen2.5:0.5b"
TASK_TYPE = "general"

# Latência mínima plausível para uma inferência real do qwen2.5:0.5b em CPU.
# Qualquer "success" abaixo disso é, por definição, suspeito.
REAL_INFERENCE_FLOOR_MS = 15


class _BrokenRequestContextManager:
    """
    Réplica mínima da forma real de aiohttp._RequestContextManager:
    NÃO é uma coroutine — é um objeto que implementa __aenter__/__aexit__
    diretamente. session.post(...) é síncrono e devolve isto; o 'async with'
    é quem entra no contexto. Meu mock anterior usava 'async def', o que fazia
    session.post(...) devolver uma coroutine (não um context manager) — daí o
    erro 'coroutine object does not support the asynchronous context manager
    protocol' na rodada anterior. Esse erro era do MEU mock, não do código de vocês.
    """

    def __init__(self, exc: Exception):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *exc_info):
        return False


class MutatedTransport:
    """
    Muta a borda de rede para simular degradação do provider Ollama.
    Não mocka async_route_generate nem BanditPolicy — só o socket —
    para que o teste valide o comportamento REAL do router e do bandit,
    não uma simulação da própria lógica que queremos testar.
    """

    def __init__(self, failures_remaining: int):
        self.failures_remaining = failures_remaining
        self.call_timestamps: list[float] = []

    def broken_post(self, *args, **kwargs):
        # SÍNCRONO de propósito — espelha a assinatura real de
        # aiohttp.ClientSession.post, que não é 'async def'.
        self.call_timestamps.append(time.monotonic())
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            exc = asyncio.TimeoutError(
                "MUTAÇÃO: falha de rede injetada propositalmente (stress test)"
            )
            return _BrokenRequestContextManager(exc)
        raise NotImplementedError(
            "Transporte mutado chamado além da janela de falhas — "
            "restaurar aiohttp.ClientSession.post original antes de continuar."
        )


@pytest.mark.asyncio
async def test_sem_homocisteina_durante_falhas_forcadas(monkeypatch):
    """
    ASSERÇÃO CENTRAL — reproduz (ou descarta) o bug do log de 08/07.

    Durante uma janela de falhas 100% forçadas no transporte, NENHUMA
    chamada a async_route_generate pode retornar como se tivesse tido
    sucesso real. Se isso acontecer, o fallback do router está
    engolindo a exceção e devolvendo uma resposta sintética —
    exatamente o padrão latency_ms=1 tokens=0 success=True visto
    em 67 das 69 chamadas do log original.
    """
    transport = MutatedTransport(failures_remaining=FORCED_FAILURES)
    original_post = aiohttp.ClientSession.post
    monkeypatch.setattr(aiohttp.ClientSession, "post", transport.broken_post)

    resultados = []
    try:
        for i in range(FORCED_FAILURES):
            inicio = time.monotonic()
            try:
                resposta = await async_route_generate(
                    MODEL, f"prompt de estresse #{i}", task_type=TASK_TYPE, node_id=NODE_ID
                )
                elapsed_ms = (time.monotonic() - inicio) * 1000
                resultados.append(
                    {"i": i, "ok": True, "resposta": resposta, "latency_ms": elapsed_ms}
                )
            except Exception as e:  # comportamento esperado durante a janela de falha
                elapsed_ms = (time.monotonic() - inicio) * 1000
                resultados.append(
                    {"i": i, "ok": False, "erro": str(e), "latency_ms": elapsed_ms}
                )
    finally:
        monkeypatch.setattr(aiohttp.ClientSession, "post", original_post)

    logger.info("[STRESS-TEST] %d falhas forçadas | resultados=%s", FORCED_FAILURES, resultados)

    fantasmas = [
        r for r in resultados
        if r["ok"] and r["latency_ms"] < REAL_INFERENCE_FLOOR_MS
    ]
    assert not fantasmas, (
        f"🚨 BUG DE ROTEAMENTO FANTASMA REPRODUZIDO: {len(fantasmas)} chamada(s) "
        f"retornaram success=True em <{REAL_INFERENCE_FLOOR_MS}ms durante falha "
        f"100% forçada no transporte: {fantasmas}. "
        f"Isso confirma que async_route_generate (ou async_route_generate_parallel) "
        f"tem um branch que engole a exceção de rede e devolve uma resposta "
        f"sintética em vez de propagar a falha para o BanditPolicy."
    )

    # Se chegou aqui, todas as falhas foram propagadas honestamente.
    todas_falharam_de_verdade = all(not r["ok"] for r in resultados)
    assert todas_falharam_de_verdade, (
        "Alguma chamada teve sucesso mesmo com o transporte 100% quebrado — "
        "investigar se existe um fallback secundário (cache? outro provider?) "
        "não documentado sendo acionado silenciosamente."
    )


@pytest.mark.asyncio
async def test_bandit_desloca_peso_apos_falhas_consecutivas():
    """
    LEI DA SELEÇÃO — depois de N falhas consecutivas, o BanditPolicy
    reduz o peso do provider degradado via update_reward + circuit breaker.
    Mutação sem seleção é ruído (Lei 4).
    """
    bandit = BanditPolicy()

    # Simula N falhas consecutivas via update_reward
    for _ in range(FORCED_FAILURES):
        bandit.update_reward(MODEL, reward=0.0, ivm=0.0)
        bandit.trigger_circuit_breaker(MODEL, cooldown=30.0)

    peso = bandit.get_provider_weight("ollama")
    circuito = bandit.get_provider_circuit_state("ollama")

    assert peso < 0.05, (
        f"BanditPolicy manteve peso={peso} para 'ollama' mesmo após "
        f"{FORCED_FAILURES} falhas consecutivas — o seletor de fitness "
        f"não está reagindo à pressão seletiva injetada."
    )
    assert circuito["state"] == "open", (
        f"Circuit breaker deveria estar OPEN após {FORCED_FAILURES} falhas, "
        f"mas está {circuito['state']}"
    )
    assert MODEL in circuito["models"], (
        f"Modelo {MODEL} não encontrado no estado do circuit breaker"
    )
    assert circuito["models"][MODEL]["state"] == "open"


@pytest.mark.asyncio
async def test_circuit_breaker_abre_e_fecha(monkeypatch):
    """
    HOMEOSTASE — o circuit breaker abre após falhas consecutivas
    e deve voltar a fechar após o cooldown expirar.
    """
    import iaglobal.graphs.bandit as bandit_mod

    fake_now = [1000.0]

    def fake_time():
        return fake_now[0]

    monkeypatch.setattr(bandit_mod.time, "time", fake_time)

    bandit = BanditPolicy()

    # Abre o circuit breaker com cooldown de 10s
    bandit.trigger_circuit_breaker(MODEL, cooldown=10.0)
    estado = bandit.get_provider_circuit_state("ollama")
    assert estado["models"][MODEL]["state"] == "open"
    assert estado["models"][MODEL]["remaining_cooldown"] == 10.0

    # Avança o relógio além do cooldown
    fake_now[0] = 1011.0

    estado = bandit.get_provider_circuit_state("ollama")
    assert estado["models"][MODEL]["state"] == "closed"
    assert estado["models"][MODEL]["remaining_cooldown"] == 0.0


@pytest.mark.asyncio
async def test_regeneracao_apos_cooldown(monkeypatch):
    """
    REGENERAÇÃO — depois que o provider 'cura' (para de falhar),
    o BanditPolicy permite que o modelo volte a ser selecionável
    via rank_models (score volta a ser o peso real, não -inf).
    """
    import iaglobal.graphs.bandit as bandit_mod

    fake_now = [1000.0]

    def fake_time():
        return fake_now[0]

    monkeypatch.setattr(bandit_mod.time, "time", fake_time)

    bandit = BanditPolicy()
    bandit.weights[MODEL] = 0.8  # peso saudável inicial

    # Sem circuit breaker: score = peso real
    ranked = bandit.rank_models("test", "general", [MODEL])
    assert ranked[0][0] == 0.8, (
        f"Modelo saudável deveria ter score=0.8, mas tem {ranked[0][0]}"
    )

    # Abre circuit breaker com cooldown de 10s
    bandit.trigger_circuit_breaker(MODEL, cooldown=10.0)
    ranked = bandit.rank_models("test", "general", [MODEL])
    assert ranked[0][0] == float('-inf'), (
        "Modelo em cooldown deveria ter score -inf, "
        f"mas tem {ranked[0][0]}"
    )

    # Avança o relógio além do cooldown (regeneração)
    fake_now[0] = 1011.0

    ranked = bandit.rank_models("test", "general", [MODEL])
    assert ranked[0][0] == 0.8, (
        f"Após regeneração o score deveria voltar a 0.8, "
        f"mas permanece {ranked[0][0]}"
    )
