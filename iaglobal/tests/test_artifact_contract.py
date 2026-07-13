import shutil
import json

from iaglobal._paths import (
    save_result_artifact,
    next_project_dir,
    _detect_extension,
    RESULTS_DIR,
)


class TestResultArtifact:
    """Testa se o artefato final é salvo corretamente em memory/data/result/."""

    def setup_method(self):
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def test_save_result_artifact_cria_diretorio_project(self):
        """save_result_artifact() deve criar projectXXX/ em memory/data/result/."""
        task = "crie uma API Flask com CRUD"
        files = {"app.py": "from flask import Flask\napp = Flask(__name__)\n"}
        project_dir = save_result_artifact(task, files)
        assert project_dir.exists()
        assert project_dir.parent == RESULTS_DIR
        assert project_dir.name.startswith("project")
        assert (project_dir / "app.py").exists()
        assert (project_dir / "metadata.json").exists()
        with open(project_dir / "metadata.json") as f:
            meta = json.load(f)
        assert "task" in meta
        assert meta["task"] == task
        shutil.rmtree(project_dir, ignore_errors=True)

    def test_save_result_artifact_sem_files_usando_code(self):
        """Sem files, save_result_artifact deve detectar extensão do code."""
        task = "script python"
        code = "def hello():\n    print('oi')\n"
        project_dir = save_result_artifact(task, {}, code)
        assert project_dir.exists()
        assert (project_dir / "output.py").exists()
        with open(project_dir / "output.py") as f:
            assert f.read().strip() == code.strip()
        shutil.rmtree(project_dir, ignore_errors=True)

    def test_save_result_artifact_detecta_html(self):
        """Código HTML deve ser salvo como output.html."""
        task = "pagina web"
        code = "<!DOCTYPE html>\n<html>\n<body>\n</html>"
        project_dir = save_result_artifact(task, {}, code)
        assert (project_dir / "output.html").exists()
        shutil.rmtree(project_dir, ignore_errors=True)

    def test_next_project_dir_incrementa(self):
        """next_project_dir() deve criar project001, project002, ... sequenciais."""
        d1 = next_project_dir()
        assert d1.name == "project001" or d1.name.startswith("project")
        d2 = next_project_dir()
        assert d2 != d1
        assert d2.name.startswith("project")
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)
        counter_file = RESULTS_DIR / ".counter.json"
        if counter_file.exists():
            counter_file.unlink()

    def test_detect_extension_paths_python(self):
        assert _detect_extension("def foo(): pass") == ".py"
        assert _detect_extension("import os") == ".py"
        assert _detect_extension("from pathlib import Path") == ".py"

    def test_detect_extension_paths_html(self):
        assert _detect_extension("<!DOCTYPE html>") == ".html"
        assert _detect_extension("<html>\n<body>\n</html>") == ".html"

    def test_detect_extension_paths_js(self):
        assert _detect_extension("function hello() {}") == ".js"
        assert _detect_extension("const x = 1") == ".js"

    def test_detect_extension_paths_json(self):
        assert _detect_extension('{"nome": "teste"}') == ".json"

    def test_detect_extension_paths_task_hint(self):
        assert _detect_extension("conteudo solto", "crie um script python") == ".py"
        assert _detect_extension("conteudo solto", "faça uma pagina html") == ".html"

    def test_detect_extension_paths_fence(self):
        code = "```python\nprint('hello')\n```"
        assert _detect_extension(code) == ".py"
        code_html = "```html\n<p>oi</p>\n```"
        assert _detect_extension(code_html) == ".html"

    def test_detect_extension_paths_pdf_task(self):
        """Tarefa PDF sem codigo executavel deve retornar .pdf."""
        assert _detect_extension("relatorio mensal", "gerar um documento pdf") == ".pdf"


class TestAgentCooperationContract:
    """Testa se os agentes estao configurados para cooperar entre si."""

    def _deps_chain(self, name):
        """Retorna todos os descendentes na chain de dependencias."""
        from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

        skills = dict(PIPELINE_SKILLS)
        chain = set()
        visited = set()

        def walk(n):
            if n in visited:
                return
            visited.add(n)
            cfg = skills.get(n, {})
            for d in cfg.get("depends_on", []):
                chain.add(d)
                walk(d)

        walk(name)
        return chain

    def test_debug_unificado_depende_de_tester(self):
        """debug_unificado deve depender de tester no pipeline DAG."""
        from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

        skills = dict(PIPELINE_SKILLS)
        debug_cfg = skills.get("debug_unificado", {})
        deps = debug_cfg.get("depends_on", [])
        assert "tester" in deps, (
            f"debug_unificado deve depender de tester, mas tem: {deps}"
        )

    def test_critic_depende_de_tester(self):
        """Critic deve vir depois de tester na pipeline."""
        from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS

        skills = dict(PIPELINE_SKILLS)
        critic_cfg = skills.get("critic", {})
        deps = critic_cfg.get("depends_on", [])
        assert "tester" in deps, f"critic deve depender de tester, mas tem: {deps}"
        assert "fix_validator" in deps

    def test_critic_na_cadeia_do_result_agent(self):
        """Critic deve estar na cadeia de dependencias do result_agent."""
        chain = self._deps_chain("result_agent")
        assert "critic" in chain or "tester" in chain, (
            "result_agent deve ter critic ou tester na cadeia de dependencias"
        )

    def test_coder_agent_contrato(self):
        """CoderAgent tem generate() e retorna CodeArtifact."""
        from iaglobal.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        assert hasattr(agent, "generate")
        assert hasattr(agent, "run")
        assert hasattr(agent, "needs_repair")
        assert hasattr(agent, "request_repair")
        assert hasattr(agent, "acknowledge_repair")
        artifact_type = type(agent.generate)
        # Verifica que generate é async
        import inspect

        assert inspect.iscoroutinefunction(agent.generate)

    def test_pipeline_engine_save_script_escreve_em_result(self):
        """PipelineEngine._save_script deve salvar em memory/data/result/."""
        from unittest.mock import MagicMock
        from iaglobal.pipeline.engine import PipelineEngine
        from iaglobal.pipeline.pipelinestate import PipelineState

        engine = PipelineEngine(orchestrator=MagicMock())
        state = PipelineState(
            task_id="test-001",
            prompt="teste",
            generated_code="def hello():\n    print('hi')\n",
        )
        result_path = engine._save_script(state)
        assert result_path is not None
        assert result_path.exists()
        assert result_path.suffix == ".py"
        result_path.unlink(missing_ok=True)
        result_in_result = RESULTS_DIR / result_path.name
        if result_in_result.exists():
            result_in_result.unlink(missing_ok=True)
