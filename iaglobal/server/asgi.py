# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ASGI application para IAGLOBAL (modo produção - sem reload).
Servidor MCP + FastAPI otimizado para integração com OpenCode.

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Health check unificado do organismo
- AXIOMA 3 (Glutationa): Circuit breaker para proteção contra falhas em cascata
- AXIOMA 8 (Sinalização): Broadcast de saúde via HTTP
"""

import asyncio
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.types import Scope, Receive, Send
import pybreaker
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from iaglobal.mcp.server import get_app as get_mcp_app
from iaglobal.server.health_aggregator import health_aggregator
from iaglobal.core.mitochondrial_probe import mitochondrial_probe

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.server.asgi")

# Variáveis globais de estado
START_TIME = time.time()
total_requests = 0

# Iniciar MitochondrialProbe como task de background
try:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # Sem event loop atual (ambiente de import)
        loop = None

    if loop and loop.is_running():
        mitochondrial_probe.start_background_task(loop)
        logger.info("[ASGI] MitochondrialProbe iniciada no bootstrap")
except Exception as e:
    logger.warning("[ASGI] Falha ao iniciar MitochondrialProbe no bootstrap: %s", e)

# Circuit breakers por serviço (proteção contra falhas em cascata)
# Configuração: falha_max=5, reset_timeout=60s
mcp_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60, name="mcp_service")

ui_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60, name="ui_service")

evolution_breaker = pybreaker.CircuitBreaker(
    fail_max=5, reset_timeout=60, name="evolution_service"
)

# Métricas Prometheus por serviço
REQUEST_COUNT = Counter(
    "iaglobal_request_total", "Total requests", ["service", "status"]
)

REQUEST_LATENCY = Histogram(
    "iaglobal_request_latency_seconds",
    "Request latency",
    ["service"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Criar aplicação FastAPI base
app = FastAPI(title="IAGlobal MCP + API", version="0.1.0")

# Montar MCP Server unificado na rota /mcp
app.mount("/mcp", get_mcp_app())


# Middleware para contar requests
@app.middleware("http")
async def count_requests(request, call_next):
    global total_requests
    total_requests += 1
    return await call_next(request)


@app.middleware("http")
async def circuit_breaker_middleware(request: Request, call_next):
    """
    Protege contra falhas em cascata usando circuit breakers por serviço.

    Se um serviço falha 5 vezes em 60s, o circuit abre e retorna 503 imediatamente
    sem tentar conectar, até o timeout de reset (60s).
    """
    path = request.url.path

    # Determina qual serviço está sendo acessado
    if path.startswith("/mcp"):
        try:
            return await mcp_breaker.call(call_next, request)
        except pybreaker.CircuitBreakerError:
            logger.warning("[CIRCUIT_BREAKER] MCP circuit open - rejeitando request")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "MCP temporarily unavailable",
                    "reason": "circuit_open",
                    "retry_after": 60,
                },
            )
        except Exception as e:
            logger.exception("[CIRCUIT_BREAKER] MCP error: %s", e)
            raise

    elif path.startswith("/@"):
        try:
            return await ui_breaker.call(call_next, request)
        except pybreaker.CircuitBreakerError:
            logger.warning("[CIRCUIT_BREAKER] UI circuit open - rejeitando request")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "UI temporarily unavailable",
                    "reason": "circuit_open",
                    "retry_after": 60,
                },
            )
        except Exception as e:
            logger.exception("[CIRCUIT_BREAKER] UI error: %s", e)
            raise

    elif path.startswith("/evolution"):
        try:
            return await evolution_breaker.call(call_next, request)
        except pybreaker.CircuitBreakerError:
            logger.warning(
                "[CIRCUIT_BREAKER] Evolution circuit open - rejeitando request"
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Evolution temporarily unavailable",
                    "reason": "circuit_open",
                    "retry_after": 60,
                },
            )
        except Exception as e:
            logger.exception("[CIRCUIT_BREAKER] Evolution error: %s", e)
            raise

    # Gateway e outros serviços não têm circuit breaker
    return await call_next(request)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    Coleta métricas de latência por serviço para Prometheus.

    Exporta:
    - iaglobal_request_total{service, status}
    - iaglobal_request_latency_seconds{service}
    """
    start_time = time.time()
    service = _extract_service(request.url.path)

    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception as e:
        status = 500
        raise
    finally:
        # Coleta métricas
        duration = time.time() - start_time
        REQUEST_COUNT.labels(service=service, status=status).inc()
        REQUEST_LATENCY.labels(service=service).observe(duration)

        # Adiciona header de latência
        # Nota: headers já foram enviados, então usamos background task ou response manipulation
        # Para simplificar, apenas coletamos as métricas


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


@app.get("/metrics")
async def metrics_endpoint():
    """
    Exporta métricas para Prometheus.

    Formato: Prometheus text exposition format
    Content-Type: text/plain; version=0.0.4

    Exemplo de scrape no Prometheus:
      scrape_configs:
        - job_name: 'iaglobal'
          static_configs:
            - targets: ['localhost:8000']
          metrics_path: '/metrics'
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Endpoint de root
@app.get("/")
async def root():
    return {
        "service": "iaglobal",
        "endpoints": {
            "/": "Bem-vindo ao MCP",
            "/health": "Health check unificado do organismo",
            "/mcp/health": "Health check do MCP",
            "/mcp/audit": "Auditoria metabólica",
            "/mcp/fix": "Acionar correção",
            "/mcp/jsonrpc": "JSON-RPC endpoint",
            "/@/": "UI ReactPy Dashboard",
            "/result/": "Resultados",
        },
    }


@app.get("/health")
async def health_consolidated():
    """
    Health check unificado de todos os serviços iaglobal.

    Retorna saúde consolidada do organismo:
    - gateway, mcp, ui, evolution
    - Estado metabólico (IVM, agentes)
    - Estado de CPU (budgets)
    - Status geral (healthy/degraded/unhealthy)
    """
    start = time.time()

    # 1. Health do próprio gateway
    gateway_health = {
        "status": "healthy",
        "uptime": time.time() - START_TIME,
        "requests_total": total_requests,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 2. Consulta saúde dos serviços internos (paralelo)
    health_map = await health_aggregator.check_all()

    # 3. Coleta estado metabólico
    metabolic_state = await health_aggregator.get_metabolic_state()
    cpu_state = await health_aggregator.get_cpu_state()
    immune_state = await health_aggregator.get_immune_state()

    # 4. Calcula status geral
    overall_status = health_aggregator.compute_overall_status(health_map)

    # 5. Monta resposta consolidada
    elapsed = (time.time() - start) * 1000

    response = {
        "organism": "iaglobal",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "response_time_ms": round(elapsed, 2),
        "vital_signs": {
            "gateway": gateway_health,
            **{
                name: health._asdict()
                if hasattr(health, "_asdict")
                else health.__dict__
                for name, health in health_map.items()
            },
        },
        "metabolic_state": metabolic_state,
        "cpu_state": cpu_state,
        "immune_state": immune_state,
    }

    logger.info(
        "[HEALTH] Check consolidado | status=%s | services=%d | time=%.0fms",
        overall_status,
        len(health_map),
        elapsed,
    )

    return response


# ASGI app
async def asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
    await app(scope, receive, send)


application = asgi_app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "iaglobal.server.asgi:application",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,
    )
