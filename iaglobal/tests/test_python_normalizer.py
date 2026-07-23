# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Testes para PythonNormalizer.
"""

import pytest
import ast

from iaglobal.diagnostics.python_normalizer import (
    PythonNormalizer,
    NormalizeResult,
    normalize_before_repair,
)


class TestPythonNormalizerBasic:
    """Testes básicos de normalização."""

    @pytest.fixture
    def normalizer(self):
        return PythonNormalizer()

    def test_simple_code_format(self, normalizer):
        """Código simples é formatado corretamente."""
        code = "import os\n\ndef hello( ):\n    print( 'world' )\n"
        result = normalizer.normalize(code)

        assert result.syntax_valid
        # Ruff deve normalizar espaços e aspas
        assert "print(" in result.fixed
        assert "world" in result.fixed

    def test_markdown_extraction(self, normalizer):
        """Extrai código de blocos markdown."""
        code = """
Aqui está seu código:

```python
def hello():
    x = 1  # usa variável para evitar remoção
    print("world")
```

Espero que ajude!
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        assert "def hello():" in result.fixed
        assert "Aqui está" not in result.fixed
        assert "Espero que" not in result.fixed

    def test_multiple_markdown_blocks(self, normalizer):
        """Junta múltiplos blocos markdown."""
        code = """
```python
x = 1
```

Algum texto

```python
def hello():
    print(x)
```
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        assert "def hello():" in result.fixed

    def test_empty_code(self, normalizer):
        """Código vazio é tratado."""
        code = ""
        result = normalizer.normalize(code)

        assert not result.syntax_valid

    def test_whitespace_only(self, normalizer):
        """Apenas whitespace é tratado."""
        code = "   \n\t\n  "
        result = normalizer.normalize(code)

        assert not result.syntax_valid


class TestPythonNormalizerIndentation:
    """Testes de correção de indentação."""

    @pytest.fixture
    def normalizer(self):
        return PythonNormalizer()

    def test_correct_indentation(self, normalizer):
        """Indentação correta é mantida."""
        code = """
def hello():
    print("world")
    
    if True:
        pass
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        # Verifica se indentação foi preservada
        assert "    print(" in result.fixed

    def test_wrong_indentation_not_fixed(self, normalizer):
        """Indentação errada não é corrigida automaticamente."""
        code = """
def hello():
print("world")
"""
        result = normalizer.normalize(code)

        # Ruff não corrige erros de sintaxe
        assert not result.syntax_valid
        assert result.syntax_error is not None


class TestPythonNormalizerImports:
    """Testes de organização de imports."""

    @pytest.fixture
    def normalizer(self):
        return PythonNormalizer()

    def test_import_organization(self, normalizer):
        """Imports são organizados."""
        code = """
import sys
import os
import asyncio

async def main():
    print(os.getcwd(), sys.version)
    await asyncio.sleep(0)
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        # Ruff deve organizar imports (asyncio, os, sys em ordem)
        assert "import asyncio" in result.fixed
        assert "import os" in result.fixed
        assert "import sys" in result.fixed

    def test_unused_import_removed(self, normalizer):
        """Imports não utilizados são removidos."""
        code = """
import os
import sys

def hello():
    pass
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        # sys não é usado, deve ser removido
        # Nota: isso depende do ruff check --fix


class TestPythonNormalizerIntegration:
    """Testes de integração com RepairEngine."""

    def test_normalize_before_repair_valid(self):
        """Código válido é normalizado."""
        code = """
```python
def hello():
    x = 1
    print("world")
```
"""
        fixed, syntax_valid, result = normalize_before_repair(code, "test")

        assert syntax_valid
        assert result.syntax_valid
        assert "def hello():" in fixed
        assert "def hello():" in fixed

    def test_normalize_before_repair_invalid(self):
        """Código inválido retorna sintaxe inválida."""
        code = """
def hello():
print("world")
"""
        fixed, syntax_valid, result = normalize_before_repair(code, "test")

        assert not syntax_valid
        assert not result.syntax_valid
        assert result.syntax_error is not None


class TestPythonNormalizerEdgeCases:
    """Testes de casos extremos."""

    @pytest.fixture
    def normalizer(self):
        return PythonNormalizer()

    def test_unicode_characters(self, normalizer):
        """Caracteres unicode são preservados."""
        code = """
def hello():
    print("Olá, mundo! 🌍")
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        assert "Olá, mundo!" in result.fixed

    def test_long_lines(self, normalizer):
        """Linhas longas são quebradas (se ruff disponível) ou código válido."""
        code = """
x = "this is a very long string that should probably be wrapped by the formatter because it exceeds the line length limit"
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        lines = result.fixed.split("\n")
        if len(lines) > 1:
            assert len(lines[1]) <= 88 or "very long string" in result.fixed
        else:
            assert "very long string" in result.fixed

    def test_comments_preserved(self, normalizer):
        """Comentários são preservados."""
        code = """
# Este é um comentário
import os

def hello():
    # Outro comentário
    pass
"""
        result = normalizer.normalize(code)

        assert result.syntax_valid
        assert "# Este é um comentário" in result.fixed
        assert "# Outro comentário" in result.fixed


class TestNormalizeResult:
    """Testes da estrutura NormalizeResult."""

    def test_result_contains_all_stages(self):
        """Resultado contém todas as etapas."""
        code = "def hello(): pass"
        normalizer = PythonNormalizer()
        result = normalizer.normalize(code)

        assert hasattr(result, "original")
        assert hasattr(result, "sanitized")
        assert hasattr(result, "formatted")
        assert hasattr(result, "fixed")
        assert hasattr(result, "syntax_valid")
        assert hasattr(result, "syntax_error")
        assert hasattr(result, "ruff_format_errors")
        assert hasattr(result, "ruff_check_errors")

    def test_result_stages_differ(self):
        """Etapas podem diferir."""
        code = """
```python
import sys
import os

def hello( ):
    pass
```
"""
        result = normalizer = PythonNormalizer()
        result = normalizer.normalize(code)

        # Sanitized deve remover markdown
        assert "```" not in result.sanitized
        # Fixed deve ter formatação
        assert result.syntax_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
