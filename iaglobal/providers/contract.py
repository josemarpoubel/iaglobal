# iaglobal/providers/contract.py
# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger("iaglobal.providers.contract")


@dataclass
class GenerateResult:
    success: bool
    text: str = ""
    error: str = ""
    latency_ms: float = 0.0
    model: str = ""
    provider: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    async def async_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout: int = 120,
        **kwargs: Any,
    ) -> str: ...

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout: int = 120,
        **kwargs: Any,
    ) -> str: ...

    async def warmup(self, model: Optional[str] = None) -> bool: ...


@dataclass
class ProviderEntry:
    name: str
    generate: Callable
    async_generate: Callable
    warmup: Optional[Callable] = None


class LLMProviderRegistry:
    """Registry de LLM Providers (Groq, NVIDIA, Ollama, Gemini, etc.).

    Responsável por registrar e recuperar provedores de modelo de linguagem.
    Cada provider expõe generate(), async_generate() e opcionalmente warmup().
    """

    def __init__(self) -> None:
        self._entries: dict[str, ProviderEntry] = {}

    def register_funcs(
        self,
        name: str,
        generate: Callable,
        async_generate: Callable,
        warmup: Optional[Callable] = None,
    ) -> None:
        self._entries[name] = ProviderEntry(
            name=name,
            generate=generate,
            async_generate=async_generate,
            warmup=warmup,
        )

    def register(self, name: str, provider: LLMProvider) -> None:
        self._entries[name] = ProviderEntry(
            name=name,
            generate=provider.generate,
            async_generate=provider.async_generate,
            warmup=getattr(provider, "warmup", None),
        )

    def get(self, name: str) -> Optional[ProviderEntry]:
        return self._entries.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._entries.keys())

    @property
    def sync(self) -> dict[str, Callable]:
        return {n: e.generate for n, e in self._entries.items()}

    @property
    def async_(self) -> dict[str, Callable]:
        return {n: e.async_generate for n, e in self._entries.items()}

    async def warmup_all(self, timeout: int = 120) -> dict[str, bool]:
        """Dispara warmup de todos os providers registrados em paralelo.

        Providers sem warmup são ignorados. Falhas são logadas como warning
        — nunca bloqueiam o startup.  Retorna dict[nome_provider → True/False].
        """
        results: dict[str, bool] = {}

        async def _warm_one(name: str, entry: ProviderEntry) -> tuple[str, bool]:
            fn = entry.warmup
            if fn is None:
                return name, True
            try:
                if asyncio.iscoroutinefunction(fn):
                    ok = await asyncio.wait_for(fn(), timeout=timeout)
                else:
                    ok = await asyncio.to_thread(fn)
                return name, bool(ok)
            except asyncio.TimeoutError:
                logger.warning("[WARMUP] %s timeout (%ds)", name, timeout)
                return name, False
            except Exception as exc:
                logger.warning("[WARMUP] %s falhou: %s", name, exc)
                return name, False

        tasks = [
            _warm_one(name, entry)
            for name, entry in self._entries.items()
            if entry.warmup is not None
        ]
        if not tasks:
            return results

        for name, ok in await asyncio.gather(*tasks):
            results[name] = ok
        return results


class ProviderRegistry(LLMProviderRegistry):
    """
    Alias de compatibilidade temporária.

    DEPRECATED: Use LLMProviderRegistry diretamente.
    Será removido na versão 2.0.
    """

    pass


llm_provider_registry = LLMProviderRegistry()

registry = llm_provider_registry
