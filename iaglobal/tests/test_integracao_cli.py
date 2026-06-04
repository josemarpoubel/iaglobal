import os
import sys
import io
import json
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.cli.output import OutputRenderer
from iaglobal.pipeline.result import PipelineResult
from iaglobal.graphs.artifact import Artifact


class TestOutputRenderer(unittest.TestCase):
    """Testa o OutputRenderer com todos os tipos de resultado possiveis."""

    def capture_render(self, result) -> str:
        out = io.StringIO()
        with patch("sys.stdout", out):
            OutputRenderer.render(result)
        return out.getvalue()

    # =========================================================
    # PipelineResult scenarios
    # =========================================================

    def test_pipeline_result_com_script_path(self):
        """PipelineResult com script_path -> mensagem de sucesso"""
        r = PipelineResult(
            success=True,
            response="print('hello')",
            script_path="/tmp/scripts/test_123.py",
            score=1.0,
        )
        output = self.capture_render(r)
        self.assertIn("Seu script ficou pronto na pasta", output)
        self.assertIn("/tmp/scripts/test_123.py", output)
        self.assertIn("Código gerado", output)
        self.assertIn("14", output)

    def test_pipeline_result_sem_script_path(self):
        """PipelineResult sem script_path -> mostra response direto"""
        r = PipelineResult(
            success=True,
            response="print('hello')",
            score=0.5,
        )
        output = self.capture_render(r)
        self.assertIn("print('hello')", output)
        self.assertNotIn("Seu script ficou pronto", output)

    def test_pipeline_result_com_erro(self):
        """PipelineResult com erro -> mensagem de erro"""
        r = PipelineResult(
            success=False,
            error="Falha na geracao de codigo",
        )
        output = self.capture_render(r)
        self.assertIn("Erro: Falha na geracao de codigo", output)

    def test_pipeline_result_com_errors_list(self):
        """PipelineResult com lista de erros -> cada erro em linha"""
        r = PipelineResult(
            success=False,
            errors=["Erro 1: sintaxe invalida", "Erro 2: timeout"],
        )
        output = self.capture_render(r)
        self.assertIn("Erro 1: sintaxe invalida", output)
        self.assertIn("Erro 2: timeout", output)

    # =========================================================
    # Dict scenarios (raw DAG results)
    # =========================================================

    def test_dict_com_artifact_writer_raw(self):
        """Dict com raw_results.artifact_writer -> mensagem de sucesso"""
        art = Artifact(content="print('hello')", type="code", path="/tmp/scripts/test.py")
        result = {
            "success": True,
            "raw_results": {
                "artifact_writer": {
                    "persisted": True,
                    "path": "/tmp/scripts/test.py",
                    "artifact_code": "print('hello')",
                    "artifact": art,
                }
            }
        }
        output = self.capture_render(result)
        self.assertIn("Seu script ficou pronto na pasta", output)
        self.assertIn("/tmp/scripts/test.py", output)

    def test_dict_com_artifact_writer_objeto(self):
        """Dict com objeto Artifact no artifact_writer -> mensagem de sucesso"""
        art = Artifact(content="code", type="code", path="/tmp/evo/test.py",
                       metadata={"node": "evo_coder", "evo": True})
        result = {
            "success": True,
            "raw_results": {
                "artifact_writer": {
                    "persisted": True,
                    "artifact": art,
                    "path": "/tmp/evo/test.py",
                    "artifact_code": "code",
                }
            }
        }
        output = self.capture_render(result)
        self.assertIn("Seu script ficou pronto", output)
        self.assertIn("/tmp/evo/test.py", output)

    def test_dict_com_final_output_e_artifact(self):
        """Dict com final_output + artifact -> mensagem de sucesso"""
        art = Artifact(content="code", type="code", path="/tmp/out.py")
        result = {
            "success": True,
            "final_output": "print('ok')",
            "artifact": art,
        }
        output = self.capture_render(result)
        self.assertIn("Seu script ficou pronto", output)
        self.assertIn("/tmp/out.py", output)

    def test_dict_com_final_output_sem_artifact(self):
        """Dict com final_output sem artifact -> mostra o output"""
        result = {
            "success": True,
            "final_output": "print('ok')",
        }
        output = self.capture_render(result)
        self.assertIn("print('ok')", output)

    def test_dict_com_raw_results_fallback(self):
        """Dict com raw_results contendo code -> mostra o code"""
        from iaglobal.graphs.artifact import SolutionArtifact
        result = {
            "success": True,
            "raw_results": {
                "debugger": {
                    "output": SolutionArtifact(code="x = 1"),
                }
            }
        }
        output = self.capture_render(result)
        self.assertIn("x = 1", output)

    def test_dict_com_erro_direto(self):
        """Dict com error -> mensagem de erro"""
        result = {"error": "Algo deu errado"}
        output = self.capture_render(result)
        self.assertIn("Erro: Algo deu errado", output)

    # =========================================================
    # Edge cases
    # =========================================================

    def test_result_vazio(self):
        """Resultado vazio ou inesperado -> print bruto"""
        output = self.capture_render("texto puro")
        self.assertIn("texto puro", output)

    def test_result_none(self):
        """None -> print(None)"""
        output = self.capture_render(None)
        self.assertIn("None", output)

    def test_pipeline_result_response_vazio(self):
        """script_path sem response -> sem linha de codigo"""
        r = PipelineResult(success=True, response="", script_path="/tmp/s.py")
        output = self.capture_render(r)
        self.assertIn("Seu script ficou pronto", output)
        self.assertNotIn("Código gerado", output)

    def test_dict_artifact_writer_sem_artifact_objeto(self):
        """artifact_writer com path mas sem objeto Artifact -> usa path direto"""
        result = {
            "raw_results": {
                "artifact_writer": {
                    "persisted": True,
                    "path": "/tmp/direto.py",
                    "artifact_code": "print('x')",
                }
            }
        }
        output = self.capture_render(result)
        self.assertIn("Seu script ficou pronto", output)
        self.assertIn("/tmp/direto.py", output)


