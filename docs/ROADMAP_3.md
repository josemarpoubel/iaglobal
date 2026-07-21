# ROADMAP 3 — AwarenessCache: Camada de Consciência Global da Execução

> **v3.1 CONGELADO** — Comportamento validado. Nenhuma alteração na API pública até v4.
> **v3.1.5** — Pré-requisito antes de v3.2: refatoração estrutural zero-delta (movimentação de código sem mudança de comportamento).

---

## API Pública Congelada (v3.1)

Membros sujeitos a contrato de estabilidade durante toda a série v3.x.
Mudanças somente em v4.

| Método | Assinatura | Status |
|--------|-----------|--------|
| `publish()` | `(execution_id, node_id, status, ...) -> float` | ✅ Congelada |
| `snapshot()` | `(execution_id, domain?, relevance?) -> dict \| DomainSnapshot \| list[CausalChain]` | ✅ Congelada |
| `query()` | `(execution_id, **filters) -> list[AgentActivity]` | ✅ Congelada |
| `history()` | `(execution_id, node_id?, fields?, limit?) -> list[dict]` | ✅ Congelada |
| `replay()` | `(execution_id) -> list[dict]` | ✅ Congelada |
| `as_of()` | `(execution_id, timestamp) -> dict[str, AgentActivity]` | ✅ Congelada |
| `diff()` | `(execution_id, t1, t2) -> dict[str, Any]` | ✅ Congelada |
| `export_episodic_memory()` | `(execution_id, final_status, ivm_score?, lessons?) -> EpisodicMemory` | ✅ Congelada |
| `get_confidence_timeline()` | `(execution_id, node_id?) -> list[ConfidenceSnapshot]` | ✅ Congelada |
| `get_artifact_confidence()` | `(execution_id, artifact_id) -> ArtifactConfidence \| None` | ✅ Congelada |

---

## Invariantes Arquiteturais (permanentes)

Propriedades que NUNCA podem ser violadas, independentemente de refatorações internas.

| # | Invariante | Como é validado |
|---|------------|-----------------|
| 1 | `replay(history) == snapshot` | Audit 1 (100 sequências aleatórias) |
| 2 | Dual-write sempre atômico (activities + activity_events + confidence_history) | Audit 2 + `with self._db:` + commit único |
| 3 | `confidence ∈ [0,1]` em duas camadas | `clamp()` + `CHECK(confidence >= 0 AND confidence <= 1)` |
| 4 | ConfidenceTrace: `base + Σpositivos − Σnegativos == final` (após clamp) | `compute_confidence()` determinística em `models.py` |
| 5 | `effective_confidence` nunca altera histórico (função pura) | `effective_confidence()` em `models.py` |
| 6 | `AwarenessCache` é a única fachada pública | Engines não exportados em `__init__.py` |
| 7 | Engines nunca conversam diretamente entre si | Dependências mediadas por `AwarenessContext` (sem imports cruzados) |
| 8 | `old_status` reflete estado anterior real | Fix em `publish()` — lê DB antes de `INSERT OR REPLACE` |
| **9** | **Backup v3.1 é restaurado identicamente em v3.2+** | `restore(v3.1_backup).snapshot() == snapshot pré-upgrade` |
| **10** | **Ordem EventBus: persistência → commit → emit (nunca revertida)** | Contrato em `publish()`; auditado por invariante 2 |

---

## Visão Geral

Implementar uma **camada de consciência coletiva** (Working Memory) para o iaglobal, separando claramente:

| Camada | Responsabilidade | Armazenamento |
|--------|------------------|---------------|
| **ExecutionRegistry** | Fatos operacionais (claim, retry, recovery, lifecycle) | SQLite persistente |
| **AwarenessCache** | Percepção coletiva, contexto, colaboração | SQLite `:memory:` + asyncio.Lock |
| **Persistence Converter** | Memória episódica persistente | `awareness.db` (SQLite + CBOR2) |
| **Obsidian** | Conhecimento consolidado, synapses | Markdown + JSON |

---

## Estrutura de Arquivos (v3.1 — monolítico validado)

```
iaglobal/
└── cognition/
    └── awareness/
        ├── __init__.py              # Exportações públicas v3.1.0
        ├── models.py                # ConfidenceTrace, ArtifactConfidence, compute_confidence()
        ├── time_provider.py         # ClockProvider (SystemClock, FakeClock)
        ├── awareness_schema.py      # Schema SQLite + CHECK constraints + índices
        ├── awareness_cache.py       # AwarenessCache v3.1 (dual-write atômico)
        └── awareness_persistence.py # Background backup/restore
```

