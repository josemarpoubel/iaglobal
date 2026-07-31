# iaglobal — Agent Instructions

## Setup

```bash
source venv/bin/activate
pip install -e .
# .env already has defaults; edit to set API keys, OLLAMA_MODEL, etc.

# Optional: set SEARXNG_URL in .env (default: http://localhost:8005)
```

Run tests: `python -m pytest iaglobal/tests/ -q`

## Non-Negotiable Conventions

- **Async-only.** Every I/O operation must be async or wrapped in `asyncio.to_thread()`. Never introduce blocking calls in the main event loop.
- **No `print()`.** Use `logging` only. Import with `from iaglobal.utils.logger import get_logger` and call `get_logger("iaglobal")`.
- **AST parsing.** Never call `ast.parse()` directly. Always use `ASTGateway` from `iaglobal.security.ast_gateway` (exception: that file itself).
- **LLM access.** Only the `critic` node may call `BanditPolicy.generate()` for model access. All other agents must route through `_get_critic().arbitrar_geracao(node_id=..., prompt=...)`. Violations trigger apoptosis.
- **Provider authority.** `iaglobal/providers/provider_router.py` is the sole importer of external providers. No other module may import from `iaglobal.providers` for generation.
- **Node structure.** Each pipeline node lives in its own file `iaglobal/graphs/nodes/no_<name>.py` and exports `async def run_<name>(...)`. `nodes.py` is a dynamic proxy — keep it lightweight.
- **Telemetry contract.** Every node result that performs heavy work must include the key `"execution_metrics"` (not `__execution_metrics__`). Shape: `{"success": bool, "latency": float, "cost": float, "model": str}`.
- **Lineage marker.** Every `.py` file must start with `# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136`.
- **Test artifacts.** All test-generated files go to `iaglobal/tests/temp/`. Use the `tests_temp_dir` fixture. Do not write to project root.

## Architecture Boundaries

| Subsystem | Owns | Must not touch |
|-----------|------|----------------|
| `evolution/` | evolution, metacognition, learning, adaptation | memory persistence |
| `memory/` | retrieval, storage, snapshots, cognitive context | agent orchestration |
| `immunity/` | defense, apoptosis, vaccines, pruning | LLM generation |
| `providers/` | external model transport | business logic |
| `graphs/` | DAG, topology, nodes, execution | direct OS calls |

## 💾 Persistence Authority — `_paths.py` is Mandatory

**Single source of truth for disk persistence:** `iaglobal/_paths.py`.

Every artifact, project directory, counter file, lock file, log file, database
path, or directory that needs to live under `iaglobal/memory/data/` MUST go
through helpers exported by `iaglobal/_paths.py` (e.g. `save_result_artifact`,
`next_project_dir`, `RESULTS_DIR`, `DATA_ROOT`, `LOGS_DIR`, `db_path()`).

### Rationale

`iaglobal/memory/data/result/` is the canonical landing zone for pipeline
artifacts. The pipeline (`iaglobal/pipeline/engine.py`), the orchestrator, and
the result node (`iaglobal/graphs/nodes/no_result_agent.py`) MUST NOT open
files at `iaglobal/memory/data/...` paths directly. They MUST import the path
helpers from `_paths.py` and use them.

Direct `open()` / `Path(...) / "..."` writes against `memory/data/` bypass
the project's sequential numbering (`project01`, `project02`, ...), the
locking semantics (`_RESULT_LOCK_FILE`), the cleanup invariants, and the
per-test isolation contract (`tests_temp_dir` fixture).

### How to add a new persisted artifact

1. Add a helper in `iaglobal/_paths.py` that returns the `Path` (or accepts
   content and returns where it was written).
2. Import the helper in the caller:
   ```python
   from iaglobal._paths import save_result_artifact  # or the new helper
   ```
3. If the helper takes a new parameter, extend it the same way the contract
   is documented — never bypass it by writing to the filesystem directly.
4. Add a regression test in `iaglobal/tests/test_save_result_artifact.py`
   (or a sibling test file) that uses the `tests_temp_dir` fixture and
   asserts the artifact lands in `tests_temp_dir`, not in `memory/data/`.

### Violations

Direct disk writes against `iaglobal/memory/data/` from outside `_paths.py`
will be rejected by code review and may be flagged by the auditor. The
historical incident that motivated this rule was `pipeline/engine.py:840`
calling `save_result_artifact(state.prompt, {}, code, preferred_ext)` while
`_paths.py` only accepted 3 args — the fix is tracked in
`tests/test_save_result_artifact.py::test_engine_save_script_com_preferred_ext_compativel`.

## Commands