class TestCLIIntegracao(unittest.TestCase):
    """Testa o fluxo completo do CLI com mocks."""

    @patch("iaglobal.cli.main.bootstrap")
    @patch("iaglobal.cli.main.load_env")
    def test_run_cli_com_pipeline_result(self, mock_load_env, mock_bootstrap):
        """run_cli() com PipelineResult -> mensagem de sucesso"""
        mock_orch = MagicMock()
        mock_orch.run.return_value = PipelineResult(
            success=True,
            response="print('genesis block')",
            script_path="/tmp/script/genesis.py",
            score=0.95,
        )
        mock_bootstrap.initialize.return_value = mock_orch

        from iaglobal.cli.main import run_cli
        test_args = ["iaglobal", "run", "crie um bloco genesis"]
        with patch.object(sys, "argv", test_args):
            out = io.StringIO()
            with patch("sys.stdout", out):
                run_cli()

        output = out.getvalue()
        self.assertIn("Seu script ficou pronto na pasta", output)
        self.assertIn("/tmp/script/genesis.py", output)
        self.assertIn("Código gerado", output)

    @patch("iaglobal.cli.main.bootstrap")
    @patch("iaglobal.cli.main.load_env")
    def test_run_cli_sem_prefixo_run(self, mock_load_env, mock_bootstrap):
        """run_cli() sem prefixo 'run' tambem funciona"""
        mock_orch = MagicMock()
        mock_orch.run.return_value = PipelineResult(
            success=True,
            response="print('ok')",
            script_path="/tmp/s.py",
        )
        mock_bootstrap.initialize.return_value = mock_orch

        from iaglobal.cli.main import run_cli
        test_args = ["iaglobal", "crie um bloco"]
        with patch.object(sys, "argv", test_args):
            out = io.StringIO()
            with patch("sys.stdout", out):
                run_cli()

        output = out.getvalue()
        self.assertIn("Seu script ficou pronto", output)

    @patch("iaglobal.cli.main.bootstrap")
    @patch("iaglobal.cli.main.load_env")
    def test_run_cli_com_erro(self, mock_load_env, mock_bootstrap):
        """run_cli() com erro -> mensagem de erro"""
        mock_orch = MagicMock()
        mock_orch.run.return_value = PipelineResult(
            success=False,
            error="Provider indisponivel",
        )
        mock_bootstrap.initialize.return_value = mock_orch

        from iaglobal.cli.main import run_cli
        test_args = ["iaglobal", "run", "teste"]
        with patch.object(sys, "argv", test_args):
            out = io.StringIO()
            with patch("sys.stdout", out):
                run_cli()

        output = out.getvalue()
        self.assertIn("Erro: Provider indisponivel", output)

    @patch("iaglobal.cli.main.bootstrap")
    @patch("iaglobal.cli.main.load_env")
    def test_run_cli_com_dict_result(self, mock_load_env, mock_bootstrap):
        """run_cli() com dict cru do DAG -> mensagem de sucesso com path"""
        mock_orch = MagicMock()
        mock_orch.run.return_value = {
            "success": True,
            "raw_results": {
                "artifact_writer": {
                    "persisted": True,
                    "path": "/tmp/dag/script.py",
                    "artifact_code": "print('dag result')",
                    "artifact": Artifact(content="print('dag result')", type="code", path="/tmp/dag/script.py"),
                }
            }
        }
        mock_bootstrap.initialize.return_value = mock_orch

        from iaglobal.cli.main import run_cli
        test_args = ["iaglobal", "run", "teste dag"]
        with patch.object(sys, "argv", test_args):
            out = io.StringIO()
            with patch("sys.stdout", out):
                run_cli()

        output = out.getvalue()
        self.assertIn("Seu script ficou pronto na pasta", output)
        self.assertIn("/tmp/dag/script.py", output)


