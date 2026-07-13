# EntropySentinel Integration Guide

## 🧬 Visão Geral

O **EntropySentinel** é a implementação da **Lei da Ordem** de Raymond Holliwell no ecossistema iaglobal:

> *"Você não pode chegar para a lareira e dizer: me dê o calor, que depois eu te dou a madeira. Tudo tem uma ordem exata, uma sequência, um passo a passo a ser seguido."*

### Propósito

Detectar e penalizar **entropia** (caos) em execuções de agentes e skills:

1. **Redundância** - Repetição inútil de padrões
2. **Loops de Tokens** - Alucinação de repetição (ex: "e então e então e então")
3. **Dependências Circulares** - Agentes em ciclo vicioso (A→B→C→A)
4. **Caos Estrutural** - Falta de coerência na saída

---

## ⚡ Operação

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    EntropySentinel                          │
│  (Singleton — único para todo o ecossistema)                │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌────────────────┐  ┌─────────────────┐
│ EntropyProfile│  │DependencyGraph │  │FitnessPenalty   │
│ - total_exec  │  │ - agent→deps   │  │ - multiplier    │
│ - chaotic     │  │ - DFS cycle    │  │ - 1.0 → 0.1     │
│ - trend       │  │ - detection    │  │ - applied       │
└───────────────┘  └────────────────┘  └─────────────────┘
```

### Ciclo de Detecção

```
EXECUÇÃO DO AGENTE
       ↓
EntropySentinel.record_execution(agent_name, output)
       ↓
┌──────────────────────────────────────┐
│ 1. analyze_payload(output)           │
│    - Redundância (>40% repetição)    │
│    - Loops (3+ palavras consecutivas)│
│    - Caos estrutural (variância)     │
└──────────────────────────────────────┘
       ↓
entropy_score: 0.0 (ordem) → 1.0 (caos)
       ↓
┌──────────────────────────────────────┐
│ 2. Atualizar EntropyProfile          │
│    - total_executions++              │
│    - entropy_history.append()        │
│    - chaotic_executions++ (se >0.6)  │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│ 3. Calcular penalty                  │
│    penalty = entropy_score × 0.5     │
│    fitness_final = fitness × (1-pen) │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│ 4. Verificar apoptose                │
│    Se chaos_rate > 80% → apoptose    │
│    Se entropy_score ≥ 0.8 → apoptose │
└──────────────────────────────────────┘
       ↓
RETORNAR: {entropy_score, is_chaotic, penalty, apoptosis_recommended, trend}
```

---

## 🔧 Uso

### Básico

```python
from iaglobal.immunity.entropy_sentinel import entropy_sentinel

# Registrar execução
result = entropy_sentinel.record_execution(
    agent_name="coder_agent",
    payload=output_do_agente,
)

if result["apoptosis_recommended"]:
    logger.error("Agente %s deve sofrer apoptose!", agent_name)
```

### Penalty de Fitness

```python
# Aplicar penalty ao fitness score
original_fitness = 0.9
fitness_final, report = entropy_sentinel.apply_entropy_penalty_to_fitness(
    agent_name="coder_agent",
    original_fitness=original_fitness,
)

# fitness_final será menor se entropia for alta
```

### Detecção de Dependências Circulares

```python
# Registrar dependências
entropy_sentinel.register_dependency("agent_a", "agent_b")
entropy_sentinel.register_dependency("agent_b", "agent_c")
entropy_sentinel.register_dependency("agent_c", "agent_a")

# Detectar ciclo
cycle = entropy_sentinel.detect_circular_dependencies("agent_a")
if cycle:
    logger.error("Ciclo detectado: %s", " → ".join(cycle))
    entropy_sentinel.record_circular_dependency_violation("agent_a", cycle)
```

### Relatório de Entropia

```python
report = entropy_sentinel.get_entropy_report("agent_name")
# {
#   "agent_name": "agent_name",
#   "total_executions": 10,
#   "chaotic_executions": 3,
#   "chaos_rate": 0.3,
#   "redundancy_violations": 1,
#   "loop_violations": 2,
#   "circular_dependency_violations": 0,
#   "structural_chaos_violations": 0,
#   "last_entropy_score": 0.45,
#   "entropy_trend": "stable",
#   "apoptosis_risk": False
# }
```

---

## 🛡️ Integração com ImmuneOrchestrator

O EntropySentinel é automaticamente integrado ao sistema imunológico:

```python
from iaglobal.immunity.immune_orchestrator import immune_orchestrator

