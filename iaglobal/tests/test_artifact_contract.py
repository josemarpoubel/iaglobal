import json

import pytest

from iaglobal._paths import (
    _detect_extension,
    next_project_dir,
    save_result_artifact,
)


@pytest.fixture
def isolated_results_dir(tests_temp_dir, monkeypatch):
    """Redireciona RESULTS_DIR e arquivos de counter/lock para tests_temp_dir.

    AGENTS.md → Persistence Authority: toda persistência em disco deve passar
    por helpers de ``iaglobal/_paths.py``. Este fixture cumpre o contrato de
    isolamento (cleanup automático via _clean_tests_temp) sem alterar a
    semântica da função testada.
    """
    import iaglobal._paths as paths_module

    redir = tests_temp_dir / "result"
    redir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths_module, "RESULTS_DIR", redir)
    monkeypatch.setattr(paths_module, "_RESULT_COUNTER_FILE", redir / ".counter.json")
    monkeypatch.setattr(paths_module, "_RESULT_LOCK_FILE", redir / ".counter.lock")
    return redir


class TestResultArtifact:
    """Testa se o artefato final é salvo corretamente via ``save_result_artifact``."""

    def test_save_result_artifact_cria_diretorio_project(self, isolated_results_dir):
        """save_result_artifact() deve criar projectXXX/ dentro de RESULTS_DIR."""
        task = "crie uma API Flask com CRUD"
        files = {"app.py": "from flask import Flask\napp = Flask(__name__)\n"}
        project_dir = save_result_artifact(task, files)
        assert project_dir.exists()
        assert project_dir.parent == isolated_results_dir
        assert project_dir.name.startswith("project")
        assert (project_dir / "app.py").exists()
        assert (project_dir / "metadata.json").exists()
        with open(project_dir / "metadata.json") as f:
            meta = json.load(f)
        assert "task" in meta
        assert meta["task"] == task

    def test_save_result_artifact_sem_files_usando_code(self, isolated_results_dir):
        """Sem files, save_result_artifact deve detectar extensão do code."""
        task = "script python"
        code = "def hello():\n    print('oi')\n"
        project_dir = save_result_artifact(task, {}, code)
        assert project_dir.exists()
        assert (project_dir / "output.py").exists()
        with open(project_dir / "output.py") as f:
            assert f.read().strip() == code.strip()

    def test_save_result_artifact_detecta_html(self, isolated_results_dir):
        """Código HTML deve ser salvo como output.html."""
        task = "pagina web"
        code = "<!DOCTYPE html>\n<html>\n<body>\n</html>"
        project_dir = save_result_artifact(task, {}, code)
        assert (project_dir / "output.html").exists()

    def test_next_project_dir_incrementa(self, isolated_results_dir):
        """next_project_dir() deve criar project001, project002, ... sequenciais."""
        d1 = next_project_dir()
        assert d1.name.startswith("project")
        assert d1.parent == isolated_results_dir
        d2 = next_project_dir()
        assert d2 != d1
        assert d2.name.startswith("project")
        assert d2.parent == isolated_results_dir


class TestDetectExtension:
    """Cobre a tabela de extensões suportada por ``_detect_extension``."""

    def test_python(self):
        assert _detect_extension("def foo(): pass") == ".py"
        assert _detect_extension("import os") == ".py"
        assert _detect_extension("from pathlib import Path") == ".py"

    def test_html(self):
        assert _detect_extension("<!DOCTYPE html>") == ".html"
        assert _detect_extension("<html>\n<body>\n</html>") == ".html"

    def test_javascript(self):
        assert _detect_extension("function hello() {}") == ".js"
        assert _detect_extension("const x = 1") == ".js"

    def test_json(self):
        assert _detect_extension('{"nome": "teste"}') == ".json"

    def test_task_hint(self):
        assert _detect_extension("conteudo solto", "crie um script python") == ".py"
        assert _detect_extension("conteudo solto", "faça uma pagina html") == ".html"

    def test_code_fence(self):
        code = "```python\nprint('hello')\n```"
        assert _detect_extension(code) == ".py"
        code_html = "```html\n<p>oi</p>\n```"
        assert _detect_extension(code_html) == ".html"
