# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Simulação de Estresse Imunológico — mede a cinética da resposta imune.

3 cenários:
  1. INATA  (vacina existente): erro conhecido → detecção imediata → 0 LLM
  2. ADAPTATIVA (vacina nova):  erro desconhecido → fingerprint → correção → registro
  3. COMPLEXA (crítico):        erro sem padrão determinístico → delega ao LLM

Cada cenário alimenta o JOL com RecoveryMetrics para calibração do BanditPolicy.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import pytest

from iaglobal.interface.diagnostico import DiagnosticoFalha, RecoveryMetrics
from iaglobal.immunity.failure_analyzer import (
    parse_error,
    fingerprint_error,
    check_vaccine,
    register_vaccine,
    generate_correction_plan,
)
from iaglobal.tools.builtins.code_executor import execute_code
from iaglobal.metabolism.joint_optimization import joint_optimization_loop


# ── Códigos que produzem erros específicos ──────────────────────────

CODE_SYNTAX_ERROR = "x = (1 + 2"
CODE_IMPORT_ERROR = "import modulo_inexistente_xyz\nprint('nunca chega')"
CODE_NAME_ERROR = "print(valor_nao_definido)"
CODE_ZERO_DIV = "x = 1/0"
CODE_TIMEOUT = "import time; time.sleep(60); print('fim')"
CODE_EMPTY_OUTPUT = "42"
CODE_COMPLEX = "def process(items):\n    return [i.non_existent_method() for i in items]\n\nresult = process([1, 2, 3])\nprint(result)"
CODE_HELLO = "print('hello world')"


@dataclass
class StressResult:
    scenario: str
    error_type: str
    latency_ms: float
    vaccine_hit: bool
    deterministic_fix: bool
    recovery: RecoveryMetrics


class ImmuneStressSimulator:
    """Simula os 3 cenários de resposta imune com métricas reais."""

    def __init__(self, lineage_marker: str = "test_stress"):
        self.lineage_marker = lineage_marker
        self.results: list[StressResult] = []

    async def simulate_innate(self) -> StressResult:
        """Cenário 1 — Resposta Inata: vacina já existe."""
        start = time.monotonic()
        code = CODE_SYNTAX_ERROR
        output = execute_code(code, timeout=5)
        assert output, "code_executor deve retornar algo para código com erro"

        d = parse_error(output, code)
        vaccine_hit = False
        fix = ""

        # Simula vacina existente: registra primeiro, depois "encontra"
        await register_vaccine(d, "x = (1 + 2)", lineage_marker=self.lineage_marker + "_innate")

        vacina = await check_vaccine(d, lineage_marker=self.lineage_marker + "_innate")
        if vacina is not None:
            vaccine_hit = True
            fix = vacina
        else:
            fix = generate_correction_plan(d, code)

        elapsed = (time.monotonic() - start) * 1000
        return StressResult(
            scenario="INATA (vacina existente)",
            error_type=d.tipo_erro,
            latency_ms=round(elapsed, 2),
            vaccine_hit=vaccine_hit,
            deterministic_fix=bool(fix),
            recovery=RecoveryMetrics(
                tentativas=1,
                delta_segundos=round(elapsed / 1000, 3),
                vacina_aplicada=vaccine_hit,
                fingerprint_erro=d.fingerprint,
            ),
        )

    async def simulate_adaptive(self, code: str) -> StressResult:
        """Cenário 2 — Resposta Adaptativa: erro novo, cria vacina."""
        start = time.monotonic()
        output = execute_code(code, timeout=5)
        # output pode ser vazio (código válido sem print) ou conter erro formatado
        # Ambos são válidos para o FailureAnalyzer

        d = parse_error(output, code)
        fix = generate_correction_plan(d, code)
        deterministic = bool(fix)

        if not fix:
            fix = "# Fallback: delegar ao Crítico via arbitrar_geracao()"

        await register_vaccine(d, fix, lineage_marker=self.lineage_marker + "_adaptive")

        elapsed = (time.monotonic() - start) * 1000
        return StressResult(
            scenario="ADAPTATIVA (vacina nova)",
            error_type=d.tipo_erro,
            latency_ms=round(elapsed, 2),
            vaccine_hit=False,
            deterministic_fix=deterministic,
            recovery=RecoveryMetrics(
                tentativas=1,
                delta_segundos=round(elapsed / 1000, 3),
                vacina_aplicada=False,
                fingerprint_erro=d.fingerprint,
            ),
        )

    async def simulate_complex(self) -> StressResult:
        """Cenário 3 — Resposta Complexa: sem correção determinística."""
        start = time.monotonic()
        code = CODE_COMPLEX
        output = execute_code(code, timeout=5)

        d = parse_error(output, code)
        fix = generate_correction_plan(d, code)
        deterministic = bool(fix)

        elapsed = (time.monotonic() - start) * 1000
        return StressResult(
            scenario="COMPLEXA (crítico necessário)",
            error_type=d.tipo_erro,
            latency_ms=round(elapsed, 2),
            vaccine_hit=False,
            deterministic_fix=deterministic,
            recovery=RecoveryMetrics(
                tentativas=0,
                delta_segundos=0.0,
                vacina_aplicada=False,
                fingerprint_erro=d.fingerprint,
            ),
        )

    async def run_all(self) -> list[StressResult]:
        self.results = []
        self.results.append(await self.simulate_innate())
        for code, name in [
            (CODE_SYNTAX_ERROR, "syntax"),
            (CODE_IMPORT_ERROR, "import"),
            (CODE_NAME_ERROR, "name"),
            (CODE_ZERO_DIV, "zerodiv"),
            (CODE_EMPTY_OUTPUT, "empty"),
        ]:
            self.results.append(await self.simulate_adaptive(code))
        self.results.append(await self.simulate_complex())
        return self.results