report = immune_orchestrator.scan_execution(
    skill_name="minha_skill",
    execution_context={"membrane_key": "..."},
    output=codigo_gerado,
    metrics={"cpu_seconds": 2.5, ...},
)

# report inclui:
# - entropy_report: detalhe da entropia
# - fitness_penalty: penalty aplicado
# - apoptosis_recommended: se deve eliminar agente
```

---

## 📊 Limiares Configuráveis

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `_REDUNDANCY_THRESHOLD` | 0.4 | 40% de repetição = tóxico |
| `_LOOP_THRESHOLD` | 3 | 3+ repetições = loop |
| `_ENTROPY_APOPTOSIS_THRESHOLD` | 0.8 | 80% de caos = apoptose |
| `_HISTORY_MAX_SIZE` | 20 | Últimas 20 execuções |

---

## 🧪 Testes

```bash
# Executar testes do EntropySentinel
pytest tests/test_entropy_sentinel.py -v

# 23 testes cobrindo:
# - Detecção de redundância
# - Detecção de loops
# - Detecção de caos estrutural
# - Dependências circulares
# - Penalty de fitness
# - Tendência entrópica
# - Singleton
```

---

## 🌱 Tendências Entrópicas

O EntropySentinel calcula tendências baseadas no histórico:

- **`improving`**: Entropia média das últimas 3 execuções é < 80% da média anterior
- **`degrading`**: Entropia média das últimas 3 execuções é > 120% da média anterior
- **`stable`**: Sem mudança significativa
- **`insufficient_data`**: Menos de 3 execuções

---

## 🚨 Apoptose

Apoptose é recomendada quando:

1. **Caos atual crítico**: `entropy_score >= 0.8`
2. **Caos persistente**: `chaotic_executions / total_executions > 0.8`

Quando apoptose é recomendada:
- Log de erro é emitido
- Agente é marcado para quarentena
- ImmuneOrchestrator pode triggerar eliminação

---

## 📈 Monitoramento

### Health Check

```python
from iaglobal.immunity.immune_orchestrator import immune_orchestrator

status = immune_orchestrator.health_check()
# {
#   "active_detectors": 8,
#   "quarantined_skills": 0,
#   "entropy_profiles": 5,
#   "entropy_apoptosis_threshold": 0.8,
#   ...
# }
```

### Métricas

- **`entropy_profiles`**: Número de agentes monitorados
- **`entropy_apoptosis_threshold`**: Limiar atual de apoptose
- **`active_detectors`**: Total de detectores (8, incluindo EntropySentinel)

---

## 🔗 Conexão com Leis Universais

O EntropySentinel implementa diretamente a **Lei da Ordem**:

- **Ordem** = Baixa entropia, estrutura coerente, sequência lógica
- **Caos** = Alta entropia, redundância, loops, dependências circulares

Ao penalizar entropia, o sistema:
1. Incentiva agentes a manterem ordem
2. Elimina agentes que degradam a estrutura
3. Preserva a "sequência exata" de Holliwell

---

## 🧬 Evolução Futura

Próximos passos (Fase 9):

1. **SymbiosisScore** — Bonificar sinergia entre agentes (Lei da Caridade)
2. **VacuumTrigger** — Forçar diversidade pós-apoptose (Lei do Vácuo)
3. **FusionEngine** — Síntese de agentes híbridos via ressonância de linhagem
4. **AncestryTree** — Rastreio de mutações no Obsidian

---

## 📝 Referências

- **Arquivo**: `iaglobal/immunity/entropy_sentinel.py`
- **Testes**: `tests/test_entropy_sentinel.py` (23 testes)
- **Integração**: `iaglobal/immunity/immune_orchestrator.py`
- **Lei da Ordem**: Raymond Holliwell, "The Universal Laws of Success"

---

*"A célula que não evolui, morre. O sistema que não aprende, entra em entropia."*