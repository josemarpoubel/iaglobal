# 🧬 Data Path Sovereignty — Contrato `_paths.py`

> **Status**: ativo · **Escopo**: todos os módulos de `iaglobal/` que escrevem em `memory/`.
> **Owner arquitetural**: `iaglobal/_paths.py` (única source of truth).
> **Auditor permanente**: `iaglobal/tests/test_audit_path_sovereignty.py`.

---

## 📜 Princípio

**`_paths.py` é o ÚNICO módulo autorizado a resolver o caminho raiz da memória do organismo.** Todos os outros módulos devem importar constantes de `iaglobal._paths`. A resolução do path raiz é sensível a dois fatores:

1. **`ORGANISM_DATA_ROOT`** — env var que sobrescreve o root padrão (default: `PACKAGE_DIR/memory/data`).
2. **`MEMORY_STORAGE_TYPE`** — seletor de backend (sqlite | json | cbor2).

Esses fatores só funcionam se forem aplicados **uma única vez, no import time de `_paths.py`**, e propagados como constantes para todos os consumidores.

## 🧬 Anatomia do path soberano

```
DATA_ROOT              = $ORGANISM_DATA_ROOT || PACKAGE_DIR/memory/data
├── JSON_DIR           = DATA_ROOT/json
├── DB_DIR             = DATA_ROOT/db
│   ├── CORE_DB        = DB_DIR/core.db
│   ├── CACHE_DB       = DB_DIR/cache.db
│   ├── MEMORIES_DB    = DB_DIR/memories.db
│   └── PROVIDER_EVENTS_DB = DB_DIR/provider_events.db
├── CBOR2_DIR          = DATA_ROOT/cbor2
├── SYNTHESIS_JSON_DIR = JSON_DIR/synthesis
├── RESULTS_DIR        = DATA_ROOT/result   ← saída do pipeline
├── LOG_DIR            = DATA_ROOT/logs
├── TEMP_DIR           = DATA_ROOT/temp
├── MEMORY_SWAP_DIR    = DATA_ROOT/cache/memory_swap
├── BACKUP_DIR         = DATA_ROOT/memory_backups
└── SNAPSHOTS_DIR      = DATA_ROOT/snapshots
```

Sub-constantes definidas em `_paths.py` (acumuladas ao longo do tempo):

| Constante | Destino | Adicionada em |
|-----------|---------|---------------|
| `JOL_DATA_DIR` | `DATA_ROOT/jol` | (este ADR) |
| `OBSIDIAN_VAULT_DIR` | `PACKAGE_DIR/obsidian` | (este ADR) |
| `KNOWLEDGE_FILE` | `JSON_DIR/knowledge.json` | já existia |
| `EMBEDDING_CACHE_PATH` | `JSON_DIR/fewshot_embeddings.cbor` | (a corrigir) |
| `PROFILES_PATH` (entropy_sentinel) | `JSON_DIR/entropy_profiles.cbor` | (a corrigir) |

## ✅ Padrão canônico

```python
# iaglobal/<modulo>.py
from iaglobal._paths import DATA_ROOT, JSON_DIR, CORE_DB  # ou o que for

class MyWriter:
    def save(self):
        target = JSON_DIR / "my_artifact.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
```

**Vantagens:**

- Override via `ORGANISM_DATA_ROOT` propaga sem alteração de código.
- Isola testes: `monkeypatch.setenv("ORGANISM_DATA_ROOT", tmp_path)` antes de importar `iaglobal.<modulo>` (ou com fixtures que resetam `iaglobal._paths`).
- Documenta a estrutura de armazenamento no próprio `_paths.py`.

## ❌ Padrões proibidos

| Padrão | Problema | Exemplo |
|--------|----------|---------|
| `Path(__file__).parent.parent / "memory" / "data"` | Ignora `ORGANISM_DATA_ROOT` | `metabolism/jol_metrics.py:33` |
| `PACKAGE_DIR / "memory" / "..."` (sem `/data/`) | Foge do contrato, escreve em `memory/` raiz | `chappie/ivm_axiom.py:951`, `chappie/bandit_evolution.py:26` |
| `Path(PROJECT_ROOT) / "iaglobal" / "..."` | Hard-coded para `~/<repo>-<branch>/...`, vaza em clones zip | `mcp/discovery.py:17,142`, `observability/registry.py:22`, `security/mcp_sandbox.py:22`, `evolution/ga/ga_runner.py:28-29`, `evolution/evolution_feedback_hook.py:70`, `colony_comms/integrator.py:16` |
| `os.path.join(..., "memory", "data")` | Mesma raiz hard-coded via API antiga | `debug/node_timing.py:146` |
| `Path("iaglobal/memory/data/...")` (relativo ao CWD) | Falha fora do `cwd` do repo | `cli/life_signals.py:72`, `graphs/nodes/no_validator_retry.py:424` |
| `Path("/home/usuario/projeto-.../...")` (absoluto) | **Quebra CI**, vaza username do dev | `tests/integration/test_stress_fase31.py:31`, `tests/test_task_router_stress.py:28` |

