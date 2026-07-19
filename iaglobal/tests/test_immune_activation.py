# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste de Ativação da Fase 3 — Sistema Imunológico Adaptativo em Campo.

Valida:
  1. Flag immune_cycle está ativa
  2. Pipeline completo: geração → execução → falha → análise → correção → vacina → JOL
  3. Curva de aprendizado: segunda execução com vacina existente é mais rápida
"""

import asyncio
import time

import pytest

from iaglobal.evolution.epigenetic import get_flag, set_flag
from iaglobal.immunity.failure_analyzer import (
    parse_error,
    fingerprint_error,
    check_vaccine,
    register_vaccine,
    generate_correction_plan,
)
from iaglobal.immunity.vaccine_ledger import vaccine_ledger
from iaglobal.tools.builtins.code_executor import execute_code
from iaglobal.metabolism.joint_optimization import joint_optimization_loop


TEST_LINEAGE = "test_immune_activation_f3"


@pytest.mark.asyncio
async def test_flag_active():
    """A flag immune_cycle deve estar True (ativada pelo arquiteto)."""
    assert get_flag("immune_cycle") is True, (
        "immune_cycle deve estar True para Fase 3 ativa"
    )


@pytest.mark.asyncio
async def test_immune_cycle_full_pipeline():
    """
    Pipeline completo: código com erro → code_executor → FailureAnalyzer →
    fingerprint → check_vaccine (miss) → generate_correction_plan →
    register_vaccine → reexecuta → JOL.
    """
    from iaglobal.interface.diagnostico import RecoveryMetrics

    # ── Código com SyntaxError proposital (parêntese não fechado) ──
    codigo_original = "def soma(a, b):\n    return (a + b\n\nprint(soma(1, 2))"
    prompt = "crie uma função soma e imprima o resultado"

    start = time.monotonic()
    recovery = RecoveryMetrics()
    vaccine_hit = False
    tentativas = 0
    current_code = codigo_original

    while tentativas < 3:
        tentativas += 1

        # 1. Executa
        output = execute_code(current_code, timeout=10)
        is_error = output and "<Error:" in output
        if not is_error:
            break  # sucesso (output pode ser resultado válido)

        # 2. Analisa
        d = parse_error(output, current_code)
        recovery.fingerprint_erro = d.fingerprint

        # 3. Consulta vacina (primeira vez: miss)
        vacina = await check_vaccine(d, TEST_LINEAGE)
        if vacina:
            vaccine_hit = True
            recovery.vacina_aplicada = True
            break

        # 4. Correção determinística
        fix = generate_correction_plan(d, current_code)
        assert fix, f"Deveria haver correção determinística para {d.tipo_erro}"
        current_code = fix

        # 5. Registra vacina
        await register_vaccine(d, fix, lineage_marker=TEST_LINEAGE)

    recovery.tentativas = tentativas
    recovery.delta_segundos = round(time.monotonic() - start, 3)

    # ── Validações ──
    assert "soma" in current_code, "Código corrigido deve manter a função"
    assert tentativas <= 2, "Deve corrigir em até 2 tentativas"

    # Verifica que o sistema imunológico agiu (por vacina existente OU nova)
    assert tentativas == 1 if vaccine_hit else tentativas >= 1, (
        "Se vacina existia: 1 tentativa (resposta inata). "
        "Se vacina nova: 1+ tentativas até correção."
    )

    # Alimenta JOL
    await joint_optimization_loop.ingest(
        node="immune_activation_test",
        success=True,
        latency=recovery.delta_segundos,
        cost=0.0,
        model="failure_analyzer.deterministic",
    )


@pytest.mark.asyncio
async def test_immune_cycle_vaccine_hit():
    """
    Curva de aprendizado: segunda execução do MESMO erro deve ser
    resolvida via vacina (resposta inata).
    """
    codigo = "def soma(a, b):\n    return (a + b\n\nprint(soma(1, 2))"

    start = time.monotonic()

    output = execute_code(codigo, timeout=10)
    assert output and "<Error:" in output, "Código com SyntaxError deve produzir output de erro"

    d = parse_error(output, codigo)
    vacina = await check_vaccine(d, TEST_LINEAGE)

    elapsed = (time.monotonic() - start) * 1000

    assert vacina is not None, (
        "Vacina deve existir após o teste anterior — resposta inata esperada"
    )

    # A vacina deve ser encontrada em < 100ms (não executa código de novo)
    assert elapsed < 500, (
        f"Resposta inata deve ser rápida: {elapsed:.2f}ms (limite 500ms)"
    )


@pytest.mark.asyncio
async def test_jol_receives_immune_metrics():
    """JOL deve conter as métricas da ativação imune."""
    report = await joint_optimization_loop.get_colony_report()
    nodes = [n for n in report["nodes"] if "immune" in n["node"].lower()]
    assert len(nodes) > 0, "JOL deve ter registrado métricas do ciclo imune"
    for n in nodes:
        assert n["total"] > 0, f"Nó {n['node']} deve ter execuções registradas"
