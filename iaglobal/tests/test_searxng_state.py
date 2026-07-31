# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_searxng_state.py — Testes do estado REAL do SearXNG no iaglobal.

Contexto arquitetural (verificado em 2026-07-31):
    O SearXNG está integrado ao pipeline de busca em dois pontos:
      1. no_search.py — `searxng` é uma fonte ativa em SOURCES (com circuit
         breaker próprio: offline → retorna "" sem tocar rede).
      2. _search_router.py — queries de conhecimento geral (sem categoria
         especializada) caem em `_general_knowledge_search` → searxng_search().

    Operacionalmente, o SearXNG é levantado pelo CLI (`_ensure_searxng`) e
    configurado via ProviderConfig.SEARXNG_URL (env SEARXNG_URL, default :8005).

Cobertura:
    - Configuração: ProviderConfig.SEARXNG_URL carregada corretamente.
    - Unit: searxng_search() com sucesso mockado, circuit breaker, TTL.
    - Integração: pipeline e router invocam searxng_search() durante execução.
    """

import json
import time
from unittest import mock

import pytest

from iaglobal.graphs.nodes import _search_sources as ss
from iaglobal.providers import provider_config as pc


# ---------------------------------------------------------------------------
# 1. Configuração — CLI / provider_config → SEARXNG_URL
# ---------------------------------------------------------------------------


class TestConfigSearxng:
    def test_default_url_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("SEARXNG_URL", raising=False)
        # zera cache da metaclass para reler do env
        pc._ENV_CACHE.pop("SEARXNG_URL", None)
        assert pc.ProviderConfig.SEARXNG_URL == "http://localhost:8005"

    def test_url_from_env(self, monkeypatch):
        monkeypatch.setenv("SEARXNG_URL", "http://searxng.internal:8888")
        pc._ENV_CACHE.pop("SEARXNG_URL", None)
        assert pc.ProviderConfig.SEARXNG_URL == "http://searxng.internal:8888"

    def test_search_sources_reads_same_env(self, monkeypatch):
        monkeypatch.setenv("SEARXNG_URL", "http://127.0.0.1:9000")
        assert ss._searxng_base_url() == "http://127.0.0.1:9000"

    def test_default_base_url_in_sources(self, monkeypatch):
        monkeypatch.delenv("SEARXNG_URL", raising=False)
        assert ss._searxng_base_url() == "http://localhost:8005"


# ---------------------------------------------------------------------------
# 2. Unit — searxng_search() com circuit breaker
# ---------------------------------------------------------------------------


class TestSearxngSearchUnit:
    @pytest.fixture(autouse=True)
    def _reset_state(self):
        ss._reset_searxng_state()
        yield
        ss._reset_searxng_state()

    def test_success_formats_results(self):
        fake_data = {
            "results": [
                {
                    "title": "Alpha",
                    "url": "https://alpha.example",
                    "content": "Conteúdo sobre alpha",
                    "engine": "google",
                },
                {
                    "title": "Beta",
                    "url": "https://beta.example",
                    "content": "Conteúdo sobre beta",
                    "engine": "bing",
                },
            ]
        }

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(fake_data).encode()

        with mock.patch(
            "urllib.request.urlopen", return_value=_FakeResp()
        ) as m_urlopen:
            result = ss.searxng_search("python asyncio")

        assert "Alpha" in result
        assert "https://alpha.example" in result
        assert "[google]" in result
        assert ss._searxng_fail_count == 0
        assert m_urlopen.call_count == 1

    def test_empty_results_returns_empty_string(self):
        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"results": []}).encode()

        with mock.patch("urllib.request.urlopen", return_value=_FakeResp()):
            assert ss.searxng_search("nada") == ""

    def test_failure_triggers_circuit_breaker(self):
        with mock.patch(
            "urllib.request.urlopen", side_effect=OSError("conexão recusada")
        ):
            assert ss.searxng_search("query") == ""

        assert ss._searxng_fail_count == 1
        assert ss._searxng_offline_until > time.monotonic()

    def test_circuit_breaker_skips_network_when_offline(self):
        # Primeira falha marca offline
        with mock.patch(
            "urllib.request.urlopen", side_effect=OSError("recusada")
        ):
            ss.searxng_search("q1")

        # Segunda chamada dentro do TTL não deve tentar rede
        with mock.patch(
            "urllib.request.urlopen", side_effect=AssertionError("rede não deve ser tocada")
        ):
            assert ss.searxng_search("q2") == ""

    def test_success_after_failure_resets_state(self):
        # Falha → estado offline
        with mock.patch("urllib.request.urlopen", side_effect=OSError("recusada")):
            ss.searxng_search("q1")
        assert ss._searxng_fail_count == 1

        # Expira o circuit breaker (simula TTL decorrido) mantendo o contador
        ss._searxng_offline_until = 0.0

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"results": [{"title": "T", "url": "http://u", "content": "c"}]}).encode()

        with mock.patch("urllib.request.urlopen", return_value=_FakeResp()):
            ss.searxng_search("q2")
        assert ss._searxng_fail_count == 0
        assert ss._searxng_offline_until == 0.0

    def test_ttl_progressivo_apos_multiplas_falhas(self):
        # Falhas consecutivas só ocorrem quando o breaker expira entre tentativas
        for _ in range(4):
            with mock.patch("urllib.request.urlopen", side_effect=OSError("recusada")):
                ss._searxng_offline_until = 0.0  # expira TTL, contador persiste
                ss.searxng_search("q")

        assert ss._searxng_fail_count >= 3
        assert ss._searxng_ttl() == 300.0


# ---------------------------------------------------------------------------
# 3. Integração — o pipeline usa SearXNG como fonte (comportamental)
# ---------------------------------------------------------------------------


class TestPipelineUsesSearxng:
    """Integração comportamental: `Pipeline → SearchRouter → SearXNG`.

    Verifica que o pipeline e o router invocam `searxng_search` durante a
    execução real (com as demais fontes desabilitadas / query sem categoria).
    """

    @pytest.mark.asyncio
    async def test_pipeline_invokes_searxng_search_during_execution(self, monkeypatch):
        from iaglobal.graphs.nodes import _search_sources
        from iaglobal.graphs.nodes import no_search

        async def _skip_all_but_searxng():
            # Skip de todas as fontes atuais; só 'searxng' roda.
            return {name for name, _, _ in no_search.SOURCES if name != "searxng"}

        # Sem disco e sem rede nas demais fontes — teste rápido e determinístico
        monkeypatch.setattr(no_search, "load_search", lambda *a, **k: None)
        monkeypatch.setattr(no_search, "save_search", lambda *a, **k: None)
        monkeypatch.setattr(no_search, "get_search_skip_list", _skip_all_but_searxng)

        ctx = {"input": {"task": "python asyncio tutorial"}}
        with mock.patch.object(
            _search_sources, "searxng_search", return_value="resultado searxng " * 10
        ) as m_searxng:
            await no_search.run_search(ctx)

        m_searxng.assert_called()

    @pytest.mark.asyncio
    async def test_search_router_invokes_searxng_for_general_knowledge(self):
        from iaglobal.graphs.nodes import _search_router
        from iaglobal.graphs.nodes import _search_sources

        # Query genérica (sem categoria especializada) deve cair no SearXNG
        with mock.patch.object(
            _search_sources, "searxng_search", return_value="resultado searxng " * 10
        ) as m_searxng:
            out = await _search_router.run_search_router("python asyncio tutorial")

        m_searxng.assert_called()
        # Observabilidade: resultado rotulado com o header canônico de fonte
        assert "=== SEARXNG ===" in out

    def test_specialized_queries_skip_searxng_fallback(self):
        """Queries com categoria especializada NÃO caem no fallback SearXNG."""
        from iaglobal.graphs.nodes import _search_router
        from iaglobal.graphs.nodes import _search_sources

        with mock.patch.object(
            _search_sources, "searxng_search", return_value="resultado searxng " * 10
        ) as m_searxng:
            sources = _search_router.classify_task("clima temperatura cidade")
            assert sources, "categoria 'clima' deveria classificar a query"
            assert not m_searxng.called
            assert len(sources) == 1
            assert sources[0][0] == "clima_weather"
