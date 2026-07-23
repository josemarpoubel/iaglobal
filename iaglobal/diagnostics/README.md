# iaglobal/diagnostics — Subsistema de Diagnóstico e Reparo

## Visão Geral

Subsistema coeso para classificação, diagnóstico e reparo de erros em código Python e JSON.

## Arquitetura

```
Exception
    ↓
ErrorClassifier (Chain of Responsibility)
    ↓
ErrorDescriptor (domínio + causa)
    ↓
RepairEngine (estratégias por capacidade)
    ↓
RepairStrategy
    ↓
RepairReport (attempt, chain, telemetry)
```

## Separação de Responsabilidades

| Componente | Responsabilidade |
|------------|-----------------|
| **ErrorClassifier** | ENTENDE o erro |
| **ErrorDescriptor** | REPRESENTA o diagnóstico |
| **RepairEngine** | ORQUESTRA o fluxo |
| **RepairStrategy** | IMPLEMENTA a correção |
| **RepairReport** | REGISTRA o resultado |

## Domínios e Causas

### Domínios (ErrorCategory)

- `SYNTAX` — Erros de sintaxe Python
- `LEXICAL` — Caracteres inválidos, strings
- `JSON` — Erros de parsing JSON
- `IMPORT` — Erros de importação
- `RUNTIME` — Erros de execução
- `NETWORK` — Timeouts, conexão
- `VALIDATION` — Erros de validação
- `UNKNOWN` — Não classificado

### Causas (ErrorCause)

Cada domínio tem causas específicas:

**IMPORT:**
- `MODULE_NOT_FOUND`
- `SYMBOL_NOT_FOUND`
- `CIRCULAR_IMPORT`
- `RELATIVE_IMPORT`

**JSON:**
- `EXTRA_DATA`
- `EXPECTING_VALUE`
- `INVALID_ESCAPE`

**SYNTAX/LEXICAL:**
- `SYNTAX_ERROR`
- `UNTERMINATED_STRING`
- `MISSING_INDENT`
- `INVALID_CHARACTER`

## Duas Confianças

O sistema separa duas naturezas de confiança:

```python
ErrorDescriptor(
    classifier_confidence=0.95,  # "Isso realmente é um MODULE_NOT_FOUND"
    repair_confidence=0.75,      # "Acho que consegui corrigir"
)
```

Isso permite avaliar classificadores e estratégias separadamente.

## Uso Básico

```python
from iaglobal.diagnostics import repair_engine, error_classifier

# Reparo automático
report = await repair_engine.repair(
    code="x = 'hello",
    error=SyntaxError("unterminated string"),
    context={"component": "validator"},
)

if report.success:
    return report.after_code
else:
    log(report.get_diagnostics())
```

## Classificação Direta

```python
from iaglobal.diagnostics import error_classifier

descriptor = error_classifier.classify(
    error=ModuleNotFoundError("No module named 'numpy'"),
    context={"component": "builder"},
)

print(descriptor.domain)    # ErrorCategory.IMPORT
print(descriptor.cause)     # ErrorCause.MODULE_NOT_FOUND
print(descriptor.severity)  # Severity.HIGH
print(descriptor.recoverable)  # False
```

## Estratégias por Capacidade

Cada estratégia declara suas capacidades:

```python
class SyntaxRepairStrategy(RepairStrategy):
    name = "syntax_repair"
    handles = {ErrorCategory.SYNTAX, ErrorCategory.LEXICAL}
    is_idempotent = True
```

O `RepairEngine` resolve automaticamente baseado no `ErrorDescriptor`.

## Cadeia de Reparos

O `RepairReport` mantém histórico completo:

```python
report = await repair_engine.repair(code, error, max_attempts=3)

# Acessa cadeia
chain = report.get_chain_summary()
# [
#   {"attempt": 1, "strategy": "syntax_repair", "success": False},
#   {"attempt": 2, "strategy": "syntax_repair", "success": True},
# ]
```

## Idempotência

Estratégias declaram se são idempotentes:

```python
if strategy.is_idempotent:
    # Seguro aplicar múltiplas vezes
    result = await strategy.execute(code, descriptor)
```

Estratégias idempotentes:
- ✅ `SyntaxRepairStrategy`
- ✅ `JsonRecoveryStrategy`
- ✅ `UnicodeRepairStrategy`

Estratégias não-idempotentes:
- ❌ `GenericRetryStrategy`

## Telemetria

Cada `RepairReport` inclui:

```python
report.execution_metrics = {
    "success": True,
    "latency": 0.5,
    "cost": 0.0,
    "model": "syntax_fallback",
}
```

E `ErrorDescriptor` fornece diagnóstico completo:

```python
diag = descriptor.get_diagnostics()
# {
#   "domain": "syntax",
#   "cause": "unterminated_string",
#   "severity": "low",
#   "classifier_confidence": 0.9,
#   "repair_confidence": 0.75,
#   ...
# }
```

## Integração com Evolution

Cada `RepairReport` pode gerar evento para o Evolution Engine:

```python
event = {
    "type": "repair_completed",
    "domain": descriptor.domain.value,
    "cause": descriptor.cause.value,
    "strategy": report.strategy_used,
    "success": report.success,
    "classifier_confidence": descriptor.classifier_confidence,
    "repair_confidence": descriptor.repair_confidence,
    "latency": report.execution_metrics["latency"],
}
```

## Testes

```bash
python -m pytest iaglobal/tests/test_diagnostics_subsystem.py -v
```

## Extensão

### Adicionar Novo Classificador

```python
from iaglobal.diagnostics.error_classifier import BaseErrorClassifier

class CustomErrorClassifier(BaseErrorClassifier):
    def can_classify(self, error, context) -> bool:
        return isinstance(error, CustomError)
    
    def _classify(self, error, context) -> ErrorDescriptor:
        return ErrorDescriptor(
            domain=ErrorCategory.RUNTIME,
            cause=ErrorCause.UNKNOWN,
            severity=Severity.MEDIUM,
            classifier_confidence=0.8,
        )

# Adiciona na cadeia
error_classifier.add_classifier(CustomErrorClassifier(), position=0)
```

### Adicionar Nova Estratégia

```python
from iaglobal.diagnostics.repair_strategies import RepairStrategy, RepairResult

class CustomRepairStrategy(RepairStrategy):
    name = "custom_repair"
    handles = {ErrorCategory.RUNTIME}
    is_idempotent = True
    
    async def execute(self, code, descriptor, context) -> RepairResult:
        # Implementa reparo
        return RepairResult(
            success=True,
            after_code=fixed_code,
            confidence=0.8,
            model="custom_repair",
            changes_made=["custom_fix"],
        )

# Registra
repair_engine.register_strategy(CustomRepairStrategy())
```

## Contrato de Módulo

```python
from iaglobal.diagnostics import (
    error_classifier,
    repair_engine,
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
    Severity,
    RepairReport,
)
```

## Não-Negociáveis

- ✅ Async-only: todos os métodos de reparo são async
- ✅ No print(): usa logging
- ✅ Lineage marker: todos os arquivos têm header
- ✅ Testes: 27 testes validam o subsistema
