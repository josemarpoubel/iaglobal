# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/server/server.py

"""
DEPRECATED — Servidor de Evolution legado (porta 8002).

Este servidor foi DESCONTINUADO. Suas funcionalidades foram migradas:

1. EvolutionRuntime → iaglobal/evolution/evolutionruntime.py (já existe)
2. Tools de evolução → iaglobal/mcp/server.py (tool: evolve_strategy)
3. Dashboard → iaglobal/mcp/server.py (tool: evolution_dashboard)
4. Health/Metrics → Integrado no ASGI Gateway (porta 8000)

Motivos da apoptose:
- Usa MockEvolver (código de teste em produção)
- Endpoints duplicados (/health, /metrics)
- Sem uso em produção documentado

Migre para:
    python -m iaglobal.mcp.server --mode both
    
Tools MCP disponíveis:
    - evolve_strategy: Alterna entre estratégias deep/fast
    - evolution_status: Status do motor evolutivo
    - evolution_dashboard: Dashboard ASCII/JSON
"""

import warnings
warnings.warn(
    "iaglobal/server/server.py está DEPRECADO. Use iaglobal/mcp/server.py",
    DeprecationWarning,
    stacklevel=2
)

import asyncio
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

from iaglobal.evolution.evolutionruntime import (
    EvolutionRuntime, 
    DeepEvolutionStrategy, 
    FastEvolutionStrategy,
    get_runtime
)
from iaglobal.evolution.execution_context import make_context
from iaglobal.evolution.execution_registry import registry
from iaglobal.evolution.evolution_replay import EvolutionReplay


# ------------------------------------------------------------------------------
# 1. INICIALIZAÇÃO DOS MOTORES CORE
# ------------------------------------------------------------------------------
class MockEvolver:
    """Simula o EvolutionEngine adaptado para chamadas async."""
    async def evolve_async(self, strategy) -> Dict[str, Any]:
        await asyncio.sleep(1)
        return {"strategy": strategy.__class__.__name__, "mutations_count": 2}

evolver_mock = MockEvolver()
runtime = EvolutionRuntime(evolver=evolver_mock, interval=30)
replay_engine = EvolutionReplay(engine=evolver_mock)

