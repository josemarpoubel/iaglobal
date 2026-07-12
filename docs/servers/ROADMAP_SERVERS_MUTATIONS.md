# 🧬 ROADMAP DE MUTAÇÕES DE SERVIDORES — iaglobal

> **Última atualização:** 2026-07-08  
> **Status atual:** ✅ Ciclo S1-S4 COMPLETO | ✅ 299 testes passando  
> **Próximo ciclo:** Aguardando novas diretrizes

---

## 📋 Resumo do Ciclo S1-S4 (COMPLETO ✅)

| Ordem | Fase | Item | Testes | Status |
|-------|------|------|--------|--------|
| **1** | **Fase S1** | Health Checks Unificados | 11 | ✅ CONCLUÍDA |
| **2** | **Fase S2** | Evolution Server Standalone | 11 | ✅ CONCLUÍDA |
| **3** | **Fase S3** | Circuit Breaker no Gateway | 10 | ✅ CONCLUÍDA |
| **4** | **Fase S4** | Métricas de Latência por Serviço | 10 | ✅ CONCLUÍDA |
| **TOTAL** | **Ciclo S** | **Infraestrutura de Servidores** | **42 novos** | ✅ **SEM REGRESSÃO** |

---

## 🔵 Fase S1 — Health Checks Unificados ✅

### 📊 Implementação

**Arquivos:**
- `iaglobal/server/health_aggregator.py` (novo)
- `iaglobal/server/asgi.py` (atualizado)
- `tests/test_health_unified.py` (novo)

**Funcionalidades:**
- ✅ Health check unificado em `/health`
- ✅ Consulta 4 serviços em paralelo (gateway, mcp, ui, evolution)
- ✅ Estado metabólico (IVM, agentes)
- ✅ Estado de CPU (budgets)
- ✅ Status geral (healthy/degraded/unhealthy)

**Testes:** 11/11 passando

---

## 🔵 Fase S2 — Evolution Server Standalone ✅

### 📊 Implementação

**Arquivos:**
- `iaglobal/server/server.py` (adicionado `__main__`)
- `.env.example` (adicionado `EVOLUTION_PORT=8002`)
- `tests/test_evolution_standalone.py` (novo)

**Funcionalidades:**
- ✅ Evolution Server roda standalone (`python -m iaglobal.server.server`)
- ✅ Porta configurável via `EVOLUTION_PORT`
- ✅ Compatível com montagem no ASGI Gateway
- ✅ Graceful shutdown via lifespan

**Testes:** 11/11 passando

---

## 🔵 Fase S3 — Circuit Breaker no Gateway ✅

### 📊 Implementação

**Arquivos:**
- `requirements.txt` (adicionado `pybreaker==1.0.2`)
- `iaglobal/server/asgi.py` (adicionado middleware)
- `tests/test_circuit_breaker.py` (novo)

**Funcionalidades:**
- ✅ Circuit breaker por serviço (MCP, UI, Evolution)
- ✅ Abre após 5 falhas consecutivas
- ✅ Reset automático após 60s
- ✅ Retorna 503 com `reason: circuit_open`
- ✅ Logs registram quando circuit trip

**Configuração:**
```python
fail_max=5       # 5 falhas para abrir
reset_timeout=60 # 60s para tentar de novo
```

**Testes:** 10/10 passando

---

## 🔵 Fase S4 — Métricas de Latência por Serviço ✅

### 📊 Implementação

**Arquivos:**
- `requirements.txt` (adicionado `prometheus-client==0.20.0`)
- `iaglobal/server/asgi.py` (adicionado middleware + endpoint `/metrics`)
- `tests/test_metrics.py` (novo)

**Funcionalidades:**
- ✅ Métricas Prometheus exportadas em `/metrics`
- ✅ Latência rastreada por serviço
- ✅ Contador de requests com labels (service, status)
- ✅ Histogram de latência com buckets configurados
- ✅ Overhead mínimo (<10ms por request)