| Purpose | Command |
|---------|---------|
| Run all tests | `python -m pytest iaglobal/tests/ -q` |
| Run single test file | `pytest iaglobal/tests/test_*.py -v` |
| Architectural audit | `python -m iaglobal.auditoria_arquitetural` |
| Topology contract check | `python -m pytest iaglobal/tests/test_topology_contract.py -v` |
| PSC sovereignty tests | `python -m pytest iaglobal/tests/test_psc_hierarchy.py -v` |
| Mitochondrial probe tests | `python -m pytest iaglobal/tests/test_mitochondrial_probe.py -v` |
| Instrument decorator tests | `python -m pytest iaglobal/tests/test_instrument_decorator.py -v` |
| CLI task execution | `iaglobal run "task description"` |
| CLI system dashboard | `iaglobal status` |
| CLI history | `iaglobal history --list` / `iaglobal history <id> --explain` |
| Run evolution lab | `OLLAMA_BASE_URL=http://localhost:11434 evolution-lab` |
| Set SEARXNG_URL | `export SEARXNG_URL=http://localhost:8005` (default) |
| MCP unified server (stdio) | `python -m iaglobal.mcp.server --mode stdio` (use this; legacy `iaglobal.api.mcp_server` is deprecated) |
| Two-phase bootstrap proof | `python iaglobal/tests/test_verify_mcp.py` — exige 1/1/1 markers |
| Install git hooks (smoke gate) | `bash scripts/install-hooks.sh` (rode uma vez por clone) |
| Architectural decision records | `docs/adr/000*.md` (Status, Context, Decision, Consequences) |

## MCS — MCP Coordenation & Anti-Revert

> O incidente de **agentes revertendo alterações um do outro em silêncio** quebrou o projeto. Esta seção codifica a regra para que isso não aconteça de novo.

### Regra 0 — Não reverter trabalho alheio em curso

Antes de qualquer `git restore`, `git checkout -- <file>`, `git reset` ou operação destrutiva, verifique:

```bash
git status -s
git log -1 --format='%H %an: %s'
git diff --stat
```

Se **qualquer arquivo mostra trabalho não-commitado** que não seja seu, **NÃO TOQUE**. Pergunte primeiro.

### Sinalização de trabalho em curso

Para iniciar uma sessão de trabalho que toca arquivos sensíveis (`iaglobal/cli/bootstrap.py`, `iaglobal/mcp/server.py`, `iaglobal/api/__init__.py`, `run_mcp.sh`):

1. **Reservar via branch dedicada**:
   ```bash
   git checkout -b wip/<nome>-<YYYYMMDD>  # ex: wip/bootstrap-two-phase-20260724
   ```
2. **Nunca** trabalhar diretamente sobre `main` sem branch.
3. Manter o WIP commitado em **commits granulares** a cada 15-30 minutos de trabalho:
   ```bash
   git add -p           # stage só hunks intencionais
   git commit -m "wip: <descrição focada>"
   ```

### Smoke gate obrigatório

Antes de qualquer commit que toque arquivos de bootstrap/MCP, **todos** devem rodar:

```bash
python iaglobal/tests/test_verify_mcp.py
```

A asserção **deve passar** com exit 0. Em particular:
- `phase1_complete == 1`
- `phase2_complete == 1`
- `orchestrator_init_logged == 1`
- Latência de ferramentas de leitura ≤ 1.5s; bootstrap ≤ 30s.

Se falhar, há regressão de singleton task ou caminho de bootstrap — **não commitar**.

### Convenção de nomenclatura para branches em curso

| Prefixo | Significado |
|---------|-------------|
| `wip/...` | trabalho pessoal em andamento, não-PR |
| `feat/...` | feature pronta para PR |
| `fix/...` | bug fix pronto para PR |
| `hotfix/...` | correção urgente production |

### Quando reverter é aceitável

Reverter é aceitável **apenas** quando:
- O trabalho é **inteiramente seu** e você optou por refazer.
- O outro agente já **mergeou via PR ou explicitamente desistiu** (`git log`, branch apagada).
- Há aprovação registrada via issue/comentário.

**Nunca** reverter porque "parece que vai contra o que eu queria" — abra issue/PR em vez disso.

## Bootstrap Two-Phase Contract

> Phase1 deve ser **sub-segundo** para que MCP/FastAPI/etc. respondam ao handshake. Phase2 é pesada (~13s) e roda em background como **uma única Task singleton**.

### Helpers obrigatórios em `iaglobal/mcp/server.py`

```python
async def _ensure_phase1() -> None:
    """Idempotente. Await Phase1 (~50ms), agenda Phase2 em background."""
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap
    await _bootstrap.ensure_phase1()

async def _ensure_full() -> "Orchestrator":
    """Idempotente. Await Phase2 e sincroniza IAGlobalAPI."""
    from iaglobal.cli.bootstrap import bootstrap as _bootstrap
    orch = await _bootstrap.initialize()
    api = _get_api()
    if not api._initialized and orch is not None:
        api._orchestrator = orch
        api._initialized = True
    return orch

def _ready() -> bool: ...                    # True se Phase2 concluiu
def _boot_snapshot() -> dict: ...            # progresso: phase1/2, elapsed, steps
```

