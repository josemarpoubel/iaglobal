# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

import asyncio

import pytest

from iaglobal.providers.contract import ProviderRegistry


@pytest.fixture
def reg():
    return ProviderRegistry()


@pytest.mark.asyncio
async def test_warmup_all_empty(reg: ProviderRegistry):
    results = await reg.warmup_all()
    assert results == {}


@pytest.mark.asyncio
async def test_warmup_all_all_succeed(reg: ProviderRegistry):
    async def _hot() -> bool:
        return True

    reg.register_funcs(
        "alpha", generate=lambda p: p, async_generate=lambda p: p, warmup=_hot
    )
    reg.register_funcs(
        "beta", generate=lambda p: p, async_generate=lambda p: p, warmup=_hot
    )
    results = await reg.warmup_all()
    assert results == {"alpha": True, "beta": True}


@pytest.mark.asyncio
async def test_warmup_all_mixed(reg: ProviderRegistry):
    async def _ok() -> bool:
        return True

    async def _fail() -> bool:
        return False

    reg.register_funcs(
        "ok", generate=lambda p: p, async_generate=lambda p: p, warmup=_ok
    )
    reg.register_funcs(
        "fail", generate=lambda p: p, async_generate=lambda p: p, warmup=_fail
    )
    results = await reg.warmup_all()
    assert results == {"ok": True, "fail": False}


@pytest.mark.asyncio
async def test_warmup_all_exception_is_false(reg: ProviderRegistry):
    async def _boom() -> bool:
        raise RuntimeError("no network")

    reg.register_funcs(
        "unstable", generate=lambda p: p, async_generate=lambda p: p, warmup=_boom
    )
    results = await reg.warmup_all()
    assert results == {"unstable": False}


@pytest.mark.asyncio
async def test_warmup_all_timeout_returns_false(reg: ProviderRegistry):
    async def _slow() -> bool:
        await asyncio.sleep(3600)
        return True

    reg.register_funcs(
        "glacial", generate=lambda p: p, async_generate=lambda p: p, warmup=_slow
    )
    results = await reg.warmup_all(timeout=0.01)
    assert results == {"glacial": False}


@pytest.mark.asyncio
async def test_warmup_ignores_providers_without_warmup(reg: ProviderRegistry):
    async def _hot() -> bool:
        return True

    reg.register_funcs(
        "has_warmup", generate=lambda p: p, async_generate=lambda p: p, warmup=_hot
    )
    reg.register_funcs("no_warmup", generate=lambda p: p, async_generate=lambda p: p)
    results = await reg.warmup_all()
    assert results == {"has_warmup": True}


@pytest.mark.asyncio
async def test_warmup_parallel(reg: ProviderRegistry):
    order: list[str] = []

    async def _slow_a() -> bool:
        await asyncio.sleep(0.05)
        order.append("a")
        return True

    async def _slow_b() -> bool:
        await asyncio.sleep(0.02)
        order.append("b")
        return True

    reg.register_funcs(
        "a", generate=lambda p: p, async_generate=lambda p: p, warmup=_slow_a
    )
    reg.register_funcs(
        "b", generate=lambda p: p, async_generate=lambda p: p, warmup=_slow_b
    )
    results = await reg.warmup_all(timeout=10)
    assert results == {"a": True, "b": True}
    assert order == ["b", "a"], "b (0.02s) deve completar antes de a (0.05s)"