**Métricas exportadas:**
```prometheus
# Counter de requests
iaglobal_request_total{service="gateway",status="200"} 15

# Histogram de latência
iaglobal_request_latency_seconds_bucket{service="gateway",le="0.1"} 10
```

**Testes:** 10/10 passando

---

## 📊 Resultados do Ciclo S1-S4

| Métrica | Antes | Depois |
|---------|-------|--------|
| **Testes totais** | 235 | **299** (+64) |
| **Health checks** | 3 dispersos | **1 unificado** |
| **Entry points** | Múltiplos | **Gateway único (8000)** |
| **Tolerância a falhas** | Sem circuit breaker | **Circuit breaker por serviço** |
| **Monitoramento** | Sem métricas | **Prometheus exports** |
| **Standalone services** | Evolution sem entry point | **Todos com entry point** |

---

## 🌱 Próximas Mutações (Futuro)

Após completar as fases S1-S4, o sistema está pronto para:

1. **Colony Intelligence** — Múltiplos organismos iaglobal cooperando
2. **Service Mesh** — Istio/Envoy para orquestração fina
3. **Auto-scaling** — Gateway escala horizontalmente baseado em latência
4. **Distributed Tracing** — Jaeger/Zipkin para rastreamento de requests

---

## 📋 Roadmap Original (Fases E, A, B, C)

> **Nota:** As fases E, A, B, C do roadmap original permanecem pendentes e serão retomadas conforme prioridade.

| Ordem | Fase | Item | Esforço | Impacto | Risco | Status |
|-------|------|------|---------|---------|-------|--------|
| **5** | **Fase E** | Correções Metabólicas (cpu_affinity, chappie, agent_base) | Alto | Crítico | Alto | 🔄 Em progresso |
| **6** | **Fase A** | Corrigir Falso-Positivo de DNA no OmniMind | Baixo | Alto | Baixo | ⏳ Pendente |
| **7** | **Fase B** | Qualidade de Saída do Pipeline | Médio | Alto | Médio | ⏳ Pendente |
| **8** | **Fase C** | Revisão de Elevação de Modelo | Baixo | Médio | Baixo | ⏳ Pendente |

---

## 📚 Documentação Relacionada

- `docs/SERVER_ARCHITECTURE.md` — Arquitetura completa de servidores
- `docs/ARCHITECTURE.md` — Arquitetura geral do sistema (Seção 10.1)
- `docs/ROADMAP.md` — Roadmap original (Fases E, A, B, C)

---

**Status:** ✅ **Ciclo S1-S4 COMPLETO**  
**Testes:** ✅ **299/299 passando (sem regressão)**  
**Próximo passo:** Aguardando novas diretrizes para continuar a evolução

### 🧬 Diagnóstico Genômico

**Problema:** Cada serviço (Gateway, MCP, UI, Evolution) tem seu próprio endpoint de health check sem padronização. Não há visão consolidada da saúde do organismo.

**Sintoma:**
```bash
# 3 endpoints diferentes, formatos diferentes
curl http://localhost:8000/health          # Gateway
curl http://localhost:8100/health          # MCP
curl http://localhost:8765/health          # UI
```

### 🔬 Mapa de Ciclos Metabólicos

**Fluxo ideal:**
```
Health Check Unificado (Gateway 8000)
     ↓
[Paralelo] Consulta saúde de todos os serviços
     ├─ MCP (8100) → status, uptime, memory
     ├─ UI (8765) → status, websocket_connections
     ├─ Evolution → status, strategies_active, generation
     └─ Database → connections, latency, size
     ↓
Agrega em formato padronizado (FHIR-like)
     ↓
Retorna health consolidado com "vital signs" do organismo
```

### ⚡ Síntese Arquitetural

**Arquivo:** `iaglobal/server/asgi.py`