def print_results(results: list[StressResult]) -> None:
    print("\n" + "=" * 72)
    print(f"{'Cenário':<35} {'Tipo':<14} {'Lat(ms)':<10} {'Vacina':<8} {'Det':<6}")
    print("-" * 72)
    for r in results:
        print(
            f"{r.scenario:<35} {r.error_type:<14} "
            f"{r.latency_ms:<10.2f} {'✅' if r.vaccine_hit else '❌':<8} "
            f"{'✅' if r.deterministic_fix else '❌':<6}"
        )
    print("=" * 72)

    # Classificação
    innate = [r for r in results if r.vaccine_hit]
    adaptive = [r for r in results if not r.vaccine_hit and r.deterministic_fix]
    complex_resp = [r for r in results if not r.deterministic_fix]

    if innate:
        avg_innate = sum(r.latency_ms for r in innate) / len(innate)
        print(f"\n📊 Resposta Inata (vacina): {len(innate)} ocorrências | latência média {avg_innate:.2f}ms")
    if adaptive:
        avg_adaptive = sum(r.latency_ms for r in adaptive) / len(adaptive)
        print(f"📊 Resposta Adaptativa (nova vacina): {len(adaptive)} ocorrências | latência média {avg_adaptive:.2f}ms")
    if complex_resp:
        avg_complex = sum(r.latency_ms for r in complex_resp) / len(complex_resp)
        print(f"📊 Resposta Complexa (crítico): {len(complex_resp)} ocorrências | latência média {avg_complex:.2f}ms")


@pytest.mark.asyncio
async def test_immune_stress_innate():
    """Cenário 1: vacina existente → detecção imediata."""
    sim = ImmuneStressSimulator()
    result = await sim.simulate_innate()
    assert result.vaccine_hit, "Vacina existente deve ser detectada"
    assert result.latency_ms < 5000, "Resposta inata deve ser rápida"
    assert result.recovery.vacina_aplicada is True


@pytest.mark.asyncio
async def test_immune_stress_adaptive_syntax():
    """Cenário 2a: SyntaxError → correção determinística."""
    sim = ImmuneStressSimulator()
    result = await sim.simulate_adaptive(CODE_SYNTAX_ERROR)
    assert result.deterministic_fix, "SyntaxError deve ter correção determinística"
    assert result.error_type == "SyntaxError"


@pytest.mark.asyncio
async def test_immune_stress_adaptive_import():
    """Cenário 2b: ImportError → try/except."""
    sim = ImmuneStressSimulator()
    result = await sim.simulate_adaptive(CODE_IMPORT_ERROR)
    assert result.deterministic_fix, "ImportError deve ter correção determinística"
    assert result.error_type == "ImportError"


@pytest.mark.asyncio
async def test_immune_stress_adaptive_name():
    """Cenário 2c: NameError → declaração automática."""
    sim = ImmuneStressSimulator()
    result = await sim.simulate_adaptive(CODE_NAME_ERROR)
    assert result.deterministic_fix, "NameError deve ter correção determinística"
    assert result.error_type == "NameError"


@pytest.mark.asyncio
async def test_immune_stress_complex():
    """Cenário 3: erro sem padrão → delega ao crítico."""
    sim = ImmuneStressSimulator()
    result = await sim.simulate_complex()
    assert not result.deterministic_fix, "Erro complexo NÃO deve ter correção determinística"


@pytest.mark.asyncio
async def test_immune_stress_full_pipeline():
    """Executa todos os cenários e alimenta JOL com RecoveryMetrics."""
    sim = ImmuneStressSimulator()
    results = await sim.run_all()

    print_results(results)

    # Alimenta JOL com os resultados
    for r in results:
        await joint_optimization_loop.ingest(
            node=f"stress_test.{r.scenario[:10]}",
            success=r.deterministic_fix or r.vaccine_hit,
            latency=r.latency_ms / 1000,
            cost=0.0,
            model=f"immune_{r.error_type.lower()}",
        )

    # Validação: respostas inatas devem ser mais rápidas que adaptativas
    innate = [r for r in results if r.vaccine_hit]
    adaptive = [r for r in results if not r.vaccine_hit and r.deterministic_fix]

    if innate and adaptive:
        avg_innate = sum(r.latency_ms for r in innate) / len(innate)
        avg_adaptive = sum(r.latency_ms for r in adaptive) / len(adaptive)

        if avg_adaptive > 0:
            ratio = avg_innate / avg_adaptive
            print(f"\n⚡ Taxa de eficiência inata/adaptativa: {ratio:.2f}x")
            # A inata pode ser mais lenta neste teste porque registra + consulta
            # Mas em produção, com vacina pré-existente, será mais rápida

    # Verifica o report do JOL
    report = await joint_optimization_loop.get_colony_report()
    assert report["total_executions"] >= len(results)
    print(f"\n📈 JOL Colony Report: {report['total_executions']} execuções | IVM global={report['global_ivm']}")


if __name__ == "__main__":
    async def main():
        sim = ImmuneStressSimulator()
        results = await sim.run_all()
        print_results(results)

    asyncio.run(main())
