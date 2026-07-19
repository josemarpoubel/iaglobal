# 🧬 Interface — Membrana de Sinalização Externa

```
iaglobal/interface/
├── __init__.py
└── chat_agent.py
```

A `interface` é a **membrana semi-permeável** do ecossistema iaglobal — o ponto único
de entrada para sinais externos (linguagem natural) serem traduzidos em comandos
estruturados e encaminhados à colônia de `EvoAgent`s.

## Princípios Arquiteturais

| Princípio | Implementação |
|-----------|---------------|
| **Membrana inteligente** | `_modelo_roteado_por_bandit` — nenhum LLM é chamado diretamente |
| **PSC compliance** | Toda geração passa por `_get_critic().arbitrar_geracao()` |
| **DNA gate** | `EvoAgentColony.registrar` valida `lineage_marker` (16 chars) |
| **Separation of concerns** | Interface não conhece provedores, apenas delega ao crítico |

## Fluxo de Execução

```
Input (string)
    │
    ▼
┌──────────────────────────────────────┐
│  pydantic_ai Agent (FunctionModel)   │
│  model = _modelo_roteado_por_bandit  │
│  output_type = IntencaoBiologica     │
│                                      │
│  Internamente:                       │
│    _modelo_roteado_por_bandit()      │
│      → _get_critic().arbitrar_geracao()  │
│        → BanditPolicy.generate()     │
│          → provider_router → LLM     │
└──────────────┬───────────────────────┘
               │
               ▼
    IntencaoBiologica (comando, urgencia, familia_alvo)
               │
               ▼
┌──────────────────────────────────────┐
│  EvoAgentColony.selecionar()         │
│  - Por especialização (se indicada)  │
│  - Fallback: menor taxa de falha     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  EvoAgent.handle(comando)            │
│  pipeline metabólico completo        │
│  → Expression (synthesis + metrics)  │
└──────────────┬───────────────────────┘
               │
               ▼
    { "resposta": Expression.to_dict(),
      "synthesis": "...",
      "intencao": {...},
      "execution_metrics": {...} }
```

## API Pública

### `interagir_com_colonia(colonia, user_input)`

Ponto de entrada único. Traduz linguagem natural → ação do agente.

```python
async def interagir_com_colonia(
    colonia: EvoAgentColony,
    user_input: str,
) -> dict
```

**Retorno:**
```python
{
    "resposta": dict | None,       # Expression.to_dict()
    "synthesis": str | None,       # Expressao.synthesis
    "intencao": dict,              # IntencaoBiologica.model_dump()
    "agente_utilizado": str,       # especializacao do EvoAgent
    "execution_metrics": {         # para JointOptimizationLoop
        "success": bool,
        "latency": float | None,
        "cost": float,
        "model": str | None,
    },
}
```

**Erros:**
- `"erro": "falha_extracao"` — `arbitrar_geracao` falhou
- `"erro": "colonia_vazia"` — nenhum EvoAgent registrado

### `criar_colonia_evoagents(especializacoes, nadph_reserve=0.5)`

Fábrica que instancia `EvoAgent.genesis()` para cada especialização.

```python
async def criar_colonia_evoagents(
    especializacoes: list[str],
    nadph_reserve: float = 0.5,
) -> EvoAgentColony
```

### `class EvoAgentColony`

Pool thread-safe de `EvoAgent`s indexado por especialização.

| Método | Descrição |
|--------|-----------|
| `registrar(agente, especializacao)` | Valida DNA (isinstance + 16-char marker) e adiciona ao pool |
| `selecionar(especializacao=None)` | Retorna agente por especialização ou fallback por fitness |
| `registrar_resultado(esp, sucesso, latencia)` | Atualiza métricas de fitness do agente |

### `class IntencaoBiologica`

Schema pydantic da intenção extraída pela membrana de sinalização.

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `comando` | `str` | — | Ação ou tarefa solicitada |
| `urgencia` | `str` | `"normal"` | `baixa \| normal \| alta \| critica` |
| `familia_alvo` | `Optional[str]` | `None` | Especialização do EvoAgent, se indicada |
| `contexto_adicional` | `dict` | `{}` | Metadados extras |
| `diagnostico` | `Optional[DiagnosticoFalha]` | `None` | Diagnóstico de falha preenchido pelo FailureAnalyzer |
| `plano_correcao` | `Optional[str]` | `None` | Código corrigido proposto pós-análise |
| `recovery` | `Optional[RecoveryMetrics]` | `None` | Métricas de recuperação (delta erro→correção) |

