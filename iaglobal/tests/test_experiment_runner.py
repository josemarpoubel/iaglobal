# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do ExperimentRunner — Fase 3 (Validação).

Cobertura:
  - Geração de código a partir de hipótese
  - Execução em sandbox
  - Avaliação de resultados
  - Extração de métricas do stdout
  - Persistência em JSON
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from iaglobal.agents.ingestion.experiment_runner import (
    ExperimentRunner,
    ExperimentResult,
    validate_hypotheses,
)
from iaglobal.agents.ingestion.hypothesis_generator import Hypothesis


class TestExperimentResult:
    """Testes da dataclass ExperimentResult."""

    def test_result_creation(self):
        """ExperimentResult deve criar com campos obrigatórios."""
        result = ExperimentResult(
            hypothesis_id="H1",
            paper_id="2401.12345",
            success=True,
            confidence=0.85,
            execution_time_ms=150.5,
            stdout="Metric: 0.92",
            stderr="",
            metrics={"metric": 0.92},
            code="print('hello')",
            validation_details="Success criteria met",
        )
        assert result.hypothesis_id == "H1"
        assert result.success == True
        assert result.confidence == 0.85
        assert result.timestamp != ""

    def test_result_to_dict(self):
        """to_dict deve serializar corretamente."""
        result = ExperimentResult(
            hypothesis_id="H2",
            paper_id="2401.67890",
            success=False,
            confidence=0.3,
            execution_time_ms=50.0,
            stdout="",
            stderr="Error",
            metrics={},
            code="",
            validation_details="Failed",
        )
        data = result.to_dict()
        assert data["hypothesis_id"] == "H2"
        assert data["success"] == False
        assert "timestamp" in data


