# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Exemplo de uso do subsistema diagnostics.

Demonstra:
  - Classificação em cadeia
  - Domínio + causa separados
  - Duas confianças
  - Estratégias por capacidade
  - Cadeia de reparos
"""

import asyncio
import json

from iaglobal.diagnostics import (
    ErrorCategory,
    ErrorCause,
    ErrorDescriptor,
    Severity,
    error_classifier,
    repair_engine,
)


async def example_syntax_error():
    """Exemplo: erro de sintaxe Python."""
    print("\n=== Exemplo 1: SyntaxError ===")

    code = "def foo()\n    pass"
    error = SyntaxError("expected ':'")
    error.lineno = 1

    # Classifica
    descriptor = error_classifier.classify(
        error,
        context={"component": "validator", "code": code},
    )

    print(f"Domínio: {descriptor.domain.value}")
    print(f"Causa: {descriptor.cause.value}")
    print(f"Severidade: {descriptor.severity.value}")
    print(f"Confiança (classificação): {descriptor.classifier_confidence:.2f}")
    print(f"Recuperável: {descriptor.recoverable}")
    print(f"Prioridade de reparo: {descriptor.get_repair_priority():.2f}")

    # Repara
    report = await repair_engine.repair(
        code=code,
        error=error,
        context={"component": "validator"},
    )

    print(f"\nEstratégia usada: {report.strategy_used}")
    print(f"Tentativa: {report.attempt}")
    print(f"Sucesso: {report.success}")
    print(f"Confiança (reparo): {descriptor.repair_confidence}")

    if report.success:
        print(f"Código após reparo:\n{report.after_code}")

    print(f"\nDiagnóstico completo: {report.get_diagnostics()}")


async def example_json_error():
    """Exemplo: erro JSON."""
    print("\n=== Exemplo 2: JSON Error ===")

    code = '{"name": "test", "value": 123} extra_data'

    try:
        json.loads(code)
    except json.JSONDecodeError as e:
        # Classifica
        descriptor = error_classifier.classify(
            e,
            context={"component": "planner", "json_text": code},
        )

        print(f"Domínio: {descriptor.domain.value}")
        print(f"Causa: {descriptor.cause.value}")
        print(f"Severidade: {descriptor.severity.value}")
        print(f"Confiança: {descriptor.classifier_confidence:.2f}")

        # Repara
        report = await repair_engine.repair(
            code=code,
            error=e,
            context={"component": "planner"},
        )

        print(f"\nEstratégia: {report.strategy_used}")
        print(f"Sucesso: {report.success}")

        if report.success:
            print(f"JSON corrigido: {report.after_code}")
            # Verifica se é JSON válido
            parsed = json.loads(report.after_code)
            print(f"JSON parseado: {parsed}")


async def example_import_error():
    """Exemplo: erro de import (não recuperável)."""
    print("\n=== Exemplo 3: ImportError (não recuperável) ===")

    code = "import numpy as np"
    error = ModuleNotFoundError("No module named 'numpy'")

    # Classifica
    descriptor = error_classifier.classify(
        error,
        context={"component": "builder", "module": "numpy"},
    )

    print(f"Domínio: {descriptor.domain.value}")
    print(f"Causa: {descriptor.cause.value}")
    print(f"Severidade: {descriptor.severity.value}")
    print(f"Confiança: {descriptor.classifier_confidence:.2f}")
    print(f"Recuperável: {descriptor.recoverable}")
    print(f"Pode tentar reparo: {descriptor.can_attempt_repair()}")

    # Tenta reparo (vai falhar)
    report = await repair_engine.repair(
        code=code,
        error=error,
        context={"component": "builder"},
    )

    print(f"\nEstratégia: {report.strategy_used}")
    print(f"Sucesso: {report.success}")
    print(f"Motivo: {report.diagnostics.get('reason')}")


async def example_repair_chain():
    """Exemplo: cadeia de reparos."""
    print("\n=== Exemplo 4: Cadeia de Reparos ===")

    code = "x = 'hello"
    error = SyntaxError("unterminated string")

    # Simula múltiplas tentativas
    report = await repair_engine.repair(
        code=code,
        error=error,
        context={"component": "validator"},
        max_attempts=2,
    )

    print(f"Tentativas: {report.attempt}")
    print(f"Estratégia: {report.strategy_used}")
    print(f"Sucesso: {report.success}")

    # Acessa histórico
    chain = report.get_chain_summary()
    print(f"\nCadeia de reparos ({len(chain)} tentativas):")
    for attempt in chain:
        status = "✓" if attempt["success"] else "✗"
        print(
            f"  {status} Attempt {attempt['attempt']}: {attempt['strategy']} (confidence={attempt['confidence']:.2f})"
        )


async def example_capabilities():
    """Exemplo: capacidades do engine."""
    print("\n=== Exemplo 5: Capacidades do Engine ===")

    caps = repair_engine.get_capabilities()

    print("Estratégias registradas por categoria:")
    for category, strategies in caps.items():
        print(f"  {category}: {strategies}")


async def example_custom_descriptor():
    """Exemplo: cria ErrorDescriptor manualmente."""
    print("\n=== Exemplo 6: ErrorDescriptor Manual ===")

    descriptor = ErrorDescriptor(
        domain=ErrorCategory.IMPORT,
        cause=ErrorCause.CIRCULAR_IMPORT,
        severity=Severity.CRITICAL,
        classifier_confidence=0.95,
        recoverable=False,
        component="evolution_engine",
        error_type="ImportError",
        error_message="Circular import detected",
    )

    print(f"Descriptor: {descriptor}")
    print(f"É crítico: {descriptor.is_critical()}")
    print(f"Alta confiança: {descriptor.is_high_confidence()}")
    print(f"Prioridade: {descriptor.get_repair_priority():.2f}")

    # Adiciona tentativas de reparo
    descriptor.add_repair_attempt("import_fallback", success=False, confidence=0.0)

    print(f"\nTentativas: {len(descriptor.repair_attempts)}")
    print(f"Diagnóstico: {descriptor.get_diagnostics()}")


async def main():
    """Executa todos os exemplos."""
    print("=" * 60)
    print("DIAGNOSTICS SUBSYSTEM - EXEMPLOS DE USO")
    print("=" * 60)

    await example_syntax_error()
    await example_json_error()
    await example_import_error()
    await example_repair_chain()
    await example_capabilities()
    await example_custom_descriptor()

    print("\n" + "=" * 60)
    print("FIM DOS EXEMPLOS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
