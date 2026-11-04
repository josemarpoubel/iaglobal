# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ADR 0001 — Bootstrap em duas fases (Phase1 + Phase2 background)

- **Status**: Aceita
- **Data**: 2026-07-24
- **Contexto**: MCP handshake exige resposta sub-segundo; bootstrap completo custa ~13s.

## Contexto

Antes desta decisão, o bootstrap (`iaglobal/cli/bootstrap.py:initialize()`)
era executado **em série, no caminho de qualquer chamada** que precisasse
do `IAGlobalAPI`. O trabalho pesado concentrava-se em:

- `Orchestrator.initialize()` — incluindo preload do `sentence-transformers/all-MiniLM-L6-v2` (~9.93s sozinho)
- `await provider_registry.warmup_all(timeout=120)` — aquece o Ollama local
- Chappie (IVM / Vacuum / ErrorEnricher / LineageGuardian) — instanciação + tasks de fundo
- Mitochondrial probe — `start_background_task()`

Como qualquer `tool/call` em `iaglobal/api/mcp_server.py` invocava
`await api.initialize_async()`, a primeira chamada após start do servidor
padrão levava ≥10s, excedendo o timeout MCP de vários clients
(OpenCode: handshake de 5–30s).

Pior: dois pontos diferentes do código (background task do MCP + cada tool)
iniciavam **bootstrap concorrentes** — `phase1_complete` aparecia DUAS vezes
em `app.log`, threads acumulavam (33 → leak de CLOSE_WAIT para
`2600:9000:28ee:443` AWS CloudFront).

## Decisão

Adotar o padrão **Two-Phase Singleton Task**:

- **Phase 1** (~50ms): estrutura de diretórios, tribunal Genesis, DB init,
  `Orchestrator()` (somente construtor, **sem** `.initialize()`).
  Idempotente. Libera o event loop imediatamente.

- **Phase 2** (~13s em background): orchestrator init completo, chappie,
  warmup Ollama, mitochondrial probe.
  Disparada por `asyncio.create_task()` em background. **Apenas uma vez**
  via singleton (`if self._phase2_task is None:`).

- Tools MCP de leitura (`get_status`, `get_system_health`, `get_bandit_scores`,
  `get_insights`, `list_scripts`, `get_history`, `get_execution_history`)
  respondem em modo **"BOOTING"** se Phase2 ainda corre, sem bloquear.

- Tools MCP de execução pesada (`run_task`, `metabolic_audit`) podem
  opcionalmente aguardar Phase2 via `_ensure_full()`.

## Consequências

### Positivas

- Handshake MCP responde em **~50ms** em vez de 13s.
- Tudo que precisa ler status/insights/etc nunca bloqueia o event loop.
- Bootstrap concorrente eliminado (singleton task).
- Threads zumbis não acumulam mais (16 vs 33).
- Telemetria exposta via `bootstrap.snapshot()["metrics"]`:
  `phase1_duration`, `phase2_duration`, `time_to_ready`,
  `phase2_schedule_count`, `ready_at_iso`.

### Custos

- Leitura durante BOOTING pode retornar dados parciais (lazy).
- `IAGlobalAPI.get_status()` exige `_initialized=True`, então
  `iaglobal/api/__init__.py:orchestrator` foi relaxada para aceitar
  `_orchestrator is not None`.
- `iaglobal/cli/bootstrap.py` ganhou ~110 linhas vs a versão original
  (justificada pelo contrato).

### Tradeoffs documentados

- `FEWSHOT_PRELOAD` em `.env` foi setado para `false` — preload sync
  bloqueia o event loop por 10s. Embedder agora carrega on-demand.
- Warmup Ollama permanece na Phase2 (afeta só a 1ª task que chamar LLM).

## Alternativas consideradas

1. **Process isolation (worker pré-boot)**: rejeitada — adiciona IPC +
   complexidade de orquestração.
2. **Aguardar Phase2 em `initialize_async()`**: rejeitada — é exatamente
   o bug original.
3. **Async tasks + queue com timeout**: mais complexo, sem ganho real
   para este caso.

## Reversibilidade

Total — basta retornar `bootstrap.py` ao layout original e ajustar
`iaglobal/mcp/server.py` para usar `await api.initialize_async()`
em vez dos helpers `_ensure_phase1/_ensure_full`. O `test_verify_mcp.py`
detectará regressão de singleton imediatamente.

## Validação automatizada

- `iaglobal/tests/test_verify_mcp.py` é o smoke gate. Marcadores:
  - `phase1_complete == 1`
  - `phase2_complete <= 1`
  - `Orchestrator async init completo == 1`
- Cada tool de leitura dispara verificação "não aciona bootstrap"
  via diff de marcadores no stderr.
