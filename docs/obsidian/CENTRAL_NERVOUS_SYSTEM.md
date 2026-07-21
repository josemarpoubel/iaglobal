# 🧬 CENTRAL NERVOUS SYSTEM — AwarenessCache v2

> **Camada de consciência global da execução** — O sistema nervoso central do iaglobal.
> Memória de trabalho coletiva (working memory) em tempo real, com persistência episódica.

---

## 📐 Arquitetura Geral


```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION AWARENESS LAYER                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌──────────────┐      publish()       ┌─────────────────────┐        │
│    │   Agentes    │ ───────────────────▶ │   AwarenessCache    │        │
│    │  (coder,     │                      │                     │        │
│    │  critic,     │ ◀─────────────────── │  SQLite :memory:    │        │
│    │  planner,    │    snapshot()        │  asyncio.Lock       │        │
│    │  ...)        │                      └──────────┬──────────┘        │
│    └──────────────┘                             │                       │
│                                                 │ snapshot()            │
│                        ┌────────────────────────┼────────────────┐      │
│                        │                        │                │      │
│                        ▼                        ▼                ▼      │
│                  ┌──────────┐             ┌──────────┐     ┌──────────┐ │
│                  │  Coder   │             │  Critic  │     │ Planner  │ │
│                  └──────────┘             └──────────┘     └──────────┘ │
│                                                 │                       │
│                                                 │ background task       │
│                                                 ▼                       │
│                                       ┌─────────────────────┐           │
│                                       │  Persistence        │           │
│                                       │  Converter          │           │
│                                       │                     │           │
│                                       │  sqlite3.backup()   │           │
│                                       └──────────┬──────────┘           │
│                                                  │                      │
│                                                  ▼                      │
│                                       ┌─────────────────────┐           │
│                                       │   awareness.db      │           │
│                                       │                     │           │
│                                       │  SQLite nativo      │           │
│                                       │  + CBOR2 em metadata│           │
│                                       │  + JSON em chains   │           │
│                                       └─────────────────────┘           │
│                                                  │                      │
│                                                  │ replay / restore     │
│                                                  ▼                      │
│                                       ┌─────────────────────┐           │
│                                       │  Evolution Engine   │           │
│                                       │  → Obsidian 04_Synapses         │
│                                       └─────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

```

                    Execution

                       |
                       v

              Awareness Runtime

                       |
        +--------------+--------------+
        |                             |
        v                             v

 activity_events              confidence_history

 fatos operacionais           evolução epistemológica

        |                             |
        +--------------+--------------+

                       |
                       v

               Replay Engine

                       |
                       v

              Evolution Engine

                       |
                       v

             Estratégia melhorada
```

---

## 🗂️ Estrutura de Arquivos

```
iaglobal/cognition/awareness/
├── __init__.py                 # v2.0.0 exports
├── models.py                   # Dataclasses (AgentActivity, CausalChain, DomainSnapshot, EpisodicMemory)
├── awareness_schema.py         # Schema SQLite + helpers CBOR2/JSON
├── awareness_cache.py          # Core: publish, snapshot, causal, attention, episodic
└── awareness_persistence.py    # Backup periódico RAM → disco
```

---

## 💾 Persistência Híbrida (SQLite + CBOR2 + JSON)

| Tabela | Colunas Nativas | Blob CBOR2 | JSON Text |
|--------|-----------------|------------|-----------|
| `activities` | execution_id, node_id, status, summary, updated_at | `metadata` | — |
| `executions` | execution_id, started_at, ended_at, final_status, ivm_score | `lessons_learned` | — |
| `causal_chains` | id, execution_id, blocked_node, root_cause, depth | — | `blocking_chain` |

**Backup:** `sqlite3.backup()` — cópia página-a-página, atômica, non-blocking (via `asyncio.to_thread`).

**Intervalo:** `AWARENESS_BACKUP_INTERVAL=2` (segundos, via env var).

---

## 🧠 Três Capacidades Cognitivas v2

### 1. Consciência Causal — `snapshot(relevance="blocking")`

```python
chains = await cache.snapshot("exec_1", relevance="blocking")
# Retorna: list[CausalChain]
# CausalChain(blocked_node="coder", blocking_chain=("architect",), root_cause="architect", depth=1)

explanation = await cache.get_causal_explanation("exec_1", "coder")
# "coder → architect (causa raiz: architect)"
```

**Uso:** Agentes perguntam *"quem está me bloqueando?"* e recebem a cadeia completa até a causa raiz.

---

### 2. Atenção Seletiva — `snapshot(domain="security")`

```python
security_snap = await cache.snapshot("exec_1", domain=NodeDomain.SECURITY.value)
# Retorna: DomainSnapshot(domain="security", activities=(AgentActivity, ...), timestamp=...)

