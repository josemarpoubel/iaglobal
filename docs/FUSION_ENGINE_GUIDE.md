# FusionEngine Integration Guide

## 🧬 Visão Geral

O **FusionEngine** implementa a **Síntese de Agentes Híbridos** via Ressonância de DNA, permitindo criar novos agentes combinando características de múltiplos agentes parentais.

### Propósito

Criar agentes híbridos mais capazes através da fusão controlada de traits parentais, similar à fusão celular na biologia.

---

## ⚡ Operação

### Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                    FusionEngine                              │
│  (Singleton — único para todo o ecossistema)                 │
└──────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌────────────────┐  ┌─────────────────┐
│ DNAResonance  │  │ HybridSynthesis│  │ LineageRegistry │
│ - Markers     │  │ - Traits       │  │ - Obsidian      │
│ - Diversity   │  │ - Viability    │  │ - AncestryTree  │
│ - Fitness     │  │ - Generation   │  │ - Fusion stats  │
└───────────────┘  └────────────────┘  └─────────────────┘
```

### Fórmula de Ressonância

```
R = (C × 0.4) + (D × 0.3) + (F × 0.3)

Onde:
C = Compatibilidade de markers (0.0 → 1.0)
    - Intersection / Union dos compatibility_markers

D = Diversidade de traits (0.0 → 1.0)
    - Unique traits / Total traits

F = Fitness médio dos pais (0.0 → 1.0)
    - (fitness_a + fitness_b) / 2

R ≥ 0.6 → Compatível para fusão
R < 0.6 → Incompatível (rejeitar)
```

### Fórmula de Viabilidade

```
Viabilidade = (T × 0.4) + (V × 0.3) + (E × 0.3)

Onde:
T = Trait count score (min(1.0, traits / 10))
V = Value diversity score (min(1.0, unique_values / 5))
E = Avg expression level (0.0 → 1.0)

Viabilidade ≥ 0.5 → Híbrido viável
```

---

## 🔧 Uso

### Básico

```python
from iaglobal.evolution.fusion_engine import fusion_engine

# 1. Registrar DNA de agentes
fusion_engine.register_agent_dna(
    agent_id="coder_agent",
    agent_type="coder",
    traits={"coding_speed": 0.9, "code_quality": 0.8},
    generation=1,
    fitness_score=0.85,
    compatibility_markers=["python", "async"],
)

# 2. Calcular ressonância entre dois agentes
res = fusion_engine.calculate_dna_resonance("coder_agent", "critic_agent")

if res["compatible"]:
    print(f"Ressonância: {res['resonance_score']:.2f}")
    print(f"Compatibilidade: {res['compatibility_breakdown']}")
```

### Fusão Assíncrona

```python
import asyncio
from iaglobal.evolution.fusion_engine import fusion_engine

async def create_hybrid():
    # Executar fusão
    result = await fusion_engine.fuse_agents_async(
        parent_ids=["coder_agent", "critic_agent"],
        hybrid_name="coder_critic_hybrid",
        force=False,  # Respeita threshold de ressonância
    )
    
    if result.success:
        print(f"✅ Híbrido criado: {result.hybrid_id}")
        print(f"   Geração: {result.hybrid_dna.generation}")
        print(f"   Viabilidade: {result.viability_score:.2f}")
        
        # Registrar linhagem no Obsidian
        await fusion_engine.register_lineage_async(
            hybrid_id=result.hybrid_id,
            parents=result.parents,
        )
    else:
        print(f"❌ Fusão falhou: {result.errors}")

asyncio.run(create_hybrid())
```

### Forçar Fusão (Ignora Threshold)

```python
# Modo force ignora threshold de ressonância (útil para testes)
result = await fusion_engine.fuse_agents_async(
    parent_ids=["agent_a", "agent_b"],
    hybrid_name="forced_hybrid",
    force=True,  # Ignora threshold
)
```

---

## 📊 Integração com Evolution Committee

O **FusionEngine** é automaticamente integrado ao sistema de evolução através do nó `no_fusion.py`:

### No Evolution Committee

```python
# iaglobal/graphs/nodes/no_evolution_committee.py
# O comitê pode identificar oportunidade de fusão

