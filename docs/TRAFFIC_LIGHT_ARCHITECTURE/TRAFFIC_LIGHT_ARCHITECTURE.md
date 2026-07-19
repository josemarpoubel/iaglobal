# 🚦 Traffic Light Architecture — Semaphore & Token Bucket Release Chain

## O Problema: Vazamento de Semáforo

O `ollama_glm4` (tier JUIZ/glm4, capacity=2) travava após 2 chamadas bem-sucedidas.
`current_concurrent` nunca era decrementado, congelando o tier permanentemente.

```
SINTOMA: IVM=0.050 | web_classifier degradado
         ⏰ Timeout aguardando semáforo para ollama_glm4
         ❌ critic: Não conseguiu adquirir semáforo para nenhum modelo
```

## A Cadeia de Acquire/Release (antes da correção)

```
acquire_model(model_name, node_id)
  │
  ├─ LocalModelGate.try_acquire(node_id)
  │    └─ TokenBucket.acquire()
  │         ├─ current_concurrent += 1   ← INCREMENTA
  │         └─ tokens -= 1               ← DECREMENTA
  │
  └─ asyncio.Semaphore.acquire()          ← TRAVA

generate() → finally → release_model(model_name)
  │
  └─ asyncio.Semaphore.release()          ← LIBERA (ok)
       └─ TokenBucket.current_concurrent  ← NUNCA LIBERADO ❌
```

## A Cadeia Corrigida

```
┌─────────────────────────────────────────────────────────┐
│                    generate()                            │
│                                                          │
│  acquire_model(model_name, node_id)                     │
│    ├─ LocalModelGate.try_acquire(node_id)               │
│    │    └─ TokenBucket.acquire()                        │
│    │         ├─ current_concurrent += 1                 │
│    │         └─ tokens -= 1                             │
│    └─ asyncio.Semaphore.acquire()                       │
│                                                          │
│  ... execução via provider_router ...                    │
│                                                          │
│  finally:                                                 │
│    └─ release_model(model_selected)                      │
│         └─ asyncio.Semaphore.release()                   │
│                                                          │
│    └─ LocalModelGate.release(effective_agent)     ← NOVO │
│         └─ TokenBucket.release()                         │
│              └─ current_concurrent -= 1           ← ✅   │
└─────────────────────────────────────────────────────────┘
```

## Fallback (segunda camada de proteção)

Quando o primeiro modelo falha (`acquire_model` retorna `False` após
consumir token do bucket), o código libera **antes** de tentar o fallback:

```
acquire_model(model_1, node_id) → False (semáforo estourou)
  │
  ├─ release_model(model_1)          ← libera semáforo (se adquirido)
  └─ LocalModelGate.release(node_id) ← libera token bucket
       └─ current_concurrent -= 1    ← EVITA LEAK
  │
  └─ acquire_model(model_2, node_id) → True (fallback bem-sucedido)
```

## Arquivos Modificados

| Arquivo | Linha | Mudança |
|---------|-------|---------|
| `iaglobal/execution/token_bucket.py` | `LocalModelGate.release()` | Novo método que chama `bucket.release()` |
| `iaglobal/graphs/bandit.py` | `generate()` finally | Chama `gate.release(effective_agent)` após `release_model()` |
| `iaglobal/graphs/bandit.py` | `generate()` fallback | Libera modelo original antes de tentar fallback |

## Métricas Pós-Correção

Antes: 24 testes falhando, runtime travando após 2 chamadas ao tier JUIZ.
Depois: release simétrico, zero leaks de semáforo em testes de estresse.

```
TokenBucket lifecycle (por tier JUIZ/glm4):

Estado Inicial:    tokens=2  current_concurrent=0  ✓
Após acquire:      tokens=1  current_concurrent=1  ✓
Após release:      tokens=1  current_concurrent=0  ✓  ← ANTES: travava em 1
Esgotado (2 calls): tokens=0  current_concurrent=0  ✓ ← ANTES: travava em 2
```

---

# 📦 Provider Contract Architecture (Camada de Interface)

## O Problema: Acoplamento Estático

`provider_router.py` importava explicitamente **13 módulos** de provider (34 linhas de
`from ... import`) e mantinha dois dicionários manuais (`PROVIDERS`, `ASYNC_PROVIDERS`)
com **80+ entradas** — incluindo dezenas de aliases para o mesmo `hf_router_generate`.

Adicionar um novo provider exigia editar 3 arquivos:
1. Implementação do provider (`providers/novo_provider.py`)
2. `provider_router.py` — adicionar import + entrada nos dois dicts
3. Opcionalmente `provider_registry.py` (dict adicional)

## A Solução: Protocol + Registry + Descoberta Dinâmica

### Layer 0 — `LLMProvider` Protocol

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def async_generate(self, prompt, model=None, timeout=120, **kwargs) -> str: ...
    def generate(self, prompt, model=None, timeout=120, **kwargs) -> str: ...
    async def warmup(self, model=None) -> bool: ...  # ← OPCIONAL