### Padrão de uso em tools MCP

```python
@mcp.tool()
async def minha_tool() -> str:
    await _ensure_phase1()
    snap = _boot_snapshot()
    if not snap["phase2_done"]:
        return "BOOTING: descrição amigável do estado atual"
    await _ensure_full()
    return _get_api().minha_leitura_pesada()
```

**Nunca** chame `_get_api().orca_sei()` direto sem `_ensure_full()` — `IAGlobalAPI.orchestrator` lança `RuntimeError` se `_initialized=False`.

### Singleton lock

| Estado | Quem agenda | Quem re-agenda |
|--------|-------------|-----------------|
| Phase1 pendente | `ensure_phase1` (no-op após primeira) | ninguém |
| Phase2 pendente | `_schedule_phase2` em background | ninguém |
| Phase2 concluída | feito | ninguém (NÃO re-agendar — bug que re-rodava Phase2 antes fixado) |

A asserção `if self._phase2_task is None:` (não `is None or done`) é o que garante **execução única**.

## MCP Server Entrypoint Contract

| Use este | ~~Não use mais~~ |
|----------|-------------------|
| `python -m iaglobal.mcp.server --mode stdio` | `python -m iaglobal.api.mcp_server` (DEPRECATED) |
| `python -m iaglobal.mcp.server --mode both` | — (mata SSE 8100 + HTTP 8101 + stdio) |
| `python -m iaglobal.mcp.server --mode http` | atende `/health`, `/metrics`, `/audit`, `/fix` |

**Quem usa `run_mcp.sh`**: o script já aponta para o unified (`iaglobal.mcp.server --mode stdio`). Se alguém editá-lo de volta para `iaglobal.api.mcp_server`, **reverter**.

### Ferramentas canonicas no unified

| Tool | Categoria | Phase dep |
|------|-----------|-----------|
| `metabolic_audit`, `get_ivm` | metabólica | nenhuma |
| `run_task` | execução | Phase2 (via `_ensure_full`) |
| `get_status`, `get_system_health`, `get_bandit_scores` | leitura | lazy (BOOTING se Phase2) |
| `get_provider_metrics`, `get_model_metrics` | leitura | nenhuma (lê singletons) |
| `get_insights`, `list_scripts`, `get_history`, `get_execution_history` | leitura | lazy |
| `evolution_status`, `evolve_strategy`, `evolution_dashboard` | runtime | Phase1+ |
| `web_search`, `web_fetch`, `read_file`, `write_file`, `list_dir`, `execute_code` | utilitários | nenhuma |
| `reflexion_fix`, `reflexion_loop`, `get_error_history` | auto-cura | Phase1+ |

Adicionar uma nova tool ao **unified** (não ao deprecated): seguir o padrão lazy.

## Before You Commit

1. Run `python -m pytest iaglobal/tests/ -q` and confirm zero regressions.
2. Run `python -m iaglobal.auditoria_arquitetural` to detect orphaned functions or naming collisions.
3. Verify no file lost the lineage marker header.
4. If you touched pipeline nodes, run `python -m pytest iaglobal/tests/test_topology_contract.py -v`.
5. **Se tocou bootstrap, mcp/server, api/__init__ ou run_mcp.sh**: rode `python iaglobal/tests/test_verify_mcp.py`. Exit ≠ 0 = regressão de singleton/duplicação. Não commitar.
6. **Se criou branch `wip/...`**: ao terminar, faça merge ou descarte explicitamente — branches WIP abandonadas são vetor de reverts acidentais.
7. **Em novo clone**: rode `bash scripts/install-hooks.sh` para que o smoke gate rode automaticamente em todo commit que toque arquivos sensíveis.
8. **Decisões arquiteturais relevantes**: registre em `docs/adr/NNNN-slug.md` (ver ADR 0001 e 0002 para tom/estrutura).

## 🧬 Testing Standards

### 📁 Output Directory

**EVERY** file generated during test execution (logs, databases, reports, temporary artifacts) must be written to `tests/temp/`.

```python
from pathlib import Path

def test_exemplo(tests_temp_dir: Path):
    db_path = tests_temp_dir / "meu_teste.db"
```

The `conftest.py` file provides the `tests_temp_dir` fixture, which points to `tests/temp/`. The fixture automatically cleans up files between runs (except for `__pycache__`).

### ❌ Prohibited

