# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Teste de integração do no_validator_retry — prova que o JSGateway
desvia JS/Java/SQL do ASTGateway Python no caminho real do run_validator_retry.

Complementa test_js_gateway.py (ferramenta isolada) com o fluxo completo:
get_best_artifact(memory) -> ResolvedArtifact -> gate de kind=HTML ->
gate de kind=CODE + heurística não-Python -> JSGateway.parse().

O bug original: código JS cai em ArtifactKind.CODE (core/artifact.py usa
code_indicators monolítico) e o ASTGateway Python queima 3 retries. O
fix desvia para JSGateway que parseia na linguagem certa.
"""

import pytest

from iaglobal.graphs.nodes.no_validator_retry import run_validator_retry


# ── JS genuíno dentro de kind=CODE ──


@pytest.mark.asyncio
async def test_js_valido_passa_sem_retry():
    js_code = (
        "const app = {\n"
        "  init() { document.getElementById('form').addEventListener('submit', this.handle); },\n"
        "  handle(e) { e.preventDefault(); console.log('ok'); }\n"
        "};\n"
        "document.addEventListener('DOMContentLoaded', () => app.init());\n"
    )
    ctx = {"memory": {"multi_coder": {"output": js_code}}}
    result = await run_validator_retry(ctx)

    assert result.success is True
    assert result.metadata["code_valid"] is True
    assert result.metadata["retries"] == 0
    assert result.metadata["syntax_error"] is None
    assert result.metadata["validator"] == "js_gateway"


@pytest.mark.asyncio
async def test_js_invalido_falha_com_erro_estruturado():
    js_bad = "function broken() { return 42; )))"
    ctx = {"memory": {"multi_coder": {"output": js_bad}}}
    result = await run_validator_retry(ctx)

    assert result.success is False
    assert result.metadata["code_valid"] is False
    assert result.metadata["retries"] == 0
    assert result.metadata["validator"] == "js_gateway"
    assert "ERROR" in result.metadata["syntax_error"] or "missing" in result.metadata["syntax_error"]
    assert result.metadata["error_line"] is not None
    assert result.metadata["error_line"] >= 1


# ── Python genuíno (não dispara heurística, vai pelo ASTGateway) ──


@pytest.mark.asyncio
async def test_python_valido_passa():
    py = "def add(a, b):\n    return a + b\n"
    ctx = {"memory": {"multi_coder": {"output": py}}}
    result = await run_validator_retry(ctx)

    assert result.success is True
    assert result.metadata["code_valid"] is True
    # Python genuíno não cai no JSGateway (heurística não dispara)
    assert result.metadata.get("validator") != "js_gateway"


@pytest.mark.asyncio
async def test_python_invalido_com_erro_sintatico_falha():
    py_bad = "def broken(\n    return 42\n"
    ctx = {"memory": {"multi_coder": {"output": py_bad}}}
    result = await run_validator_retry(ctx)

    assert result.success is False
    assert result.metadata["code_valid"] is False
    # Vai pelo ASTGateway, não pelo JSGateway
    assert result.metadata.get("validator") != "js_gateway"


# ── HTML (gate anterior, sem mudança) ──


@pytest.mark.asyncio
async def test_html_passa_sem_validar():
    html = "<!DOCTYPE html>\n<html><body><h1>Hi</h1></body></html>\n"
    ctx = {"memory": {"multi_coder": {"output": html}}}
    result = await run_validator_retry(ctx)

    assert result.success is True
    assert result.metadata["code_valid"] is True
    assert result.metadata.get("validator") != "js_gateway"


# ── SQL (também cai em CODE, JSGateway marca como inválido) ──


@pytest.mark.asyncio
async def test_sql_invalido_no_jsgateway_mas_estruturado():
    sql = "SELECT * FORM users WHERE id = 1"  # FORM em vez de FROM
    ctx = {"memory": {"multi_coder": {"output": sql}}}
    result = await run_validator_retry(ctx)

    # SQL começa com SELECT — heurística captura
    assert result.metadata.get("validator") == "js_gateway"
    # JSGateway marca como inválido (SQL não é JS válido)
    assert result.success is False
    assert result.metadata["code_valid"] is False
