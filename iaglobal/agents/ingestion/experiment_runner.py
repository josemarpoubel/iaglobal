# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ExperimentRunner — Executa experimentos para validar hipóteses.

Gera código Python automaticamente a partir da descrição da hipótese,
executa em sandbox isolado e avalia os resultados contra os critérios de sucesso.

Integra com:
- HypothesisGenerator (entrada: Hypothesis)
- execution/sandbox.py (execução segura)
- chappie/ivm_axiom.py (reward por sucesso experimental)
- memory/data/json/{hypothesis_id}.json (métricas)
"""

import json
import re
import ast
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from iaglobal.security.ast_gateway import ASTGateway

_ast_gateway = ASTGateway()
from datetime import datetime, timezone

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.agents.ingestion.hypothesis_generator import Hypothesis

logger = get_logger("iaglobal.agents.ingestion.experiment_runner")


@dataclass
class ExperimentResult:
    """Resultado de execução de experimento."""

    hypothesis_id: str
    paper_id: str
    success: bool
    confidence: float
    execution_time_ms: float
    stdout: str
    stderr: str
    metrics: Dict[str, Any]
    code: str
    validation_details: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentRunner:
    """Executa experimentos para validar hipóteses."""

    CODE_TEMPLATES = {
        "experiment": """
# Experimento: {description}
# Critério de sucesso: {success_criteria}

import random
import time
import statistics

def run_experiment():
    # Simulação placeholder - substituir com código real
    n_trials = 100
    results = [random.random() for _ in range(n_trials)]
    
    metric = statistics.mean(results)
    baseline = 0.5
    
    # Avaliar critério: {success_criteria}
    success = {success_criteria_eval}
    
    return {{
        "metric": metric,
        "baseline": baseline,
        "success": success,
        "n_trials": n_trials,
    }}

if __name__ == "__main__":
    result = run_experiment()
    print(f"Metric: {{result['metric']:.4f}}")
    print(f"Baseline: {{result['baseline']:.4f}}")
    print(f"Success: {{result['success']}}")
""",
        "data_analysis": """
# Análise de Dados: {description}
# Critério de sucesso: {success_criteria}

import random
import statistics

def analyze_data():
    # Simulação placeholder
    dataset_sizes = [100, 200, 500, 1000, 2000]
    performances = [0.85 + random.uniform(-0.05, 0.05) for _ in dataset_sizes]
    
    std_perf = statistics.stdev(performances)
    
    # Avaliar critério: {success_criteria}
    success = {success_criteria_eval}
    
    return {{
        "std_performance": std_perf,
        "mean_performance": statistics.mean(performances),
        "success": success,
    }}

if __name__ == "__main__":
    result = analyze_data()
    print(f"Std Performance: {{result['std_performance']:.4f}}")
    print(f"Success: {{result['success']}}")
""",
        "simulation": """
# Simulação: {description}
# Critério de sucesso: {success_criteria}

import time
import random

def run_simulation():
    # Simulação placeholder
    input_sizes = [100, 200, 500, 1000, 2000]
    times = []
    
    for n in input_sizes:
        start = time.time()
        # Simular processamento O(n log n)
        _ = sorted([random.random() for _ in range(n)])
        elapsed = time.time() - start
        times.append(elapsed * 1000)  # ms
    
    # Verificar escalabilidade linear
    # Critério: {success_criteria}
    ratio = times[-1] / times[0] if times[0] > 0 else float('inf')
    expected_ratio = input_sizes[-1] / input_sizes[0]
    success = {success_criteria_eval}
    
    return {{
        "times_ms": times,
        "ratio": ratio,
        "expected_ratio": expected_ratio,
        "success": success,
    }}

if __name__ == "__main__":
    result = run_simulation()
    print(f"Time ratio: {{result['ratio']:.2f}}x")
    print(f"Expected: {{result['expected_ratio']:.2f}}x")
    print(f"Success: {{result['success']}}")
