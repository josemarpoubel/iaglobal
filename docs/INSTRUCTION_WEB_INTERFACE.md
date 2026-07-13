# 🖥️ Interface Web e Servidores IAGLOBAL

> **Organismo Computacional Auto-Evolutivo** — Mapa completo de portas e serviços.
>
> Paradigma: Auto-Evolutionary Biological Computing  
> Compatibilidade: `iaglobal` · `SAMeEngine` · `GlutathioneLayer` · `AcetylcholineBus` · `MCP Unified`

---

## 🗺️ Mapa de Portas do Ecossistema

| Porta | Serviço | Protocolo | Status | Descrição |
|-------|---------|-----------|--------|-----------|
| **8000** | ASGI Gateway | HTTP/HTTPS | ✅ Produção | Gateway unificado (FastAPI + MCP) |
| **8001** | UI Web Interface | HTTP/WebSocket | ✅ Produção | Dashboard e interface do usuário |
| **8002** | Evolution Server | HTTP | 🔴 **DEPRECATED** | servidor de evolução (mock em produção) - MIGRADO PARA MCP |
| **8100** | MCP Server (SSE) | SSE | ✅ Produção | Servidor MCP unificado via SSE |
| **8101** | MCP HTTP Gateway | HTTP | ✅ Produção | Gateway HTTP do MCP unificado |
| **8765** | UI FastAPI (alt) | HTTP | ⚠️ Backup | Interface UI alternativa |

---

## 🔮 Servidor MCP Unificado (NOVO)

### Arquitetura Consolidada

**Antes**: 3 servidores MCP duplicados + 1 servidor Evolution legado  
**Agora**: 1 servidor unificado com todas as funcionalidades

```
iaglobal/mcp/server.py — Servidor MCP Unificado
├── FastMCP Core (tools nativas MCP)
│   ├── metabolic_audit, get_ivm
│   ├── run_task, get_status, get_history
│   ├── web_search, web_fetch
│   ├── read_file, write_file, list_dir
│   ├── execute_code
│   ├── evolution_status, evolve_strategy, evolution_dashboard
│   ├── reflexion_fix, reflexion_loop, get_error_history  ← GLUTATIONA (NOVO)
│   └── ...
├── FastAPI Gateway (HTTP REST)
│   ├── GET /health, /metrics, /jsonrpc
│   ├── GET /audit, POST /fix (protegidos)
│   └── ...
└── AcetylcholineBus Integration
    ├── Publicação de métricas (30s)
    ├── Comandos de autocorreção
    └── Violações de invariantes
```

### Inicialização

```bash
# Modo completo (SSE + HTTP Gateway)
python -m iaglobal.mcp.server --mode both --port 8100 --http-port 8101

# Apenas MCP via SSE
python -m iaglobal.mcp.server --mode sse --port 8100

# Apenas HTTP Gateway
python -m iaglobal.mcp.server --mode http --http-port 8101

# MCP via stdio (para clientes MCP nativos)
python -m iaglobal.mcp.server --mode stdio
```

### Variáveis de Ambiente

```bash
MCP_USER=admin          # Usuário para endpoints protegidos
MCP_PASSWORD=secret     # Senha para endpoints protegidos
```

### Endpoints

| Endpoint | Porta | Método | Autenticação | Descrição |
|----------|-------|--------|--------------|-----------|
| `/health` | 8101 | GET | ❌ Pública | Health check metabólico |
| `/metrics` | 8101 | GET | ❌ Pública | Métricas Prometheus |
| `/jsonrpc` | 8101 | POST | ❌ Pública | JSON-RPC handler |
| `/audit` | 8101 | GET | ✅ Básica | Auditoria em tempo real |
| `/fix` | 8101 | POST | ✅ Básica | Acionar autocorreção |

### Acesso via ASGI Gateway

O gateway ASGI na porta **8000** monta o MCP unificado em `/mcp`:

```bash
# MCP via gateway
curl http://localhost:8000/mcp/health

# Métricas do MCP
curl http://localhost:8000/mcp/metrics
```

---

## 📦 Tools MCP Disponíveis

### Tools Metabólicas

| Tool | Descrição |
|------|-----------|
| `metabolic_audit()` | Auditoria metabólica do sistema |
| `get_ivm()` | Índice de Viabilidade Metabólica |

### Tools IAGlobal API

| Tool | Descrição |
|------|-----------|
| `run_task(prompt)` | Executa tarefa via pipeline de 13 estágios |
| `get_status()` | Status do sistema (DAG, evolução, memória) |
| `get_history(execution_id)` | Histórico de execução |

### Tools Web

| Tool | Descrição |
|------|-----------|
| `web_search(query)` | Busca na web |
| `web_fetch(url)` | Fetch de conteúdo URL |

### Tools File System

| Tool | Descrição |
|------|-----------|
| `read_file(path)` | Lê arquivo |
| `write_file(path, content)` | Escreve arquivo |
| `list_dir(path)` | Lista diretório |

