# Arquitetura do Subsistema Diagnostics

## Evolução

### Versão Inicial (Pipeline)
```
Planner/Builder/Validator
    ↓
Cada um fazia:
  - Classificação
  - Reparo
  - Logs
```

**Problemas:**
- Duplicação de código
- Acoplamento alto
- Heurísticas espalhadas
- Sem observabilidade unificada

### Versão Atual (Subsistema Coeso)
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
    ↓
TelemetryCollector
```

**Vantagens:**
- Separação clara de responsabilidades
- Baixo acoplamento
- Estratégias plugáveis
- Observabilidade rica
- Evolução independente

---

## Princípios de Design

### 1. Separação Domínio/Causa

```python
# ANTES:
category = ErrorCategory.IMPORT

# DEPOIS:
domain = ErrorCategory.IMPORT
cause = ErrorCause.MODULE_NOT_FOUND
```

**Benefício:** Estatísticas granulares, seleção precisa de estratégias.

### 2. Duas Confianças

```python
classifier_confidence = 0.95  # "Isso é MODULE_NOT_FOUND"
repair_confidence = 0.75      # "Acho que corrigi"
```

**Benefício:** Avalia classificadores e estratégias separadamente.

### 3. Estratégias por Capacidade

```python
# ANTES:
map = {
    ErrorCategory.SYNTAX: SyntaxRepairStrategy,
}

# DEPOIS:
class SyntaxRepairStrategy:
    handles = {ErrorCategory.SYNTAX, ErrorCategory.LEXICAL}
```

**Benefício:** Auto-registro, sem mapa central, extensível.

### 4. Chain of Responsibility

```python
SyntaxClassifier → JsonClassifier → ImportClassifier → GenericClassifier
```

**Benefício:** Elimina if/elif, fácil adicionar classificadores.

### 5. Idempotência

```python
class SyntaxRepairStrategy:
    is_idempotent = True
```

**Benefício:** Estratégias idempotentes são seguras em pipelines distribuídos.

### 6. Cadeia de Reparos

```python
RepairReport(
    attempt=3,
    parent_report=previous_report,
    repair_chain=[r1, r2],
)
```

**Benefício:** Reconstrói sequência completa de reparos.

---

## Modelo de Domínio

### ErrorDescriptor

```python
@dataclass
class ErrorDescriptor:
    # Identificação
    domain: ErrorCategory
    cause: ErrorCause
    severity: Severity
    
    # Confianças (separadas)
    classifier_confidence: float
    repair_confidence: Optional[float]
    
    # Recuperabilidade
    recoverable: bool
    
    # Detalhes
    component: str
    error_type: str
    error_message: str
    error_line: Optional[int]
    error_column: Optional[int]
    
    # Histórico
    repair_attempts: List[Dict]
    parent_report: Optional[RepairReport]
```

### RepairReport

```python
@dataclass
class RepairReport:
    success: bool
    before_code: str
    after_code: Optional[str]
    descriptor: ErrorDescriptor
    strategy_used: str
    attempt: int
    parent_report: Optional[RepairReport]
    repair_chain: List[RepairReport]
    execution_metrics: Dict[str, Any]
    diagnostics: Dict[str, Any]
```

---

## Fluxo de Execução

### 1. Classificação

```
Exception
    ↓
ErrorClassifierEngine
    ↓
Chain of Responsibility
    ↓
ErrorDescriptor
```

### 2. Reparo

```
ErrorDescriptor
    ↓
RepairEngine (seleciona por capacidade)
    ↓
RepairStrategy (executa)
    ↓
RepairResult
    ↓
RepairReport
```

### 3. Telemetria

```
RepairReport
    ↓
execution_metrics (latency, cost, model)
diagnostics (domain, cause, severity)
    ↓
EvolutionFeedback
```

---

## Estatísticas Habilitadas

### Distribuição por Domínio

```sql
SELECT domain, cause, COUNT(*), AVG(classifier_confidence), SUM(success)
FROM repair_reports
GROUP BY domain, cause;
```

### Recuperação por Severidade

```sql
SELECT severity, COUNT(*), AVG(repair_confidence), success_rate
FROM repair_reports
WHERE recoverable = true
GROUP BY severity;
```

### Eficácia de Estratégias

```sql
SELECT strategy_used, domain, cause, 
       COUNT(*) as attempts,
       SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*) as success_rate,
       AVG(repair_confidence) as avg_confidence
FROM repair_reports
GROUP BY strategy_used, domain, cause;
```

---

## Integração com Outros Subsistemas

### BanditPolicy

```python
# Usa ErrorDescriptor para decisão
if descriptor.domain == ErrorCategory.IMPORT:
    # Não tenta repair, falha rápido
    return False
```

### EvolutionEngine

```python
# Recebe feedback de reparos
feedback = {
    "domain": descriptor.domain.value,
    "cause": descriptor.cause.value,
    "strategy": report.strategy_used,
    "success": report.success,
    "confidence": descriptor.repair_confidence,
}
```

### MetricsCollector

```python
# Coleta métricas de reparos
metrics = {
    "repair_latency": report.execution_metrics["latency"],
    "repair_success_rate": success_count / total_count,
    "avg_confidence": avg(descriptor.repair_confidence),
}
```

---

## Extensibilidade

### Novo Classificador

```python
class CustomClassifier(BaseErrorClassifier):
    def can_classify(self, error, context) -> bool:
        return isinstance(error, CustomError)
    
    def _classify(self, error, context) -> ErrorDescriptor:
        return ErrorDescriptor(
            domain=ErrorCategory.RUNTIME,
            cause=ErrorCause.UNKNOWN,
            severity=Severity.MEDIUM,
            classifier_confidence=0.8,
        )

error_classifier.add_classifier(CustomClassifier(), position=0)
```

### Nova Estratégia

```python
class CustomStrategy(RepairStrategy):
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

repair_engine.register_strategy(CustomStrategy())
```

---

## Contrato de Módulo

```python
from iaglobal.diagnostics import (
    # Engines
    error_classifier,
    repair_engine,
    
    # Tipos
    ErrorDescriptor,
    ErrorCategory,
    ErrorCause,
    Severity,
    RepairReport,
)
```

---

## Testes

```bash
# Validação completa
python -m pytest iaglobal/tests/test_diagnostics_subsystem.py -v

# 27 testes:
# - ErrorDescriptor (6)
# - ErrorClassifier (5)
# - RepairEngine (4)
# - RepairReport (4)
# - Strategy Idempotence (3)
# - Domain/Cause Separation (3)
# - Integration (2)
```

---

## Próximos Passos

1. **RepairTelemetryCollector** — Persiste RepairReports em banco
2. **RepairEvent** — Evento para EvolutionFeedback
3. **Verify** — Método de verificação pós-reparo
4. **StrategyRanking** — Rankeia estratégias por histórico
5. **AdaptiveRetry** — Ajusta max_attempts baseado em histórico

---

## Não-Negociáveis

- ✅ Async-only
- ✅ No print() (usa logging)
- ✅ Lineage marker em todos os arquivos
- ✅ ASTGateway para parsing
- ✅ Testes validam contrato
