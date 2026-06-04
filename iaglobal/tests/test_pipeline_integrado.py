"""Testes integrados do pipeline: cache, AST, detectores, artifact_writer, CLI."""

import os
import sys
import io
import json
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.graphs.builder import (
    _extrair_multifile,
    _imports_framework,
    _is_python_code,
    _validate_syntax,
    _make_artifact_writer_run,
    _detect_ext_and_name,
)
from iaglobal.graphs.artifact import SolutionArtifact, Artifact
from iaglobal.cli.output import OutputRenderer
from iaglobal.pipeline.result import PipelineResult


class TestDetectores:
    """Testes dos detectores: python, framework, sintaxe, extensao."""

    def test_is_python_code_html_retorna_false(self):
        assert _is_python_code("<!DOCTYPE html><html>") is False
        assert _is_python_code("<html><body>") is False

    def test_is_python_code_python_retorna_true(self):
        assert _is_python_code("print('hello')") is True
        assert _is_python_code("def foo(): pass") is True
        assert _is_python_code("from flask import Flask") is True

    def test_is_python_code_vazio_retorna_true(self):
        assert _is_python_code("") is True

    def test_imports_framework_django(self):
        assert _imports_framework("from django import forms") is True

    def test_imports_framework_flask(self):
        assert _imports_framework("import flask") is True

    def test_imports_framework_nao_frameworks(self):
        assert _imports_framework("import os") is False
        assert _imports_framework("import json") is False

    def test_validate_syntax_python_valido(self):
        ok, err = _validate_syntax("x = 1")
        assert ok is True
        assert err == ""

    def test_validate_syntax_python_invalido(self):
        ok, err = _validate_syntax("x = ")
        assert ok is False
        assert "SyntaxError" in err

    def test_detect_ext_html(self):
        ext, name = _detect_ext_and_name("<!DOCTYPE html><html>")
        assert ext == ".html"
        assert name == "index.html"

    def test_detect_ext_python(self):
        ext, name = _detect_ext_and_name("print('hello')")
        assert ext == ".py"
        assert name == "main.py"

    def test_detect_ext_json(self):
        ext, name = _detect_ext_and_name('{"key": "value"}')
        assert ext == ".json"
        assert name == "output.json"


class TestExtrairMultifile:
    """Testes do extrator de arquivos multiplos do LLM."""

    def test_sem_blocos_texto_puro(self):
        result = _extrair_multifile("print('hello')")
        assert len(result) == 1

    def test_um_bloco_python(self):
        raw = "```python\nprint('hello')\n```"
        result = _extrair_multifile(raw)
        assert "main.py" in result
        assert "hello" in result["main.py"]

    def test_um_bloco_html(self):
        raw = "```html\n<!DOCTYPE html><html>\n```"
        result = _extrair_multifile(raw)
        assert "index.html" in result

    def test_multiplos_blocos(self):
        raw = "```html\n<!DOCTYPE html>\n```\n```css\nbody {}\n```"
        result = _extrair_multifile(raw)
        assert "index.html" in result
        assert "style.css" in result

    def test_file_marker(self):
        raw = "# FILE: index.html\n<!DOCTYPE html>\n# FILE: css/style.css\nbody {}"
        result = _extrair_multifile(raw)
        assert "index.html" in result
        assert "css/style.css" in result


