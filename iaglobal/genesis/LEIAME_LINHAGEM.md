# 🧬 Sistema de Linhagem Genesis - Documentação

## Visão Geral

O **Sistema de Linhagem Genesis** é o mecanismo de certificação e validação de DNA SHA3-512 que garante a integridade de todos os componentes do iaglobal ao longo do tempo. Inspirado na biologia celular, assim como uma célula só se divide se seu DNA estiver íntegro, nenhum agente ou skill pode nascer ou evoluir sem passar pelo Gatekeeper.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    GENESIS GATEKEEPER                       │
│              (Guardião da Linhagem Universal)               │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Verify     │───▶│   Integrity  │───▶│   DNA        │  │
│  │   Genesis    │    │     Tree     │    │  Calculator  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Tribunal   │    │   CBOR       │    │   SHA3-512   │  │
│  │  (Blueprint) │    │  Storage     │    │    Hash      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │    Agents    │ │    Skills    │ │   Engines    │
    │   (~30)      │ │   (~33)      │ │    (X)       │
    └──────────────┘ └──────────────┘ └──────────────┘
```

## Componentes Principais

### 1. `verifygenesis.py` - O Tribunal
- Valida a gênese primordial do sistema
- Compara hash SHA3-512 do blueprint vs. evolutive
- Bloqueia inicialização se houver violação

### 2. `genesis_gatekeeper.py` - O Guardião
- **Singleton thread-safe** que gerifica todo o sistema
- Calcula DNA de componentes: `SHA3-512(código + nome + tipo + versão + genesis_hash)`
- Mantém **Integrity Tree** em CBOR com histórico evolutivo
- Funcionalidades:
  - `certify_component()`: Certifica nascimento de agentes/skills
  - `validate_component()`: Valida DNA atual vs. esperado
  - `get_lineage_history()`: Retorna histórico evolutivo completo
  - `revoke_component()`: Revoga componentes comprometidos

### 3. `identity.py` - Identidade Efêmera do Nó
- Gera identidade RAM-only baseada no genesis
- Nome fonético camuflado (Pysecurity1024)
- Auto-destruição de chaves ao encerrar

### 4. `integrity_tree.cbor` - Árvore de Integridade
- Armazena certificados de todos os componentes
- Estrutura:
```json
{
  "genesis_hash": "cc7017b56557586095e8dc6dae27b3e6...",
  "components": [
    {
      "component_name": "CoderAgent",
      "component_type": "agent",
      "dna": "2b2d3d329459f602...",
      "version": "1.0.0",
      "certified_at": "2026-06-26T17:28:22.882",
      "status": "active",
      "evolution_count": 0
    }
  ],
  "created_at": "...",
  "last_updated": "..."
}
```

## Scripts de Certificação em Lote

### `batch_certify_agents.py`
Certifica todos os ~30 agentes do diretório `agents/`:
```bash
cd /workspace && PYTHONPATH=/workspace:$PYTHONPATH \
  python iaglobal/genesis/scripts/batch_certify_agents.py
```

**Resultado típico:**
- ✅ 21 agentes certificados
- ⚠️ 9 skipados (classes não encontradas devido a imports circulares)

### `batch_certify_skills.py`
Certifica todas as ~33 skills dos diretórios `graphs/` e `evolution/skills/`:
```bash
cd /workspace && PYTHONPATH=/workspace:$PYTHONPATH \
  python iaglobal/genesis/scripts/batch_certify_skills.py
```

**Resultado típico:**
- ✅ 20 skills certificadas
- ⚠️ 13 skipadas

## Uso Programático

### Certificar um Agente no Nascimento
```python
from iaglobal.genesis.genesis_gatekeeper import certify_birth

class CoderAgent:
    def __init__(self):
        self.certification = certify_birth(
            CoderAgent, 
            version="2.1.0",
            metadata={"author": "iaglobal"}
        )
        print(f"DNA: {self.certification['dna']}")
```

### Validar DNA Antes de Execução Crítica
```python
from iaglobal.genesis.genesis_gatekeeper import validate_dna

if not validate_dna(CoderAgent):
    raise Exception("⚠️ DNA violado! Agente comprometido.")
```

### Consultar Histórico de Linhagem
```python
from iaglobal.genesis.genesis_gatekeeper import gatekeeper

history = gatekeeper.get_lineage_history("CoderAgent", "agent")
for cert in history:
    print(f"Versão {cert['version']}: {cert['dna'][:16]}...")
```

## Analogias Biológicas

| Conceito Biológico | Implementação no Código |
|-------------------|------------------------|
| **DNA Celular** | Hash SHA3-512 único por componente |
| **Checkpoint G1/S** | Gatekeeper valida antes de "divisão" (evolução) |
| **Árvore Genealógica** | Integrity Tree CBOR com histórico |
| **Mutações** | Mudanças no código geram novo DNA |
| **Seleção Natural** | Componentes com DNA inválido são revogados |
| **Memória Imunológica** | Histórico permite detectar "patógenos" conhecidos |

## Benefícios

1. **Imortalidade Digital**: DNA preservado mesmo após anos de evolução
2. **Detecção de Corrupção**: Qualquer alteração não autorizada é detectada
3. **Auditoria Completa**: Histórico de todas as versões de cada componente
4. **Soberania**: Sistema verifica própria integridade ao nascer
5. **Rastreabilidade**: Cada componente tem linhagem documentada

## Próximos Passos

### Para integrar mais componentes:

1. **Módulos Core** (`core/*.py`):
   ```bash
   # Criar script batch_certify_core.py
   ```

2. **Módulos de Evolução** (`evolution/*.py`):
   ```bash
   # Criar script batch_certify_evolution.py
   ```

3. **Módulos de Imunidade** (`immunity/*.py`):
   ```bash
   # Criar script batch_certify_immunity.py
   ```

4. **Validação Contínua**:
   - Adicionar `validate_dna()` no início de cada método crítico
   - Criar job agendado para auditoria periódica de todos os componentes

## Status Atual da Certificação

| Categoria | Total | Certificados | Pendentes |
|-----------|-------|--------------|-----------|
| Agents    | 30    | 21           | 9         |
| Skills    | 33    | 20           | 13        |
| **Total** | **63** | **41**       | **22**    |

*Pendentes são principalmente devido a imports circulares ou classes não encontradas durante carregamento dinâmico.*

---

**🧬 "Assim como uma célula protege seu DNA, o iaglobal protege sua linhagem."**
