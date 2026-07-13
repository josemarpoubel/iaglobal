# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# MCP Operations — Protocol Expansion (Fases 1–3)

> **Documento operacional do ecossistema MCP recém‑expandido do iaglobal.**  
> Todas as tools, agentes, camadas de segurança e integrações descritas aqui correspondem ao código vivo em `iaglobal/mcp/`, `iaglobal/agents/`, `iaglobal/security/`, `iaglobal/validation/` e `iaglobal/immunity/`.

---

## Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Fase 1 — Serviços de Cliente MCP](#2-fase-1--serviços-de-cliente-mcp)
   - [2.1 FastMCP Server (`mcp_server.py`)](#21-mcp_serverpy)
   - [2.2 Web Search (`search_web.py`)](#22-search_webpy)
   - [2.3 File System (`file_system.py`)](#23-file_systempy)
   - [2.4 Code Executor (`code_executor.py`)](#24-code_executorpy)
   - [2.5 MCP Client (`client.py`)](#25-clientpy)
   - [2.6 MCP Discovery (`discovery.py`)](#26-discoverypy)
3. [Fase 2 — Integração com Agentes](#3-fase-2--integração-com-agentes)
   - [3.1 ToolCallerAgent (`tool_caller_agent.py`)](#31-toolcalleragent)
   - [3.2 Validação de Schema MCP](#32-validação-de-schema-mcp)
4. [Fase 3 — Segurança](#4-fase-3--segurança)
   - [4.1 MCPSandbox (`mcp_sandbox.py`)](#41-mcpsandbox)
   - [4.2 Glutathione Rate Limiting](#42-glutathione-rate-limiting)
   - [4.3 Audit Trail (`audit.json`)](#43-audit-trail)
5. [Testes](#5-testes)
6. [Comandos Rápidos](#6-comandos-rápidos)
7. [Debugging](#7-debugging)

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    iaglobal MCP Layer                    │
├─────────────┬───────────────┬───────────────┬────────────┤
│  FastMCP    │  MCPClient    │  MCPDiscovery │ ToolCaller │
│  (server)   │  (externo)    │  (registro)   │ Agent      │
├─────────────┼───────────────┼───────────────┼────────────┤
│ search_web  │ file_system   │ code_executor │            │
│ (duckduckgo)│ (whitelist)   │ (sandbox)     │            │
├─────────────┴───────────────┴───────────────┴────────────┤
│                  Segurança (MCPSandbox)                   │
│  whitelist → rate_limit → audit_trail → glutathione       │
└─────────────────────────────────────────────────────────┘
```

**Fluxo de uma chamada MCP:**
1. `ToolCallerAgent.run()` recebe `{tool, arguments, agent_id}`
2. `MCPSandbox.validate_call()` checa whitelist
3. `FeedbackEngine.validate_mcp_call()` valida schema dos argumentos
4. `GlutathioneGuardrails.check_mcp_rate_limit()` verifica rate
5. Handler específico executa (ex: `FileSystemTool.read_file`)
6. `MCPSandbox.audit_call()` registra no `audit.json`
7. Retorna `{result, execution_metrics}` para o BanditPolicy

---

## 2. Fase 1 — Serviços de Cliente MCP

### 2.1 `mcp_server.py`

**FastMCP server** que expõe 8 tools metabólicas do iaglobal.

```python
from iaglobal.mcp.mcp_server import mcp, web_search, read_file, execute_code
```

**Tools expostas:**

| Tool | Parâmetros | Descrição |
|------|-----------|-----------|
| `metabolic_audit` | — | Auditoria metabólica completa (score, findings, corrections) |
| `get_ivm` | — | Índice de Viabilidade Metabólica atual |
| `web_search` | `query: str`, `max_results: int (5)` | Busca web com cache |
| `web_fetch` | `url: str`, `timeout: int (15)` | Fetch de conteúdo de URL |
| `read_file` | `path: str` | Leitura segura de arquivo |
| `write_file` | `path: str`, `content: str` | Escrita segura de arquivo |
| `list_dir` | `path: str` | Listagem de diretório |
| `execute_code` | `code: str`, `language: str (python)` | Execução em sandbox |

**Iniciar servidor:**
```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate

# Via SSE (HTTP)
python -c "import asyncio; from iaglobal.mcp.mcp_server import run_server; asyncio.run(run_server(port=8100))"
```

**Usar via OpenCode (stdio):**
```json
// .opencode.json
{
  "mcp": {
    "iaglobal-mcp": {
      "type": "local",
      "command": ["python3", "-c", "import asyncio; from iaglobal.mcp.mcp_server import mcp; mcp.run_stdio_async()"],
      "enabled": true,
      "timeout": 600000,
      "env": {
        "PYTHONPATH": "/home/kitohamachi/projeto-iaglobal"
      }
    }
  }
}
```

---

### 2.2 `search_web.py`

```python
from iaglobal.mcp.search_web import WebSearchTool

tool = WebSearchTool(cache_ttl=300)  # 5 minutos de cache

# Busca web
results = await tool.search("iaglobal autonomous AI", max_results=5)
# → [{"title", "url", "snippet", "source"}, ...]

# Fetch de página
html = await tool.fetch_page("https://example.com")
```

**Mecanismos de busca (fallback):**
1. `duckduckgo_search` (DDGS) — primário
2. `duckduckgo.com/lite/` via aiohttp — fallback
3. Cache LRU com TTL configurável (max 100 entries)

**Cache:**
```python
tool._set_cache("key", results)
tool._get_from_cache("key")  # None se expirado
```

---

### 2.3 `file_system.py`

```python
from iaglobal.mcp.file_system import FileSystemTool

tool = FileSystemTool()

# Leitura segura
content = await tool.read_file("iaglobal/mcp/mcp_agent.py")      # ✅ OK
content = await tool.read_file("/etc/passwd")                      # ❌ None (bloqueado)
content = await tool.read_file("../../etc/shadow")                 # ❌ None (bloqueado)

# Escrita segura
ok = await tool.write_file("memory/data/json/relatorio.json", {})  # ✅ True
ok = await tool.write_file("/tmp/hack.py", "evil")                 # ❌ False (bloqueado)

# Listagem segura
entries = await tool.list_dir("iaglobal/mcp")                      # ✅ 6+ entries
entries = await tool.list_dir("/etc")                              # ❌ [] (bloqueado)
```

**Whitelist de leitura:**
- `iaglobal/`, `tests/`, `docs/`, `memory/data/json/`

**Whitelist de escrita:**
- `memory/data/json/`, `memory/data/script/`

---

### 2.4 `code_executor.py`

```python
from iaglobal.mcp.code_executor import CodeExecutorTool

tool = CodeExecutorTool(timeout=30)

# Execução em sandbox
result = await tool.execute("print('hello world')")
# → {"sucesso": True, "stdout": "hello world", "returncode": 0}

# Validação sem execução
validation = await tool.validate("x = 1")
# → {"valid": True, "errors": []}

# Linguagem não suportada
result = await tool.execute("System.out.println('hi')", language="java")
# → {"sucesso": False, "erro": "UnsupportedLanguage"}
```

**Camadas de segurança aplicadas:**
1. `ASTGateway` — valida imports e sintaxe
2. `SandboxRules` — whitelist de paths e módulos
3. Subprocesso isolado com `preexec_fn` (resource limits + network guard)
4. `GlutathioneGuardrails` — padrões perigosos (eval, exec, subprocess)

---

### 2.5 `client.py`

```python
from iaglobal.mcp.client import MCPClient

client = MCPClient()

# Conexão via stdio
info = await client.connect_stdio("python3", ["-m", "some_mcp_server"])

# Conexão via SSE
info = await client.connect_sse("http://localhost:8100")

# Listar tools do servidor
tools = await client.list_tools()
# → [{"name": "tool_name", "description": "...", "parameters": {}}]

# Chamar tool
result = await client.call_tool("tool_name", {"arg": "value"})

# Fechar conexão
await client.close()
```

**Protocolo:** JSON-RPC 2.0 sobre stdio ou SSE.

---

### 2.6 `discovery.py`

```python
from iaglobal.mcp.discovery import MCPDiscovery

discovery = MCPDiscovery()

# Descobrir todas as tools (internas + externas)
catalog = await discovery.discover_all()
# → {"version": 1, "updated_at": "ISO8601", "tools": [...]}

# Buscar tool específica
tool = await discovery.get_tool("web_search")
# → {"name": "web_search", "description": "...", "server": "internal", "parameters": {...}}

tool = await discovery.get_tool("inexistente")
# → None
```

**Cache persistido em:** `iaglobal/memory/data/json/mcp_tools.json`

**Tools internas registradas (8):**
`metabolic_audit`, `get_ivm`, `web_search`, `web_fetch`, `read_file`, `write_file`, `list_dir`, `execute_code`

**Servidores externos:** Registrados em `iaglobal/memory/data/json/mcp_servers.json`

```json
{
  "servers": [
    {"name": "meu-servidor", "type": "stdio", "command": "python3", "args": ["-m", "meu_mcp"]}
  ]
}
```

---

## 3. Fase 2 — Integração com Agentes

### 3.1 ToolCallerAgent

```python
from iaglobal.agents.tool_caller_agent import ToolCallerAgent

agent = ToolCallerAgent()

result = await agent.run({
    "tool_name": "read_file",
    "arguments": {"path": "iaglobal/mcp/__init__.py"},
    "agent_id": "orchestrator",
})
# → {
#     "result": "...",
#     "execution_metrics": {
#         "tool_name": "read_file",
#         "success": True,
#         "latency": 0.023,
#         "arguments": {"path": "..."},
#         "result_summary": "...",
#     }
# }
```

**Mapa de tools internas** (dispatch direto, sem discovery):
- `web_search`, `web_fetch` → `WebSearchTool`
- `read_file`, `write_file`, `list_dir` → `FileSystemTool`
- `execute_code` → `CodeExecutorTool`

**Tools externas:** Resolvidas via `MCPDiscovery.get_tool()` + `MCPClient.call_tool()`.

**Integração com BanditPolicy:** O dicionário `execution_metrics` é consumido pelo `JointOptimizationLoop` para calcular rewards (success, latency, cost).

---

### 3.2 Validação de Schema MCP

Adicionada ao `FeedbackEngine` em `iaglobal/validation/engine.py`:

```python
from iaglobal.validation.engine import FeedbackEngine

engine = FeedbackEngine()

schema = {"parameters": {"query": {"type": "string"}, "limit": {"type": "integer"}}}

engine.validate_mcp_call(schema, {"query": "ai", "limit": 5})         # ✅ True
engine.validate_mcp_call(schema, {"query": "ai", "limit": "cinco"})   # ❌ False
engine.validate_mcp_call(schema, {})                                   # ✅ True (opcionais)
engine.validate_mcp_call({}, {"qualquer": "coisa"})                    # ✅ True (sem schema)
```

**Tipos validados:** `string`, `integer`, `boolean`. Parâmetros ausentes ou `None` são aceitos.

---

## 4. Fase 3 — Segurança

### 4.1 MCPSandbox

```python
from iaglobal.security.mcp_sandbox import MCPSandbox

sandbox = MCPSandbox()

# Whitelist
await sandbox.validate_call("web_search", {})         # ✅ True
await sandbox.validate_call("rm_rf", {})               # ❌ False
await sandbox.validate_call("os.system", {})           # ❌ False

# Rate limit
await sandbox.check_rate_limit("read_file", "agent_x")  # ✅ True (se dentro do limite)
await sandbox.check_rate_limit("execute_code", "agent_x") # pode ser False se excedeu

# Audit
await sandbox.audit_call("web_search", {"q": "test"}, result, agent_id="evo-1", allowed=True)
```

**Whitelist de tools (`ALLOWED_TOOLS`):**
`web_search`, `web_fetch`, `read_file`, `write_file`, `list_dir`, `execute_code`, `metabolic_audit`, `get_ivm`

**Rate limits por tool:**

| Tool | Chamadas/min | Cooldown (s) |
|------|-------------|--------------|
| `web_search` | 10 | 6 |
| `web_fetch` | 15 | 4 |
| `execute_code` | 5 | 12 |
| `read_file` | 30 | 2 |
| `write_file` | 10 | 6 |

---

### 4.2 Glutathione Rate Limiting

Em `iaglobal/immunity/glutathione_guardrails.py`:

```python
from iaglobal.immunity.glutathione_guardrails import (
    GlutathioneGuardrails,
    MCP_RATE_LIMITS,
)

# Verificar rate limit antes de chamada MCP
check = GlutathioneGuardrails.check_mcp_rate_limit("web_search", "evo-agent")
# → {"allowed": True, "calls_in_window": 1}

# Se excedeu:
check = {"allowed": False, "reason": "Rate limit: 10/min"}
```

Integrado com o sistema SAMe — cada chamada MCP pode consumir créditos SAMe.

---

### 4.3 Audit Trail

Toda chamada MCP (permitida ou bloqueada) é registrada em:

**Arquivo:** `iaglobal/memory/data/json/audit.json`

```json
{
  "audits": [
    {
      "timestamp": "2026-07-09T07:00:00Z",
      "agent_id": "evo-1",
      "tool": "web_search",
      "arguments": {"query": "iaglobal"},
      "result_summary": "[...]",
      "sandbox_decision": "allowed"
    }
  ]
}
```

**Limite:** Máximo de 1000 entradas (as mais antigas são podadas automaticamente).

**Consultar audit trail:**
```bash
python -c "import json; data=json.load(open('iaglobal/memory/data/json/audit.json')); print(f'{len(data[\"audits\"])} registros')"
```

---

## 5. Testes

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate

# Todos os testes MCP
python -m pytest tests/test_mcp_protocol_expansion.py -v

# Teste específico por classe
python -m pytest tests/test_mcp_protocol_expansion.py::TestFileSystemTool -v
python -m pytest tests/test_mcp_protocol_expansion.py::TestMCPSandbox -v
python -m pytest tests/test_mcp_protocol_expansion.py::TestToolCallerAgent -v

# Regressão completa
python -m pytest tests/ -q --tb=short
```

**47 testes** distribuídos:
- 19 — Fase 1 (servidores, tools, cache)
- 9 — Fase 2 (agentes, schema validation)
- 11 — Fase 3 (sandbox, rate limit, audit)
- 3 — Integração end-to-end
- 5 — Schemas e imports

---

## 6. Comandos Rápidos

```bash
# Verificar que todos os módulos MCP importam
python -c "from iaglobal.mcp.mcp_server import mcp; from iaglobal.mcp.search_web import WebSearchTool; from iaglobal.mcp.file_system import FileSystemTool; from iaglobal.mcp.code_executor import CodeExecutorTool; from iaglobal.mcp.client import MCPClient; from iaglobal.mcp.discovery import MCPDiscovery; print('✅ MCP ok')"

# Descobrir tools e ver cache
python -c "import asyncio; from iaglobal.mcp.discovery import MCPDiscovery; d=asyncio.run(MCPDiscovery().discover_all()); print(f'{len(d[\"tools\"])} tools'); print('\\n'.join(f'  - {t[\"name\"]}' for t in d['tools']))"

# Ler audit trail
python -c "import json; a=json.loads(open('iaglobal/memory/data/json/audit.json').read()); print(f'{len(a[\"audits\"])} audits'); [print(f'  {e[\"timestamp\"]} | {e[\"agent_id\"]} | {e[\"tool\"]} | {e[\"sandbox_decision\"]}') for e in a['audits'][-5:]]"

# Testar leitura segura
python -c "import asyncio; from iaglobal.mcp.file_system import FileSystemTool; f=FileSystemTool(); print(asyncio.run(f.read_file('iaglobal/mcp/mcp_agent.py'))[:100])"

# Testar executor em sandbox
python -c "import asyncio; from iaglobal.mcp.code_executor import CodeExecutorTool; r=asyncio.run(CodeExecutorTool().execute('print(42)')); print(r['stdout'])"
```

---

## 7. Debugging

| Problema | Causa Provável | Solução |
|----------|---------------|---------|
| `ModuleNotFoundError: No module named 'mcp'` | FastMCP não instalado | `pip install mcp` |
| `read_file()` retorna `None` | Path fora da whitelist | Usar path relativo a `iaglobal/`, `tests/` ou `memory/data/json/` |
| `execute_code()` retorna `SecurityViolation` | Código contém eval/exec/subprocess | Revisar código para remover padrões perigosos |
| `ToolCallerAgent` retorna `success=False` | Tool não mapeada ou erro no handler | Verificar `tool_name` e `arguments` |
| `discovery.get_tool()` retorna `None` | Tool não registrada | Executar `discovery.discover_all()` primeiro |
| Rate limit excessivo | Agente chamando tool muito rápido | Aumentar `calls_per_minute` em `RATE_LIMITS` ou adicionar backoff |
| Audit trail com muitas entradas | Sem poda automática | Limite 1000 entradas no `_append_audit()` — aguardar ou limpar manualmente |

---

> **Axioma MCP:** "Toda tool externa que entra no organismo iaglobal passa pela membrana semi-permeável do MCPSandbox — ou entra purificada, ou é rejeitada como antígeno."
