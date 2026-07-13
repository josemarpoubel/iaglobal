# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do decorator @instrument do LifeSignalCollector."""

import pytest

from iaglobal.utils.life_signal_collector import instrument, collector


@pytest.fixture(autouse=True)
def _clear_signals():
    collector.clear()
    yield


async def test_instrument_records_life_signal_async():
    """@instrument registra life-signal após execução de função async."""
    calls = []

    @instrument(name="test.async_fn")
    async def my_async():
        calls.append(1)
        return 42

    result = await my_async()

    assert result == 42
    assert len(calls) == 1
    signals = collector.get_signals("test.async_fn")
    assert len(signals) == 1


def test_instrument_records_life_signal_sync():
    """@instrument registra life-signal após execução de função sync."""
    calls = []

    @instrument(name="test.sync_fn")
    def my_sync():
        calls.append(1)
        return "ok"

    result = my_sync()

    assert result == "ok"
    assert len(calls) == 1
    signals = collector.get_signals("test.sync_fn")
    assert len(signals) == 1


async def test_instrument_preserves_exception_async():
    """@instrument não suprime exceções em funções async."""

    @instrument(name="test.error_async")
    async def will_fail():
        raise ValueError("ops")

    with pytest.raises(ValueError, match="ops"):
        await will_fail()


def test_instrument_preserves_exception_sync():
    """@instrument não suprime exceções em funções sync."""

    @instrument(name="test.error_sync")
    def will_fail():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        will_fail()


async def test_instrument_preserves_metadata():
    """@instrument preserva __name__, __doc__, __module__ da função original."""

    @instrument(name="test.metadata")
    async def minha_funcao_async():
        """Documentação preservada."""
        return 1

    assert minha_funcao_async.__name__ == "minha_funcao_async"
    assert minha_funcao_async.__doc__ == "Documentação preservada."


def test_instrument_default_name_uses_qualname():
    """@instrument sem name explícito usa nome baseado no módulo."""

    @instrument()
    def my_func():
        return 1

    my_func()
    # Deve ter registrado com o nome gerado automaticamente
    all_signals = collector.get_all_signals()
    assert len(all_signals) == 1
    signal_name = list(all_signals.keys())[0]
    assert "my_func" in signal_name


async def test_instrument_failure_does_not_break_call():
    """Falha interna do decorator não quebra a função chamadora."""
    # Força falha no collector
    original_record = collector.record

    def broken_record(*args, **kwargs):
        raise RuntimeError("collector failure")

    collector.record = broken_record
    try:

        @instrument(name="test.broken")
        async def my_func():
            return 99

        result = await my_func()
        assert result == 99
    finally:
        collector.record = original_record


async def test_multiple_calls_accumulate_signals():
    """Múltiplas chamadas acumulam múltiplos life-signals."""

    @instrument(name="test.multi")
    async def multi():
        return 1

    for _ in range(5):
        await multi()

    signals = collector.get_signals("test.multi")
    assert len(signals) == 5


async def test_instrument_on_method():
    """@instrument funciona em método de classe."""

    class MyClass:
        @instrument(name="test.my_method")
        async def method(self):
            return "from method"

    obj = MyClass()
    result = await obj.method()
    assert result == "from method"
    signals = collector.get_signals("test.my_method")
    assert len(signals) == 1
