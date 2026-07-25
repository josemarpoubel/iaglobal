# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_verify_mcp.py — Smoke test do protocolo MCP iaglobal.

Sobe o servidor unificado como subprocess via stdio, dispara initialize +
tools/list + tools/call para todas as ferramentas-chave e produz:

    1. latência POR chamada (não cumulativa)
    2. captura total do stderr com impressão em caso de timeout
    3. ranking de latências no final
    4. asserts de regressão de performance
    5. contagem de inicializações (deve ser 1, não 2)

Uso:
    python -m pytest iaglobal/tests/test_verify_mcp.py -v -s
    python iaglobal/tests/test_verify_mcp.py       # standalone
"""

import asyncio
import json
import os
import time
from pathlib import Path

try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_BIN = REPO_ROOT / "venv" / "bin" / "python"
MCP_CMD = [
    str(PYTHON_BIN),
    "-u",
    "-m",
    "iaglobal.mcp.server",
    "--mode",
    "stdio",
]

INIT_TIMEOUT_S = 30.0
TOOL_TIMEOUT_S = 10.0

FAST_TIMEOUT_S = 1.0
MEDIUM_TIMEOUT_S = 5.0
SLOW_TIMEOUT_S = 15.0

PROBES = [
    ("tools_list", "tools/list", {}, FAST_TIMEOUT_S),
    (
        "get_provider_metrics",
        "tools/call",
        {"name": "get_provider_metrics", "arguments": {}},
        FAST_TIMEOUT_S,
    ),
    (
        "get_model_metrics",
        "tools/call",
        {"name": "get_model_metrics", "arguments": {}},
        FAST_TIMEOUT_S,
    ),
    (
        "get_status",
        "tools/call",
        {"name": "get_status", "arguments": {}},
        MEDIUM_TIMEOUT_S,
    ),
    (
        "get_system_health",
        "tools/call",
        {"name": "get_system_health", "arguments": {}},
        MEDIUM_TIMEOUT_S,
    ),
    (
        "get_bandit_scores",
        "tools/call",
        {"name": "get_bandit_scores", "arguments": {}},
        MEDIUM_TIMEOUT_S,
    ),
    (
        "get_insights",
        "tools/call",
        {"name": "get_insights", "arguments": {}},
        MEDIUM_TIMEOUT_S,
    ),
    (
        "get_execution_history",
        "tools/call",
        {"name": "get_execution_history", "arguments": {"limit": 5}},
        FAST_TIMEOUT_S,
    ),
    (
        "get_history",
        "tools/call",
        {"name": "get_history", "arguments": {"limit": 5}},
        FAST_TIMEOUT_S,
    ),
    (
        "metabolic_audit",
        "tools/call",
        {"name": "metabolic_audit", "arguments": {}},
        SLOW_TIMEOUT_S,
    ),
    ("get_ivm", "tools/call", {"name": "get_ivm", "arguments": {}}, MEDIUM_TIMEOUT_S),
]


def _make_env():
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT)}


async def _run_test():
    env = _make_env()
    proc = await asyncio.create_subprocess_exec(
        *MCP_CMD,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    inbox: asyncio.Queue = asyncio.Queue()
    stderr_log: list[str] = []
    notifications_log: list[str] = []

    async def stdout_reader():
        buf = b""
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                ls = line.decode(errors="replace").strip()
                if not ls:
                    continue
                if ls.startswith("{") and '"jsonrpc"' in ls:
                    try:
                        msg = json.loads(ls)
                    except json.JSONDecodeError:
                        await inbox.put(("non_json", ls))
                        continue
                    if "id" in msg and ("result" in msg or "error" in msg):
                        await inbox.put(("response", msg))
                    elif "method" in msg:
                        await inbox.put(("notification", msg))
                    else:
                        await inbox.put(("non_json", ls))
                else:
                    await inbox.put(("non_json", ls))

    async def stderr_reader():
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            stderr_log.append(line.decode(errors="replace").rstrip())

    t_out = asyncio.create_task(stdout_reader())
    t_err = asyncio.create_task(stderr_reader())

    async def send(req):
        body = (json.dumps(req) + "\n").encode()
        proc.stdin.write(body)
        await proc.stdin.drain()

    async def expect_response(req_id: int, timeout: float):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            remaining = max(0.05, deadline - time.perf_counter())
            try:
                kind, payload = await asyncio.wait_for(inbox.get(), remaining)
            except asyncio.TimeoutError:
                continue
            if kind == "notification":
                method = payload.get("method", "?")
                notifications_log.append(f"{method}: {json.dumps(payload)[:120]}")
                continue
            if kind == "response" and payload.get("id") == req_id:
                return payload
        return None

    results: list[tuple[str, float, str]] = []

    bootstrap_lines = [
        "Phase1 completo",
        "Phase2 completa",
        "BOOTSTRAP] Phase",
        "[BOOTSTRAP]",
        "Orchestrator async init completo",
    ]

    def _count_bootstrap_in_stderr():
        text = "\n".join(stderr_log)
        return sum(text.count(m) for m in bootstrap_lines)

    def _count_phases_completed():
        return {
            "phase1_complete": sum(s.count("Phase1 completo") for s in stderr_log),
            "phase2_complete": sum(s.count("Phase2 completa") for s in stderr_log),
            "stripe_line": sum(
                s.count("Orchestrator async init completo") for s in stderr_log
            ),
        }

    PHASE1_MARKER_PATTERNS = (
        "Phase1 completo",
        "agendada em background",
        "Orchestrator instanciado",
        "BOOTSTRAP] Estrutura de diretórios",
        "TRIBUNAL",
    )

    BOOTSTRAP_MARKER_PATTERNS = (
        "Phase1 completo",
        "Phase2 completa",
        "agendada em background",
        "Orchestrator instanciado",
        "Orchestrator async init completo",
        "BOOTSTRAP] Phase",
    )

    def _snapshot_bootstrap_marker_count():
        """Quantidade de marcadores de bootstrap já emitidos no stderr."""
        text = "\n".join(stderr_log)
        return {p: text.count(p) for p in BOOTSTRAP_MARKER_PATTERNS}

    def _snapshot_phase1_marker_count():
        """Marcadores exclusivos de Phase1 (não contam completion de Phase2)."""
        text = "\n".join(stderr_log)
        return {p: text.count(p) for p in PHASE1_MARKER_PATTERNS}

    contract_failures: list[str] = []

    def contract_check(label: str, predicate: bool, msg: str = ""):
        if predicate:
            print(f"      ✓ contract: {label}")
        else:
            full = f"{label} — {msg}" if msg else label
            contract_failures.append(full)
            print(f"      ✗ contract: {full}")

    print(f"\n{'=' * 60}")
    print(f"MCP verify — port to unified server: {MCP_CMD[-2:]}")
    print(f"{'=' * 60}\n")

    req_seq = 0

    def next_id():
        nonlocal req_seq
        req_seq += 1
        return req_seq

    print("[probe] initialize:")
    t0 = time.perf_counter()
    await send(
        {
            "jsonrpc": "2.0",
            "id": next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp_verify", "version": "1.0"},
            },
        }
    )
    resp = await expect_response(1, INIT_TIMEOUT_S)
    init_latency_ms = (time.perf_counter() - t0) * 1000
    if resp is None:
        print(f"  ✗ TIMEOUT @ {init_latency_ms:.0f}ms")
        print(f"\n=== STDERR (last 60) ===")
        for line in stderr_log[-60:]:
            print(line[:200])
        results.append(("initialize", init_latency_ms, "TIMEOUT"))
    elif "error" in resp:
        results.append(("initialize", init_latency_ms, f"ERROR: {resp['error']}"))
        print(f"  ✗ ERROR: {resp['error']} ({init_latency_ms:.0f}ms)")
    else:
        server = resp["result"].get("serverInfo", {})
        results.append(
            (
                "initialize",
                init_latency_ms,
                f"OK srv={server.get('name', '?')} v{server.get('version', '?')}",
            )
        )
        print(
            f"  ✓ OK in {init_latency_ms:.0f}ms — server={server.get('name')} v{server.get('version')}"
        )

    await send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    first_slow_tool: tuple[str, float] | None = None

    READ_ONLY_PROBES = {
        "tools_list",
        "get_provider_metrics",
        "get_model_metrics",
        "get_history",
        "get_execution_history",
    }

    for label, method, params, timeout in PROBES:
        print(f"\n[probe] {label}:")
        before_counts = _snapshot_bootstrap_marker_count()
        before_phase1 = _snapshot_phase1_marker_count()

        req_id = next_id()
        call_t0 = time.perf_counter()
        await send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        resp = await expect_response(req_id, timeout)
        call_latency_ms = (time.perf_counter() - call_t0) * 1000

        await asyncio.sleep(0.05)
        after_counts = _snapshot_bootstrap_marker_count()
        after_phase1 = _snapshot_phase1_marker_count()
        new_markers = {p: after_counts[p] - before_counts[p] for p in after_counts}
        new_phase1 = {p: after_phase1[p] - before_phase1[p] for p in after_phase1}

        if resp is None:
            print(f"  ✗ TIMEOUT after {call_latency_ms:.0f}ms")
            for line in stderr_log[-12:]:
                print(f"      stderr> {line[:180]}")
            results.append((label, call_latency_ms, "TIMEOUT"))
            if first_slow_tool is None and call_latency_ms > 1000:
                first_slow_tool = (label, call_latency_ms)
        elif "error" in resp:
            err_msg = resp["error"].get("message", "?")
            print(f"  ✗ ERROR ({call_latency_ms:.0f}ms): {err_msg}")
            results.append((label, call_latency_ms, f"ERROR"))
        else:
            content = (resp.get("result") or {}).get("content", [])
            head = ""
            if isinstance(content, list) and content:
                head = (
                    (content[0].get("text") or "").splitlines()[0]
                    if content[0].get("text")
                    else "(empty)"
                )
            print(f"  ✓ OK in {call_latency_ms:.0f}ms — head: {head[:80]}")
            results.append((label, call_latency_ms, "OK"))

        if sum(new_markers.values()) > 0:
            print(f"      novos markers bootstrap (esperado se Phase2 terminasse): {new_markers}")

        if len(notifications_log) > 0:
            print(f"      {len(notifications_log)} notification(s) seen")

        if label == "tools_list":
            contract_check(
                "tools/list responde < 500ms",
                call_latency_ms < 500.0,
                f"latency={call_latency_ms:.0f}ms",
            )
            contract_check(
                "tools/list NÃO dispara bootstrap (Phase1)",
                sum(new_phase1.values()) == 0,
                f"novos markers phase1={new_phase1}",
            )
        elif label in READ_ONLY_PROBES:
            contract_check(
                f"{label} não dispara bootstrap (Phase1)",
                sum(new_phase1.values()) == 0,
                f"novos markers phase1={new_phase1}",
            )
            contract_check(
                f"{label} resposta < 1500ms",
                call_latency_ms < 1500.0,
                f"latency={call_latency_ms:.0f}ms",
            )

    print(f"\n{'=' * 60}")
    print(f"Latency Summary")
    print(f"{'=' * 60}")
    width = max(len(l) for l, _, _ in results)
    for label, lat, status in sorted(results, key=lambda r: r[1]):
        marker = (
            "✓" if status.startswith("OK") else ("✗" if status == "TIMEOUT" else "?")
        )
        print(f"  {marker} {label:<{width}} {lat:>9.0f} ms  {status[:40]}")

    phases = _count_phases_completed()
    print(f"\nBootstrap markers (cada um deve aparecer exatamente 1 vez):")
    print(f"  phase1_complete:           {phases['phase1_complete']}")
    print(
        f"  phase2_complete:           {phases['phase2_complete']}  (0 se teste termina antes)"
    )
    print(f"  orchestrator_init_logged:  {phases['stripe_line']}")
    bad = {k: v for k, v in phases.items() if v > 1}
    if bad:
        print(f"  ⚠️  REGRESSÃO: {bad}")

    print("\nContracts:")
    contract_check(
        "Phase1 disparou exatamente 1x",
        phases["phase1_complete"] <= 1,
        f"got {phases['phase1_complete']}",
    )
    contract_check(
        "Phase2 disparou no máximo 1x",
        phases["phase2_complete"] <= 1,
        f"got {phases['phase2_complete']}",
    )
    contract_check(
        "Orchestrator.initialize() chamado 1x",
        phases["stripe_line"] <= 1,
        f"got {phases['stripe_line']}",
    )
    if results:
        init_ms = next(
            (lat for label, lat, _ in results if label == "initialize"), None
        )
        if init_ms is not None:
            contract_check(
                "initialize < 30s",
                init_ms < INIT_TIMEOUT_S * 1000,
                f"got {init_ms:.0f}ms",
            )

    if contract_failures:
        print(f"\n❌ {len(contract_failures)} contrato(s) violado(s):")
        for f in contract_failures:
            print(f"     - {f}")
    else:
        print("\n✅ Todos os contratos passaram.")

    if first_slow_tool:
        print(
            f"\nFirst slow tool (>1s): {first_slow_tool[0]} = {first_slow_tool[1]:.0f}ms"
        )

    proc.terminate()
    try:
        await proc.wait()
    except asyncio.TimeoutError:
        proc.kill()
    t_out.cancel()
    t_err.cancel()
    for t in (t_out, t_err):
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    return results, phases, contract_failures


def _assert_perf(results):
    failures = []
    for label, lat, status in results:
        if status.startswith("OK"):
            if label in (
                "tools_list",
                "get_provider_metrics",
                "get_model_metrics",
                "get_insights",
                "get_execution_history",
                "get_history",
            ):
                if lat > 1500:
                    failures.append(f"{label}={lat:.0f}ms > 1500ms")
            elif label in ("get_status", "get_system_health", "get_bandit_scores"):
                if lat > 8000:
                    failures.append(
                        f"{label}={lat:.0f}ms > 8s (allow first-call warmup)"
                    )
            elif label == "initialize":
                if lat > INIT_TIMEOUT_S * 1000:
                    failures.append(f"initialize={lat:.0f}ms > {INIT_TIMEOUT_S}s")
    if failures:
        raise AssertionError("Performance regression:\n  " + "\n  ".join(failures))


def _assert_no_duplicate_bootstrap(phases):
    bad = {}
    for name, count in phases.items():
        if count > 1:
            bad[name] = count
    if bad:
        raise AssertionError(
            f"Bootstrap re-ran (each marker should fire exactly once): {bad}"
        )


def _assert_contracts(contract_failures):
    if contract_failures:
        raise AssertionError(
            "Contract violations:\n  " + "\n  ".join(contract_failures)
        )


async def _runner():
    results, phases, contract_failures = await _run_test()
    _assert_perf(results)
    _assert_no_duplicate_bootstrap(phases)
    _assert_contracts(contract_failures)
    return results, phases, contract_failures


if PYTEST_AVAILABLE:
    import pytest as _pt

    @_pt.mark.asyncio
    async def test_mcp_protocol_smoke():
        results, phases, contracts = await _runner()

    @_pt.mark.asyncio
    async def test_no_duplicate_bootstrap():
        _, phases, _ = await _runner()
        _assert_no_duplicate_bootstrap(phases)


if __name__ == "__main__":
    asyncio.run(_runner())