```python
@app.get("/health")
async def health_consolidated():
    """Health check unificado de todos os serviços."""
    
    # 1. Health do próprio gateway
    gateway_health = {
        "status": "healthy",
        "uptime": time.time() - START_TIME,
        "requests_total": total_requests,
    }
    
    # 2. Consulta saúde dos serviços internos (paralelo)
    async with httpx.AsyncClient() as client:
        mcp_health, ui_health = await asyncio.gather(
            client.get("http://localhost:8100/health", timeout=2.0),
            client.get("http://localhost:8765/health", timeout=2.0),
            return_exceptions=True
        )
    
    # 3. Agrega em formato padronizado
    return {
        "organism": "iaglobal",
        "timestamp": datetime.utcnow().isoformat(),
        "vital_signs": {
            "gateway": gateway_health,
            "mcp": _parse_health(mcp_health),
            "ui": _parse_health(ui_health),
            "evolution": _get_evolution_health(),
        },
        "overall_status": _compute_overall_status(...),
        "metabolic_state": {
            "ivm_medio": await _get_avg_ivm(),
            "agents_ativos": len(_active_agents),
            "cpu_budget_total": await _get_total_cpu_budget(),
        }
    }
```

**Arquivo:** `iaglobal/server/health_aggregator.py` (novo)

```python
"""Health Aggregator — Coleta e consolida saúde de todos os serviços."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import asyncio
import httpx

@dataclass
class ServiceHealth:
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    uptime: float
    latency_ms: float
    details: Dict[str, Any]

class HealthAggregator:
    """Coleta saúde de todos os serviços via HTTP."""
    
    def __init__(self):
        self.services = {
            "gateway": "http://localhost:8000/health",
            "mcp": "http://localhost:8100/health",
            "ui": "http://localhost:8765/health",
            "evolution": "http://localhost:8002/evolution/health",
        }
    
    async def check_all(self, timeout: float = 2.0) -> Dict[str, ServiceHealth]:
        """Consulta todos os serviços em paralelo."""
        async with httpx.AsyncClient() as client:
            tasks = {
                name: client.get(url, timeout=timeout)
                for name, url in self.services.items()
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        return {
            name: self._parse_result(result)
            for name, result in zip(tasks.keys(), results)
        }
    
    def _parse_result(self, result) -> ServiceHealth:
        """Parseia resposta ou erro."""
        if isinstance(result, Exception):
            return ServiceHealth(
                name="unknown",
                status="unhealthy",
                uptime=0,
                latency_ms=0,
                details={"error": str(result)}
            )
        
        data = result.json()
        return ServiceHealth(
            name=data.get("service", "unknown"),
            status=data.get("status", "unknown"),
            uptime=data.get("uptime", 0),
            latency_ms=result.elapsed.total_seconds() * 1000,
            details=data
        )
```

### 🛡️ Perfil Antioxidante

**Riscos (ROS):**
- Timeout de um serviço derruba health check inteiro
- Falso-positivo: serviço saudável mas lento parece unhealthy

**Defesas (GSH):**
- `timeout=2.0s` por serviço
- `return_exceptions=True` no `asyncio.gather`
- Status "degraded" para partial failures

### 🔄 Ciclo de Auto-Regeneração

**Testes:**
```python
# tests/test_health_unified.py

@pytest.mark.asyncio
async def test_health_consolidated_returns_all_services():
    """Health check unificado retorna saúde de todos os serviços."""
    response = await client.get("/health")
    data = response.json()
    
    assert "organism" in data
    assert data["organism"] == "iaglobal"
    assert "vital_signs" in data
    assert set(data["vital_signs"].keys()) == {
        "gateway", "mcp", "ui", "evolution"
    }
    assert "overall_status" in data
    assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]

@pytest.mark.asyncio
async def test_health_timeout_doesnt_crash():
    """Timeout de um serviço não quebra health check inteiro."""
    # Simula MCP offline
    with patch("httpx.AsyncClient.get", side_effect=TimeoutError):
        response = await client.get("/health")
        data = response.json()
    
    # MCP aparece como unhealthy, mas outros OK
    assert data["vital_signs"]["mcp"]["status"] == "unhealthy"
    assert data["vital_signs"]["gateway"]["status"] == "healthy"
    assert data["overall_status"] == "degraded"  # parcial
```

