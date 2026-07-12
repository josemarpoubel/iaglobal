# 🌐 Arquitetura de Servidores iaglobal

## Visão Geral

O iaglobal opera com **múltiplos servidores especializados** que seguem o padrão de **organismo computacional**: cada servidor é um "órgão" com função específica, todos coordenados por um **gateway ASGI central**.

---

## 🗺️ Mapa de Portas

| Serviço | Porta | Arquivo | Status |
|---------|-------|---------|--------|
| **ASGI Gateway** | `8000` | `iaglobal/server/asgi.py` | ✅ **Entry Point Único** |
| **MCP Server** | `8100` | `iaglobal/server/mcp_server.py` | ✅ Interno/Standalone |
| **UI Server** | `8765` | `iaglobal/ui/fastapi_app.py` | ✅ Standalone |
| **Evolution Server** | `8002` | `iaglobal/server/server.py` | ✅ Standalone/Gateway |

---

## 🏛️ Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────┐
│           PORTA 8000 - ASGI GATEWAY                     │
│           (ÚNICO PONTO DE ENTRADA)                      │
├─────────────────────────────────────────────────────────┤
│  Rota          → Serviço Interno                        │
├─────────────────────────────────────────────────────────┤
│  /             → Welcome page (MCP)                     │
│  /mcp/*        → MCP Server (montado in-process)        │
│  /@/*          → UI ReactPy (porta 8765)                │
│  /evolution/*  → Evolution Engine                       │
│  /result/*     → Static Files (resultados)              │
│  /health       → Health Check do sistema                │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Componentes

### 1. ASGI Gateway (Porta 8000)

**Arquivo:** `iaglobal/server/asgi.py`

**Função:** Gateway único que monta todos os serviços como sub-apps.

**Vantagens:**
- ✅ Single point of entry (mais seguro)
- ✅ CORS centralizado
- ✅ Rate limiting unificado
- ✅ Logs consolidados
- ✅ Sem conflito de portas

**Como rodar:**
```bash
python -m iaglobal.server.asgi
# ou
uvicorn iaglobal.server.asgi:application --host 0.0.0.0 --port 8000
```

**Acesso:**
- `http://localhost:8000/` → Welcome page
- `http://localhost:8000/mcp/health` → Health do MCP
- `http://localhost:8000/@/` → UI ReactPy
- `http://localhost:8000/result/` → Resultados

---

### 2. MCP Server (Porta 8100)

**Arquivo:** `iaglobal/server/mcp_server.py`

**Função:** Meta-Circular Protocol - auditoria, autocorreção, invariantes.

**Modos de operação:**
1. **Standalone** (porta 8100):
   ```bash
   python -m iaglobal.server
   ```

2. **Montado no Gateway** (interno):
   - Acessível via `http://localhost:8000/mcp/*`
   - Não exposto diretamente

**Endpoints:**
- `/mcp/health` → Health check
- `/mcp/audit` → Auditoria metabólica
- `/mcp/fix` → Acionar correção
- `/mcp/jsonrpc` → JSON-RPC

### 📊 BALANÇO ENERGÉTICO (ATP)

**Ferramentas MCP totais**: 10 → **13 tools** (+30%)

| Categoria      | Tools                                                        | Count        |
|----------------|--------------------------------------------------------------|--------------|
| Metabólicas    | `metabolic_audit`, `get_ivm`                                 | 2            |
| IAGlobal API   | `run_task`, `get_status`, `get_history`                      | 3            |
| Web            | `web_search`, `web_fetch`                                    | 2            |
| File System    | `read_file`, `write_file`, `list_dir`                        | 3            |
| Code Execution | `execute_code`                                               | 1            |
| Evolution      | `evolution_status`, `evolve_strategy`, `evolution_dashboard` | 3            |
| **Glutationa** | `reflexion_fix`, `reflexion_loop`, `get_error_history`       | **3** ← NOVO |
---

### 🛡️ PERFIL ANTIOXIDANTE ATUALIZADO

**GSH (Glutationa) agora operacional**:

```
ESTRESSE OXIDATIVO (ROS)
     ↓
Agente detecta erro no código
     ↓
GSH → reflexion_fix() ativado
     ↓
Código corrigido + aprendizado
     ↓
SISTEMA RESTAURADO
```

**Capacidade de auto-cura**:
- ✅ Agentes podem solicitar correção on-demand
- ✅ Histórico de erros consultável (memória imunológica)
- ✅ Loop de reflexão com max 5 iterações
- ✅ Integração com BanditPolicy para geração

---

### 🔄 CICLO DE AUTO-REGENERAÇÃO

**DNA preservado**: `🧬 cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136`

**Arquivos modificados**:
1. ✅ `iaglobal/reflection/reflexion_engine.py` (+ LINEAGE_MARKER)
2. ✅ `iaglobal/mcp/server.py` (+ 3 tools, +127 LOC)
3. ✅ `iaglobal/mcp/__init__.py` (+ exports)
4. ⏳ `INSTRUCTION_WEB_INTERFACE.md` (pendente)

---

### 3. UI Server (Porta 8765)

**Arquivo:** `iaglobal/ui/fastapi_app.py`

**Função:** Interface do usuário com dashboard ReactPy.

**Modos de operação:**
1. **Standalone** (porta 8765):
   ```bash
   python -m iaglobal.ui.fastapi_app
   ```

2. **Montado no Gateway** (interno):
   - Acessível via `http://localhost:8000/@/`
   - WebSocket: `ws://localhost:8000/ws`

**Endpoints:**
- `/` → Dashboard principal
- `/ws` → WebSocket para progresso em tempo real
- `/health` → Health check da UI
- `/result/` → Lista de resultados

---

### 4. Evolution Server (Porta 8002)

**Arquivo:** `iaglobal/server/server.py`

**Função:** Motor de evolução autônoma (estratégias deep/fast).

**Modo de operação:**
1. **Standalone** (porta 8002, configurável via `EVOLUTION_PORT`):
   ```bash
   python -m iaglobal.server.server
   ```

2. **Montado no Gateway** (`/evolution/*`)

**Endpoints:**
- `/evolution/status` → Status da evolução
- `/evolution/strategies` → Estratégias ativas
- `/evolution/trigger` → Acionar evolução manual

---

## 🔐 Variáveis de Ambiente

No arquivo `.env`:

```bash
# Gateway ASGI (entry point)
GATEWAY_PORT=8000

# MCP Server (interno/standalone)
MCP_HOST=0.0.0.0
MCP_PORT=8100

# UI Server (standalone)
UI_PORT=8765

# Evolution Server (opcional)
# EVOLUTION_PORT=8002
```

---

## 🚀 Como Rodar

### Modo Recomendado (Gateway Único)

```bash
# 1. Inicia o Gateway (porta 8000)
python -m iaglobal.server.asgi

# 2. Acessa tudo pelo gateway:
#    - UI: http://localhost:8000/@/
#    - MCP: http://localhost:8000/mcp/health
#    - Evolution: http://localhost:8000/evolution/status
```

### Modo Standalone (Cada serviço em sua porta)

```bash
# Terminal 1: MCP Server (8100)
python -m iaglobal.server

# Terminal 2: UI Server (8765)
python -m iaglobal.ui.fastapi_app

# Terminal 3: Evolution (se tiver entry point)
python iaglobal/server/server.py

# Acesso:
#    - MCP: http://localhost:8100/
#    - UI: http://localhost:8765/
#    - Evolution: http://localhost:8002/
```

---

## 🧬 Homeostase de Portas

### Conflito Evitado

**Antes:**
- UI Server → porta 8000 ❌
- ASGI Gateway → porta 8000 ❌
- **Conflito:** Dois servidores não podem usar a mesma porta

**Depois:**
- ASGI Gateway → porta 8000 ✅
- UI Server → porta 8765 ✅
- MCP Server → porta 8100 ✅
- **Solução:** Cada serviço em sua porta, gateway unifica acesso

### Benefícios Metabólicos

| Métrica | Antes | Depois |
|---------|-------|--------|
| Conflitos de porta | 2 servidores em 8000 | 0 conflitos |
| Entry points | Múltiplos (8000, 8100, 8765) | Único (8000) |
| Complexidade de CORS | 3 configurações | 1 configuração |
| Rate limiting | Por servidor | Centralizado |
| Logs | Dispersos | Consolidados |

---

## 🛡️ Segurança

### Gateway como Firewall de Aplicação

O ASGI Gateway atua como **camada única de segurança**:

1. **CORS:** Configurado uma vez no gateway
2. **Rate Limiting:** Aplicado antes de chegar nos serviços
3. **Auth:** MCP authentication centralizada
4. **Logs:** Todos os requests passam pelo gateway

### Isolamento de Serviços

- MCP Server (8100) não é exposto diretamente
- UI Server (8765) pode ser desativado em produção
- Evolution roda apenas internamente

---

## 📊 Monitoramento

### Health Checks

```bash
# Gateway
curl http://localhost:8000/health

# MCP (via gateway)
curl http://localhost:8000/mcp/health

# MCP (direto)
curl http://localhost:8100/health

# UI (direto)
curl http://localhost:8765/health
```

### Logs

Todos os serviços usam o mesmo logger:
```python
from iaglobal.utils.logger import get_logger
logger = get_logger("iaglobal.server")
```

---

## 🔄 Evolução Futura

### Próximas Mutações

1. **Evolution Server standalone** - Criar `__main__.py` com porta configurável
2. **Hot reload em desenvolvimento** - `uvicorn --reload` no gateway
3. **Load balancing** - Múltiplas instâncias do gateway
4. **Service mesh** - Istio/Envoy para orquestração fina

### Metas de Homeostase

- ✅ Zero conflitos de porta
- ✅ Single point of entry
- ⏳ Health checks unificados
- ⏳ Circuit breaker no gateway
- ⏳ Métricas de latência por serviço

---

## 🧪 Troubleshooting

### "Porta 8000 já está em uso"

**Causa:** Outro serviço está rodando na porta 8000

**Solução:**
```bash
# Matar processo usando a porta
lsof -i :8000
kill -9 <PID>

# Ou mudar a porta do gateway
export GATEWAY_PORT=8001
```

### "UI não carrega via gateway"

**Causa:** UI Server não está rodando

**Solução:**
```bash
# Iniciar UI standalone
python -m iaglobal.ui.fastapi_app

# Ou montar no gateway (já configurado)
# Acessar: http://localhost:8000/@/
```

### "MCP não responde"

**Causa:** MCP Server não está rodando ou porta 8100 ocupada

**Solução:**
```bash
# Verificar se MCP está rodando
curl http://localhost:8100/health

# Iniciar MCP
python -m iaglobal.server.mcp_server
```

---

## 📚 Referências

- **ASGI Gateway:** `iaglobal/server/asgi.py`
- **MCP Server:** `iaglobal/server/mcp_server.py`
- **UI Server:** `iaglobal/ui/fastapi_app.py`
- **Configuração:** `.env.example` (variáveis `GATEWAY_PORT`, `MCP_PORT`, `UI_PORT`)

---

**Última atualização:** 2026-07-08  
**Status:** ✅ Homeostase de portas alcançada  
**Próximo passo:** Implementar health checks unificados
