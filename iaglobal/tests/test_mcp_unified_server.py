# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_mcp_unified_server.py — Testes unitários do iaglobal/mcp/server.py (unified).

Cobre o contrato definido no AGENTS.md:
    1. Tools canônicas registradas no FastMCP (sem depender de subprocess).
    2. Padrão lazy: get_status responde BOOTING antes do Phase2 sem chamar _ensure_full.
    3. Helpers obrigatórios: _ensure_phase1 / _ensure_full / _ready / _boot_snapshot.
    4. Singleton lock do bootstrap (uma única task de Phase2).
    5. Sincronização IAGlobalAPI em _ensure_full (_initialized).

Não sobe subprocess — usa monkeypatch no singleton bootstrap.
"""

import pytest

from iaglobal.mcp import server as server_module
from iaglobal.cli import bootstrap as bootstrap_module


CANONICAL_TOOLS = {
    "metabolic_audit",
    "get_ivm",
    "run_task",
    "get_status",
    "get_system_health",
    "get_bandit_scores",
    "get_provider_metrics",
    "get_model_metrics",
    "get_insights",
    "list_scripts",
    "get_history",
    "get_execution_history",
    "evolution_status",
    "evolve_strategy",
    "evolution_dashboard",
    "web_search",
    "web_fetch",
    "read_file",
    "write_file",
    "list_dir",
    "execute_code",
    "reflexion_fix",
    "reflexion_loop",
    "get_error_history",
}


def _reset_bootstrap(bootstrap):
    bootstrap._phase1_done = False
    bootstrap._phase2_done = False
    bootstrap._phase2_task = None
    bootstrap._phase2_progress = {}


# ---------------------------------------------------------------------------
# Tools canônicas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonical_tools_registered():
    tools = await server_module.mcp.list_tools()
    names = {t.name for t in tools}
    missing = CANONICAL_TOOLS - names
    assert not missing, f"tools canônicas ausentes: {missing}"
    assert len(names) >= len(CANONICAL_TOOLS)


@pytest.mark.asyncio
async def test_fastmcp_instance_not_placeholder():
    assert type(server_module.mcp).__name__ == "FastMCP"


# ---------------------------------------------------------------------------
# Padrão lazy — BOOTING antes do Phase2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_booting_before_phase2(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True
    b._phase2_done = False
    b._phase2_progress = {"memory": "running", "evolution": "pending"}
    monkeypatch.setattr(b, "ensure_phase1", _async_noop)
    monkeypatch.setattr(server_module, "_ensure_full", _fail_if_called)

    out = await server_module.mcp.call_tool("get_status", {})
    text = str(out)
    assert "phase1_done" in text
    assert "phase2_running" in text
    assert "running" in text


@pytest.mark.asyncio
async def test_get_status_does_not_ensure_full_when_booting(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True
    b._phase2_done = False
    monkeypatch.setattr(b, "ensure_phase1", _async_noop)
    monkeypatch.setattr(server_module, "_ensure_full", _fail_if_called)
    monkeypatch.setattr(server_module, "_get_api", _fail_if_called)

    out = await server_module.mcp.call_tool("get_status", {})
    assert "⚡" in str(out) or "phase1_done" in str(out)


# ---------------------------------------------------------------------------
# Helpers obrigatórios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ready_reflects_phase2_done(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase2_done = False
    assert server_module._ready() is False
    b._phase2_done = True
    assert server_module._ready() is True


@pytest.mark.asyncio
async def test_boot_snapshot_delegates_to_bootstrap(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True
    b._phase2_done = False
    b._phase2_progress = {"x": "ok"}

    snap = server_module._boot_snapshot()
    assert snap["phase1_done"] is True
    assert snap["phase2_done"] is False
    assert "phase2_steps" in snap
    assert "phase2_elapsed_seconds" in snap
    assert "phase2_running" in snap
    assert "current_phase" in snap


@pytest.mark.asyncio
async def test_ensure_phase1_idempotente(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    calls = []
    monkeypatch.setattr(b, "ensure_phase1", _make_async_counter(calls))

    await server_module._ensure_phase1()
    await server_module._ensure_phase1()
    assert len(calls) == 2  # delega ao bootstrap, que é idempotente internamente


@pytest.mark.asyncio
async def test_ensure_full_syncs_ia_global_api(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase2_done = True

    class _FakeOrch:
        pass

    class _FakeAPI:
        def __init__(self):
            self._initialized = False
            self._orchestrator = None

    fake_api = _FakeAPI()
    monkeypatch.setattr(b, "initialize", _make_async_return(_FakeOrch()))
    monkeypatch.setattr(server_module, "_get_api", lambda: fake_api)

    orch = await server_module._ensure_full()
    assert orch is not None
    assert fake_api._initialized is True
    assert fake_api._orchestrator is orch


@pytest.mark.asyncio
async def test_ensure_full_skips_resync_when_initialized(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase2_done = True

    class _FakeAPI:
        def __init__(self):
            self._initialized = True
            self._orchestrator = "keep-me"

    fake_api = _FakeAPI()
    monkeypatch.setattr(b, "initialize", _make_async_return("new-orch"))
    monkeypatch.setattr(server_module, "_get_api", lambda: fake_api)

    await server_module._ensure_full()
    assert fake_api._orchestrator == "keep-me"


# ---------------------------------------------------------------------------
# Singleton lock do bootstrap (_schedule_phase2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_phase2_single_task(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True

    async def _fake_phase2():
        pass

    monkeypatch.setattr(b, "_phase2", _fake_phase2)
    b._schedule_phase2()
    first = b._phase2_task
    assert first is not None
    assert b._phase2_schedule_count == 1

    b._schedule_phase2()
    assert b._phase2_task is first, "re-agendamento criaria task duplicada"
    assert b._phase2_schedule_count == 1

    await first
    b._phase2_done = True


@pytest.mark.asyncio
async def test_schedule_phase2_sets_progress_reset(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True

    async def _fake_phase2():
        pass

    monkeypatch.setattr(b, "_phase2", _fake_phase2)
    b._schedule_phase2()
    assert b._phase2_progress != {}
    assert b._phase2_task is not None
    await b._phase2_task


@pytest.mark.asyncio
async def test_phase2_completion_flips_done(monkeypatch):
    b = bootstrap_module.bootstrap
    _reset_bootstrap(b)
    b._phase1_done = True
    b.initialized = False

    async def _fake_phase2():
        pass

    monkeypatch.setattr(b, "_phase2", _fake_phase2)
    b._schedule_phase2()
    await b._phase2_task
    assert b._phase2_done is True
    assert b.initialized is True


# ---------------------------------------------------------------------------
# Singletons do server
# ---------------------------------------------------------------------------


def test_server_singletons_initialized_none():
    assert server_module._agent is None
    assert server_module._api is None
    assert server_module._web_search is None
    assert server_module._file_system is None
    assert server_module._code_exec is None


def test_get_api_returns_lazy_ia_global_api(monkeypatch):
    created = []

    class _FakeIAGlobalAPI:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(server_module, "IAGlobalAPI", _FakeIAGlobalAPI)
    monkeypatch.setattr(server_module, "_api", None)

    api = server_module._get_api()
    assert api is not None
    assert created and created[0] == {"lazy_init": True}


# ---------------------------------------------------------------------------
# Helpers síncronos
# ---------------------------------------------------------------------------


async def _async_noop():
    return None


def _make_async_counter(calls: list):
    async def _counter():
        calls.append(1)

    return _counter


def _make_async_return(value):
    async def _fn():
        return value

    return _fn


async def _fail_if_called(*args, **kwargs):
    raise AssertionError("não deveria ser chamado no caminho BOOTING")