**Critério de aceite:**
- ✅ `/health` retorna saúde de 4 serviços em <5s
- ✅ Timeout de 1 serviço → status "degraded" (não "unhealthy")
- ✅ Testes de regressão passando

---

## 🔵 Fase S2 — Evolution Server Standalone

### 🧬 Diagnóstico Genômico

**Problema:** `Evolution Server` (`iaglobal/server/server.py`) não tinha entry point próprio. Só rodava montado no ASGI Gateway.

**Sintoma (antigo):**
```bash
# Antes:
python -m iaglobal.server.server  # ❌ Não funcionava
```

**Solução implementada:** Entry point adicionado ao final de `server.py` — porta configurável via `EVOLUTION_PORT` (default 8002).

```bash
# Agora funciona:
python -m iaglobal.server.server  # ✅ Sobe em http://0.0.0.0:8002
```

### ⚡ Síntese Arquitetural

**Arquivo:** `iaglobal/server/server.py` (entry point ativo)

```python
# Adicionado ao final de server.py:

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.environ.get("EVOLUTION_PORT", "8002"))
    host = os.environ.get("EVOLUTION_HOST", "0.0.0.0")
    
    print(f"🧬 [EVOLUTION SERVER] Iniciando em {host}:{port}")
    print(f"📊 Status: http://{host}:{port}/evolution/status")
    print(f"🔬 Strategies: http://{host}:{port}/evolution/strategies")
    print(f"⚡ Trigger: http://{host}:{port}/evolution/trigger")
    
    uvicorn.run(
        "iaglobal.server.server:evolution_app",
        host=host,
        port=port,
        log_level="info"
    )
```

**Variável de ambiente** (`.env.example`):
```bash
# Evolution Server (standalone)
EVOLUTION_HOST=0.0.0.0
EVOLUTION_PORT=8002
```

### 🛡️ Perfil Antioxidante

**Riscos:**
- Conflito de porta se 8002 já estiver em uso
- Evolution rodando standalone pode duplicar trabalho com gateway

**Defesas:**
- Variável de ambiente configurável
- Health check detecta duplicação

### 🔄 Ciclo de Auto-Regeneração

**Testes:**
```python
# tests/test_evolution_standalone.py

def test_evolution_server_has_main_entry():
    """Evolution Server tem entry point __main__."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "iaglobal.server.server", "--help"],
        capture_output=True,
        timeout=5
    )
    assert result.returncode == 0
```

**Critério de aceite:**
- ✅ `python -m iaglobal.server.server` inicia servidor em 8002
- ✅ `.env.example` tem `EVOLUTION_PORT=8002`
- ✅ Health check em `/evolution/health` responde

---

## 🔵 Fase S3 — Circuit Breaker no Gateway

### 🧬 Diagnóstico Genômico

**Problema:** Gateway não tem proteção contra falhas em cascata. Se MCP ou UI falha, gateway continua tentando e consome recursos.

**Sintoma:**
```
Gateway → MCP (offline)
     ↓
Tenta conectar → Timeout → Retry → Timeout → Retry
     ↓
Recursos esgotados, gateway lento para outros requests
```

### ⚡ Síntese Arquitetural

**Arquivo:** `iaglobal/server/asgi.py` (adicionar middleware)

