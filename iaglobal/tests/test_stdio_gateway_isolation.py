# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
test_stdio_gateway_isolation.py
Garante que `import iaglobal.mcp.server` NÃO carrega o gateway HTTP
no caminho stdio. Teste de regressão para a otimização futura de
lazy imports.

Estado atual (baseline xfail): `fastapi`, `starlette`, `uvicorn`,
`sse_starlette`, `orjson`, `logfire`, `opentelemetry` são puxados
antecipadamente por import-time.

Após a refatoração (mover os imports para dentro de
`_create_fastapi_app()` ou um branch condicional), basta remover
o `@pytest.mark.xfail(reason=...)` para que o teste vigie a
regressão permanentemente.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

GATEWAY_MODULES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "sse_starlette",
    "orjson",
    "logfire",
    "opentelemetry",
)


def _probe_present_modules() -> list[str]:
    code = (
        "import sys\n"
        "import iaglobal.mcp.server  # importa sem efeitos colaterais perigosos\n"
        f"target = {list(GATEWAY_MODULES)!r}\n"
        "present = []\n"
        "for name in target:\n"
        "    if name in sys.modules or any(k == name or k.startswith(name + '.') for k in sys.modules):\n"
        "        present.append(name)\n"
        "print(','.join(present))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"probe failed: {proc.stderr[:500]}")
    out = proc.stdout.strip()
    if not out:
        return []
    return [m for m in out.split(",") if m]


@pytest.mark.xfail(
    reason=(
        "baseline before lazy imports: o entrypoint atual carrega fastapi/starlette/uvicorn "
        "via imports module-level. Após mover para _create_fastapi_app() ou branch condicional, "
        "remover este xfail — o teste passa a vigiar regressões de lazy-import."
    ),
    strict=False,
)
def test_stdlib_import_does_not_load_gateway_modules():
    """
    Invariante: ao importar só `iaglobal.mcp.server`, nenhum módulo do gateway HTTP
    deve aparecer em sys.modules. Quando otimização for feita, este teste vira
    o contratante permanente.
    """
    found = _probe_present_modules()
    assert found == [], (
        "iaglobal.mcp.server importou estes módulos do gateway: "
        f"{found}. Devem ser movidos para dentro de _create_fastapi_app() "
        "ou guardados por `if args.mode in ('http', 'both'):`."
    )


def test_present_modules_baseline_snapshot():
    """
    Documentação viva: lista quais módulos estão importados HOJE.
    Sempre passa — apenas produz evidência para o próximo passo.
    """
    found = _probe_present_modules()
    print(f"\n[baseline] módulos do gateway atualmente importados por iaglobal.mcp.server: {found}")
    assert found is not None