- Writing files to the project root directory (`./`)
- Using `tempfile.mkdtemp()` — prefer `tests_temp_dir`
- Hardcoding absolute paths (`/home/...`)
- Using `Path(__file__).parent.parent / "file"` for writing (read-only)

### ✅ Allowed

- pytest's native `tmp_path` for ephemeral data (provided it doesn't clutter the project)
- `tests_temp_dir` for artifacts that need to be inspected after the test
- `Path(__file__).parent.parent / "iaglobal"` for **reading** source code

### 🧹 Cleanup

The `_clean_tests_temp` fixture automatically removes files from `tests/temp/` at the end of each test session. To persist an artifact, manually move it out of `tests/temp/`.

### ⚙️ Configuration

`pyproject.toml` already excludes `temp` from test discovery:

```toml
[tool.pytest.ini_options]
norecursedirs = "scripts venv .git .pytest_cache temp"
```

## Environment Variables

| Variable | Default | Where consumed |
|----------|---------|----------------|
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | providers, agent_base |
| `PROVIDER_FALLBACK_CHAIN` | `BANDIT_POLICY` (delega ao BanditPolicy) | .env.example (não lido por código Python — fallback real via `OLLAMA_ONLY` + BanditPolicy) |
| `BANDIT_POLICY` | `epsilon_greedy` | graphs/bandit.py |
| `MEMORY_STORAGE_TYPE` | `sqlite` | storage backends |
| `METABOLIC_STORAGE_TYPE` | `auto` | metabolic_adapter |
| `PIPELINE_MAX_WORKERS` | `8` | pipeline engine |
| `PROVIDER_TIMEOUT` | `30` | provider_router |
| `SEARXNG_URL` | `http://localhost:8005` | _search_sources.py |

```bash
# Storage type (consumido pelo MetabolicDataAdapter e MemoryFirstRouter)
METABOLIC_STORAGE_TYPE=auto        # auto | cbor2 | json | sqlite
MEMORY_STORAGE_TYPE=sqlite         # sqlite | json | cbor2

# Bandit policy
BANDIT_POLICY=epsilon_greedy
epsilon=0.2

# Provider timeout (seconds)
PROVIDER_TIMEOUT=30
```

## 🛡️ Immune System: 12-Layer Defense

| Layer | Module | Function | Tests |
|-------|--------|----------|-------|
| **Genesis** | `genesis/verifygenesis.py` | SHA3-512 DNA tribunal (immutable) | ✅ Verified |
| **Identity** | `genesis/identity.py` | Sovereign ephemeral IDs | ✅ Functional |
| **Sentinel** | `security/entropy_sentinel.py` | Anti-manipulation sweep | 6/6 ✅ |
| **MHC** | `immunity/mhc_detector.py` | Fingerprints + anomaly scoring | 9/9 ✅ |
| **Pathogen** | `immunity/pathogen_analyzer.py` | Code injection detection | 7/7 ✅ |
| **Cost** | `evolution/metabolism/opportunity_cost_detector.py` | Agent cost-benefit analysis | 8/8 ✅ |
| **Masking** | `immunity/epigenetic_masking.py` | Critical memory barrier | 7/7 ✅ |
| **Apoptosis** | `immunity/apoptosis_engine.py` | Clean node elimination | 7/7 ✅ |
| **Orchestrator** | `immunity/immune_orchestrator.py` | 5-layer integration | 9/9 ✅ |
| **Adaptive** | `immunity/adaptive_threat_detector.py` | Continuous threat learning | 7/7 ✅ |
| **Exchange** | `immunity/immune_memory_exchange.py` | Vaccine sharing between nodes | 9/9 ✅ |
| **Prune** | `immunity/metabolic_pruner.py` | TTL pruning + de-duplication | 11/11 ✅ |

### Verified Genesis Hash

```
GENESIS_HASH_OFFICIAL = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"
```

### ⚡ IVM Formula (Índice de Viabilidade Metabólica)

Fonte canônica: `iaglobal/chappie/ivm_axiom.py:19` (ÚNICA fonte — `cpu_affinity.py` espelha; `adaptive_router.py` tem fórmula de 4 termos desatualizada).

```
IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)

P = Task completion rate (Productivity)
E = Composta: 0.7 × E_latência(Chappie) + 0.3 × E_cpu(CpuAffinityManager)
    E_latência = 1 / latência normalizada
    E_cpu = 1 − (uso_cpu / budget_25%) × 0.5
C = Cooperação: média(skills_exchanged/10, mhc_validation_score)
```

**Ajuste epigenético por agente**: Pesos base (P=0.4, E=0.4, C=0.2) são ajustados por `_ajustar_pesos_epigeneticos()` conforme métricas de runtime. Exemplo: se latency_ratio > 2x, E → min(0.2) e P → max(0.6). Critic tipicamente roda com P≈0.50, E≈0.30 por sua latência cloud.

