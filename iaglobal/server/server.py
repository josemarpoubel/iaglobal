# iaglobal/server/server.py

import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

# CORREÇÃO: Importando tudo a partir de evolutionruntime para centralizar o acesso
from iaglobal.evolution.evolutionruntime import (
    EvolutionRuntime, 
    DeepEvolutionStrategy, 
    FastEvolutionStrategy,
    get_runtime # Importando a função Singleton que criamos
)

from iaglobal.evolution.execution_context import make_context
from iaglobal.evolution.execution_registry import registry
from iaglobal.evolution.evolution_replay import EvolutionReplay

# Exemplo de como inicializar o runtime corretamente no servidor:
def startup_event():
    # Usando o Singleton centralizado
    runtime = get_runtime() 
    # O set_strategy agora funcionará sem erros de importação
    runtime.current_strategy = FastEvolutionStrategy()

app = FastAPI(title="🧬 iaglobal Autonomous Evolution Server")

# ------------------------------------------------------------------------------
# 1. INICIALIZAÇÃO DOS MOTORES CORE (Singletons Nativos)
# ------------------------------------------------------------------------------
class MockEvolver:
    """Simula o seu EvolutionEngine adaptado para chamadas async."""
    async def evolve_async(self, strategy) -> Dict[str, Any]:
        await asyncio.sleep(1) # Simula a LLM reescrevendo prompts
        return {"strategy": strategy.__class__.__name__, "mutations_count": 2}

evolver_mock = MockEvolver()
runtime = EvolutionRuntime(evolver=evolver_mock, interval=30)
replay_engine = EvolutionReplay(engine=evolver_mock)

@app.on_event("startup")
async def startup_event():
    """Liga o motor de evolução em background assim que o servidor liga."""
    # Começa no modo rápido por padrão
    runtime.set_strategy(FastEvolutionStrategy())
    runtime.start()
    print("🚀 [SERVIDOR] Motor de evolução assíncrono ativado com sucesso!")

@app.on_event("shutdown")
async def shutdown_event():
    """Desliga o motor de forma segura ao fechar o servidor."""
    runtime.stop()
    print("🛑 [SERVIDOR] Motor de evolução desligado.")

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

@app.post("/tasks/run")
async def disparar_tarefa(request: TaskRequest, background_tasks: BackgroundTasks):
    """
    Recebe uma tarefa do usuário e dispara o grafo de agentes em background
    sem travar a requisição HTTP.
    """
    # Cria o snapshot imutável de contexto usando a refatoração de Proxy que fizemos
    contexto = make_context(
        execution_id=request.execution_id,
        task=request.task_prompt,
        metadata=request.metadata
    )
    
    # Inicializa as barreiras de antiloop e idempotência no Registry
    registry.init_execution(contexto.execution_id, node_ids=["planner", "coder", "critic", "tester"])
    
    # Próximo passo: Aqui você chamaria o seu ExecutionGraph.run() dentro de uma background task
    # background_tasks.add_task(seu_grafo.run, contexto)
    
    return {
        "status": "QUEUED",
        "message": "Agentes especializados foram convocados para a tarefa.",
        "execution_id": contexto.execution_id
    }

@app.get("/evolution/status")
async def obter_saude_do_motor():
    """Retorna a telemetria em tempo real do metrónomo de evolução."""
    return runtime.status()

@app.post("/evolution/strategy")
async def alternar_estrategia(modo: str):
    """Altera a estratégia de evolução em tempo de execução via API (Flexibilidade)."""
    if modo == "deep":
        runtime.set_strategy(DeepEvolutionStrategy())
    elif modo == "fast":
        runtime.set_strategy(FastEvolutionStrategy())
    else:
        raise HTTPException(status_code=400, detail="Estratégia inválida. Escolha 'deep' ou 'fast'.")
    return {"status": "SUCCESS", "nova_estrategia": modo}

@app.get("/evolution/dashboard", response_model=None)
async def visualizar_dashboard_ascii(max_geracao: int = 5):
    """
    A MÁQUINA DO TEMPO: Retorna o painel analítico da evolução em texto puramente limpo.
    Você pode chamar esse endpoint no terminal usando 'curl' para ver o gráfico subindo.
    """
    dashboard_texto = replay_engine.render_ascii_dashboard(max_gen=max_geracao)
    return dashboard_texto