# Helper direto:
coders = await cache.get_nodes_by_domain("exec_1", NodeDomain.CODING.value)
```

**Domínios disponíveis:**
```python
class NodeDomain(Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    CODING = "coding"
    PLANNING = "planning"
    CRITIC = "critic"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    GENERAL = "general"
```

**Uso:** Agentes focam apenas no domínio relevante — redução de ruído cognitivo.

---

### 3. Memória Episódica — `export_episodic_memory()`

```python
memory = await cache.export_episodic_memory(
    execution_id="exec_1",
    final_status="completed",
    ivm_score=0.87,
    lessons_learned=["Use typed dicts", "Add integration tests early"],
)
# Retorna: EpisodicMemory
#   .nodes: dict[str, AgentActivity]
#   .causal_chains: tuple[CausalChain, ...]
#   .duration: float
#   .to_dict() → serializável para Obsidian/Evolution Engine
```

**Persiste automaticamente** no banco em memória → backup → `awareness.db`.

**Recuperação pós-restart:**
```python
cache2 = AwarenessCache()
persistence2 = AwarenessPersistence(cache2, db_path="awareness.db")
await persistence2.restore(cache2)
memory = await cache2.get_episodic_memory("exec_1")
```

---

## 🔌 API Principal

### AwarenessCache

```python
cache = AwarenessCache(event_bus=acetylcholine_bus)

# Publica estado com causalidade e domínio
await cache.publish(
    execution_id="exec_1",
    node_id="coder",
    status="blocked",
    summary="Aguardando schema",
    domain=NodeDomain.CODING.value,
    depends_on=["architect"],    # ← o que eu preciso
    blocks=["tester"],           # ← quem eu bloqueio
    metadata={"file": "api.py", "lines": 120},
)

# Snapshots
all_nodes = await cache.snapshot("exec_1")                    # dict[node_id → AgentActivity]
domain_snap = await cache.snapshot("exec_1", domain="security")  # DomainSnapshot
causal_chains = await cache.snapshot("exec_1", relevance="blocking")  # list[CausalChain]

# Helpers de status
await cache.get_active_nodes("exec_1")    # ["coder", "planner"]
await cache.get_waiting_nodes("exec_1")   # ["critic"]
await cache.get_blocked_nodes("exec_1")   # ["tester"]

# Explicação causal legível
await cache.get_causal_explanation("exec_1", "tester")
# "tester → coder → architect (causa raiz: architect)"

# Memória episódica (fim da execução)
memory = await cache.export_episodic_memory(
    execution_id="exec_1",
    final_status="completed",
    ivm_score=0.85,
    lessons_learned=["...", "..."],
)

await cache.close()
```

### AwarenessPersistence

```python
persistence = AwarenessPersistence(
    cache=cache,
    db_path=Path("awareness.db"),
    interval=2.0,  # segundos
)

await persistence.start()   # Inicia loop de backup
# ... execução roda ...
await persistence.stop()    # Backup final + fecha

# Restore em nova instância
await persistence.restore(new_cache)
```

---

## 📡 Integração com AcetylcholineBus

Cada `publish()` emite evento `NODE_ACTIVITY`:

```json
{
  "execution_id": "exec_1",
  "node": "coder",
  "status": "blocked",
  "summary": "Aguardando schema",
  "domain": "coding",
  "depends_on": ["architect"],
  "blocks": ["tester"],
  "timestamp": 1752930000.123
}
```

**Consumidores:** Dashboard, observador humano, métricas, agentes interessados — **sem polling**.

---

## 🔄 Separação de Responsabilidades

| Componente | Responsabilidade |
|------------|------------------|
| **ExecutionRegistry** | Fatos operacionais: claim, retry, recovery, lifecycle |
| **AwarenessCache** | Percepção coletiva: contexto, colaboração, consciência causal, atenção seletiva |
| **Persistence Converter** | Memória episódica: replay, auditoria, recuperação |
| **Obsidian** | Conhecimento consolidado: synapses, patterns, lições |

---

## ✅ Testes Validados

| Suite | Testes | Cobertura |
|-------|--------|-----------|
| `test_awareness_cache.py` | 11 | Concorrência (100 agents), snapshot durante escrita, backup concorrente, recovery, isolamento, CBOR2 |
| `test_awareness_cache_v2.py` | 12 | Causal chains multi-nível, domain filter, episodic memory persist/restore, integração full |

**Total:** 23 testes passando.

---

## 🚀 Próximas Evoluções (v3)

| Capacidade | Descrição |
|------------|-----------|
| **Meta-cognição** | Cache monitora própria saúde (latência, taxa de erro, saturação) |
| **Previsão de bloqueio** | ML leve prevê gargalos baseando-se em causal_chains históricos |
| **Atenção distribuída** | Múltiplos "focos" simultâneos por agente (multi-domain snapshot) |
| **Synapse auto-gen** | `export_episodic_memory()` → gera markdown direto no Obsidian 04_Synapses |

---

## 📝 Variáveis de Ambiente

```bash
AWARENESS_BACKUP_INTERVAL=2    # segundos entre backups (default: 2)
# awareness.db criado no CWD ou caminho customizado via AwarenessPersistence(db_path=...)
```

---

## 🔗 Referências Arquiteturais

- **AXIOMA 1** — Homeostase: AwarenessCache mantém estado vivo equilibrado
- **AXIOMA 4** — Autofagia: Background task limpa estados órfãos (TTL futuro)
- **AXIOMA 8** — Sinalização Celular: Eventos `NODE_ACTIVITY` são ligantes para receptores
- **PSC** — AwarenessCache **não** chama BanditPolicy; apenas publica estado local

---

> *"O sistema nervoso não pensa — ele percebe, conecta e memoriza. O pensar emerge da rede."*
> — iaglobal Central Nervous System v2
