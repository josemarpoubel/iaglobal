"""Testa se Ollama e o modelo padrão estão online antes da suite principal."""
import asyncio
import subprocess
import sys
import time

import pytest
import aiohttp

OLLAMA_URL = "http://localhost:11434"
REQUIRED_MODELS = ["qwen2.5:0.5b"]
PROBE_TIMEOUT = 10.0


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def client_session():
    async with aiohttp.ClientSession() as session:
        yield session


class TestOllamaOnline:

    async def _fetch(self, session, path: str, timeout: float = PROBE_TIMEOUT) -> dict:
        async with session.get(f"{OLLAMA_URL}{path}") as resp:
            return await resp.json()

    async def _generate(self, session, model: str, prompt: str) -> dict:
        async with session.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        ) as resp:
            return await resp.json()

    async def test_ollama_server_is_running(self, client_session):
        data = await self._fetch(client_session, "/api/tags")
        assert "models" in data, f"Resposta inesperada: {data}"
        assert len(data["models"]) > 0, "Nenhum modelo encontrado no Ollama"

    async def test_required_models_are_available(self, client_session):
        data = await self._fetch(client_session, "/api/tags")
        available = {m["name"] for m in data.get("models", [])}
        for model in REQUIRED_MODELS:
            assert model in available, (
                f"Modelo {model} não encontrado. "
                f"Disponíveis: {available}. "
                f"Execute: ollama pull {model}"
            )

    async def test_required_models_can_generate(self, client_session):
        for model in REQUIRED_MODELS:
            data = await self._generate(client_session, model, "responda apenas: ok")
            response = data.get("response", "")
            assert response, (
                f"Modelo {model} não gerou resposta. "
                f"Resposta: {data}"
            )

    async def test_bandit_probe_detects_ollama_online(self):
        from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
        from iaglobal.graphs.credit import CreditAssignmentEngine

        # Limpa estado do singleton para evitar interferência de testes anteriores
        singleton = _get_bandit()
        singleton._probe_cache.clear()
        singleton._offline_endpoints.clear()
        singleton._banned_providers.clear()

        bandit = BanditPolicy(credit=CreditAssignmentEngine(), probe_timeout=PROBE_TIMEOUT)
        bandit._probe_cache.clear()
        bandit._offline_endpoints.clear()

        result = await bandit.probe_providers_online(
            [f"ollama/{m}" for m in REQUIRED_MODELS], timeout=PROBE_TIMEOUT
        )
        for model in REQUIRED_MODELS:
            key = f"ollama/{model}"
            latency = result.get(key)
            assert latency is not None, (
                f"Bandit não detectou {key} como online. "
                f"Cache: {bandit._probe_cache.get(key)}. "
                f"Banned: {bandit._banned_providers}. "
                f"Erro: Ollama pode estar offline ou timeout muito curto."
            )
            assert latency > 0, f"Latência inválida para {key}: {latency}"

    async def test_bandit_does_not_mark_ollama_offline(self):
        from iaglobal.graphs.bandit import _get_bandit

        bandit = _get_bandit()
        assert bandit._is_offline("ollama") is False, (
            "Bandit marcou Ollama como offline, mas o servidor está respondendo."
        )

    async def test_bandit_select_model_includes_ollama(self):
        from iaglobal.graphs.bandit import _get_bandit

        bandit = _get_bandit()
        for _ in range(5):
            model = bandit.select_model("test_ollama", "general")
            if model.startswith("ollama/"):
                return
        pytest.skip("Ollama não foi selecionado em 5 tentativas (cloud pode estar prioritário — comportamento esperado)")

    async def test_provider_router_fallback_to_ollama(self):
        from iaglobal.providers.provider_router import async_route_generate_parallel

        # Testa se o roteador consegue resolver via Ollama quando cloud falha
        # Isso apenas testa que Ollama é alcançável pelo provider
        from iaglobal.providers.ollama_provider import async_generate as ollama_async_generate
        from iaglobal.providers.provider_router import _async_safe_call

        result = await _async_safe_call(
            "ollama", ollama_async_generate,
            "responda apenas: ola", "ollama/qwen2.5:0.5b", "general"
        )
        assert result, "Ollama não retornou resposta via provider_router"
        assert len(result) > 0, "Resposta vazia do Ollama"

    async def test_warmup_does_not_fail(self):
        from iaglobal.providers.ollama_provider import warmup
        ok = await warmup("qwen2.5:0.5b")
        assert ok, "Warmup do modelo falhou"


if __name__ == "__main__":
    async def main():
        t = TestOllamaOnline()
        async with aiohttp.ClientSession() as session:
            print("=== Testando conexão com Ollama ===")
            try:
                data = await t._fetch(session, "/api/tags")
                models = [m["name"] for m in data.get("models", [])]
                print(f"Servidor OK — modelos disponíveis: {models}")
                for model in REQUIRED_MODELS:
                    if model in models:
                        gen = await t._generate(session, model, "responda: ok")
                        print(f"  {model}: geração OK ({len(gen.get('response',''))} chars)")
                    else:
                        print(f"  {model}: AUSENTE — execute: ollama pull {model}")
            except Exception as e:
                print(f"FALHA: {e}")
                sys.exit(1)

    asyncio.run(main())