class TestCacheQualityGate:
    """Testes do quality gate do cache (pipeline/engine.py)."""

    def setUp(self):
        self.engine_patch = patch("iaglobal.pipeline.engine.PipelineEngine")
        self.mock_engine = self.engine_patch.start()

    def tearDown(self):
        self.engine_patch.stop()

    def test_cache_rejeita_stub_curto(self):
        """Cache com <100 chars deve ser rejeitado."""
        from iaglobal.pipeline.engine import PipelineEngine
        state = MagicMock()
        state.prompt = "test"
        state.task_id = "123"
        state.metadata = {}
        state.errors = []

        mock_orch = MagicMock()
        mock_orch.memory.retrieve.return_value = {
            "score": 0.8,
            "response": "from django import forms",
            "codigo": "from django import forms",
        }
        engine = PipelineEngine(mock_orch)

        result = engine._memory_stage(state)
        assert result is None

    def test_cache_aceita_codigo_completo(self):
        """Cache com >100 chars e class/def deve ser aceito."""
        from iaglobal.pipeline.engine import PipelineEngine
        state = MagicMock()
        state.prompt = "test"
        state.task_id = "123"
        state.metadata = {}
        state.errors = []

        codigo_completo = """
class Pessoa:
    def __init__(self, nome):
        self.nome = nome

def main():
    p = Pessoa("Joao")
    print(p.nome)
""" * 3
        mock_memoria = MagicMock()
        mock_memoria.retrieve.return_value = {
            "score": 0.8,
            "response": codigo_completo,
            "codigo": codigo_completo,
            "metadata": {"script_path": "/tmp/test.py"},
        }

        mock_orch = MagicMock()
        mock_orch.memory = mock_memoria
        engine = PipelineEngine(mock_orch)
        result = engine._memory_stage(state)
        assert result is not None
        assert result.success is True


class TestArtifactWriter:
    """Testes do artifact_writer: pastas, extensoes, multi-arquivo."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("iaglobal.graphs.builder.SCRIPTS_DIR", Path(self.tmpdir))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_artifact_writer(self, code: str, files: dict = None, task: str = "test"):
        solution = SolutionArtifact(task=task, code=code, files=files or {})
        gatekeeper_result = {
            "output": solution,
            "gatekeeper_passed": True,
            "artifact": Artifact(content=code, type="code",
                                 metadata={"task": task, "score": 0.9}),
        }
        ctx = {"memory": {"final_gatekeeper": gatekeeper_result}}
        fn = _make_artifact_writer_run(None)
        all_runs = []
        ctx["_all_runs"] = all_runs
        return asyncio.run(fn(ctx))

    def test_html_salvo_como_index_html_em_pasta(self):
        result = self._run_artifact_writer("<!DOCTYPE html><html></html>")
        assert result.get("persisted") is True
        path = result.get("path", "")
        assert "index.html" in path

    def test_cria_pasta_por_projeto(self):
        result = self._run_artifact_writer("print('hello')")
        path = result.get("path", "")
        assert os.path.isdir(os.path.dirname(path))
        assert "main.py" in path

    def test_python_salvo_como_main_py(self):
        result = self._run_artifact_writer("print('hello')")
        assert "main.py" in result.get("path", "")

    def test_cria_subpastas_web(self):
        result = self._run_artifact_writer(
            "<!DOCTYPE html><html></html>",
            task="crie uma pagina web"
        )
        path = result.get("path", "")
        dir_path = os.path.dirname(path)
        assert os.path.isdir(os.path.join(dir_path, "css"))
        assert os.path.isdir(os.path.join(dir_path, "js"))
        assert os.path.isdir(os.path.join(dir_path, "templates"))

    def test_multi_arquivo_via_files(self):
        result = self._run_artifact_writer(
            "<!DOCTYPE html><html></html>",
            files={"css/style.css": "body {}", "js/app.js": "console.log('hi')"},
            task="projeto web"
        )
        project_dir = os.path.dirname(result["path"])
        assert os.path.exists(os.path.join(project_dir, "css", "style.css"))
        assert os.path.exists(os.path.join(project_dir, "js", "app.js"))


class TestOutputRenderer:
    """Testes do OutputRenderer com projeto em pasta."""

    def capture_render(self, result) -> str:
        out = io.StringIO()
        with patch("sys.stdout", out):
            OutputRenderer.render(result)
        return out.getvalue()

    def test_exibe_pasta_do_projeto(self):
        r = PipelineResult(
            success=True,
            response="print('hello')",
            script_path="/tmp/scripts/meu_projeto_123/index.html",
            score=1.0,
        )
        output = self.capture_render(r)
        assert "Seu script ficou pronto na pasta" in output
        assert "meu_projeto_123" in output
