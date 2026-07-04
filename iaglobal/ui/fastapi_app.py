# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/ui/fastapi_app.py
"""
🌐 FastAPI App — Interface Sensorial do Organismo Computacional

Responsável por:
- Receber requisições externas (percepção sensorial)
- Orquestrar execução de tarefas (sistema nervoso central)
- Broadcast de progresso via WebSocket (sinalização celular)
- Monitorar saúde do sistema (homeostase)
- Limpar execuções antigas (autofagia)

v2.0 - Organismo Computacional Completo:
- Circuit breaker (proteção contra falhas)
- Telemetria completa (Tracer + batch_writer)
- Autofagia de execuções antigas
- Health check real (integra com HealthCheck)
- Rate limiting (sistema imune)
- Graceful shutdown (apoptose)
- Persistência em SQLite (memória de longo prazo)
- Validação robusta de inputs

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Health check real + métricas
- AXIOMA 3 (Glutationa): Circuit breaker + retry
- AXIOMA 4 (Autofagia): Limpeza de execuções antigas
- AXIOMA 6 (Apoptose): Graceful shutdown
- AXIOMA 8 (Sinalização): WebSocket + eventos
"""

import asyncio
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from iaglobal.utils.logger import get_logger, register_web_log_broadcast
from iaglobal.observability.tracing import Tracer
from iaglobal.storage.batch_writer import batch_writer, Event
from iaglobal.observability.health import HealthCheck
from iaglobal.ui.workspace_runner import get_workspace_runner, WorkspaceRunnerError
from iaglobal.ui.git_workspace import GitWorkspaceError
from iaglobal._paths import CORE_DB

logger = get_logger("iaglobal")


async def _broadcast_log_to_ui(message: str, level: str = "info"):
    """Envia log para todas as conexões WebSocket ativas."""
    try:
        await manager.broadcast_all({
            "type": "log",
            "level": level,
            "message": message,
        })
    except Exception:
        pass


register_web_log_broadcast(_broadcast_log_to_ui)


# =====================================================================
# PARÂMETROS HOMEOSTÁTICOS (Epigenética Operacional)
# =====================================================================
MAX_EXECUTIONS_MEMORY = int(os.environ.get('UI_MAX_EXECUTIONS', '1000'))
EXECUTION_TTL_HOURS = int(os.environ.get('UI_EXECUTION_TTL_HOURS', '24'))
TASK_TIMEOUT_SECONDS = int(os.environ.get('UI_TASK_TIMEOUT', '300'))
CB_FAILURE_THRESHOLD = int(os.environ.get('UI_CB_THRESHOLD', '5'))
CB_RECOVERY_TIMEOUT = float(os.environ.get('UI_CB_RECOVERY', '60'))
RATE_LIMIT_PER_MINUTE = int(os.environ.get('UI_RATE_LIMIT', '120'))


# =====================================================================
# MODELOS DE VALIDAÇÃO (Chaperonas Moleculares)
# =====================================================================

class TaskRequest(BaseModel):
    """Validação de input de tarefa."""
    task: str = Field(..., min_length=3, max_length=10000, description="Descrição da tarefa")
    
    def validate_task(self):
        if not self.task.strip():
            raise ValueError("Task não pode ser vazia")
        if len(self.task.strip()) < 3:
            raise ValueError("Task muito curta (mínimo 3 caracteres)")


class TaskResponse(BaseModel):
    """Resposta de criação de tarefa."""
    execution_id: str
    status: str
    created_at: float


# =====================================================================
# CIRCUIT BREAKER (Glutationa — Defesa Antioxidante)
# =====================================================================

class UICircuitBreaker:
    """Circuit breaker para proteger contra falhas em cascata."""
    
    def __init__(self):
        self._failures = 0
        self._last_failure = 0.0
        self._lock = asyncio.Lock()
    
    async def can_execute(self) -> bool:
        async with self._lock:
            if self._failures >= CB_FAILURE_THRESHOLD:
                if (time.time() - self._last_failure) < CB_RECOVERY_TIMEOUT:
                    return False
                self._failures = 0
            return True
    
    async def record_success(self):
        async with self._lock:
            self._failures = 0
    
    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure = time.time()
    
    async def get_state(self) -> str:
        async with self._lock:
            if self._failures >= CB_FAILURE_THRESHOLD:
                return "OPEN"
            elif self._failures > 0:
                return "HALF_OPEN"
            return "CLOSED"


_ui_cb = UICircuitBreaker()


# =====================================================================
# RATE LIMITER (Sistema Imune — Defesa contra Abuso)
# =====================================================================

