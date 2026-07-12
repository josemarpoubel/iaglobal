#!/usr/bin/env python3
"""
iaglobal — Smoke Test
======================
Verifica se o ambiente está funcional após clonar/migrar de PC.

Uso:
    source venv/bin/activate
    python scripts/smoke_test.py

Retorna código 0 se tudo OK, 1 se houver falhas.
"""

import importlib
import subprocess
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0
SKIP = 0


def heading(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check(name: str, result: bool, detail: str = ""):
    global PASS, FAIL
    if result:
        PASS += 1
        print(f"  ✅  {name}")
    else:
        FAIL += 1
        print(f"  ❌  {name}" + (f"  — {detail}" if detail else ""))


def check_skip(name: str, detail: str = ""):
    global SKIP
    SKIP += 1
    print(f"  ⏭️  {name}" + (f"  — {detail}" if detail else ""))


# ── 1. Python & Environment ──────────────────────────────────────────────

heading("1. Python & Ambiente")

check("Python >= 3.10", sys.version_info >= (3, 10), sys.version)

venv_active = hasattr(sys, "real_prefix") or (
    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
)
check("Virtualenv ativo", venv_active)

pip_ok = subprocess.run(
    [sys.executable, "-m", "pip", "--version"], capture_output=True, text=True
)
check("pip funcional", pip_ok.returncode == 0)

# ── 2. Dependências instaladas ──────────────────────────────────────────

heading("2. Dependências (pip install -e .)")

try:
    import iaglobal  # noqa
    check("Pacote iaglobal instalado", True)
except ImportError:
    check("Pacote iaglobal instalado", False, "rode: pip install -e .")

CORE_DEPS = [
    "aiohttp",
    "httpx",
    "pytest",
    "asyncio",
    "mcp",
    "cbor2",
    "deepdiff",
    "fastembed",
    "jsonschema",
    "openai",
    "dotenv",
    "watchdog",
]

for dep in CORE_DEPS:
    try:
        importlib.import_module(dep)
        check(f"  {dep}", True)
    except ImportError:
        check(f"  {dep}", False, "pip install")

# ── 3. Import tree crítica ──────────────────────────────────────────────

heading("3. Import tree crítica")

CRITICAL_MODULES = [
    "iaglobal.core.env_loader",
    "iaglobal.utils.logger",
    "iaglobal.cli.bootstrap",
    "iaglobal.cli.main",
    "iaglobal.cli.status",
    "iaglobal.graphs.credit",
    "iaglobal.graphs.bandit",
    "iaglobal.events.replay",
    "iaglobal.core.orchestrator",
    "iaglobal.providers.provider_metrics",
    "iaglobal.memory.db_manager",
    "iaglobal.security.sandbox_rules",
]

for mod in CRITICAL_MODULES:
    try:
        importlib.import_module(mod)
        check(f"  {mod}", True)
    except Exception as e:
        check(f"  {mod}", False, str(e).splitlines()[0])

# ── 4. Subsystems (immunity, genesis, evolution) ──────────────────────

heading("4. Subsistemas (imunidade, gênese, evolução)")

SUBSYSTEMS = [
    "iaglobal.immunity.mhc_detector",
    "iaglobal.immunity.pathogen_analyzer",
    "iaglobal.immunity.epigenetic_masking",
    "iaglobal.immunity.apoptosis_engine",
    "iaglobal.immunity.immune_orchestrator",
    "iaglobal.immunity.adaptive_threat_detector",
    "iaglobal.immunity.immune_memory_exchange",
    "iaglobal.immunity.metabolic_pruner",
    "iaglobal.genesis.verifygenesis",
    "iaglobal.genesis.identity",
    "iaglobal.evolution.metabolism.opportunity_cost_detector",
    "iaglobal.evolution.metacognition.evaluator",
]

for mod in SUBSYSTEMS:
    try:
        importlib.import_module(mod)
        check(f"  {mod}", True)
    except Exception as e:
        check(f"  {mod}", False, str(e).splitlines()[0])

# ── 5. API initialization (sync + async) ────────────────────────────────

heading("5. API IAGlobalAPI (inicialização)")

try:
    from iaglobal.api import IAGlobalAPI

    # Sync init (fora de event loop)
    api_sync = IAGlobalAPI()
    status = api_sync.get_status()
    check("IAGlobalAPI sync init", bool(status))
    check("  get_status retornou dict", isinstance(status, dict))

    insights = api_sync.get_insights(limit=2)
    check("  get_insights retornou list", isinstance(insights, list))

    scripts = api_sync.list_scripts()
    check("  list_scripts retornou list", isinstance(scripts, list))
except Exception as e:
    check("IAGlobalAPI sync init", False, str(e).splitlines()[0])

# ── 6. MCP tools (async) ────────────────────────────────────────────────

heading("6. MCP Tools (chamadas async)")

try:
    import asyncio

    async def test_mcp_tools():
        from iaglobal.api import IAGlobalAPI
        api = IAGlobalAPI(lazy_init=True)
        await api.initialize_async()
        check("MCP: initialize_async", True)

        status = api.get_status()
        check("MCP: get_status", bool(status))

        # Test orchestrator property
        orch = api.orchestrator
        check("MCP: orchestrator acessível", orch is not None)

    asyncio.run(test_mcp_tools())
except Exception as e:
    check("MCP tools async", False, str(e).splitlines()[0])

# ── 7. CLI entry points existem ─────────────────────────────────────────

heading("7. Entry points (CLI)")

CLI_COMMANDS = [
    ("iaglobal", "iaglobal.cli.main:main"),
    ("evolution-lab", "iaglobal.cli.evolution_lab:run_evolution_lab"),
    ("life-signals", "iaglobal.cli.life_signals:main"),
]

for name, ep in CLI_COMMANDS:
    mod_path, func_name = ep.split(":")
    try:
        mod = importlib.import_module(mod_path)
        func = getattr(mod, func_name, None)
        check(f"  {name} → {ep}", func is not None and callable(func))
    except Exception as e:
        check(f"  {name} → {ep}", False, str(e).splitlines()[0])

# ── 8. MCP Server import ────────────────────────────────────────────────

heading("8. MCP Server (FastMCP)")

try:
    from iaglobal.api.mcp_server import mcp
    check("MCP Server (FastMCP) instanciado", mcp is not None)
    tools_list = mcp._tool_manager._tools if hasattr(mcp, "_tool_manager") else []
    n_tools = len(tools_list) if tools_list else "N/A"
    check("  Ferramentas registradas", n_tools != "N/A" and n_tools > 0, str(n_tools))
except Exception as e:
    check("MCP Server", False, str(e).splitlines()[0])

# ── 9. Paths essenciais ─────────────────────────────────────────────────

heading("9. Diretórios essenciais")

ESSENTIAL_DIRS = [
    "iaglobal",
    "iaglobal/core",
    "iaglobal/cli",
    "iaglobal/graphs",
    "iaglobal/graphs/nodes",
    "iaglobal/api",
    "iaglobal/immunity",
    "iaglobal/genesis",
    "iaglobal/evolution",
    "iaglobal/evolution/metabolism",
    "iaglobal/evolution/metacognition",
    "iaglobal/memory",
    "iaglobal/providers",
    "iaglobal/security",
    "iaglobal/utils",
]

for d in ESSENTIAL_DIRS:
    p = ROOT / d
    check(f"  {d}/", p.is_dir())

# ── 10. Report ──────────────────────────────────────────────────────────

heading("RESUMO")
total = PASS + FAIL + SKIP
print(f"  ✅  Pass: {PASS}")
print(f"  ❌  Fail: {FAIL}" + ("  ⚠️  Reveja as falhas acima" if FAIL else ""))
print(f"  ⏭️  Skip: {SKIP}")
print(f"  ──────────")
print(f"  Total: {total}")
print()

if FAIL > 0:
    print("  ❌  ALGUMAS VERIFICAÇÕES FALHARAM — revise os detalhes acima.")
    sys.exit(1)
else:
    print("  ✅  TODAS AS VERIFICAÇÕES PASSARAM — iaglobal está pronto!")
    sys.exit(0)
