# PythonNormalizer — Pipeline de Normalização Sintática

## Visão Geral

O `PythonNormalizer` é um pipeline determinístico que processa todo código Python gerado por LLM antes de:
- Validação semântica
- AST parsing
- Score de qualidade
- Persistência em disco

## Pipeline

```
LLM Output
    ↓
Extract Code (remove markdown, texto externo)
    ↓
Sanitize (limpeza básica)
    ↓
ruff format (padronização determinística)
    ↓
ruff check --fix (correções automáticas)
    ↓
ast.parse (validação sintática)
    ↓
NormalizeResult
```

## Instalação

```bash
pip install ruff
```

## Uso Básico

```python
from iaglobal.diagnostics.python_normalizer import PythonNormalizer

normalizer = PythonNormalizer()
result = normalizer.normalize(code)

if result.syntax_valid:
    return result.fixed  # código normalizado
else:
    # enviar para RepairEngine
    raise SyntaxError(result.syntax_error)
```

## Integração com RepairEngine

O `RepairEngine` automaticamente normaliza código antes de tentar reparo:

```python
from iaglobal.diagnostics.repair_engine import RepairEngine

engine = RepairEngine()
report = await engine.repair(code, error)

# Internamente:
# 1. normalize_before_repair(code, error)
# 2. Se syntax_valid: usa código normalizado
# 3. Se syntax_invalid: usa código original + estratégia de reparo
```

## Integração com SemanticValidator

O `SemanticValidatorAgent` normaliza código antes de validar:

```python
from iaglobal.agents.semantic_validator import SemanticValidatorAgent

validator = SemanticValidatorAgent()
result = validator.validate(code, task)

# Internamente:
# 1. PythonNormalizer.normalize(code)
# 2. Se syntax_valid: usa código normalizado para validação
# 3. Score calculado sobre código normalizado (não bruto)
```

## NormalizeResult

```python
@dataclass
class NormalizeResult:
    original: str          # Código original (LLM output)
    sanitized: str         # Após extract & sanitize
    formatted: str         # Após ruff format
    fixed: str             # Após ruff check --fix
    syntax_valid: bool     # ast.parse() succeeded?
    syntax_error: Optional[str]
    ruff_format_errors: list
    ruff_check_errors: list
```

## Benefícios

### Redução de SyntaxError
- Indentação padronizada
- Blocos bem formados
- Aspas normalizadas

### Imports Organizados
- Ordem alfabética automática
- Imports duplicados removidos
- Imports não utilizados removidos

### Score Justo
- Código normalizado antes de pontuar
- Penaliza apenas problemas estruturais
- Ignora diferenças cosméticas

### Diffs Limpos
- Formatação consistente
- Sem ruído de estilo
- Revisão facilitada

## Exemplos

### Exemplo 1: Código com Markdown

**Input:**
```python
"""
Aqui está seu código:

```python
import os

def hello():
    print( 'world' )
```

Espero que ajude!
"""
```

**Output:**
```python
def hello():
    print("world")
```

### Exemplo 2: Imports Desorganizados

**Input:**
```python
import sys
import os
import asyncio

async def main():
    print(os.getcwd(), sys.version)
    await asyncio.sleep(0)
```

**Output:**
```python
import asyncio
import os
import sys


async def main():
    print(os.getcwd(), sys.version)
    await asyncio.sleep(0)
```

### Exemplo 3: Código Inválido

**Input:**
```python
def hello():
print("world")  # indentação errada
```

**Output:**
```python
# syntax_valid = False
# syntax_error = "Expected an indented block after function definition"
# Enviar para RepairEngine → ValidatorRetry
```

## Configuração Avançada

### Ruff Path Personalizado

```python
normalizer = PythonNormalizer(ruff_path="/usr/local/bin/ruff")
```

### Timeout Personalizado

Editando `python_normalizer.py`:
```python
result = subprocess.run(
    [self.ruff_cmd, "format", temp_path],
    timeout=30,  # default: 10
    ...
)
```

## Troubleshooting

### Ruff não encontrado

```
Warning: Ruff não encontrado (ruff). Instale com: pip install ruff
```

**Solução:**
```bash
pip install ruff
```

### Timeout no format

```
Warning: Ruff format timeout
```

**Solução:** Aumentar timeout ou reduzir tamanho do código.

### Código válido mas syntax_valid=False

Verifique `syntax_error`:
```python
result = normalizer.normalize(code)
if not result.syntax_valid:
    print(result.syntax_error)  # detalhe do erro
```

## Performance

- **ruff format**: ~10-50ms para 1000 linhas
- **ruff check --fix**: ~20-100ms para 1000 linhas
- **ast.parse**: <1ms para 1000 linhas

**Total**: ~50-150ms para código típico (<500 linhas)

## Arquitetura

```
iaglobal/
├── diagnostics/
│   ├── python_normalizer.py      # Pipeline principal
│   ├── repair_engine.py          # Integra com normalizer
│   └── ...
├── agents/
│   └── semantic_validator.py     # Integra com normalizer
└── tests/
    └── test_python_normalizer.py # 16 testes
```

## Contratos

### Normalization Contract

Todo código Python deve passar por `PythonNormalizer` antes de:
1. `ast.parse()`
2. `SemanticValidatorAgent.validate()`
3. `RepairEngine.repair()`
4. `ArtifactWriter.write()`

### Exception: Código Não-Python

O normalizer é específico para Python. Para outros languages:
- HTML: usar HTML formatter
- JSON: usar JSON parser
- Genérico: passar direto

## Futuro

- [ ] Suporte a TypeScript (`prettier`)
- [ ] Suporte a Markdown (`prettier`)
- [ ] Configuração via `pyproject.toml`
- [ ] Cache de código normalizado
- [ ] Parallel ruff execution

## Referências

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [AST Gateway](iaglobal/security/ast_gateway.py)
- [Repair Engine](iaglobal/diagnostics/repair_engine.py)
- [Semantic Validator](iaglobal/agents/semantic_validator.py)