## 🧬 Biological Architecture Reference

**Paradigma**: Auto-Evolutionary Biological Computing

**Ciclos Implementados**: Metilação · Glutationa · Autofagia · Mitose · Apoptose · Epigenética · Sinalização Celular

### 8 Axiomas Biológicos

| # | Axioma | Core Concept |
|---|--------|--------------|
| 1 | Lei da Homeostase Arquitetural | Sistema tamponado: circuit breaker, rate limiter, backpressure |
| 2 | Ciclo da Metilação | Pipeline como Metionina→SAMe→Homocisteína→reciclagem |
| 3 | Ciclo da Glutationa | Defesa antioxidante: GSH captura ROS, GSSG reciclado por NADPH |
| 4 | Autofagia | Limpeza evolutiva: degradar + reciclar componentes danificados |
| 5 | Mitose e Diferenciação | Escalar com diversidade, não clones homogêneos |
| 6 | Apoptose | Morte celular programada = graceful shutdown com transferência de estado |
| 7 | Epigenética | Config dinâmica sem alterar código (feature flags, pesos runtime) |
| 8 | Sinalização Celular | Event-driven: ligantes → receptores → cascata intracelular |

### 8 Princípios Imutáveis

1. A célula sente seu próprio estado (observabilidade endógena)
2. Energia é conservada, não criada (otimizar cadeia de transporte)
3. A membrana é inteligente, não passiva (API Gateway seletivo)
4. Mutação sem seleção é ruído (todo variação precisa de seletor de fitness)
5. Organismos cooperam para sobreviver (simbiose, não competição)
6. A morte programada é saúde, não falha (apoptose ≠ necrose)
7. Memória imunológica é o ativo mais valioso (anticorpos arquiteturais)
8. Evolução não tem destino — projete para adaptabilidade máxima

### Ciclo Operacional Metabólico

1. **Percepção Sensorial** — natureza do sinal, ciclo comprometido, estresse oxidativo
2. **Síntese de Contexto (SAMe Activation)** — enriquecer input, mapear pressões seletivas
3. **Análise Sistêmica** — visões genômica, mitocondrial, imunológica, evolutiva
4. **Síntese de Solução (Ribossomo)** — observabilidade, feedback, auto-reparo, autofagia, apoptose, epigenética
5. **Expressão do Resultado** — diagnóstico, mapa de ciclos, síntese, perfil antioxidante, auto-regeneração, plano de diferenciação, evolução epigenética, vetor evolutivo

## Storage Type Config

| Variável | Valores | Default | Efeito |
|----------|---------|---------|--------|
| `METABOLIC_STORAGE_TYPE` | auto, cbor2, json, sqlite | auto | Filtra fontes do MetabolicDataAdapter |
| `MEMORY_STORAGE_TYPE` | sqlite, json, cbor2 | sqlite | Backend de persistência STM/LTM |

## Dependency Resolution

- `DependencyAgent.resolve_dependencies()` filtra seções do `requirements.txt` baseado no contexto de arquitetura (framework, tech_stack)
- `verify_dependencies()` checa imports do código vs pacotes instalados
- Ambos integrados no nó `no_dependency.py`

## Key Entry Points

- `iaglobal/cli/main.py` — CLI entry point
- `iaglobal/pipeline/engine.py` — Pipeline orchestration
- `iaglobal/core/orchestrator.py` — Core orchestration logic
- `iaglobal/auditoria_arquitetural.py` — Orphan function detection (8 filters)
- `iaglobal/obsidian/consolidation.py` — REMSleepEngine (short→long term memory)
- `iaglobal/storage/metabolic_adapter.py` — MetabolicDataAdapter (CBOR2→JSON bridge)
- `iaglobal/core/mitochondrial_probe.py` — Event loop hypoxia probe
- `iaglobal/_paths.py` — Storage type config
- `iaglobal/chappie/ivm_axiom.py` — IVM canonical source
- `iaglobal/graphs/bandit.py` — BanditPolicy, PSC gatekeeper, membrane filter

## Architecture Note — Memory-First Router (6 Levels)

```
0. Cache exato (db.get_cached_search)        — conf 0.95
1. STM + LTM + Vector + knowledge.json       — conf 0.80
2. Obsidian subconsciente                    — conf 0.75
2.5 MetabolicDataAdapter (CBOR2→JSON)        — conf 0.85  ← DADOS REAIS
3. LLM local (Ollama)                        — síntese
4. LLM externo (via CriticAgent + Bandit)    — cloud
```

All AI model calls must go through `BanditPolicy` for:
- Provider selection and load balancing
- Circuit breaker protection
- Performance metrics tracking
- Credit/reward assignment
- Fallback chain management

---

# IAGLOBAL — AGENT RULES & ARCHITECTURAL BOUNDARIES