---

## ✅ v3.1 — Estado Validado (47/47 testes | 4 auditorias aprovadas)

### Implementação Entregue

| Componente | Arquivo | Status |
|------------|---------|--------|
| `AgentActivity`, `ConfidenceTrace`, `ExecutionContext` | `models.py` | ✅ |
| Schema v3.1 (activities, activity_events, confidence_history, schema_version) | `awareness_schema.py` | ✅ |
| CHECK constraints `confidence ∈ [0,1]` (Python + SQLite dupla camada) | `awareness_schema.py` | ✅ |
| `publish()` dual-write atômico com `old_status` tracking | `awareness_cache.py` | ✅ |
| `snapshot()`, `history()`, `as_of()`, `diff()`, `replay()`, `query()` | `awareness_cache.py` | ✅ |
| `get_confidence_timeline()`, `get_artifact_confidence()` | `awareness_cache.py` | ✅ |
| `AwarenessPersistence` (backup periódico + restore) | `awareness_persistence.py` | ✅ |
| `__init__.py` v3.1.0 com exports completos | `__init__.py` | ✅ |

### Testes v3.1 (47/47 passing)

| Suite | Testes | Cobertura |
|-------|--------|-----------|
| `test_awareness_cache.py` | 11 | Core: publish, snapshot, domain, causal, backup/restore |
| `test_awareness_cache_v2.py` | 12 | v2: causal chains, domain filter, episodic memory, full workflow |
| `test_awareness_stress.py` | 15 | Stress: 10k concurrent, backup under load, memory stability, p99 latency |
| `test_awareness_audits.py` | 9 | **4 auditorias hardening** (ver abaixo) |

### 🛡️ Auditorias v3.1 (todas aprovadas)

| # | Auditoria | Propriedade | Status |
|---|-----------|-------------|--------|
| **1** | Replay Determinístico | `snapshot_original == replay(history)` para 100+ sequências aleatórias | ✅ |
| **2** | Dual-Write Consistency | `COUNT(events) ≥ 1`, transições registradas, sem eventos perdidos | ✅ |
| **3** | Performance Baseline | p50/p95/p99/max/stddev; p99 < 50ms publish, p99 < 20ms snapshot | ✅ |
| **4** | Crash Recovery | `restore() → snapshot == último_state_persistido` | ✅ |

---

## 🔄 v3.1.5 — Pré-Modularização (zero-delta extraction)

> **Objetivo:** Separar código em módulos sem alterar nenhum comportamento.
> **Critério:** 47 testes continuam verdes após cada passo.

### Passo A: Criar módulos auxiliares (sem lógica nova)

```
Novos arquivos:
├── time_provider.py      # ClockProvider, SystemClock, FakeClock
├── interfaces.py         # Protocols (ConfidenceProvider, HistoryProvider, etc.)
├── storage_backend.py    # PersistenceBackend ABC + SQLiteBackend
└── awareness_context.py  # AwarenessContext (db, lock, clock, backend)
```

### Passo B: Mover funções puras para módulos separados

```
Exemplo:
awareness_cache.py:
    def _build_causal_chains(...) → moves to → causal_engine.py::_build_causal_chains()

AwarenessCache:
    def _build_causal_chains(self, ...):
        return causal_engine.build(self._context, ...)
```

**Regra:** `AwarenessCache` mantém todas as assinaturas públicas idênticas. Apenas a implementação interna muda para chamar funções extraídas.

### Passo C: Validar após cada movimentação

```bash
python -m pytest iaglobal/tests/test_awareness_*.py -q
# Esperado: 47 passed
```

---

## 🔄 v3.2 — Modularização (gate final)

> **Pré-requisito:** v3.1.5 concluído (código organizado em módulos, 47 testes verdes).

### Objetivo

Converter funções extraídas em engines com classe, mantendo interface idêntica.

### Arquitetura Final (v3.2)

```
AwarenessCache (Facade — 150 linhas)
    │
    ▼ AwarenessContext
    │  (db, lock, clock: ClockProvider, backend: PersistenceBackend, metrics)
    │
    ├── ConfidenceEngine   # compute_confidence(), ConfidenceTrace, decay temporal
    ├── HistoryEngine      # replay(), as_of(), diff(), get_confidence_timeline()
    ├── QueryEngine        # snapshot(), query(), domain filter, get_active_nodes()
    ├── CausalEngine       # get_blocking_chains(), get_causal_explanation()
    ├── EpisodicEngine     # export_episodic_memory(), get_episodic_memory()
    └── StorageRepository  # TODAS as operações SQL — engines não importam sqlite3
```