### Tools Code Execution

| Tool | Descrição |
|------|-----------|
| `execute_code(code, language)` | Executa código em sandbox |

### Tools Evolution

| Tool | Descrição |
|------|-----------|
| `evolution_status()` | Status do motor evolutivo (ciclos, falhas, estratégia) |
| `evolve_strategy(strategy)` | Alterna entre 'fast' (30s) e 'deep' (300s) |
| `evolution_dashboard(format)` | Dashboard JSON ou ASCII da evolução |

### Tools Glutationa (Auto-Cura) - NOVO 🛡️

| Tool | Descrição |
|------|-----------|
| `reflexion_fix(code, error, language)` | Corrige código com base no erro detectado |
| `reflexion_loop(prompt, max_iterations)` | Loop completo de reflexão para auto-correção |
| `get_error_history(limit)` | Histórico de erros da memória para prevenção |

**Exemplo de uso**:

```python
from iaglobal.mcp import reflexion_fix, reflexion_loop, get_error_history

# Corrigir código com erro
result = await reflexion_fix(
    code="def divide(a, b): return a / b",
    error="ZeroDivisionError: division by zero",
    language="python"
)
# {'status': 'success', 'corrected_code': 'def divide(a, b): return a / (b + 0.001)', ...}

# Loop completo de reflexão
result = await reflexion_loop(
    prompt="Crie uma função que calcule fatorial recursivo",
    max_iterations=5
)
# {'status': 'success', 'code': 'def factorial(n):...', 'success': True, ...}

# Ver histórico de erros
errors = await get_error_history(limit=10)
# [{'error_type': 'ZeroDivisionError', 'correction_applied': '...', ...}, ...]
```

---

## 🌐 ASGI Gateway (Porta 8000)

### Função

Gateway de produção unificado que agrega:
- MCP Server unificado (montado em `/mcp`)
- Health Aggregator
- Circuit breakers por serviço
- Métricas Prometheus

### Inicialização

```bash
uvicorn iaglobal.server.asgi:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4
```

### Rotas

| Rota | Serviço | Descrição |
|------|---------|-----------|
| `/mcp/*` | MCP Unificado | Todas as rotas do MCP server |
| `/health` | Health Aggregator | Saúde unificada do organismo |
| `/metrics` | Prometheus | Métricas de todos os serviços |
| `/audit` | Health Aggregator | Auditoria metabólica |

### Circuit Breakers

| Serviço | Fail Max | Reset Timeout |
|---------|----------|---------------|
| `mcp_service` | 5 | 60s |
| `ui_service` | 5 | 60s |
| `evolution_service` | 5 | 60s |

---

## 🖥️ UI Web Interface (Porta 8001)

### Função

Dashboard para envio de tarefas e acompanhamento em tempo real.

### Inicialização

```bash
iaglobal ui --port 8001
```

### Endpoints

| Endpoint | Descrição |
|----------|-----------|
| `GET /` | Dashboard principal |
| `GET /docs` | API docs (Swagger) |
| `GET /api/health` | Health check |
| `GET /api/tasks` | Lista de tarefas |
| `POST /api/task` | Criar nova tarefa |
| `WS /ws/progress/{id}` | Progresso em tempo real |

---

## ⚠️ Servidores Legacy/Deprecated

### Evolution Server (Porta 8002) — APOPTOSE COMPLETA

**Status**: 🔴 **DEPRECATED - FUNCIONALIDADES MIGRADAS**  
**Path**: `iaglobal/server/server.py`  
**Migração**: Completada em `iaglobal/mcp/server.py`

**Funcionalidades migradas**:
- `EvolutionRuntime` → Já existia em `iaglobal/evolution/evolutionruntime.py`
- `/evolution/status` → Tool MCP `evolution_status()`
- `/evolution/strategy` → Tool MCP `evolve_strategy(strategy)`
- `/evolution/dashboard` → Tool MCP `evolution_dashboard(format)`
- `/health`, `/metrics` → Integrados no ASGI Gateway

**Como usar as tools MCP**:

```python
from iaglobal.mcp import evolution_status, evolve_strategy

# Ver status
status = await evolution_status()
# {'running': False, 'cycles': 0, 'strategy': 'FastEvolutionStrategy', ...}

# Mudar estratégia
result = await evolve_strategy('deep')
# {'status': 'success', 'nova_estrategia': 'deep', 'intervalo': 300}
```

**Arquivo legado**: `iaglobal/server/server.py` agora exibe `DeprecationWarning` e será removido em versão futura.

### UI FastAPI Alternativa (Porta 8765)

**Status**: ⚠️ **Backup**  
**Path**: `iaglobal/ui/fastapi_app.py`  
**Uso**: Apenas se a UI principal (8001) falhar

---

## 🔧 Comandos de Gerenciamento