class TestArtifactCLIFlow(unittest.TestCase):
    """Testa o fluxo completo Artifact -> OutputRenderer -> CLI."""

    def test_artifact_do_gatekeeper_ate_output(self):
        """
        Simula o fluxo real:
        1. final_gatekeeper cria Artifact
        2. artifact_writer persiste e retorna
        3. PipelineEngine extrai e cria PipelineResult
        4. OutputRenderer exibe
        """
        from iaglobal.graphs.artifact import SolutionArtifact

        solution = SolutionArtifact(task="genesis", code="import hashlib", score=85.0)
        artifact = Artifact(
            content=solution.code,
            type="code",
            metadata={"task": solution.task, "score": solution.score},
        )

        gatekeeper_result = {
            "output": solution,
            "gatekeeper_passed": True,
            "status": "approved",
            "artifact": artifact,
            "output_mode": "file",
        }
        self.assertEqual(gatekeeper_result["status"], "approved")
        self.assertEqual(gatekeeper_result["artifact"].content, "import hashlib")

        artifact.path = "/tmp/script/genesis_123.py"
        artifact_writer_result = {
            "output": "/tmp/script/genesis_123.py",
            "path": "/tmp/script/genesis_123.py",
            "artifact": artifact,
            "artifact_code": "import hashlib",
            "persisted": True,
        }

        pipeline_result = PipelineResult(
            success=True,
            response=artifact_writer_result.get("artifact_code", ""),
            script_path=artifact_writer_result.get("path"),
            score=0.85,
        )
        self.assertEqual(pipeline_result.script_path, "/tmp/script/genesis_123.py")
        self.assertEqual(pipeline_result.response, "import hashlib")

        output = io.StringIO()
        with patch("sys.stdout", output):
            OutputRenderer.render(pipeline_result)
        rendered = output.getvalue()
        self.assertIn("Seu script ficou pronto na pasta", rendered)
        self.assertIn("/tmp/script/genesis_123.py", rendered)
        self.assertIn("Código gerado (14 caracteres)", rendered)

    def test_artifact_fluxo_dict_sem_pipeline_result(self):
        """
        Fluxo alternativo: resultado do DAG vai direto pro OutputRenderer
        sem passar pelo PipelineEngine (ex: chamada direta a run_graph_task).
        """
        artifact = Artifact(
            content="print('blockchain')",
            type="code",
            path="/tmp/dag/evo_script.py",
            metadata={"task": "evo", "score": 70, "node": "evo_coder", "evo": True},
        )
        dag_result = {
            "success": True,
            "raw_results": {
                "evo_coder": {
                    "output": type("SA", (), {"code": "print('blockchain')", "task": "evo", "score": 70})(),
                    "artifact": artifact,
                },
                "artifact_writer": {
                    "persisted": True,
                    "path": "/tmp/dag/evo_script.py",
                    "artifact_code": "print('blockchain')",
                    "artifact": artifact,
                },
            }
        }

        output = io.StringIO()
        with patch("sys.stdout", output):
            OutputRenderer.render(dag_result)
        rendered = output.getvalue()
        self.assertIn("Seu script ficou pronto na pasta", rendered)
        self.assertIn("/tmp/dag/evo_script.py", rendered)


if __name__ == "__main__":
    unittest.main()