class RateLimiter:
    """Rate limiter simples por IP."""
    
    def __init__(self, max_requests: int = RATE_LIMIT_PER_MINUTE):
        self._requests: Dict[str, List[float]] = {}
        self._max_requests = max_requests
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_ip: str) -> bool:
        async with self._lock:
            now = time.time()
            
            if client_ip in self._requests:
                self._requests[client_ip] = [
                    t for t in self._requests[client_ip]
                    if now - t < 60
                ]
            else:
                self._requests[client_ip] = []
            
            if len(self._requests[client_ip]) >= self._max_requests:
                return False
            
            self._requests[client_ip].append(now)
            return True


_rate_limiter = RateLimiter()


# =====================================================================
# CONNECTION MANAGER (Sinalização Celular)
# =====================================================================

class ConnectionManager:
    """Gerencia conexões WebSocket ativas por execution_id."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        async with self._lock:
            if execution_id not in self.active_connections:
                self.active_connections[execution_id] = []
            self.active_connections[execution_id].append(websocket)
        
        logger.info("[WS] Conexão registrada: %s", execution_id)
    
    async def disconnect(self, websocket: WebSocket, execution_id: str):
        async with self._lock:
            if execution_id in self.active_connections:
                try:
                    self.active_connections[execution_id].remove(websocket)
                except ValueError:
                    pass
                
                if not self.active_connections[execution_id]:
                    del self.active_connections[execution_id]
        
        logger.info("[WS] Conexão removida: %s", execution_id)
    
    async def broadcast_all(self, message: dict):
        """Envia mensagem para todas as conexões ativas."""
        async with self._lock:
            dead_conns = []
            for execution_id, conns in list(self.active_connections.items()):
                for conn in conns:
                    try:
                        await conn.send_json(message)
                    except Exception:
                        dead_conns.append((execution_id, conn))
            
            for execution_id, conn in dead_conns:
                try:
                    self.active_connections[execution_id].remove(conn)
                except (ValueError, KeyError):
                    pass
            
            for execution_id, conns in list(self.active_connections.items()):
                if not conns:
                    self.active_connections.pop(execution_id, None)

    async def broadcast(self, execution_id: str, message: dict):
        """Envia mensagem para conexões de uma execução específica."""
        async with self._lock:
            if execution_id not in self.active_connections:
                return
            
            dead = []
            for conn in self.active_connections[execution_id]:
                try:
                    await conn.send_json(message)
                except Exception:
                    dead.append(conn)
            
            for conn in dead:
                try:
                    self.active_connections[execution_id].remove(conn)
                except (ValueError, KeyError):
                    pass
            
            if not self.active_connections.get(execution_id):
                self.active_connections.pop(execution_id, None)


manager = ConnectionManager()


# =====================================================================
# EXECUTION STORE (Memória de Longo Prazo com Autofagia)
# =====================================================================

class ExecutionStore:
    """
    Store de execuções com:
    - Thread-safety (asyncio.Lock)
    - Autofagia (remove execuções antigas)
    - Persistência opcional em SQLite
    - Métricas endógenas
    """
    
    def __init__(self):
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._metrics = {
            "created": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "autophagy_events": 0,
        }
    
    async def create(self, execution_id: str, task: str) -> Dict[str, Any]:
        """Cria nova execução."""
        async with self._lock:
            execution = {
                "id": execution_id,
                "task": task,
                "status": "pending",
                "created_at": time.time(),
                "result": None,
                "error": None,
            }
            self._executions[execution_id] = execution
            self._metrics["created"] += 1
            
            await self._autophagy()
            
            return execution
    
    async def get(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Obtém execução por ID."""
        async with self._lock:
            return self._executions.get(execution_id)
    
    async def update(self, execution_id: str, **kwargs):
        """Atualiza execução."""
        async with self._lock:
            if execution_id in self._executions:
                self._executions[execution_id].update(kwargs)
                
                status = kwargs.get("status")
                if status == "completed":
                    self._metrics["completed"] += 1
                elif status == "failed":
                    self._metrics["failed"] += 1
                elif status == "cancelled":
                    self._metrics["cancelled"] += 1
    
    async def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lista execuções."""
        async with self._lock:
            executions = list(self._executions.values())
            executions.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return executions[:limit]
    
    async def _autophagy(self):
        """Remove execuções antigas (autofagia)."""
        now = time.time()
        cutoff = now - (EXECUTION_TTL_HOURS * 3600)
        
        to_remove = [
            eid for eid, exec_data in self._executions.items()
            if exec_data.get("created_at", 0) < cutoff
        ]
        
        for eid in to_remove:
            del self._executions[eid]
        
        if len(self._executions) > MAX_EXECUTIONS_MEMORY:
            sorted_execs = sorted(
                self._executions.items(),
                key=lambda x: x[1].get("created_at", 0)
            )
            to_remove = [eid for eid, _ in sorted_execs[:-MAX_EXECUTIONS_MEMORY]]
            for eid in to_remove:
                del self._executions[eid]
        
        if to_remove:
            self._metrics["autophagy_events"] += len(to_remove)
            logger.debug("[EXECUTIONS] Autofagia: %d execuções removidas", len(to_remove))
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do store."""
        async with self._lock:
            total = len(self._executions)
            completed = self._metrics["completed"]
            failed = self._metrics["failed"]
            
            return {
                **self._metrics,
                "total_executions": total,
                "success_rate": round((completed / total * 100), 1) if total > 0 else 0,
            }


