# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ADR 0002 — Servidor MCP unificado (iaglobal.mcp.server)

- **Status**: Aceita
- **Data**: 2026-07-24
- **Supersede**: nenhum
- **Superseded by**: —

## Contexto

O projeto historicamente tinha **dois** entrypoints MCP:

| Path | Uso | Estado |
|---|---|---|
| `iaglobal/api/mcp_server.py` | entrypoint original (run_mcp.sh → `python -m iaglobal.api.mcp_server`) | DEPRECATED, mantido p/ compat |
| `iaglobal/mcp/server.py` | entrypoint consolidado (unified, FastMCP + FastAPI gateway + bus) | canônico |

Padrões problemáticos observados:

- `run_mcp.sh` ainda apontava para o módulo antigo (`-m iaglobal.api.mcp_server`), mesmo após o unified existir.
- O módulo antigo não tinha bus integration, FastAPI gateway, ou FastMCP tools adicionais.
- Tools duplicadas/missing entre os dois (`get_provider_metrics`, `get_bandit_scores`, `get_insights`, `get_system_health`, etc só existiam no deprecated).
- OpenCode apontava para o módulo antigo via `run_mcp.sh`, então o cliente consumia a versão sem ferramentas de observabilidade.

## Decisão

Adotar **`iaglobal/mcp.server`** (unified) como único entrypoint canônico. Manter
`iaglobal/api/mcp_server.py` como shim de compat até cutover definitivo
(marcado DEPRECATED no docstring do arquivo).

### Helpers obrigatórios no unified

```python
async def _ensure_phase1() -> None
async def _ensure_full() -> Orchestrator
def _boot_snapshot() -> dict
def _ready() -> bool
```

Padrão de uso em tools MCP (do ADR 0001):

```python
@mcp.tool()
async def minha_tool() -> str:
    await _ensure_phase1()
    snap = _boot_snapshot()
    if not snap["phase2_done"]:
        return "BOOTING: ..."
    await _ensure_full()
    return _get_api().minha_leitura_pesada()
```

### `run_mcp.sh` migrado

```bash
exec venv/bin/python -u -m iaglobal.mcp.server --mode stdio "$@"
```

### Ferramentas canonicas no unified

Ver AGENTS.md § "MCP Server Entrypoint Contract" para mapeamento completo.

## Consequências

### Positivas

- Um único entrypoint MCP. Sem ambiguidade para `run_mcp.sh`, OpenCode,
  scripts de smoke, CI.
- `iaglobal/mcp/server.py` adicionado com 7 ferramentas migradas:
  `get_insights`, `list_scripts`, `get_provider_metrics`,
  `get_model_metrics`, `get_bandit_scores`, `get_execution_history`,
  `get_system_health`.
- `get_status` migrado para caminho **lazy** (responde BOOTING se Phase2 roda).
- `run_server()` (entrypoint stdio/SSE) chama `_ensure_phase1()` antes
  do `mcp.run_stdio_async()` — handshake concluído antes do cliente conectar.
- Constraints de ferramentas garantidos: nenhuma tool `requires Phase2`
  toca o bootstrap durante BOOTING.

### Custos

- `iaglobal/mcp/server.py` passou de **898 → 1192 linhas** (modalidade lazy
  + helpers + 7 tools).
- `iaglobal/api/mcp_server.py` virou shim de compat (~440 linhas
  marcadas DEPRECATED no docstring).

### Dependências

- **ADR 0001**: depende do `EnsurePhase1 + Snapshot + Lazy` do bootstrap
  duas fases. Sem o ADR 0001, este ADR reintroduziria instabilidade.

## Alternativas consideradas

1. **Remover `iaglobal/api/mcp_server.py` totalmente**: rejeitada —
   `scripts/smoke_test.py:219` ainda importa `from iaglobal.api.mcp_server import mcp`
   para os smoke tests legados. Cortaria até cutover coordenado.
2. **Manter os dois arquivos em paralelo indefinidamente**: rejeitada —
   acopla risco de drift e浪费时间 em manutenções duplicadas.
3. **Mover tudo para `iaglobal/server/`**: rejeitada — aumentaria churn
   sem ganho funcional; padrão consolidado em `iaglobal/mcp/server.py`.

## Reversibilidade

Total — basta renomear imports e atualizar `run_mcp.sh`. Sem perda de
funcionalidade.

## Validação automatizada

- `test_verify_mcp.py` deve passar com exit 0.
- Tools `get_*` migrate respondendo corretamente em sub-segundo.
- `iaglobal_get_status` via MCP respondendo imediatamente
  (não mais timeout).

## Quando revisar

- Se Linux Foundation padronizar outro protocolo (gRPC, REST/SSE v2).
- Se aparecer problema de TLS/auth no unified que exija novo formato.