### Regra de Acoplamento

> Nenhum engine importa `AwarenessCache` ou outro engine.
> Todos recebem `AwarenessContext` e acessam dados apenas via `StorageRepository`.

```
ConfidenceEngine(context) ─┐
                            ├── StorageRepository (operacões semânticas)
HistoryEngine(context)  ────┤
                            └── ClockProvider (determinismo)
QueryEngine(context)     ────┘
```

### StorageRepository (operacões semânticas)

```python
class StorageRepository:
    async def save_activity(execution_id, node_id, status, summary, metadata, timestamp): ...
    async def append_event(execution_id, node_id, event_type, old_status, new_status,
                            confidence, trace, metadata, timestamp): ...
    async def append_confidence(execution_id, node_id, artifact_id, domain,
                                 confidence, reason, contributors, timestamp): ...
    async def load_history(execution_id, node_id=None, limit=100) -> list[dict]: ...
    async def load_events_up_to(execution_id, timestamp) -> list[dict]: ...
    async def save_episodic_memory(memory: EpisodicMemory): ...
    async def load_episodic_memory(execution_id) -> EpisodicMemory | None: ...
    async def snapshot_db(self) -> bytes: ...  # backup binário
    async def restore_from_backup(self, data: bytes): ...
```

**Regra:** Nenhum `SELECT *`, `INSERT` solto nos engines. Toda query semântica tem nome.

### Interfaces Contratuais

```python
# awareness/interfaces.py
class ConfidenceProvider(Protocol):
    async def compute(self, ctx: ExecutionContext) -> tuple[float, ConfidenceTrace]: ...
    async def get_timeline(self, execution_id: str, node_id: str | None = None) -> list[ConfidenceSnapshot]: ...

class HistoryProvider(Protocol):
    async def replay(self, execution_id: str) -> list[dict]: ...
    async def as_of(self, execution_id: str, timestamp: float) -> dict[str, AgentActivity]: ...
    async def diff(self, execution_id: str, t1: float, t2: float) -> dict[str, Any]: ...

class QueryProvider(Protocol):
    async def snapshot(self, execution_id: str, domain=None, relevance=None) -> dict[str, AgentActivity]: ...
    async def query(self, execution_id: str, **filters) -> list[AgentActivity]: ...

class CausalProvider(Protocol):
    async def get_blocking_chains(self, execution_id: str) -> list[CausalChain]: ...
    async def explain(self, execution_id: str, blocked_node: str) -> str | None: ...

class EpisodicProvider(Protocol):
    async def export(self, execution_id: str, ...) -> EpisodicMemory: ...
    async def restore(self, memory: EpisodicMemory) -> None: ...
```

### ClockProvider (replay determinístico)

```python
# awareness/time_provider.py
class ClockProvider(Protocol):
    def now(self) -> float: ...

class SystemClock:
    def now(self) -> float:
        return time.time()

class FakeClock:
    def __init__(self, initial: float = 0.0):
        self._t = initial
        def now(self) -> float:
            return self._t
        def advance(self, delta: float):
            self._t += delta
```

**Regra:** Nenhum engine chama `time.time()` diretamente. Sempre via `context.clock.now()`.

### Métricas de Dívida Técnica (critérios de aceite rígidos)

| Métrica | Meta |
|---------|------|
| `awareness_cache.py` | ≤150 linhas |
| Cada engine | ≤300 linhas |
| Cada função/método | ≤50 linhas |
| Complexidade ciclomática | ≤10 por função |
| Dependências cíclicas | 0 |
| Imports cruzados entre engines | 0 |
| Cobertura por engine | ≥95% |

### Contrato EventBus (ordem garantida)

Sequência obrigatória em `publish()`:

```
1. compute_confidence(ctx)          ← sinal epistemológico calculado
2. old_status = repo.get_status()   ← lê estado anterior
3. repo.save_activity(...)          ← atualiza state
4. repo.append_event(...)           ← registra evento
5. repo.append_confidence(...)      ← registra evolução epistemológica
6. repo.commit()                    ← atomicidade garantida
7. await event_bus.emit("NODE_ACTIVITY", ...)  ← notificação externa
8. return confidence
```

**NUNCA:** `emit()` antes de `commit()` — consumidores podem observar estados que nunca foram persistidos.

