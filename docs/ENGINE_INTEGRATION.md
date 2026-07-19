# ENGINE INTEGRATION — Tribunal Cognitivo & Sistema Endócrino

## Índice

1. [Arquitetura Geral](#1-arquitetura-geral)
2. [CognitiveRouter — O Córtex Pré-Frontal](#2-cognitiverouter)
3. [BucketManager — O Sistema Endócrino](#3-bucketmanager)
4. [SentinelOrchestrator — O Sentinela Paralelo](#4-sentinelorchestrator)
5. [AcetylcholineBus — Barramento de Sinalização](#5-acetylcholinebus)
6. [Integração no Pipeline](#6-integração-no-pipeline)
7. [Degradação Graciosa](#7-degradao-graciosa)
8. [Testes](#8-testes)

---

## 1. Arquitetura Geral

```
┌────────────────────────────────────────────────────────────────────────────┐
│                       TRIBUNAI COGNITIVO (3 Camadas)                       │
│                                                                            │
│  CognitiveRouter.resolve_route(node_id, task_type)                         │
│       │                                                                    │
│       ▼                                                                    │
│  ┌──────────────────┐   ┌──────────────┐   ┌──────────────────┐           │
│  │  JUIZ (GLM4)     │   │ OPERÁRIO     │   │ SENTINELA (LFM) │           │
│  │  ollama_glm4     │   │ ollama       │   │ ollama_lfm      │           │
│  │                  │   │              │   │                  │           │
│  │ critic           │   │ coder        │   │ sandbox_valid    │           │
│  │ failure_analysis │   │ multi_coder  │   │ lsp_valid        │           │
│  │ arbitrar_geracao │   │ planner      │   │ semantic_valid   │           │
│  │ system_design    │   │ pm           │   │ security_audit   │           │
│  │ req_correction   │   │ enhancement  │   │ performance_audit│           │
│  │                  │   │ doc_writer   │   │ compliance_audit │           │
│  │ max_conc=1       │   │ front/back   │   │ system_analysis  │           │
│  │ tokens/min=4096  │   │ api/db       │   │ metrics          │           │
│  │ timeout=120s     │   │ deployment   │   │ pipeline_updater │           │
│  │ fallback→operário│   │ task_break   │   │ evolution_trigger│           │
│  │                  │   │ documentação │   │ gap_analyzer     │           │
│  │                  │   │              │   │ memory_cleaner   │           │
│  │                  │   │ max_conc=3   │   │ evaluator        │           │
│  │                  │   │ tokens/min=  │   │ retrospective    │           │
│  │                  │   │ 8192         │   │                  │           │
│  │                  │   │ timeout=60s  │   │ max_conc=5       │           │
│  │                  │   │ (sem fb)     │   │ tokens/min=15000 │           │
│  │                  │   │              │   │ timeout=30s      │           │
│  └────────┬─────────┘   └──────┬───────┘   └────────┬─────────┘           │
│           │                    │                     │                     │
│           └────────┬───────────┴──────────┬──────────┘                    │
│                    │                      │                               │
│                    ▼                      ▼                               │
│        ┌──────────────────────────────────────────────┐                   │
│        │           BucketManager (Sist. Endócrino)    │                   │
│        │                                              │                   │
│        │  3 TokenBuckets independentes:                │                   │
│        │  - ollama_glm4: cap=4096, conc=1, fill=68/s  │                   │
│        │  - ollama: cap=8192, conc=3, fill=136/s      │                   │
│        │  - ollama_lfm: cap=15000, conc=5, fill=250/s │                   │
│        │                                              │                   │
│        │  acquire(route, tokens, timeout) → bool        │                   │
│        │  acquire_with_fallback(route) → route | None  │                   │
│        └──────────────────────┬───────────────────────┘                   │
│                               │                                           │
│                               ▼                                           │
│        ┌──────────────────────────────────────────────┐                   │
│        │          cognitive_dispatch()                 │                   │
│        │  (Router → Bucket → async_route_generate)    │                   │
│        └──────────────────────────────────────────────┘                   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CognitiveRouter

**Arquivo:** `iaglobal/providers/provider_router.py` (linha 91)

Mapeia a intenção da tarefa (`node_id` + `task_type`) para uma das três rotas metabólicas.

### Métodos Principais

| Método | Retorno | Descrição |
|--------|---------|-----------|
| `resolve_route(node_id, task_type)` | `str` | Nome da rota (`ollama`, `ollama_glm4`, `ollama_lfm`) |
| `resolve_model_id(route)` | `str` | `model_id` do ProviderConfig |
| `get_route_config(route)` | `dict` | Config metabólica completa |
| `build_candidates(route)` | `list[str]` | Lista [primário, fallback] para o BanditPolicy |

### Mapa de Decisão (39+ node_ids)

**JUIZ (`ollama_glm4`):** critic, failure_analysis, arbitrar_geracao, pipeline.requirement_correction, system_design

**OPERÁRIO (`ollama`):** coder, multi_coder, backend_builder, frontend_builder, database_builder, api_builder, planner, pm, requirements, technology_selection, enhancement, doc_writer, artifact_writer, knowledge_writer, deployment_plan, task_breakdown, documentation

**SENTINELA (`ollama_lfm`):** sandbox_validator, lsp_validator, semantic_validator, fix_validator, security_audit, performance_audit, compliance_audit, system_analysis, metrics, pipeline_updater, evolution_trigger, retrospective, gap_analyzer, evaluator, memory_cleaner

**Heurística (fallback):** se `task_type` contém "valid", "audit" ou "monitor" → Sentinela. Caso contrário → Operário.

### Exemplo de Uso

```python
from iaglobal.providers.provider_router import CognitiveRouter

route = CognitiveRouter.resolve_route("critic", "general")
# → "ollama_glm4"

model = CognitiveRouter.resolve_model_id(route)
# → "yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest"

candidates = CognitiveRouter.build_candidates(route)
# → ["ollama/yasserrmd/GLM4.7-Distill-LFM2.5-1.2B:latest",
#     "ollama/qwen2.5:0.5b"]  (fallback_role = OPERARIO)
```

---

## 3. BucketManager

**Arquivo:** `iaglobal/metabolism/bucket_manager.py`

Sistema Endócrino — regula a liberação de ATP (tokens) por tier cognitivo. Singleton global.

### TokenBucket

```
TokenBucket(capacity, fill_rate, max_concurrent)
  ├── capacity:    tokens máximos (ex: 4096 para JUIZ)
  ├── fill_rate:   tokens/segundo (capacity / 60)
  ├── max_concurrent: slots simultâneos
  │
  ├── acquire(estimated_tokens=100, timeout=0.0) → bool
  │     timeout=0: non-blocking (retorna False imediatamente)
  │     timeout>0: espera até N segundos por slot + tokens
  │
  ├── release() → None
  └── utilization → float (0.0=vazio, 1.0=cheio)
```

### BucketManager (Singleton)

```python
from iaglobal.metabolism.bucket_manager import BucketManager

bm = await BucketManager.get_instance()

# Acquire com timeout curto (default 0.5s para Sentinela)
ok = await bm.acquire("ollama_lfm", estimated_tokens=512, timeout=0.5)

# Acquire com fallback automático
route = await bm.acquire_with_fallback("ollama_glm4", tokens=2048, timeout=2.0)
# Tenta ollama_glm4 → se falhar, tenta ollama (fallback_role=OPERARIO)
# Retorna a rota que concedeu, ou None

# Liberar após uso
await bm.release(route)

# Status
summary = bm.summary
await bm.print_summary()
```

### Buckets por Tier

| Rota | capacity | fill_rate | max_conc | Tempo de espera |
|------|----------|-----------|----------|-----------------|
| `ollama_glm4` | 4096 | 68.3/s | 1 | 2.0s |
| `ollama` | 8192 | 136.5/s | 3 | 1.0s |
| `ollama_lfm` | 15000 | 250.0/s | 5 | 0.5s |

---

## 4. SentinelOrchestrator

**Arquivo:** `iaglobal/metabolism/sentinel.py`

Monitor paralelo não-bloqueante de artefatos. Acopla-se ao Operário via `asyncio.Future`.

### Fluxo Interno

```
monitor_task(task_id, prompt, code_future)
  │
  ├─ await code_future (com timeout de 120s)
  │     ├─ CancelledError → término gracioso
  │     └─ TimeoutError → log e retorno
  │
  ├─ _analyze_requirements(prompt, code)
  │     │
  │     ├─ FASE 1: FailureAnalysisAgent.check_requirements()
  │     │   keyword scan (zero custo de inferência)
  │     │   detecta: autenticação, login, tema escuro,
  │     │   dark mode, python, flask, fastapi, django
  │     │
  │     └─ FASE 2 (se violações encontradas):
  │         cognitive_dispatch(node_id="sentinel",
  │           prompt=LFM_CONFIRM_PROMPT, task_type="validation")
  │         LFM-230M confirma ou refuta as violações
  │         timeout de 30s; se falhar, mantém violações
  │
  └─ Se violações confirmadas:
      bus.publish(AgentMessage(
        message_type="sentinel_intervention",
        content={task_id, violations, action: "escalate_to_juiz"}
      ))
```

### Prompt do LFM (Confirmação Semântica)

```
You are a requirements compliance auditor.
Given the user request and the generated code below, check if the code
satisfies the requirements. Output only JSON:
{{"compliant": true/false, "reason": "..."}}

User request:
{request}

Generated code:
{code}
```

### Degradação

| Situação | Comportamento |
|----------|---------------|
| LFM time out (30s) | Mantém violações da Fase 1 (keyword scan) |
| LFM diz "compliant" | Descarta violações (falso positivo filtrado) |
| `CancelledError` | Término silencioso — zero impacto no pipeline |
| `code_future` nunca resolvido | Timeout de 120s → aborta monitoria |

---

## 5. AcetylcholineBus

**Arquivo:** `iaglobal/graphs/comms/acetylcholine_bus.py`

Duas camadas de comunicação:

1. **Broadcast (pub/sub):** subscribers por channel/recipient — usado para sinais globais
2. **Fila por task_id:** `consume_event(task_id)` — polling não bloqueante

### API

```python
from iaglobal.graphs.comms.acetylcholine_bus import AcetylcholineBus, AgentMessage

bus = AcetylcholineBus()

# --- Fila por task_id ---
bus.register_task("task-123")
# Durante execução: publish() enfileira automaticamente
# se content tiver chave task_id

msg = bus.consume_event("task-123", event_type="sentinel_intervention")
# → AgentMessage ou None (non-blocking)

payload = bus.consume_event_payload("task-123", "sentinel_intervention")
# → dict ou None (conveniência)

bus.unregister_task("task-123")

# --- Pub/Sub (broadcast) ---
def callback(msg: AgentMessage):
    print(msg.content)

bus.subscribe("alertas", callback)
await bus.publish(AgentMessage(sender="system", recipient="alertas",
                 message_type="warning", content={"msg": "hello"}))
```

### Arquitetura da Fila

```
register_task("task-42")
  └─ cria asyncio.Queue() em self._queues["task-42"]

publish(AgentMessage(content={"task_id": "task-42", ...}))
  ├─ emit() → _enqueue_for_task()
  │     Se content.task_id existe e está registrada:
  │       await self._queues[task_id].put(message)
  └─ broadcast para subscribers

consume_event("task-42")
  └─ queue.get_nowait() → AgentMessage ou None (zero bloqueio)

unregister_task("task-42")
  └─ self._queues.pop("task-42", None) — coleta de lixo
```

---

## 6. Integração no Pipeline

**Arquivo:** `iaglobal/pipeline/engine.py`

A integração ocorre no método `async_execute()` da classe `PipelineEngine`.

### Fluxo Completo

```
PipelineEngine.async_execute(prompt)
  │
  ├─ state = PipelineState(task_id=uuid, prompt, metadata)
  │
  ├─ _sentinel_task = None; _code_future = None; _bus = None
  │
  ├─ try:
  │     ├─ (inicialização do grafo, evolver, cache...)
  │     │
  │     ├─ [SENTINELA STARTUP]
  │     │   from iaglobal.graphs.comms.acetylcholine_bus import bus
  │     │   from iaglobal.metabolism.sentinel import SentinelOrchestrator
  │     │
  │     │   bus.register_task(state.task_id)
  │     │   _code_future = asyncio.Future()
  │     │   _sentinel_task = create_task(
  │     │       sentinel.monitor_task(state.task_id, prompt, _code_future)
  │     │   )
  │     │
  │     ├─ [GERAÇÃO]
  │     │   _async_generation_stage(state, parallel)
  │     │
  │     │   if state.generated_code and not _code_future.done():
  │     │       _code_future.set_result(state.generated_code)
  │     │
  │     ├─ [VALIDAÇÃO] _validation_stage(state)
  │     │
  │     ├─ [REQUISITOS] FailureAnalysisAgent.analyze()
  │     │   (ciclo corretivo existente via critic.arbitrar_geracao)
  │     │
  │     ├─ [ESCUTA DO CÓRTEX]
  │     │   intervention = bus.consume_event_payload(
  │     │       state.task_id, "sentinel_intervention"
  │     │   )
  │     │   if intervention:
  │     │       violações LFM-confirmadas
  │     │       se não corrigidas → escalona Juiz
  │     │
  │     ├─ [PERSISTÊNCIA] _async_persistence_stage(state)
  │     │   _async_metabolism_stage(state)
  │     │   _async_learn_stage(state)
  │     │
  │     └─ return PipelineResult(success=True, response=code)
  │
  ├─ except:
  │     cancela _sentinel_task se ativo
  │     return PipelineResult(success=False, error=...)
  │
  └─ finally:
        if _code_future and not done: _code_future.cancel()
        if _bus: _bus.unregister_task(state.task_id)
```

### Código de Integração (engine.py)

```python
# Startup — sentinela em background
from iaglobal.graphs.comms.acetylcholine_bus import bus as _acetylcholine_bus
from iaglobal.metabolism.sentinel import SentinelOrchestrator

if self._sentinel is None:
    self._sentinel = SentinelOrchestrator(_acetylcholine_bus)
_acetylcholine_bus.register_task(state.task_id)
_code_future = asyncio.Future()
_sentinel_task = asyncio.create_task(
    self._sentinel.monitor_task(state.task_id, state.prompt, _code_future)
)

# Após geração
if state.generated_code and not _code_future.done():
    _code_future.set_result(state.generated_code)

# Escuta do córtex (após requisitos)
_intervention = _acetylcholine_bus.consume_event_payload(
    state.task_id, event_type="sentinel_intervention"
)
if _intervention:
    violations = _intervention.get("violations", [])
    if violations:
        # Escalona Juiz se ainda não corrigido
        ...

# Cleanup
finally:
    if _code_future and not _code_future.done():
        _code_future.cancel()
    if _acetylcholine_bus is not None:
        _acetylcholine_bus.unregister_task(state.task_id)
```

---

## 7. Degradação Graciosa

### Matriz de Degradação

| Tier | Rota | Timeout acquire | Se exausto | Fallback |
|------|------|----------------|------------|----------|
| Juiz | `ollama_glm4` | 2.0s | Fallback → Operário | `CognitiveRole.OPERARIO` |
| Operário | `ollama` | 1.0s | Sem fallback (core) | N/A |
| Sentinela | `ollama_lfm` | 0.5s | Bypass (sem validação) | N/A |

### Cadeia de Fallback

```
cognitive_dispatch(node_id, prompt, task_type)
  │
  ├─ route = CognitiveRouter.resolve_route(node_id, task_type)
  │
  ├─ granted = BucketManager.acquire_with_fallback(route, tokens, timeout)
  │     │
  │     ├─ True  → granted == route (rota principal)
  │     ├─ False → tenta fallback_role do ProviderConfig
  │     │           Ex: ollama_glm4 exausto → tenta ollama
  │     │           ├─ True  → granted == "ollama"
  │     │           └─ False → granted == None (todos exaustos)
  │     └─ None   → retorna "" (bypass completo)
  │
  ├─ model = CognitiveRouter.resolve_model_id(granted)
  ├─ result = async_route_generate(model, prompt, ...)
  └─ finally: BucketManager.release(granted)
```

### Sentinela: Fila Curta → Bypass

Quando o Sentinela (`ollama_lfm`) está com todos os 5 slots ocupados:

1. `acquire("ollama_lfm", timeout=0.5)` tenta por 500ms
2. Se um slot liberar dentro desse tempo → validação executada
3. Se não liberar → **bypass silencioso**: o artefato segue sem validação LFM
4. O pipeline **nunca bloqueia** esperando o Sentinela

---

## 8. Testes

### Testes de Unidade

```bash
# PSC Hierarchy (10 testes — soberania do crítico)
python -m pytest iaglobal/tests/test_psc_hierarchy.py -v

# TokenBucket (bucket_manager)
python -c "
from iaglobal.metabolism.bucket_manager import BucketManager
import asyncio
bm = asyncio.run(BucketManager.get_instance())
print(bm.summary)
"

# SentinelOrchestrator
python -c "
from iaglobal.metabolism.sentinel import SentinelOrchestrator
from iaglobal.graphs.comms.acetylcholine_bus import AcetylcholineBus
bus = AcetylcholineBus()
sentinel = SentinelOrchestrator(bus)
print('SentinelOrchestrator OK')
"

# CognitiveRouter
python -c "
from iaglobal.providers.provider_router import CognitiveRouter
for node in ['critic', 'coder', 'sandbox_validator', 'unknown']:
    route = CognitiveRouter.resolve_route(node, 'general')
    print(f'{node} → {route}')
"
```

### Testes de Integração

```bash
# Pipeline completo (requer Ollama local)
iaglobal run "crie uma API com autenticação"

# Verificar barramento
python -c "
from iaglobal.graphs.comms.acetylcholine_bus import bus
history = bus.get_history()
for msg in history:
    print(f'{msg.message_type}: {msg.sender} → {msg.recipient}')
"

# Status metabólico
iaglobal status
```

### Métricas Pós-Integração

| Teste | Status |
|-------|--------|
| PSC Hierarchy | 10/10 |
| Mitochondrial Probe | 8/8 |
| Instrument Decorator | 17/17 |
| CognitiveRouter resolve | ✅ 39 node_ids mapeados |
| BucketManager acquire/release | ✅ 3 buckets operacionais |
| Sentinel LFM confirmation | ✅ Híbrido keyword+LFM |
| Bus consume_event | ✅ Zero bloqueio |

---

## Referências

| Arquivo | Linha | Componente |
|---------|-------|------------|
| `iaglobal/providers/provider_config.py` | 24 | `COGNITIVE_MODELS` — 3 tiers |
| `iaglobal/providers/provider_router.py` | 91 | `CognitiveRouter` class |
| `iaglobal/providers/provider_router.py` | 196 | `cognitive_dispatch()` function |
| `iaglobal/metabolism/bucket_manager.py` | 27 | `TokenBucket` class |
| `iaglobal/metabolism/bucket_manager.py` | 102 | `BucketManager` singleton |
| `iaglobal/metabolism/sentinel.py` | 36 | `SentinelOrchestrator` class |
| `iaglobal/graphs/comms/acetylcholine_bus.py` | 57 | `AcetylcholineBus` with per-task queues |
| `iaglobal/pipeline/engine.py` | 40 | `PipelineEngine.async_execute()` |