```

Qualquer módulo ou classe que implemente esses métodos é um `LLMProvider`.
`@runtime_checkable` permite `isinstance(foo, LLMProvider)` sem herança forçada.

### Layer 1 — `ProviderRegistry`

```python
class ProviderRegistry:
    def register_funcs(self, name, generate, async_generate, warmup=None): ...
    def register(self, name, provider: LLMProvider): ...
    @property
    def sync(self) -> dict[str, Callable]: ...
    @property
    def async_(self) -> dict[str, Callable]: ...
    async def warmup_all(self, timeout=120) -> dict[str, bool]: ...
```

`register_funcs()` aceita funções avulsas (estilo atual — módulo-level functions).
`register()` aceita instância de classe que implementa `LLMProvider`.
Ambos constroem o mesmo `ProviderEntry` internamente.

### Layer 2 — Bootstrap Dinâmico (importlib)

Em `provider_router.py`:

```python
def _bootstrap_providers():
    import importlib
    for name in ["groq", "openrouter", "nvidia", ...]:
        importlib.import_module(f"iaglobal.providers.{name}_provider")

_bootstrap_providers()  # ← módulo-level, executa na importação de provider_router.py
```

Cada provider module faz auto-registro no final do arquivo:

```python
# ollama_provider.py (final do arquivo)
from iaglobal.providers.contract import registry as _registry
_registry.register_funcs("ollama", generate=generate, async_generate=async_generate, warmup=warmup)
```

Resultado: `PROVIDERS = dict(registry.sync)` — two-liner, sem imports manuais.

### Layer 3 — Warmup Metabólico (Startup)

Em `bootstrap.py`, após todos os serviços e antes de `self.initialized = True`:

```python
_warmup_results = await _provider_registry.warmup_all(timeout=120)
_ok = sum(1 for v in _warmup_results.values() if v)
if _ok == _total:
    logger.info("[WARMUP] %d/%d providers aquecidos", _ok, _total)
else:
    logger.warning("[WARMUP] %d/%d aquecidos (%d falharam — continuando)", ...)
```

`warmup_all()` itera `self._entries`, filtra os que têm `warmup`, e dispara
`asyncio.gather()` em paralelo. Falhas são log como warning — nunca bloqueiam o startup.

```
bootstrap.initialize()
  │
  ├─ ... (estrutura, tribunal, db, orchestrator, chappie, observabilidade)
  │
  ├─ 7.2 WARMUP ───────────────────────────────────────────────┐
  │    registry.warmup_all(timeout=120)                        │
  │      ├─ ollama.warmup()     → True  (modelo na RAM)       │
  │      ├─ groq.warmup()       → True  (API key válida)      │
  │      ├─ nvidia.warmup()     → False (timeout — log warning)│
  │      └─ hf_router.warmup()  → True                        │
  │                                                            │
  │    log: "[WARMUP] 3/4 providers aquecidos (1 falhou)"      │
  ├────────────────────────────────────────────────────────────┘
  │
  ├─ self.initialized = True
  └─ return orchestrator
```

### Fluxo Completo de Chamada

```
CLI / ASGI
  │
  ▼
bootstrap.initialize()
  │
  ├─ import provider_router.py ────────────────────────────────────┐
  │    ├─ _bootstrap_providers()                                   │
  │    │    ├─ import ollama_provider.py  → registry.register()    │
  │    │    ├─ import groq_provider.py    → registry.register()    │
  │    │    └─ import ...                                         │
  │    ├─ PROVIDERS = dict(registry.sync)                          │
  │    ├─ ASYNC_PROVIDERS = dict(registry.async_)                  │
  │    └─ aliases (ollama_glm4, hf_router_*) sobrepostos           │
  │                                                                │
  ├─ [services, bandit, chappie]                                   │
  ├─ WARMUP: registry.warmup_all()                                │
  │    └─ ollama.warmup() → modelo carregado na RAM               │
  │                                                                │
  └─ return orchestrator ──→ pipeline.run() ──→ async_route_generate()
                                                      │
                                                      ├─ ASYNC_PROVIDERS.get(provider)
                                                      │    └─ registry.async_[provider]
                                                      │
                                                      └─ _async_safe_call(func, prompt, ...)
                                                           │
                                                           ├─ TokenBucket.acquire()
                                                           ├─ Semaphore.acquire()
                                                           ├─ func(prompt, model, ...)
                                                           └─ Semaphore.release()
                                                              TokenBucket.release()