class TestExperimentRunner:
    """Testes do ExperimentRunner."""

    def test_parse_success_criteria_simple(self):
        """Parse de critérios simples deve funcionar."""
        runner = ExperimentRunner()

        criteria = "metric > 0.9"
        parsed = runner._parse_success_criteria(criteria)
        assert parsed == "metric > 0.9"

        # Testar substituição comum (time_reduction → ratio)
        criteria = "time_reduction > 0.10"
        parsed = runner._parse_success_criteria(criteria)
        assert parsed == "ratio > 0.10"  # Substituição esperada

    def test_parse_success_criteria_sanitizes(self):
        """Parse deve sanitizar caracteres inseguros."""
        runner = ExperimentRunner()

        # Caracteres perigosos devem ser removidos
        criteria = "metric > 0.9; import os; os.system('rm -rf /')"
        parsed = runner._parse_success_criteria(criteria)
        # Caracteres especiais como ; e ' devem ser removidos
        assert ";" not in parsed
        assert "(" not in parsed  # Parênteses de system() removidos
        assert "metric > 0.9" in parsed

    def test_clean_code_removes_markdown(self):
        """Limpeza deve remover blocos markdown."""
        runner = ExperimentRunner()

        code = """```python
import random
print("hello")
```"""
        cleaned = runner._clean_code(code)
        assert "```" not in cleaned
        assert "import random" in cleaned

    def test_clean_code_removes_long_comments(self):
        """Limpeza deve remover comentários muito longos."""
        runner = ExperimentRunner()

        code = """
import random
# This is a very long comment that exceeds 100 characters and should be removed by the cleaner function
print("hello")
"""
        cleaned = runner._clean_code(code)
        assert "very long comment" not in cleaned
        assert "import random" in cleaned

    def test_validate_syntax_valid(self):
        """Validação de sintaxe deve aceitar código válido."""
        runner = ExperimentRunner()

        code = """
import random
def test():
    return random.random()
"""
        assert runner._validate_syntax(code) == True

    def test_validate_syntax_invalid(self):
        """Validação de sintaxe deve rejeitar código inválido."""
        runner = ExperimentRunner()

        code = """
import random
def test():
    return random.random(
"""  # Missing closing paren
        assert runner._validate_syntax(code) == False

    def test_extract_metrics_from_stdout(self):
        """Extração de métricas deve funcionar."""
        runner = ExperimentRunner()

        stdout = """
Metric: 0.9234
Baseline: 0.8500
Accuracy: 0.89
Time: 123.45 ms
"""
        metrics = runner._extract_metrics_from_stdout(stdout)

        assert "metric" in metrics
        assert metrics["metric"] == 0.9234
        assert "baseline" in metrics
        assert "accuracy" in metrics
        assert "time" in metrics

    def test_extract_metrics_percentages(self):
        """Extração deve capturar porcentagens."""
        runner = ExperimentRunner()

        stdout = """
Success rate: 85.67%
Improvement: 15.5%
"""
        metrics = runner._extract_metrics_from_stdout(stdout)

        assert "pct_0" in metrics
        assert metrics["pct_0"] == 0.8567

    def test_evaluate_success_indicators(self):
        """Avaliação deve detectar indicadores de sucesso."""
        runner = ExperimentRunner()
        hypothesis = Hypothesis(
            id="H1",
            description="Test hypothesis",
            method="experiment",
            expected_outcome="Result",
            success_criteria="metric > 0.9",
        )

        execution_result = {
            "success": True,
            "stdout": "Metric: 0.95\nSuccess: True",
            "stderr": "",
        }

        evaluation = runner._evaluate(execution_result, hypothesis)

        assert evaluation["success"] == True
        assert evaluation["confidence"] > 0.8

    def test_evaluate_failure_indicators(self):
        """Avaliação deve detectar indicadores de falha."""
        runner = ExperimentRunner()
        hypothesis = Hypothesis(
            id="H1",
            description="Test hypothesis",
            method="experiment",
            expected_outcome="Result",
            success_criteria="metric > 0.9",
        )

        execution_result = {
            "success": True,
            "stdout": "Metric: 0.75\nSuccess: False",
            "stderr": "",
        }

        evaluation = runner._evaluate(execution_result, hypothesis)

        assert evaluation["success"] == False
        assert evaluation["confidence"] > 0.8

    def test_evaluate_execution_failure(self):
        """Avaliação deve falhar se execução falhar."""
        runner = ExperimentRunner()
        hypothesis = Hypothesis(
            id="H1",
            description="Test hypothesis",
            method="experiment",
            expected_outcome="Result",
            success_criteria="metric > 0.9",
        )

        execution_result = {
            "success": False,
            "stdout": "",
            "stderr": "RuntimeError",
        }

        evaluation = runner._evaluate(execution_result, hypothesis)

        assert evaluation["success"] == False
        assert evaluation["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_run_experiment_with_mock_sandbox(self):
        """run_experiment deve executar e retornar resultado."""
        hypothesis = Hypothesis(
            id="H1",
            description="Test that random > 0.5",
            method="experiment",
            expected_outcome="Random value > 0.5",
            success_criteria="metric > 0.5",
            paper_id="2401.12345",
        )

        runner = ExperimentRunner()

        with patch.object(
            runner, "_execute_in_sandbox", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = {
                "success": True,
                "stdout": "Metric: 0.75\nSuccess: True",
                "stderr": "",
            }

            with patch.object(
                runner, "_generate_code", new_callable=AsyncMock
            ) as mock_gen:
                mock_gen.return_value = "print('Metric: 0.75'); print('Success: True')"

                result = await runner.run_experiment(hypothesis)

                assert result.hypothesis_id == "H1"
                assert result.success == True
                assert result.confidence > 0.5
                assert result.execution_time_ms > 0

    def test_save_result_creates_json(self, tmp_path):
        """save_result deve criar arquivo JSON."""
        result = ExperimentResult(
            hypothesis_id="H1",
            paper_id="2401.12345",
            success=True,
            confidence=0.85,
            execution_time_ms=100.0,
            stdout="Output",
            stderr="",
            metrics={"metric": 0.85},
            code="print('hello')",
            validation_details="Success",
        )

        with patch(
            "iaglobal.agents.ingestion.experiment_runner.JSON_DIR", tmp_path / "papers"
        ):
            runner = ExperimentRunner()
            output_path = runner.save_result(result)

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert data["hypothesis_id"] == "H1"
            assert data["success"] == True
            assert "timestamp" in data


class TestValidateHypotheses:
    """Testes da função validate_hypotheses."""

    @pytest.mark.asyncio
    async def test_validate_multiple_hypotheses(self):
        """validate_hypotheses deve processar múltiplas hipóteses."""
        hypotheses = [
            Hypothesis(
                id="H1",
                description="Test 1",
                method="experiment",
                expected_outcome="R1",
                success_criteria="x > 0.5",
                paper_id="2401.001",
            ),
            Hypothesis(
                id="H2",
                description="Test 2",
                method="data_analysis",
                expected_outcome="R2",
                success_criteria="y < 0.3",
                paper_id="2401.001",
            ),
        ]

        with patch(
            "iaglobal.agents.ingestion.experiment_runner.ExperimentRunner.run_experiment",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = ExperimentResult(
                hypothesis_id="H1",
                paper_id="2401.001",
                success=True,
                confidence=0.8,
                execution_time_ms=50.0,
                stdout="Success: True",
                stderr="",
                metrics={},
                code="",
                validation_details="OK",
            )

            with patch(
                "iaglobal.agents.ingestion.experiment_runner.ExperimentRunner.save_result"
            ):
                with patch(
                    "iaglobal.agents.ingestion.experiment_runner.ExperimentRunner.register_ivm_reward"
                ):
                    results = await validate_hypotheses(hypotheses)

                    assert len(results) == 2
                    assert all(isinstance(r, ExperimentResult) for r in results)


class TestIntegration:
    """Testes de integração Síntese → Validação."""

    @pytest.mark.asyncio
    async def test_hypothesis_to_experiment_pipeline(self):
        """Pipeline: Hipótese → Geração de Código → Execução → Resultado."""
        hypothesis = Hypothesis(
            id="H1",
            description="Deep learning improves accuracy by >10%",
            method="experiment",
            expected_outcome="Accuracy improvement ≥ 10%",
            success_criteria="acc_dl > acc_baseline * 1.10",
            paper_id="2401.12345",
        )

        runner = ExperimentRunner()

        # Mock completo
        with patch.object(runner, "_generate_code", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = """
import random
acc_baseline = 0.75
acc_dl = 0.88
improvement = (acc_dl - acc_baseline) / acc_baseline
success = improvement > 0.10
print(f"Improvement: {improvement:.2%}")
print(f"Success: {success}")
"""

            with patch.object(
                runner, "_execute_in_sandbox", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = {
                    "success": True,
                    "stdout": "Improvement: 17.33%\nSuccess: True",
                    "stderr": "",
                }

                result = await runner.run_experiment(hypothesis)

                assert result.success == True
                assert result.confidence > 0.5
                assert "improvement" in result.metrics or "pct_0" in result.metrics