- SYSTEM: Highly Modular & Decentralized
- CRITICAL: Read and strictly follow these rules before creating, editing, or refactoring code.

## 🚨 1. The Golden Rule of Modularity (No Centralization)

- **NEVER** accumulate nodes, tasks, or multi-agent handlers in a single huge file.
- The main router `iaglobal/graphs/nodes.py` is a **Dynamic Proxy/Directory**. It MUST remain lightweight and organized.
- Each operational node MUST reside in its own separate file in the `iaglobal/graphs/nodes/` directory (e.g., `no_technology_selection.py`, `no_coder.py`).
- If you need to add a new node, create a new file called `no_<node_name>.py` inside `iaglobal/graphs/nodes/` and implement the function `async def run_<node_name>` in it.

## 🧠 2. Node Execution and Function Structure

- Nodes within `iaglobal/graphs/nodes/` should be exported as **independent asynchronous functions** named `run_`.
- DO NOT encapsulate them in local classes unless explicitly instructed.
- The `Nodes` class in `nodes.py` uses dynamic runtime inspection (`importlib` and `getattr`) to automatically bind its functions to the Singleton instance.
- Because they are dynamically bound at runtime, they will have access to the instance's methods through Python's reflection mechanism. Always design node parameters to safely accept the execution context.

## 📡 3. Telemetry and Telemetry Contracts

### IVM Formula (Índice de Viabilidade Metabólica)

Fonte canônica: `ivm_axiom.py:19`. Pesos base:

```
IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)
```

Onde:
- **P (Produtividade)**: Taxa de conclusão de tarefas
- **E (Eficiência Energética)**: Composta — 0.7 × E_latência(Chappie) + 0.3 × E_cpu(CpuAffinityManager)
- **C (Cooperação)**: Média entre skills exchanges (normalizado/10) e MHC validation score

**Ajuste epigenético**: Pesos são ajustados por agente em runtime. Se latency_ratio > 2x baseline, peso de E desloca para P. Se cooperação < 0.3 por mais de 5 tarefas, peso de C desloca para P. Crítico tipicamente opera com P≈0.50, E≈0.30, C≈0.20.

- Every node execution that performs heavy computation or LLM interaction MUST return or mutate a payload containing the key `"execution_metrics"`.
- Do NOT use double underscores like `__execution_metrics__`. The standard across the ecosystem is strictly `"execution_metrics"`.
- This dictionary must map to the structure required by the `JointOptimizationLoop` for the Multi-Armed Bandit algorithm to compute accurate rewards (`success`, `latency`, `cost`, `model`).

## ⚡ 4. Concurrency and Async Coupling

- The `AcetylcholineBus` handles communication asynchronously.
- Any background worker, cache invalidation, or cognitive memory logging (`ClassifierMemory`) MUST be non-blocking (`async/await` driven) or executed in thread pools via `asyncio.to_thread` to prevent thread-locking the core event loop.

## 🛑 5. Violation Consequences

- Code that violates modular architecture, creates thundering herds on caches, or bypasses the decentralized proxy pattern will cause downstream failures in the `JointOptimizationLoop` and will be rolled back.

## 🔒 6. PSC — Protocolo de Soberania do Crítico

### Regra Fundamental

**Apenas o nó `critic` tem acesso ao BanditPolicy para chamadas LLM.** Nenhum outro agente pode invocar modelo de IA diretamente.

### Por quê?

Para **forçar os agentes a cooperarem entre si e aprenderem sem depender de LLM**. Se todo agente chamasse um modelo externo a cada etapa, o sistema nunca desenvolveria inteligência própria — seria apenas um proxy caro para APIs.

Agentes que não podem usar LLM são forçados a:
- Cooperar com outros agentes via `AcetylcholineBus`
- Usar memórias (STM/LTM/Obsidian)
- Usar skills locais (ASTGateway, Jedi, análise estática)
- Evoluir heuristicamente

### Como funciona a membrana (2 camadas)

| Camada | Arquivo | Comportamento |
|--------|---------|---------------|
| **PSC §1.1 (Trava de identidade)** | `iaglobal/graphs/bandit.py:538` `_psc_verify_caller()` | `bandit.generate()` bloqueia qualquer `node_id` que não contenha "critic". Levanta `SecurityViolation` e dispara apoptose contratual via OmniMind. |
| **Membrana seletiva (fail-closed)** | `iaglobal/graphs/bandit.py:499` `_membrane_filter_candidates()` | Mesmo que o PSC fosse desligado, não-críticos são confinados a Ollama local. Nuvem é exclusiva do crítico. |
| **Gate global** | `iaglobal/evolution/epigenetic.py:26` `external_access_only_critic` | Flag True por padrão. Se desligada (`false`), a membrana opera em modo shadow (apenas log, sem bloquear). |