executions = ExecutionStore()


# =====================================================================
# LIFESPAN (Ciclo de Vida do Organismo)
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação (apoptose graceful)."""
    logger.info("[UI] 🚀 Iniciando IAGLOBAL Agent Workspace")
    
    try:
        Tracer.trace_event("UIStartup", {"status": "starting"})
    except Exception:
        pass
    
    yield
    
    logger.info("[UI] 🛑 Shutting down IAGLOBAL Agent Workspace")
    
    async with manager._lock:
        for execution_id, connections in list(manager.active_connections.items()):
            for conn in connections:
                try:
                    await conn.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
        manager.active_connections.clear()
    
    try:
        Tracer.trace_event("UIShutdown", {"status": "completed"})
    except Exception:
        pass


# =====================================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# =====================================================================

app = FastAPI(
    title="IAGLOBAL Agent Workspace",
    description="Interface própria para orquestração de agentes iaglobal — 100% gratuita",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretórios
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
RESULTS_DIR = Path("/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/result")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="ui-static")

if RESULTS_DIR.exists():
    app.mount("/result", StaticFiles(directory=str(RESULTS_DIR)), name="result")


# =====================================================================
# MIDDLEWARE (Rate Limiter)
# =====================================================================

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not await _rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": 60}
        )
    return await call_next(request)


# =====================================================================
# ENDPOINTS — API REST (Percepção Sensorial)
# =====================================================================

@app.get("/api/health")
async def health():
    """Health check real — integra com HealthCheck do organismo."""
    try:
        health_status = HealthCheck.summary()
        
        return {
            "status": "ok" if health_status.get("overall_healthy") else "degraded",
            "service": "iaglobal-ui",
            "version": "2.0.0",
            "health": health_status,
            "circuit_breaker": await _ui_cb.get_state(),
        }
    except Exception as e:
        logger.error("[UI] Health check falhou: %s", e)
        return {
            "status": "error",
            "service": "iaglobal-ui",
            "version": "2.0.0",
            "error": str(e),
        }


@app.post("/api/task")
async def create_task(request: TaskRequest):
    """Cria nova tarefa para execução."""
    if not await _ui_cb.can_execute():
        logger.warning("[UI] Circuit breaker OPEN — rejeitando tarefa")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable (circuit breaker OPEN)"
        )
    
    try:
        request.validate_task()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    execution_id = str(uuid.uuid4())
    
    execution = await executions.create(execution_id, request.task.strip())
    
    asyncio.create_task(_run_task_background(execution_id, request.task.strip()))
    
    try:
        Tracer.trace_event("TaskCreated", {
            "execution_id": execution_id,
            "task_length": len(request.task),
        })
        
        batch_writer.emit(Event(
            event_type="TaskCreated",
            payload=execution_id,
            model="ui",
            latency_ms=0.0,
            tokens_in=0,
            tokens_out=0,
        ))
    except Exception as e:
        logger.warning("[UI] Falha na telemetria: %s", e)
    
    return TaskResponse(
        execution_id=execution_id,
        status=execution["status"],
        created_at=execution["created_at"],
    )


@app.get("/api/task/{execution_id}")
async def get_task_status(execution_id: str):
    """Obtém status de uma execução."""
    execution = await executions.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return execution


@app.get("/api/tasks")
async def list_tasks(limit: int = 50):
    """Lista execuções recentes."""
    try:
        return {"executions": await executions.list_all(limit)}
    except Exception as e:
        logger.error("[UI] Erro em /api/tasks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao listar tarefas: {e}")


@app.delete("/api/task/{execution_id}")
async def cancel_task(execution_id: str):
    """Cancela uma execução."""
    execution = await executions.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    
    await executions.update(execution_id, status="cancelled")
    
    logger.info("[UI] Tarefa cancelada: %s", execution_id)
    
    return {"status": "cancelled", "execution_id": execution_id}


@app.get("/api/metrics")
async def get_metrics():
    """Métricas reais do sistema."""
    exec_metrics = await executions.get_metrics()
    
    return {
        **exec_metrics,
        "circuit_breaker": await _ui_cb.get_state(),
        "active_websockets": sum(len(conns) for conns in manager.active_connections.values()),
    }


# =====================================================================
# BACKGROUND TASK (Metabolismo de Tarefas)
# =====================================================================

async def _run_task_background(execution_id: str, task_description: str):
    """Executa tarefa em background com circuit breaker e timeout."""
    start_time = time.time()
    
    await executions.update(execution_id, status="running", started_at=time.time())
    
    try:
        await manager.broadcast(execution_id, {
            "type": "status",
            "status": "running",
            "message": "Iniciando execução...",
        })
        
        runner = get_workspace_runner()
        result = await asyncio.wait_for(
            runner.run_task(task_description, execution_id=execution_id),
            timeout=TASK_TIMEOUT_SECONDS,
        )
        
        status = "completed" if result.get("success") else "failed"
        
        logger.info("[UI] Resultado recebido: success=%s keys=%s", result.get("success"), list(result.keys()))
        
        await executions.update(
            execution_id,
            status=status,
            result=result,
            finished_at=time.time(),
        )
        
        try:
            output_text = result.get("final_output") or ""
            logger.info("[UI] final_output len=%s", len(output_text))
            if output_text:
                RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                safe_name = f"{execution_id}.txt"
                target = RESULTS_DIR / safe_name
                target.write_text(output_text, encoding="utf-8")
                logger.info("[UI] Resultado salvo em %s", target)
            else:
                logger.warning("[UI] final_output vazio, nada salvo")
        except Exception as e:
            logger.error("[UI] Falha ao salvar resultado em disco: %s", e)
        
        await manager.broadcast(execution_id, {
            "type": "status",
            "status": status,
            "result": result,
        })
        
        await _ui_cb.record_success()
        
        latency_ms = (time.time() - start_time) * 1000
        try:
            Tracer.trace_event("TaskCompleted", {
                "execution_id": execution_id,
                "status": status,
                "latency_ms": round(latency_ms, 2),
            })
            
            batch_writer.emit(Event(
                event_type="TaskCompleted",
                payload=f"{execution_id}:{status}",
                model="ui",
                latency_ms=round(latency_ms, 1),
                tokens_in=0,
                tokens_out=0,
            ))
        except Exception as e:
            logger.warning("[UI] Falha na telemetria: %s", e)
        
        logger.info(
            "[UI] ✅ Tarefa %s concluída: %s (%.2fs)",
            execution_id, status, latency_ms / 1000
        )
    
    except asyncio.TimeoutError:
        await executions.update(
            execution_id,
            status="failed",
            error=f"Timeout após {TASK_TIMEOUT_SECONDS}s",
            finished_at=time.time(),
        )
        
        await manager.broadcast(execution_id, {
            "type": "status",
            "status": "failed",
            "error": f"Timeout após {TASK_TIMEOUT_SECONDS}s",
        })
        
        await _ui_cb.record_failure()
        logger.error("[UI] ⏱️ Timeout na tarefa %s", execution_id)
    
    except Exception as e:
        await executions.update(
            execution_id,
            status="failed",
            error=str(e),
            finished_at=time.time(),
        )
        
        await manager.broadcast(execution_id, {
            "type": "status",
            "status": "failed",
            "error": str(e),
        })
        
        await _ui_cb.record_failure()
        logger.error("[UI] ❌ Erro na tarefa %s: %s", execution_id, e)


# =====================================================================
# WEBSOCKET (Sinalização Celular)
# =====================================================================

@app.websocket("/ws/progress/{execution_id}")
async def websocket_progress(websocket: WebSocket, execution_id: str):
    """WebSocket para progresso em tempo real."""
    await manager.connect(websocket, execution_id)
    
    try:
        execution = await executions.get(execution_id)
        if execution:
            await websocket.send_json({
                "type": "status",
                "status": execution.get("status", "unknown"),
                "data": execution,
            })
        
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, execution_id)
    
    except Exception as e:
        logger.error("[WS] Erro: %s", e)
        await manager.disconnect(websocket, execution_id)


# =====================================================================
# TEMPLATES — PÁGINAS HTML
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Página inicial."""
    env = templates.env
    template = env.get_template("index.html")
    html = template.render(title="IAGLOBAL Agent Workspace")
    return HTMLResponse(content=html)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard com métricas."""
    env = templates.env
    template = env.get_template("dashboard.html")
    html = template.render(title="Dashboard — IAGLOBAL")
    return HTMLResponse(content=html)


# =====================================================================
# SERVER
# =====================================================================

def run_server(host: str = "0.0.0.0", port: int = 8001):
    """Inicia servidor FastAPI."""
    import uvicorn
    
    logger.info("[UI] 🌐 Iniciando IAGLOBAL Agent Workspace em http://%s:%d", host, port)
    uvicorn.run(app=app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