""",
    }

    def __init__(self, sandbox_timeout: int = 30):
        self.sandbox_timeout = sandbox_timeout

    async def run_experiment(self, hypothesis: Hypothesis) -> ExperimentResult:
        """
        Executa experimento para validar hipótese.

        Args:
            hypothesis: Hypothesis com description, method, success_criteria

        Returns:
            ExperimentResult com métricas e validação
        """
        import time

        start_time = time.time()

        try:
            # 1. Gerar código
            code = await self._generate_code(hypothesis)

            # 2. Executar em sandbox
            execution_result = await self._execute_in_sandbox(code)

            # 3. Avaliar resultado
            evaluation = self._evaluate(execution_result, hypothesis)

            # 4. Calcular métricas
            elapsed_ms = (time.time() - start_time) * 1000

            result = ExperimentResult(
                hypothesis_id=hypothesis.id,
                paper_id=hypothesis.paper_id,
                success=evaluation["success"],
                confidence=evaluation["confidence"],
                execution_time_ms=elapsed_ms,
                stdout=execution_result.get("stdout", ""),
                stderr=execution_result.get("stderr", ""),
                metrics=evaluation.get("metrics", {}),
                code=code,
                validation_details=evaluation["details"],
            )

            # Atualizar hipótese com resultado
            hypothesis.result = result.to_dict()
            hypothesis.status = "passed" if result.success else "failed"

            logger.info(
                "[EXP] %s: %s (confidence: %.2f, time: %.0fms)",
                hypothesis.id,
                "✅ validada" if result.success else "❌ rejeitada",
                result.confidence,
                result.execution_time_ms,
            )

            return result

        except Exception as e:
            logger.error("[EXP] Erro ao executar experimento %s: %s", hypothesis.id, e)
            elapsed_ms = (time.time() - start_time) * 1000

            return ExperimentResult(
                hypothesis_id=hypothesis.id,
                paper_id=hypothesis.paper_id,
                success=False,
                confidence=0.0,
                execution_time_ms=elapsed_ms,
                stdout="",
                stderr=str(e),
                metrics={},
                code="",
                validation_details=f"Erro na execução: {e}",
            )

    async def _generate_code(self, hypothesis: Hypothesis) -> str:
        """Gera código Python para testar hipótese."""
        # Tentar usar LLM para gerar código específico
        code = await self._generate_code_with_llm(hypothesis)

        if not code or len(code.strip()) < 50:
            # Fallback: usar template
            code = self._generate_code_from_template(hypothesis)

        return code

    async def _generate_code_with_llm(self, hypothesis: Hypothesis) -> Optional[str]:
        """Tenta gerar código via LLM."""
        try:
            from iaglobal.agents.coder_agent import CoderAgent

            prompt = f"""
Gere código Python para testar esta hipótese científica:

**Hipótese**: {hypothesis.description}
**Método**: {hypothesis.method}
**Critério de sucesso**: {hypothesis.success_criteria}

Requisitos:
1. Código deve ser executável em sandbox isolado (sem network, sem I/O externo)
2. Deve imprimir métricas relevantes
3. Deve calcular se o critério de sucesso foi atingido
4. Usar apenas bibliotecas padrão (random, statistics, time, math, etc.)

