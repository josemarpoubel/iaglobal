"""Testes robustos: skills registradas, DAG completo, pipeline end-to-end com mocks."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.evolution.skills.skill_registry import SkillRegistry
from iaglobal.evolution.skills.skill import (
    Skill, ExecutionPolicy,
    SKILL_PLANNER, SKILL_CODER,
    SKILL_TESTER, SKILL_DEBUGGER,
    SKILL_SEARCH,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_KNOWLEDGE,
)
from iaglobal.graphs.builder import (
    PIPELINE_SKILLS, build_graph_from_skills, build_default_graph,
    _register_default_skill_implementations,
)
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.artifact import SolutionArtifact, Artifact

TODAS_SKILLS = [
    SKILL_PLANNER, SKILL_CODER,
    SKILL_TESTER, SKILL_DEBUGGER,
    SKILL_SEARCH,
    SKILL_SEMANTIC_VALIDATOR,
    SKILL_KNOWLEDGE,
]
NOMES_SKILLS = {s.name for s in TODAS_SKILLS}


class TestSkillsRegistradas:
    """Verifica que todas as skills necessarias existem e podem ser registradas."""

    def test_todas_skills_tem_nome(self):
        for s in TODAS_SKILLS:
            assert s.name, f"Skill sem nome: {s}"
            assert s.name in NOMES_SKILLS

    def test_todas_skills_tem_execution_policy(self):
        for s in TODAS_SKILLS:
            assert isinstance(s.execution_policy, ExecutionPolicy)

    def test_numero_de_skills(self):
        assert len(TODAS_SKILLS) == 7


# =========================================================
# TEST 2: DAG construido corretamente
# =========================================================

class TestDAGPipeline:
    """Verifica a construcao do grafo com todos os nos e dependencias."""

    def test_pipeline_skills_tem_25_nos(self):
        assert len(PIPELINE_SKILLS) == 25

    def test_prompt_intake_e_primeiro_no(self):
        assert PIPELINE_SKILLS[0][0] == "prompt_intake"

    def test_planner_depende_de_performance_design(self):
        for name, opts in PIPELINE_SKILLS:
            if name == "planner":
                assert "performance_design" in opts.get("depends_on", [])

    def test_todos_nos_tem_dependencias_validas(self):
        nomes = set()
        for name, opts in PIPELINE_SKILLS:
            nomes.add(opts.get("name", name))
        for name, opts in PIPELINE_SKILLS:
            node_name = opts.get("name", name)
            for dep in opts.get("depends_on", []):
                assert dep in nomes, f"Node '{node_name}' depende de '{dep}' que nao existe"

    def test_nenhum_no_depende_de_si_mesmo(self):
        for name, opts in PIPELINE_SKILLS:
            assert name not in opts.get("depends_on", []), f"Node '{name}' depende de si mesmo"

    def test_grafo_sem_ciclo(self):
        edges = {name: opts.get("depends_on", []) for name, opts in PIPELINE_SKILLS}
        visitados = set()
        def visita(no, pilha):
            assert no not in pilha, f"Ciclo detectado em '{no}'"
            if no in visitados:
                return
            visitados.add(no)
            pilha.add(no)
            for dep in edges.get(no, []):
                visita(dep, pilha)
            pilha.remove(no)
        for no in edges:
            visita(no, set())

    def test_build_graph_nao_lanca_erro(self):
        mock_orch = MagicMock()
        mock_orch._model_fn = lambda p: "print('ok')"
        with patch("iaglobal.evolution.skills.skill_registry.skill_registry", SkillRegistry()):
            _register_default_skill_implementations(mock_orch)
            graph = build_graph_from_skills(mock_orch)
        assert len(graph.nodes) >= 13


# =========================================================
# TEST 3: Pipeline end-to-end com mocks
# =========================================================

class TestPipelineEndToEnd:
    """Pipeline completo mockado: do input ao artifact salvo."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_script_cria_arquivo(self):
        from iaglobal.pipeline.engine import PipelineEngine
        from iaglobal._paths import SCRIPTS_DIR

        with patch("iaglobal.pipeline.engine.SCRIPTS_DIR", Path(self.tmpdir)):
            state = MagicMock()
            state.script_path = None
            state.prompt = "crie uma pagina de contato"
            state.task_id = "test_123"
            state.generated_code = "from flask import Flask\napp = Flask(__name__)"
            state.score = 0.85
            state.metadata = {}
            state.errors = []

            engine = PipelineEngine(MagicMock())
            path = engine._save_script(state)
            assert path is not None
            assert path.exists()
            assert "contato" in path.read_text() or "flask" in path.read_text().lower()

    def _run_artifact_writer(self, code, files=None, task="test"):
        import asyncio
        from iaglobal.graphs.builder import _make_artifact_writer_run
        from iaglobal._paths import SCRIPTS_DIR

        with patch("iaglobal._paths.SCRIPTS_DIR", Path(self.tmpdir)):
            solution = SolutionArtifact(task=task, code=code, files=files or {})
            gatekeeper_result = {
                "output": solution,
                "gatekeeper_passed": True,
                "artifact": Artifact(content=solution.code, type="code",
                                     metadata={"task": task, "score": 0.9}),
            }
            ctx = {"memory": {"final_gatekeeper": gatekeeper_result}}
            return asyncio.run(_make_artifact_writer_run(None)(ctx))

    def test_artifact_writer_cria_pasta_com_arquivos(self):
        result = self._run_artifact_writer(
            "from flask import Flask\napp = Flask(__name__)",
            files={"css/style.css": "body {}", "js/app.js": "console.log('ok')"},
            task="crie uma pagina de contato",
        )
        assert result.get("persisted") is True
        pasta = os.path.dirname(result["path"])
        assert os.path.isdir(pasta)
        assert os.path.exists(os.path.join(pasta, "main.py"))
        assert os.path.exists(os.path.join(pasta, "css", "style.css"))
        assert os.path.exists(os.path.join(pasta, "js", "app.js"))

    def test_artifact_writer_projeto_sem_python_cria_index_html(self):
        result = self._run_artifact_writer(
            "<!DOCTYPE html><html><body><h1>Contato</h1></body></html>",
            task="pagina web",
        )
        assert "index.html" in result["path"]

    def test_artifact_writer_cria_subpastas_web(self):
        result = self._run_artifact_writer(
            "<!DOCTYPE html><html></html>",
            task="crie uma pagina web",
        )
        pasta = os.path.dirname(result["path"])
        assert os.path.isdir(os.path.join(pasta, "css"))
        assert os.path.isdir(os.path.join(pasta, "js"))
        assert os.path.isdir(os.path.join(pasta, "templates"))

    def test_pipeline_rejeita_cache_stub(self):
        from iaglobal.pipeline.engine import PipelineEngine
        mock_memoria = MagicMock()
        mock_memoria.retrieve.return_value = {
            "score": 0.8, "response": "from django import forms",
            "codigo": "from django import forms",
        }
        mock_orch = MagicMock()
        mock_orch.memory = mock_memoria
        state = MagicMock(prompt="test", task_id="123", metadata={}, errors=[])
        engine = PipelineEngine(mock_orch)
        assert engine._memory_stage(state) is None

    def test_pipeline_aceita_cache_completo(self):
        from iaglobal.pipeline.engine import PipelineEngine
        codigo = ("class Form:\n def __init__(self): pass\n\ndef main():\n return\n" * 3)
        mock_memoria = MagicMock()
        mock_memoria.retrieve.return_value = {
            "score": 0.85, "response": codigo, "codigo": codigo,
            "metadata": {"script_path": "/tmp/test.py"},
        }
        mock_orch = MagicMock()
        mock_orch.memory = mock_memoria
        state = MagicMock(prompt="test", task_id="123", metadata={}, errors=[])
        engine = PipelineEngine(mock_orch)
        result = engine._memory_stage(state)
        assert result is not None
        assert result.success is True

    def test_output_renderer_exibe_pasta(self):
        from iaglobal.cli.output import OutputRenderer
        from iaglobal.pipeline.result import PipelineResult
        import io

        r = PipelineResult(
            success=True, response="print('hello')",
            script_path="/tmp/meu_projeto_123/index.html", score=1.0,
        )
        out = io.StringIO()
        with patch("sys.stdout", out):
            OutputRenderer.render(r)
        assert "Seu script ficou pronto na pasta" in out.getvalue()
        assert "meu_projeto_123" in out.getvalue()