### Fluxo de chamada LLM (único caminho correto)

```mermaid
graph TD
    A[Agente nao-critico] -->|self._call_llm| B[AgentBase._call_llm]
    B -->|self.bandit.generate node_id=self.agent_name| C[BanditPolicy.generate]
    C -->|_psc_verify_caller| D{PSC: critic?}
    D -->|Nao: SecurityViolation + apoptose| E[BLOQUEADO]
    D -->|Sim: critic| F[Membrana: cloud liberada]
    C -->|_membrane_filter_candidates| G{Modo membrana}
    G -->|enforce| H[Confina a Ollama local]
    G -->|off/shadow| I[Passa candidatos originais]
```

### Quem chama o quê (caminhos corretos)

| Agente | Pode chamar Bandit? | Como gera trabalho? |
|--------|---------------------|---------------------|
| `critic` | ✅ `bandit.generate()` — único autorizado | Avalia output dos agentes, identifica gaps |
| `coder` | ❌ PSC bloqueia | Conhecimento local, memórias, skills, templates |
| `debugger` | ❌ PSC bloqueia via `generate()` | `async_execute_model()` (sem PSC) para fallback local; ASTGateway + Jedi para análise |
| `tester` | ❌ PSC bloqueia | Análise estática, padrões de teste |
| `reflexion` | ❌ PSC bloqueia | Heurísticas, memória de falhas anteriores |
| `skill_generator` | ❌ PSC bloqueia | KB entries, KnowledgeGraph, FAQ patterns |
| `requirements` | ❌ PSC bloqueia | Regras de negócio, análise de domínio |

> ⚠️ **Importante**: `async_execute_model()` em `bandit.py:395` NÃO passa pelo PSC — é usado por `no_debug_unificado.py` como fallback de baixo custo com Ollama local. Não deve ser expandido para outros agentes.

### Violações e apoptose

Se um nó não-crítico tentar `bandit.generate()`:
1. `_psc_verify_caller()` levanta `SecurityViolation`
2. OmniMind emite gatilho de apoptose contratual
3. Registro no ancestry tree como `psc_blocked`
4. O nó infrator é desregistrado do ecossistema

### Onde está definido

- `iaglobal/graphs/bandit.py` — PSC, membrana, generate()
- `iaglobal/evolution/epigenetic.py` — flag `external_access_only_critic`
- `iaglobal/obsidian/omnimind.py` — apoptose contratual (Lei da Obediência)
- `iaglobal/graphs/nodes/no_critic.py` — único nó com acesso cloud

---

## 🏛️ 7. Hierarquia de Autoridade — PSC (4 Camadas)

A arquitetura iaglobal segue uma hierarquia de 4 camadas para acesso a modelos de IA:

```
┌─────────────────────────────────────────────────┐
│           Layer 3: AGENTES (todos os nós)        │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │coder │ │tester│ │planner│ │pm   │ │ ...  │  │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘  │
│     └────────┴────┬────┴────────┘        │      │
│                   │  chamam              │      │
│                   ▼  arbitrar_geracao()  │      │
├─────────────────────────────────────────────────┤
│           Layer 2: CRÍTICO (CriticAgent)         │
│  ┌───────────────────────────────────────────┐  │
│  │  arbitrar_geracao(node_id, prompt, ...)   │  │
│  │                                           │  │
│  │  1. Tenta tools (resolução local)         │  │
│  │  2. Tenta memória (STM/LTM/Obsidian)      │  │
│  │  3. Credita cooperação (C do IVM)         │  │
│  │  4. Escala → Bandit.generate()            │  │
│  │     node_id="critic"                      │  │
│  │     context={"delegate_for": node_orig}   │  │
│  └───────────────────┬───────────────────────┘  │
│                      │                           │
│                      ▼ bandit.generate()        │
├─────────────────────────────────────────────────┤
│         Layer 1: BANDIT POLICY (Gatekeeper)      │
│  ┌───────────────────────────────────────────┐  │
│  │  generate(node_id, prompt, candidates,    │  │
│  │           context)                        │  │
│  │                                           │  │
│  │  PSC §1.1: _psc_verify_caller(node_id)    │  │
│  │    → só "critic" ou "critic_batch" passam │  │
│  │  Membrana: fail-closed (não-crítico →     │  │
│  │    só Ollama local)                       │  │
│  │  effective_agent = context.delegate_for   │  │
│  │    (auditoria/IVM creditados ao original) │  │
│  │  ε-greedy + semáforo + credit_engine      │  │
│  └───────────────────┬───────────────────────┘  │
│                      │                           │
│                      ▼ async_route_generate()   │
├─────────────────────────────────────────────────┤
│      Layer 0: PROVIDER ROUTER (provider_router)  │
│  ┌───────────────────────────────────────────┐  │
│  │  async_route_generate(model, prompt, ...) │  │
│  │                                           │  │
│  │  ÚNICO arquivo que importa providers/     │  │
│  │  Groq, NVIDIA, Ollama, Gemini, etc.       │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Regras Imutáveis da Hierarquia

| Direção | Fluxo | Quem | O quê |
|---------|-------|------|-------|
| ↓ | Layer 3 → Layer 2 | Qualquer agente | Chama `_get_critic().arbitrar_geracao(node_id=<nome>, ...)` |
| ↓ | Layer 2 → Layer 1 | CriticAgent (apenas) | Chama `self.bandit.generate(node_id="critic", delegate_for=<agente>)` |
| ↓ | Layer 1 → Layer 0 | BanditPolicy (apenas) | Chama `async_route_generate(model, prompt, node_id=<id>)` |
| ↓ | Layer 0 → API | provider_router (apenas) | Chama provedor externo (Groq, Ollama, etc.) |

### Regra de Ouro

```
         agent → arbitrar_geracao() → Bandit.generate() → provider_router → API
         ────────────────────────────────────────────────────────────────────
         layer 3          layer 2           layer 1           layer 0