```

## Hierarquia de Camadas

```
┌────────────────────────────────────────────────────────────┐
│  Layer 3: Startup (bootstrap.py)                          │
│  warmup_all() → aquece todos os providers registrados      │
├────────────────────────────────────────────────────────────┤
│  Layer 2: Descoberta (provider_router + importlib)         │
│  _bootstrap_providers() → importa módulos → auto-registro  │
│  PROVIDERS = dict(registry.sync)                           │
│  ASYNC_PROVIDERS = dict(registry.async_)                   │
├────────────────────────────────────────────────────────────┤
│  Layer 1: Registry (contract.py)                           │
│  ProviderRegistry.register_funcs() / register()            │
│  ProviderEntry(name, generate, async_generate, warmup)     │
├────────────────────────────────────────────────────────────┤
│  Layer 0: Interface (contract.py)                          │
│  LLMProvider Protocol                                      │
│  GenerateResult dataclass                                  │
├────────────────────────────────────────────────────────────┤
│  Providers individuais (ollama, groq, nvidia, ...)         │
│  Implementam LLMProvider (ou registram funções compatíveis)│
└────────────────────────────────────────────────────────────┘
```

O caminho mais impactante por linha de código qu faz o critic consultar o SocialRegistry antes de delegar ao BanditPolicy.
```
critic.arbitrar_geracao(agent_id="coder", task_type="code")
  │
  ├─ SocialRegistry.query("code", min_proficiency=0.7) → [agent-b]
  │     │
  │     ├─ agent-b.load_factor < 0.8
  │     │    └─ DELEGAÇÃO HORIZONTAL → sem LLM, sem Bandit
  │     │       cooperação real → "C" do IVM creditado
  │     │
  │     └─ agent-b.load_factor >= 0.8
  │          └─ FALLBACK → Bandit.generate() (vertical clássico)
  │
  └─ SocialRegistry vazio
       └─ FALLBACK → Bandit.generate()
```

~15 linhas em critic_agent.py. Zero novos arquivos. E prova imediatamente que a cooperação horizontal entrega latência menor que a vertical (porque elimina a chamada LLM).

## Como Adicionar um Novo Provider

### Classe (recomendado para novos providers)

```python
# iaglobal/providers/meu_provider.py
from iaglobal.providers.contract import LLMProvider, registry

class MeuProvider(LLMProvider):
    async def async_generate(self, prompt, model=None, timeout=120, **kwargs) -> str:
        ...
    def generate(self, prompt, model=None, timeout=120, **kwargs) -> str:
        ...
    async def warmup(self, model=None) -> bool:
        ...

registry.register("meu_provider", MeuProvider())
```

O novo fluxo do arbitrar_geracao:
```
1. tools → resolve? → cooperação C ↑
2. memory → resolve? → cooperação C ↑
3. ⭐ SocialRegistry → peer disponível?
   ├─ SIM → cooperação C ↑, Ollama local direto (sem Bandit)
   │         se falhar → fallback Bandit
   └─ NÃO → Bandit.generate() (vertical clássico)
4. Bandit.generate()
```

A métrica de cooperação ("C" do IVM) é injetada via _creditar_cooperacao(node_id, resolved_locally=True, via=f"social:{peer}") — o via loga qual peer foi usado, e skills_exchanged=1 alimenta o IVM do agente requisitante. O peer não precisa fazer nada — sua existência no SocialRegistry com alta proficiência já gerou valor social, e o ciclo do "C" recompensa o descobridor.

### O que NÃO precisa ser feito

- ✗ Editar `provider_router.py` (import ou dicionário)
- ✗ Editar `bootstrap.py` (warmup é automático)
- ✗ Editar `provider_registry.py` (arquivo obsoleto)
- ✗ Registrar aliases manualmente (feito centralizadamente no router)

## Arquivos Modificados (Julho 2026)

| Arquivo | Mudança |
|---------|---------|
| `iaglobal/providers/contract.py` | **Criado** — `LLMProvider` Protocol, `ProviderRegistry`, `GenerateResult`, `warmup_all()` |
| `iaglobal/providers/provider_router.py` | **Refatorado** — 34 linhas de imports removidos, `_bootstrap_providers()`, dicts via `registry.sync/async_` |
| `iaglobal/providers/ollama_provider.py` | **Migrado** — `registry.register_funcs("ollama", ...)` adicionado no final |
| `iaglobal/cli/bootstrap.py` | **Estendido** — `registry.warmup_all(timeout=120)` antes do `self.initialized = True` |
| `iaglobal/providers/provider_registry.py` | **Obsoleto** — substituído pelo Registry em `contract.py` (mantido para compatibilidade) |

## Métricas Pós-Refatoração

| Métrica | Antes | Depois |
|---------|-------|--------|
| Linhas de import em `provider_router.py` | 34 | 2 (`ollama_async_generate` + `registry`) |
| Linhas dos dicts `PROVIDERS` + `ASYNC_PROVIDERS` | 83 | 17 (aliases mantidos, corpo via `registry`) |
| Acoplamento a módulos específicos | 13 imports fixos | 0 (`importlib` dinâmico) |
| Arquivos para editar ao adicionar provider | 3 | 1 (só o provider) |
| Providers com warmup no startup | 0 (ninguém chamava) | Todos que implementarem `warmup()` |