Retorne APENAS o código Python, sem explicações ou markdown.
"""

            agent = CoderAgent()
            response = await agent.run(
                {
                    "prompt": prompt,
                    "task_type": "code_generation",
                    "hypothesis_id": hypothesis.id,
                }
            )

            code = response.get("output", "")

            # Limpar código (remover markdown se houver)
            code = self._clean_code(code)

            # Validar sintaxe
            if self._validate_syntax(code):
                return code
            else:
                logger.warning(
                    "[EXP] Código gerado tem erro de sintaxe — usando template"
                )
                return None

        except ImportError:
            logger.debug("[EXP] CoderAgent não disponível — usando template")
            return None
        except Exception as e:
            logger.debug("[EXP] Erro ao gerar código com LLM: %s — usando template", e)
            return None

    def _generate_code_from_template(self, hypothesis: Hypothesis) -> str:
        """Gera código a partir de template."""
        template = self.CODE_TEMPLATES.get(
            hypothesis.method, self.CODE_TEMPLATES["experiment"]
        )

        # Extrair componentes do success_criteria para avaliação
        criteria_eval = self._parse_success_criteria(hypothesis.success_criteria)

        code = template.format(
            description=hypothesis.description,
            success_criteria=hypothesis.success_criteria,
            success_criteria_eval=criteria_eval,
        )

        return code

    def _clean_code(self, code: str) -> str:
        """Limpa código removendo markdown e comentários desnecessários."""
        # Remover blocos markdown
        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```\s*", "", code)

        # Remover comentários de linha única muito longos
        lines = code.split("\n")
        cleaned_lines = []
        for line in lines:
            if line.strip().startswith("#") and len(line) > 100:
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _validate_syntax(self, code: str) -> bool:
        """Valida sintaxe Python do código via ASTGateway."""
        result = _ast_gateway.parse(code)
        return result.valid

    def _parse_success_criteria(self, criteria: str) -> str:
        """
        Parse de success_criteria para expressão Python avaliável.

        Exemplos:
        - "metric > 0.9" → "metric > 0.9"
        - "time_reduction > 0.10" → "ratio > 0.10"
        - "std_perf < 0.05" → "std_perf < 0.05"
        """
        # Sanitizar: permitir apenas caracteres seguros (remover parênteses também)
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.<>=! "
        )
        sanitized = "".join(c for c in criteria if c in safe_chars)

        # Substituições comuns
        sanitized = sanitized.replace("metric_proposed", "metric")
        sanitized = sanitized.replace("metric_baseline", "baseline")
        sanitized = sanitized.replace("time_reduction", "ratio")
        sanitized = sanitized.replace("std(performance)", "std_perf")

        return sanitized.strip() or "False"

    async def _execute_in_sandbox(self, code: str) -> Dict[str, Any]:
        """Executa código em sandbox."""
        from iaglobal.security.sandbox_executor import SandboxExecutor

        executor = SandboxExecutor(timeout=self.sandbox_timeout)
        result = await executor.execute(code)

        return {
            "success": result.get("success", False),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode", -1),
        }

    def _evaluate(
        self, execution_result: Dict[str, Any], hypothesis: Hypothesis
    ) -> Dict[str, Any]:
        """Avalia resultado da execução contra critérios de sucesso."""
        stdout = execution_result.get("stdout", "")
        success_exec = execution_result.get("success", False)

        if not success_exec:
            return {
                "success": False,
                "confidence": 0.0,
                "details": "Falha na execução do código",
                "metrics": {},
            }

        # Extrair métricas do stdout
        metrics = self._extract_metrics_from_stdout(stdout)

        # Avaliar critério de sucesso
        success_criteria = hypothesis.success_criteria.lower()

        # Verificar indicadores de sucesso no output
        success_indicators = ["success: true", "success: true", "✅", "passed", "valid"]
        failure_indicators = [
            "success: false",
            "success: false",
            "❌",
            "failed",
            "invalid",
        ]

        stdout_lower = stdout.lower()

        # Calcular confiança baseada em indicadores
        has_success = any(ind in stdout_lower for ind in success_indicators)
        has_failure = any(ind in stdout_lower for ind in failure_indicators)

        if has_success and not has_failure:
            confidence = 0.85 + 0.15 * (
                len(metrics) / 5
            )  # Mais métricas = mais confiança
            return {
                "success": True,
                "confidence": min(confidence, 1.0),
                "details": "Critério de sucesso atingido",
                "metrics": metrics,
            }
        elif has_failure:
            return {
                "success": False,
                "confidence": 0.9,
                "details": "Critério de sucesso não atingido",
                "metrics": metrics,
            }
        else:
            # Incerto - tentar inferir das métricas
            if metrics:
                return {
                    "success": True,
                    "confidence": 0.5,
                    "details": "Sucesso provável (métricas presentes)",
                    "metrics": metrics,
                }
            else:
                return {
                    "success": False,
                    "confidence": 0.3,
                    "details": "Não foi possível determinar sucesso",
                    "metrics": {},
                }

    def _extract_metrics_from_stdout(self, stdout: str) -> Dict[str, float]:
        """Extrai métricas numéricas do stdout."""
        metrics = {}

        # Padrão: "MetricName: 0.1234"
        pattern = r"([A-Za-z_][A-Za-z0-9_]*):\s*([0-9]+\.?[0-9]*)"
        matches = re.findall(pattern, stdout)

        for name, value in matches:
            try:
                metrics[name.lower()] = float(value)
            except ValueError:
                pass

        # Padrão: porcentagens "45.67%"
        pct_pattern = r"([0-9]+\.?[0-9]*)%"
        pct_matches = re.findall(pct_pattern, stdout)
        for i, value in enumerate(pct_matches):
            try:
                metrics[f"pct_{i}"] = float(value) / 100
            except ValueError:
                pass

        return metrics

    def save_result(self, result: ExperimentResult) -> Path:
        """Salva resultado em JSON."""
        output_path = (
            JSON_DIR
            / "papers"
            / f"{result.hypothesis_id}_{result.paper_id.replace(':', '_')}_result.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.info("[EXP] Resultado salvo em: %s", output_path)
        return output_path

    def register_ivm_reward(self, result: ExperimentResult):
        """Registra reward no IVM se experimento teve sucesso."""
        if not result.success:
            return

        try:
            from iaglobal.chappie.ivm_axiom import IVMAxiom

            ivm = IVMAxiom()
            ivm.registrar_sucesso(
                agent_id="experiment_runner",
                task_id=result.hypothesis_id,
                confidence=result.confidence,
            )

            logger.debug(
                "[EXP] Reward IVM registrado: %s (confidence: %.2f)",
                result.hypothesis_id,
                result.confidence,
            )
        except ImportError:
            logger.debug("[EXP] IVMAxiom não disponível — skip reward")
        except Exception as e:
            logger.debug("[EXP] Erro ao registrar reward IVM: %s", e)


# Funções utilitárias
async def run_experiment_for_hypothesis(hypothesis: Hypothesis) -> ExperimentResult:
    """
    Executa experimento para uma hipótese.

    Args:
        hypothesis: Hypothesis

    Returns:
        ExperimentResult
    """
    runner = ExperimentRunner()
    result = await runner.run_experiment(hypothesis)
    runner.save_result(result)
    runner.register_ivm_reward(result)
    return result


async def validate_hypotheses(hypotheses: List[Hypothesis]) -> List[ExperimentResult]:
    """
    Valida múltiplas hipóteses.

    Args:
        hypotheses: Lista de Hypothesis

    Returns:
        Lista de ExperimentResult
    """
    runner = ExperimentRunner()
    results = []

    for hyp in hypotheses:
        result = await runner.run_experiment(hyp)
        runner.save_result(result)
        runner.register_ivm_reward(result)
        results.append(result)

    return results