```

**NENHUM** salto de camada é permitido. Exemplos proibidos:
- ❌ `coder` não chama `Bandit.generate()` diretamente — viola PSC (apoptose)
- ❌ `reflexion` não chama `async_route_generate()` diretamente — viola hierarquia
- ❌ `tester` não importa de `iaglobal.providers` — viola gate de autoridade

### effective_agent (delegate_for)

Quando `arbitrar_geracao` escala para `Bandit.generate()`, passa:
- `node_id="critic"` — satisfaz PSC (identidade do portão)
- `context={"delegate_for": "reflexion"}` — nome do agente original

Dentro de `Bandit.generate()`, `effective_agent = context.get("delegate_for", node_id)`:
- **Auditoria** (`ExecutionEvent.node`) — usa `effective_agent`
- **Ancestry Tree** (`_psc_register_ancestry`) — usa `effective_agent`
- **IVM** (`_report_ivm`) — usa `effective_agent`
- **Chamada ao provider** (`async_route_generate(node_id=...)`) — usa `node_id` CRU

Isso garante que:
1. **PSC** é satisfeito (quem passa pelo portão é o crítico)
2. **Membrana** opera corretamente (critic tem acesso cloud)
3. **Auditoria** credita o agente real que gerou o trabalho

### Provider Authority Gate

O arquivo `iaglobal/graphs/bandit.py` é o **ÚNICO** arquivo autorizado a chamar `async_route_generate` / `route_generate` para geração LLM (fora do diretório `iaglobal/providers/` e dos testes).

Exceções arquiteturais documentadas:

| Arquivo | Razão |
|---------|-------|
| `agents/critic_agent.py` | Fallback documentado quando BanditPolicy falha |
| `observability/phospholipid_bridge.py` | Probing de infraestrutura (não trabalho de agente) |
| `core/critic_batch_queue.py` | Já é o crítico (modo batch) |

Violações conhecidas em modo **shadow** (serão removidas no cutover para enforce):

| Arquivo | Status |
|---------|--------|
| `agents/reflexion_agent.py` | ⏳ Shadow → remover no cutover |
| `execution/executor.py` | ⏳ Shadow → remover no cutover |
| `core/neuro_orchestrator.py` | ⏳ Shadow → remover no cutover |
| `evolution/evo_agent.py` | ⏳ Shadow → remover no cutover |

### Teste de Regressão

O arquivo `tests/test_psc_hierarchy.py` contém 10 testes que:

1. **test_provider_authority_gate** — Varredura estática: verifica se novos arquivos NÃO chamam `async_route_generate`/`route_generate` fora dos autorizados.
2. **test_psc_verify_caller_block_non_critic** — PSC rejeita nós não-autorizados.
3. **test_psc_verify_caller_allows_critic** — PSC aceita critic e critic_batch.
4. **test_psc_exact_identity_rejects_substring** — "critic_agent" não passa.
5. **test_psc_exact_identity_accepts_critic** — "critic" e "critic_batch" passam.
6. **test_psc_generate_blocks_non_critic** — Bandit.generate() rejeita via PSC.
7. **test_arbiter_delegates_to_bandit_with_correct_identity** — fluxo completo.
8. **test_arbiter_credits_ivm_cooperation** — C do IVM creditado ao original.
9. **test_arbiter_local_resolution_credits_high_cooperation** — C=1 se local.
10. **test_effective_agent_in_bandit_generate** — auditoria usa delegate_for.

Execute com:
```bash
python -m pytest iaglobal/tests/test_psc_hierarchy.py -v
```