## 🛡️ Auditor permanente

`iaglobal/tests/test_audit_path_sovereignty.py` é um scanner regex-based que detecta todos os padrões acima. Pode rodar como teste (gerando `BOOTING`-style reporting) ou ser executado por `auditoria_arquitetural.py` como filtro adicional:

```bash
# Execução direta
python iaglobal/tests/test_audit_path_sovereignty.py iaglobal

# Como pytest (conv pytest naming)
python -m pytest iaglobal/tests/test_audit_path_sovereignty.py -v
```

**Comportamentos para evitar autoimunidade:**

- Auto-exclui por identidade de **path resolvido** (`Path(__file__).resolve()`), não por nome — sobrevive a rename.
- Ignora docstrings, comentários e strings decorativas na varredura (análise via `ast` para detectar `ast.Expr` strings).

## 🧪 Testes que tocam filesystem real — fixture de isolamento

Tests que rodam subsistemas com persistência (stress tests, audits end-to-end) **DEVEM** isolar via `tmp_path` + `monkeypatch.setenv("ORGANISM_DATA_ROOT", tmp_path)`. Padrão:

```python
import pytest

@pytest.fixture(autouse=True)
def isolate_data_root(monkeypatch, tmp_path):
    """Stress tests nunca tocam a memória real do organismo."""
    monkeypatch.setenv("ORGANISM_DATA_ROOT", str(tmp_path))
    yield
```

Para casos onde o módulo a ser testado importa `_paths` no **import time** (não no uso), pytest oferece `importorskip`-style ou `monkeypatch.setattr("iaglobal._paths.DATA_ROOT", ...)`. Decidir por feature-test empírica.

## 🚨 Anomalias arquiteturais correlatas (não são path sovereignty)

### 1. `ivm_axiom.py:951` default morto

```python
if db_path is None:
    db_path = PACKAGE_DIR / "memory" / "ivm.db"   # fora de DATA_ROOT!
```

Em produção, `cli/bootstrap.py:260` chama `init_ivm_axiom_com_persistencia(db_path=MEMORY_SWAP_DIR / "ivm.db")` — path canônico dentro de `DATA_ROOT`. Mas `get_ivm_axiom()` em L925 instancia `IVMAxiom()` sem args → cai no default errado se bootstrap falhou antes dessa linha. Mina terrestre: silencioso, escreve no path órfão nos momentos em que log confiável mais importa.

**Fix proposto**: trocar para `MEMORY_SWAP_DIR / "ivm.db"` (igual bootstrap) — reaproveita path canônico, zero migração de dado.

### 2. Anomalia 2 — código não-convergido persiste em CORE_DB

`no_validator_retry.py:433-445` retorna `NodeResult(success=False, output=corrected_code)` quando o reflexion loop esgota `MAX_RETRIES`. O pipeline em `_async_persistence_stage` (L885-895) chama `memory_instance.store(state.prompt, state.generated_code, metadata)` **sem checar `state.success` ou `state.retries`**. Resultado: código que falhou validação entra no `success_registry` (em CORE_DB) com score de fallback `50`. Contamina a base que `MEMORY` usa para recuperação futura.

**Gate proposto** (em `_async_persistence_stage`):

```python
metadata = {
    "ts": time.time(),
    "score": state.score,
    "script_path": str(state.script_path) if state.script_path else "",
    "path": str(state.script_path) if state.script_path else "",
    "converged": state.score >= SCORE_CONVERGED_THRESHOLD,  # ex.: 80
    "validation_status": "passed" if state.syntax_valid else "failed",
}
```

**Decisão arquitetural pendente** (entre Opção A e B):

- **Opção A**: não persistir se `state.score < threshold`. Pró: simplicidade. Contra: perde rastro de falha (imunológico).
- **Opção B**: persistir com `metadata["converged"]=False` e fazer `retrieve()` ponderar por isso. Pró: mantém trilha. Contra: requer patching em TODOS os pontos de retrieval que filtram (5+ arquivos já conhecidos com bug similar).

**Recomendação**: Opção A como default até confirmar que existe (ou construir) mecanismo de ponderação por confiança no retrieval.

## 📜 ADRs relacionadas

- **ADR 0001** — Genesis tribunal (DNA imutável).
- **ADR 0002** — Lineage marker obrigatório.
- **ADR 0004** — Eventos de capacidade.
- **ADR 0005** — Change lifecycle (Investigação → Instrumentação → Correção → Refatoração).

(ADR para este domínio ainda não foi criado — sugestão: `docs/adr/0006-data-path-sovereignty.md`.)

## 🔄 Histórico de mudanças

| Data | Mudança |
|------|---------|
| 2026-07-30 | Criação deste doc + auditor (`test_audit_path_sovereignty.py`) + diffs para `JOL_DATA_DIR` e `OBSIDIAN_VAULT_DIR` em `_paths.py`. |