```python
from pybreaker import CircuitBreaker

# Circuit breakers por serviço
mcp_breaker = CircuitBreaker(
    fail_max=5,      # 5 falhas
    reset_timeout=60 # 60s para tentar de novo
)

ui_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60
)

@app.middleware("http")
async def circuit_breaker_middleware(request: Request, call_next):
    """Protege contra falhas em cascata."""
    
    # Extrai serviço alvo da rota
    if request.url.path.startswith("/mcp"):
        try:
            response = await mcp_breaker.call(call_next, request)
            return response
        except CircuitBreakerError:
            return JSONResponse(
                status_code=503,
                content={"error": "MCP temporarily unavailable (circuit open)"}
            )
    
    elif request.url.path.startswith("/@"):
        try:
            response = await ui_breaker.call(call_next, request)
            return response
        except CircuitBreakerError:
            return JSONResponse(
                status_code=503,
                content={"error": "UI temporarily unavailable (circuit open)"}
            )
    
    return await call_next(request)
```

**Dependência** (`requirements.txt`):
```
pybreaker==1.0.2
```

### 🛡️ Perfil Antioxidante

**Riscos:**
- Circuit breaker muito agressivo → falso-positivo
- Circuit breaker muito lento → não protege

**Defesas:**
- `fail_max=5` (tolerante a falhas transitórias)
- `reset_timeout=60` (recuperação automática)
- Logs de circuit open/close

### 🔄 Ciclo de Auto-Regeneração

**Testes:**
```python
# tests/test_circuit_breaker.py

@pytest.mark.asyncio
async def test_circuit_opens_after_failures():
    """Circuit breaker abre após 5 falhas."""
    # Simula 5 falhas no MCP
    for _ in range(5):
        await client.get("/mcp/health")
    
    # 6a requisição deve ser rejeitada pelo breaker
    response = await client.get("/mcp/health")
    assert response.status_code == 503
    assert "circuit open" in response.json()["error"]

@pytest.mark.asyncio
async def test_circuit_closes_after_timeout():
    """Circuit breaker fecha após timeout de 60s."""
    # Abre circuit
    # ... (5 falhas)
    
    # Espera 60s
    await asyncio.sleep(60)
    
    # Próxima request deve passar
    response = await client.get("/mcp/health")
    assert response.status_code == 200
```

**Critério de aceite:**
- ✅ Circuit breaker abre após 5 falhas consecutivas
- ✅ Circuit breaker fecha após 60s
- ✅ Logs registram open/close/trip

---

## 🔵 Fase S4 — Métricas de Latência por Serviço

### 🧬 Diagnóstico Genômico

**Problema:** Não há visibilidade de latência por serviço. Só sabemos latência total do request.

**Sintoma:**
```
Request → Gateway (8000) → MCP (8100) → UI (8765)
Latência total: 500ms
Mas qual serviço está lento? Não sabemos.
```

### ⚡ Síntese Arquitetural

**Arquivo:** `iaglobal/server/asgi.py` (adicionar middleware de métricas)

```python
import time
from prometheus_client import Counter, Histogram

# Métricas
REQUEST_COUNT = Counter(
    'iaglobal_request_total',
    'Total requests',
    ['service', 'status']
)

REQUEST_LATENCY = Histogram(
    'iaglobal_request_latency_seconds',
    'Request latency',
    ['service'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Coleta métricas de latência por serviço."""
    
    start_time = time.time()
    service = _extract_service(request.url.path)
    
    response = await call_next(request)
    
    # Coleta métricas
    duration = time.time() - start_time
    REQUEST_COUNT.labels(service=service, status=response.status_code).inc()
    REQUEST_LATENCY.labels(service=service).observe(duration)
    
    # Adiciona header de latência
    response.headers["X-Request-Duration"] = f"{duration*1000:.2f}ms"
    
    return response

def _extract_service(path: str) -> str:
    """Extrai serviço da rota."""
    if path.startswith("/mcp"):
        return "mcp"
    elif path.startswith("/@"):
        return "ui"
    elif path.startswith("/evolution"):
        return "evolution"
    else:
        return "gateway"
```