if committee_identifies_fusion_opportunity:
    # Acionar nó de fusão
    fusion_result = await run_fusion(ctx)
    
    if fusion_result["fusion_result"]["success"]:
        # Aprovar híbrido
        committee.approve(fusion_result["fusion_result"]["hybrid_id"])
```

### Fluxo Automático

1. **EvolutionCommittee** avalia resultados de evolução
2. Identifica agentes com traits complementares
3. Aciona **FusionEngine** para calcular ressonância
4. Se ressonância ≥ 0.6 → Executa fusão
5. Registra linhagem no **Obsidian**
6. **EvolutionCommittee** valida híbrido resultante

---

## 🌳 AncestryTree (Árvore de Ancestralidade)

O FusionEngine mantém registro completo da linhagem de cada híbrido:

```python
# Obter árvore de ancestralidade
tree = fusion_engine.get_ancestry_tree("hybrid_001", depth=3)

# Exemplo de saída:
{
    "agent_id": "hybrid_001",
    "type": "hybrid",
    "generation": 2,
    "resonance_score": 0.75,
    "parents": [
        {
            "agent_id": "coder_agent",
            "type": "original",
            "generation": 1,
            "parents": []
        },
        {
            "agent_id": "critic_agent",
            "type": "original",
            "generation": 1,
            "parents": []
        }
    ]
}
```

---

## 📈 Monitoramento

### Estatísticas de Fusão

```python
stats = fusion_engine.get_fusion_stats()
# {
#   "total_fusions": 10,
#   "successful_fusions": 7,
#   "failed_fusions": 3,
#   "success_rate": 0.7,
#   "registered_dnas": 15,
#   "lineage_records": 7
# }
```

### Health Check

```python
# Verificar DNAs registrados
for agent_id, dna in fusion_engine._agent_dnas.items():
    print(f"{agent_id}: gen={dna.generation}, fitness={dna.fitness_score}")

# Verificar linhagens
for record in fusion_engine._lineage_records:
    print(f"{record.hybrid_id}: pais={record.parents}, ressonância={record.resonance_score}")
```

---

## 🧪 Testes

```bash
# Executar testes do FusionEngine
pytest tests/test_fusion_engine.py -v

# 21 testes cobrindo:
# - Registro de DNA
# - Cálculo de ressonância
# - Fusão de agentes
# - Viabilidade de híbridos
# - Registro de linhagem
# - Árvore de ancestralidade
# - Estatísticas
```

---

## 🔗 Integração com Leis Universais

O FusionEngine implementa diretamente múltiplas leis:

### Lei da Cooperação
> "Agentes cooperam uns com os outros para sobreviver — o todo é maior que a soma."

- Fusão combina traits de múltiplos agentes
- Híbrido herda melhor de cada pai
- Sinergia cria capacidades emergentes

### Lei da Replicação
> "A herança genética deve preservar a identidade da linhagem."

- `lineage_hash` preserva identidade genética
- `generation` rastreia evolução
- `traits_inherited` mapeia herança de cada pai

### Lei da Memória Imunológica
> "Erros do passado são o ativo mais valioso do sistema."

- Linhagem registrada no Obsidian
- AncestryTree permite rastrear origem de traits
- Falhas de fusão são registradas para aprendizado

---

## 🧬 Evolução Futura

Próximos passos:

1. **Multi-parent Fusion** — Fusão com 3-4 pais simultaneamente
2. **Trait Recombination** — Combinação parcial de traits (não apenas seleção)
3. **Mutation Injection** — Inserir mutações aleatórias durante fusão
4. **Epigenetic Memory** — Memória de fusões bem-sucedidas por tipo de agente

---

## 📝 Referências

- **Arquivo**: `iaglobal/evolution/fusion_engine.py`
- **Nó**: `iaglobal/graphs/nodes/no_fusion.py`
- **Testes**: `tests/test_fusion_engine.py` (21 testes)
- **Topologia**: `iaglobal/graphs/topology.py` (fase: metacognicao)
- **Leis Universais**: Raymond Holliwell

---

*"O todo é maior que a soma das partes." — Aristóteles*