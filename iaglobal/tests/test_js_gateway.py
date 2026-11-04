# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do JSGateway — sibling do ASTGateway para parsing de JavaScript.

Mesmo contrato do ASTGateway: bool valid + lista de erros com linha/coluna,
sem subprocess, sem regex, via tree-sitter com gramática javascript.

Diferente do ASTGateway: tree-sitter é tolerante a erro por design — sempre
produz uma árvore, marcando nós ERROR/missing em vez de explodir exceção.
Por isso retornamos JSParseResult em vez de ASTResult (a tree é tree-sitter
Node, não ast.AST).
"""

import pytest

from iaglobal.security.js_gateway import JSGateway


@pytest.fixture
def js_gateway():
    return JSGateway()


# ── Codigo JS valido ──


def test_js_valido_function_declaration(js_gateway):
    js_gateway.parse("function hello() { return 42; }")
    result = js_gateway.parse("function hello() { return 42; }")
    assert result.valid is True
    assert result.errors == []


def test_js_valido_arrow_function(js_gateway):
    result = js_gateway.parse("const greet = (name) => `Hello, ${name}!`;")
    assert result.valid is True


def test_js_valido_class(js_gateway):
    result = js_gateway.parse(
        "class User { constructor(name) { this.name = name; } getName() { return this.name; } }"
    )
    assert result.valid is True


def test_js_valido_moderno_optional_chaining(js_gateway):
    """tree-sitter suporta sintaxe moderna que esprima/pyjsparser nao."""
    result = js_gateway.parse("const x = obj?.foo?.bar ?? 'default';")
    assert result.valid is True


def test_js_valido_async_await(js_gateway):
    result = js_gateway.parse(
        "async function fetchData() { const r = await fetch(url); return await r.json(); }"
    )
    assert result.valid is True


# ── Codigo JS invalido ──


def test_js_invalido_parentese_desbalanceado(js_gateway):
    """O caso que motivou o fix: parêntese não fecha."""
    result = js_gateway.parse("function hello() { return 42; )))")
    assert result.valid is False
    assert len(result.errors) > 0
    assert result.error_line is not None
    assert result.error_line >= 1


def test_js_invalido_chave_nao_fechada(js_gateway):
    result = js_gateway.parse("function hello() { if (true) { return 1;")
    assert result.valid is False
    assert len(result.errors) > 0


# ── Edge cases ──


def test_js_empty_code(js_gateway):
    result = js_gateway.parse("")
    assert result.valid is False
    assert "Empty" in result.errors[0]


def test_js_whitespace_only(js_gateway):
    result = js_gateway.parse("   \n\n\t  ")
    assert result.valid is False


# ── Tolerancia a erro do tree-sitter ──


def test_js_partial_valido_com_erro_marcado(js_gateway):
    """Mesmo com erro, tree-sitter produz arvore (não explode)."""
    result = js_gateway.parse("const x = 1;\nfunction {{{{{\nconst y = 2;")
    assert result.valid is False
    # tree-sitter devolve uma tree parcial mesmo quando invalido
    assert result.tree is not None