### Critérios de Aceite v3.2

- [ ] `time_provider.py` — `ClockProvider`, `SystemClock`, `FakeClock`
- [ ] `storage_backend.py` — `PersistenceBackend` ABC + `SQLiteBackend` com operações semânticas
- [ ] `interfaces.py` — 5 Protocols (Confidence, History, Query, Causal, Episodic)
- [ ] `awareness_context.py` — contexto compartilhado (db, lock, clock, backend, metrics)
- [ ] 5 engines extraídos: `confidence_engine.py`, `history_engine.py`, `query_engine.py`, `causal_engine.py`, `episodic_engine.py`
- [ ] `storage_repository.py` — único dono das queries SQL
- [ ] `awareness_cache.py` ≤150 linhas (facade pura)
- [ ] `clock_provider` elimina `time.time()` direto dos engines
- [ ] Testes existentes (47/47) continuam passando
- [ ] Cada engine testável isoladamente (mock de `AwarenessContext`)
- [ ] Nenhum import cruzado entre engines
- [ ] Complexidade ciclomática ≤10 por função
- [ ] Cobertura de teste por engine ≥95%
- [ ] `__init__.py` atualizado com exports opcionais (engines mockáveis)

---

## ✅ v3.1.5 — Pré-Modularização (gate obrigatório)

### Objetivo

Separar código em módulos **sem alterar nenhum comportamento**.
Compromisso: 47 testes verdes após cada passo.

### Passos

1. **Criar módulos auxiliares** (sem lógica nova):
   - `time_provider.py`: `ClockProvider`, `SystemClock`, `FakeClock`
   - `storage_backend.py`: `PersistenceBackend` ABC + `SQLiteBackend`
   - `awareness_context.py`: `AwarenessContext` (db, lock, clock, backend)
   - `interfaces.py`: Protocols

2. **Mover funções puras** para módulos:
   - `compute_confidence`, `effective_confidence` → `confidence_engine.py`
   - `_build_causal_chains`, `_trace_dependency_chain` → `causal_engine.py`
   - `_init_schema`, serialização helpers → `storage_repository.py`
   - `replay`, `as_of`, `diff` → `history_engine.py`

3. **Re-exportar via AwarenessCache:**
   ```python
   from .causal_engine import build_causal_chains
   def _build_causal_chains(self, *a, **kw):
       return build_causal_chains(self._context, *a, **kw)
   ```

4. **Substituir chamadas internas gradualmente:**
   - Cada função movida → atualizar chamadores → rodar testes → commit

5. **Critério de saída:** `python -m pytest iaglobal/tests/test_awareness_*.py -q` = 47 passed.

---

## Status Atual

| Versão | Status | Próximo Gate |
|--------|--------|--------------|
| v1 — Core (publish/snapshot/backup) | ✅ Done + Tested | — |
| v2 — Causal + Domain + Episodic | ✅ Done + Tested | v3.1 |
| v3.1 — Temporal + Confidence + Dual-Write + Auditorias | ✅ **Done + 4 Auditorias Aprovadas** | v3.1.5 |
| v3.1.5 — Pré-modularização (zero-delta) | 📋 **Próximo** | v3.2 |
| v3.2 — Engines Especializados + Repository + Clock | 📋 Registrado | v3.3 |

---

## Critérios de Promoção (checklist completo)

- [x] v1 → v2: Core publish/snapshot/backup (11 testes)
- [x] v2: Consciência causal, atenção seletiva, memória episódica (12 testes)
- [x] v2 → v3.1: Temporal versioning, confidence_history (15 stress tests)
- [x] Auditoria 1 — Replay Determinístico (100 sequências aleatórias)
- [x] Auditoria 2 — Dual-Write Consistency + Event Count + old_status tracking
- [x] Auditoria 3 — Performance Baseline (p50/p95/p99/max/stddev)
- [x] Auditoria 4 — Crash Recovery (backup/restore idempotente)
- [x] 47 testes passando (regression suite)
- [ ] v3.1.5: Mover funções puras para módulos (zero behavioral change)
- [ ] v3.1.5: time_provider + storage_backend + interfaces + context
- [ ] v3.2: 5 engines + StorageRepository + ClockProvider
- [ ] v3.2: Facade ≤150 linhas, cada engine ≤300 linhas, CC ≤10
- [ ] v3.2: Nenhum import cruzado, cobertura ≥95% por engine
- [ ] v3.2: Backward compatibility (backup v3.1 restaurado em v3.2)