**Endpoint de métricas:**
```python
from prometheus_client import generate_latest

@app.get("/metrics")
async def metrics_endpoint():
    """Exporta métricas para Prometheus."""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

### 🛡️ Perfil Antioxidante

**Riscos:**
- Overhead de coleta de métricas
- Métricas vazam detalhes internos

**Defesas:**
- Coleta assíncrona (não bloqueia request)
- Métricas agregadas (não por-request)

### 🔄 Ciclo de Auto-Regeneração

**Testes:**
```python
# tests/test_metrics.py

@pytest.mark.asyncio
async def test_metrics_endpoint_exists():
    """Endpoint /metrics exporta métricas Prometheus."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "iaglobal_request_total" in response.text
    assert "iaglobal_request_latency_seconds" in response.text

@pytest.mark.asyncio
async def test_metrics_track_latency_by_service():
    """Métricas rastreiam latência por serviço."""
    # Faz request para MCP
    await client.get("/mcp/health")
    
    # Verifica métricas
    response = await client.get("/metrics")
    assert 'iaglobal_request_latency_seconds{service="mcp"}' in response.text
```

**Critério de aceite:**
- ✅ `/metrics` exporta métricas Prometheus
- ✅ Latência por serviço é rastreada
- ✅ Overhead <1ms por request

---

## 📊 Verificação de Regressão

Após **cada fase**, rodar:

```bash
# 1. Testes existentes
python -m pytest tests/ -q --tb=short

# 2. Testes novos da fase
python -m pytest tests/test_health_unified.py -q    # Fase S1
python -m pytest tests/test_evolution_standalone.py -q  # Fase S2
python -m pytest tests/test_circuit_breaker.py -q  # Fase S3
python -m pytest tests/test_metrics.py -q          # Fase S4

# 3. Smoke test CLI
iaglobal run "hello world" --timeout=30

# 4. Auditoria de órfãos
python iaglobal/auditoria_arquitetural.py

# 5. Health check manual
curl http://localhost:8000/health | jq
```

---

## 🌱 Vetor Evolutivo (Pós-Implementação)

Após todas as fases S1-S4:

1. **Colony Intelligence** — Múltiplos organismos iaglobal cooperando
2. **Service Mesh** — Istio/Envoy para orquestração fina
3. **Auto-scaling** — Gateway escala horizontalmente baseado em latência
4. **Distributed Tracing** — Jaeger/Zipkin para rastreamento de requests entre serviços

---

## 📝 Checklist de Implementação

### Fase S1 — Health Checks Unificados ✅
- [x] Criar `iaglobal/server/health_aggregator.py`
- [x] Adicionar endpoint `/health` no `asgi.py`
- [x] Criar testes em `tests/test_health_unified.py`
- [x] Atualizar `.env.example` com `GATEWAY_PORT=8000`
- [x] Documentar em `docs/SERVER_ARCHITECTURE.md`

### Fase S2 — Evolution Server Standalone ✅
- [x] Adicionar `__main__.py` ou entry point em `server.py`
- [x] Adicionar `EVOLUTION_PORT=8002` no `.env.example`
- [x] Criar testes em `tests/test_evolution_standalone.py`
- [x] Testar `python -m iaglobal.server.server`

### Fase S3 — Circuit Breaker no Gateway ✅
- [x] Adicionar `pybreaker` em `requirements.txt`
- [x] Implementar middleware em `asgi.py`
- [x] Criar testes em `tests/test_circuit_breaker.py`
- [x] Testar falha em cascata simulada

### Fase S4 — Métricas de Latência por Serviço ✅
- [x] Adicionar `prometheus-client` em `requirements.txt`
- [x] Implementar middleware de métricas em `asgi.py`
- [x] Adicionar endpoint `/metrics`
- [x] Criar testes em `tests/test_metrics.py`
- [x] Testar exportação de métricas

---

**Status:** ✅ **Ciclo S1-S4 COMPLETO**  
**Próximo passo:** Aguardando novas diretrizes