_start_time = time.time()
_request_count = 0
_error_count = 0
_total_latency = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida do servidor (startup/shutdown)."""
    runtime.set_strategy(FastEvolutionStrategy())
    runtime.start()
    yield
    runtime.stop()


app = FastAPI(
    title="iaglobal Autonomous Evolution Server",
    lifespan=lifespan,
)


# ------------------------------------------------------------------------------
# 2. SCHEMAS DE ENTRADA DE DADOS
# ------------------------------------------------------------------------------
class TaskRequest(BaseModel):
    execution_id: str
    task_prompt: str
    metadata: Dict[str, Any] = {}


# ------------------------------------------------------------------------------
# 3. ENDPOINTS DA API REST
# ------------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check do sistema."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "runtime_running": runtime._running if hasattr(runtime, "_running") else False,
    }


@app.get("/metrics")
async def metrics():
    """Métricas de desempenho (latência, taxa de erro, uso)."""
    global _request_count, _error_count, _total_latency
    latency_avg = round(_total_latency / max(_request_count, 1), 3)
    error_rate = round(_error_count / max(_request_count, 1), 3)
    return {
        "total_requests": _request_count,
        "total_errors": _error_count,
        "error_rate": error_rate,
        "average_latency_ms": latency_avg * 1000,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.post("/tasks/run")
async def disparar_tarefa(request: TaskRequest, background_tasks: BackgroundTasks):
    global _request_count, _total_latency
    inicio = time.time()
    _request_count += 1

    contexto = make_context(
        execution_id=request.execution_id,
        task=request.task_prompt,
        metadata=request.metadata
    )
    registry.init_execution(
        contexto.execution_id,
        node_ids=["planner", "coder", "critic", "tester"],
    )

    _total_latency += time.time() - inicio

    return {
        "status": "QUEUED",
        "message": "Agentes especializados foram convocados para a tarefa.",
        "execution_id": contexto.execution_id,
    }


@app.get("/evolution/status")
async def obter_saude_do_motor():
    return runtime.status()


@app.post("/evolution/strategy")
async def alternar_estrategia(modo: str):
    if modo == "deep":
        runtime.set_strategy(DeepEvolutionStrategy())
    elif modo == "fast":
        runtime.set_strategy(FastEvolutionStrategy())
    else:
        raise HTTPException(status_code=400, detail="Estratégia inválida. Escolha 'deep' ou 'fast'.")
    return {"status": "SUCCESS", "nova_estrategia": modo}


@app.get("/evolution/dashboard", response_model=None)
async def visualizar_dashboard_ascii(max_geracao: int = 5):
    return replay_engine.render_ascii_dashboard(max_gen=max_geracao)


@app.get("/evolution/dashboard/json")
async def dashboard_json():
    """Painel em tempo real combinando evolução, CPU, memória e métricas HTTP."""
    from iaglobal.execution.cpu_affinity import cpu_affinity
    from iaglobal._paths import PACKAGE_DIR

    obsidian_dir = PACKAGE_DIR / "obsidian"
    short_term = len(list((obsidian_dir / "02_Short_Term").glob("*.md"))) if (obsidian_dir / "02_Short_Term").exists() else 0
    long_term = len(list((obsidian_dir / "03_Long_Term").glob("*.md"))) if (obsidian_dir / "03_Long_Term").exists() else 0
    synapses = len(list((obsidian_dir / "04_Synapses").glob("*.md"))) if (obsidian_dir / "04_Synapses").exists() else 0

    cpu_report = await cpu_affinity.dispersion_report()
    evo_status = runtime.status()

    return {
        "system": {
            "uptime_seconds": round(time.time() - _start_time, 1),
            "total_requests": _request_count,
            "total_errors": _error_count,
            "error_rate": round(_error_count / max(_request_count, 1), 3),
        },
        "evolution": {
            "running": evo_status.get("running", False),
            "cycles": evo_status.get("cycles", 0),
            "failures": evo_status.get("failures", 0),
            "strategy": evo_status.get("strategy", "unknown"),
            "interval": evo_status.get("interval", 30),
        },
        "cpu": {
            "total_cores": cpu_report.get("total_cores", 0),
            "total_agents": cpu_report.get("total_agents", 0),
            "ivm_medio": cpu_report.get("ivm_medio", 0),
            "fitness_medio": cpu_report.get("fitness_medio", 0),
            "agentes_em_sobrevivencia": cpu_report.get("agentes_em_sobrevivencia", 0),
            "eficiencia": cpu_report.get("efficiency", 0),
            "imbalance": cpu_report.get("imbalance", 0),
        },
        "subconsciente": {
            "notas_curto_prazo": short_term,
            "notas_longo_prazo": long_term,
            "mapas_sinapse": synapses,
        },
    }


# =====================================================================
# SERVER ENTRYPOINT — MODO STANDALONE
# =====================================================================

if __name__ == "__main__":
    import os
    import uvicorn
    
    # Lê configuração do ambiente
    host = os.environ.get("EVOLUTION_HOST", "0.0.0.0")
    port = int(os.environ.get("EVOLUTION_PORT", "8002"))
    
    print(f"🧬 [EVOLUTION SERVER] Iniciando em {host}:{port}")
    print(f"📊 Status: http://{host}:{port}/evolution/health")
    print(f"🔬 Strategies: http://{host}:{port}/evolution/strategies")
    print(f"⚡ Trigger: http://{host}:{port}/evolution/trigger")
    print(f"📈 Metrics: http://{host}:{port}/evolution/metrics")
    print(f"💡 Dica: Para acessar via ASGI Gateway, use http://localhost:8000/evolution/")
    
    uvicorn.run(
        "iaglobal.server.server:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False
    )