### `DiagnosticoFalha` (definido em `iaglobal/interface/diagnostico.py`)

Schema estruturado do erro de execução — o **mRNA do sistema imune**.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo_erro` | `str` | Classe do erro: `SyntaxError`, `TimeoutError`, `ImportError`, `NameError`, `RuntimeError`, `Unknown` |
| `mensagem` | `str` | Mensagem principal do erro (primeira linha significativa) |
| `linha` | `Optional[int]` | Linha onde o erro ocorreu |
| `arquivo` | `Optional[str]` | Arquivo onde o erro ocorreu |
| `fingerprint` | `str` | SHA256 do traceback sanitizado — **chave da vacina universal** |
| `codigo_original` | `str` | Código que falhou |
| `output_bruto` | `str` | Output completo do `code_executor` |

### `RecoveryMetrics` (definido em `iaglobal/interface/diagnostico.py`)

Marcadores de recuperação que alimentam o `JointOptimizationLoop`.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tentativas` | `int` | Número de tentativas até sucesso |
| `delta_segundos` | `float` | Tempo entre primeiro erro e correção bem-sucedida |
| `vacina_aplicada` | `bool` | Se a correção usou vacina pré-existente (resposta inata) |
| `fingerprint_erro` | `str` | Fingerprint do erro original (para deduplicação no JOL) |

## Sistema Imunológico Adaptativo — Ciclo de Correção

A interface agora integra o **FailureAnalyzer** como parte do pipeline do EvoAgent:

```
EvoAgent.handle()
    │
    ├─ gera código → code_executor (subprocesso isolado)
    │                    │
    │                    ▼ falha?
    │           ┌────────┴────────┐
    │           ▼                  ▼
    │   FailureAnalyzer      Expressão final
    │   (parse_error)        (success)
    │           │
    │           ▼ fingerprint
    │   VaccineLedger
    │           │
    │   ┌──────┴──────┐
    │   ▼              ▼
    │  HIT (inata)   MISS (adaptativa)
    │  ← 36ms        ├─ generate_correction_plan()
    │                │   ├─ determinística (33ms, 6 padrões)
    │                │   └─ Crítico (LLM, erros complexos)
    │                └─ register_vaccine() → ledger
    │                              │
    │                              ▼ RecoveryMetrics
    │                     JointOptimizationLoop
    │                     (recalibra pesos do Bandit)
    │
    └─ Expression com synthesis + recovery_metrics
```

### Cinética medida

| Resposta | Latência | Mecanismo |
|----------|----------|-----------|
| 🟢 Inata (vacina) | ~36ms | `check_vaccine()` → solução imediata, sem LLM |
| 🟡 Adaptativa determinística | ~33ms | `generate_correction_plan()` → pattern matching local |
| 🔴 Adaptativa via Crítico | variável | `arbitrar_geracao()` → LLM via BanditPolicy |

## Integração com o Chokepoint do Sistema

Diferente de chamar um LLM diretamente, a interface usa `pydantic_ai` com um
`FunctionModel` cujo corpo delega para `_get_critic().arbitrar_geracao()`.

Isso garante:
1. Respeito ao **PSC (Protocolo de Soberania do Crítico)** — Layer 2
2. Roteamento via **BanditPolicy** — Layer 1 (ε-greedy, circuit breaker, fallback)
3. Resolução local (tools + memória + **FailureAnalyzer**) antes de chamar LLM
4. Métricas `execution_metrics` + `RecoveryMetrics` no formato do `JointOptimizationLoop`

## Testes

```bash
# Schema + DNA gate + seleção
pytest iaglobal/tests/test_chat_agent_integration.py -v

# FailureAnalyzer (36 testes)
pytest iaglobal/tests/test_failure_analyzer.py -v

# Simulação de estresse imunológico (6 testes)
pytest iaglobal/tests/test_immune_stress.py -v

# Ativação Fase 3 (4 testes)
pytest iaglobal/tests/test_immune_activation.py -v

# JointOptimizationLoop (21 testes)
pytest iaglobal/tests/test_joint_optimization.py -v
```