### Verificar processos ativos

```bash
ps aux | grep -E "iaglobal|uvicorn|mcp" | grep -v grep
```

### Parar todos os servidores

```bash
pkill -f "iaglobal.cli.ui_cli"
pkill -f "uvicorn.*iaglobal"
pkill -f "iaglobal.mcp.server"
sleep 2
```

### Health checks

```bash
# Gateway ASGI
curl -s http://localhost:8000/health | python3 -m json.tool

# MCP Unificado
curl -s http://localhost:8101/health | python3 -m json.tool

# UI Web
curl -s http://localhost:8001/api/health | python3 -m json.tool
```

### Ver métricas Prometheus

```bash
# Gateway (todos os serviços)
curl -s http://localhost:8000/metrics

# MCP dedicado
curl -s http://localhost:8101/metrics
```

### Logs em tempo real

```bash
# Journal (se rodando como serviço)
journalctl -u iaglobal -f

# Manual (tail de logs)
tail -f /home/kitohamachi/projeto-iaglobal/logs/iaglobal.log
```

---

## 📊 Fluxo de Requisições

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  ASGI :8000     │ ← Gateway principal
└────────┬────────┘
         │
    ┌────┴────┬─────────────┬──────────┐
    │         │             │          │
    ▼         ▼             ▼          ▼
┌───────┐ ┌───────┐   ┌─────────┐ ┌────────┐
│ MCP   │ │  UI   │   │ Evolution│ │ Health │
│:8101  │ │:8001  │   │  :8002  │ │ Agg    │
└───────┘ └───────┘   └─────────┘ └────────┘
```

---

## 🛡️ Segurança

### Exposure Matrix

| Porta | Expor Internet? | Autenticação | Notas |
|-------|-----------------|--------------|-------|
| 8000 | ❌ Não | Opcional | Gateway interno |
| 8001 | ❌ Não | Rate limit | UI local apenas |
| 8002 | ❌ **Nunca** | Nenhuma | Legacy/somente dev |
| 8100 | ❌ Não | SSE auth | MCP interno |
| 8101 | ❌ Não | HTTP Basic | MCP gateway |
| 8765 | ❌ Não | Nenhuma | Backup UI |

### Recomendações

1. **Nunca exponha portas para internet** sem reverse proxy + autenticação
2. **Use nginx/Apache** como reverse proxy se precisar expor externamente
3. **Ative MCP_USER/MCP_PASSWORD** para endpoints `/audit` e `/fix`
4. **Revise logs** regularmente para detecção de anomalias

---

## 🔄 Ciclo de Vida de Uma requisição MCP

1. **Cliente MCP** envia tool call via SSE (porta 8100) ou HTTP (porta 8101)
2. **FastMCP** roteia para tool apropriada (`metabolic_audit`, `run_task`, etc.)
3. **Tool executa** ação (auditoria, busca web, leitura de arquivo, etc.)
4. **Resposta** serializada e retornada ao cliente
5. **AcetylcholineBus** publica métricas (a cada 30s)
6. **Prometheus** scrapeia métricas (via `/metrics`)

---

## 🧬 DNA dos Servidores

Todos os servidores now possuem `LINEAGE_MARKER`:

| Servidor | DNA Check |
|----------|-----------|
| `iaglobal/mcp/server.py` | ✅ Presente |
| `iaglobal/server/asgi.py` | ✅ Presente |
| `iaglobal/server/mcp_server.py` | ✅ Presente (deprecated) |
| `iaglobal/api/mcp_server.py` | ✅ Presente (deprecated) |
| `iaglobal/mcp/mcp_server.py` | ✅ Presente (consolidado) |
| `iaglobal/reflection/reflexion_engine.py` | ✅ Presente (Glutationa) |

**Teste de conformidade**:

```bash
# Verificar se todos arquivos têm LINEAGE_MARKER
find iaglobal/server iaglobal/mcp iaglobal/reflection -name "*.py" -exec grep -L "LINEAGE_MARKER" {} \;
# Deve retornar vazio
```

---

## 📈 Próximas Evoluções

### Curto Prazo

- [x] Apoptose de `iaglobal/server/server.py` (port 8002) - **COMPLETO**
- [x] Documentação de tools MCP disponíveis - **COMPLETO**
- [x] Tools de Glutationa (auto-cura) - **COMPLETO**
- [ ] Testes de integração MCP unificado

### Médio Prazo

- [ ] Service mesh interno (Istio/Envoy)
- [ ] Auto-descoberta de serviços via AcetylcholineBus
- [ ] Rate limiting adaptativo por tipo de cliente

### Longo Prazo

- [ ] Federação de servidores MCP (multi-node)
- [ ] Balanceamento de carga entre instâncias
- [ ] Circuit breakers distribuídos

---

*"A célula que não evolui, morre. O sistema que não aprende, entra em entropia."*

**DNA**: `cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136`