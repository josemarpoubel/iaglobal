após dar o comado ...  python3 -m iaglobal.cli.main run "Teste de conexão do sistema"

deu varios erros...

onde está o problema?...

O erro não é do `GracefulShutdown`.

O erro é uma **incompatibilidade arquitetural entre Bootstrap e Orchestrator**.

---

# Diagnóstico exato

o Bootstrap cria:

```
self.orchestrator = Orchestrator(
    memory=self.memory,
    bus=self.bus
)
```



Mas o construtor atual do Orchestrator é:

```
def __init__(
    self,
    planner=None,
    evolution_interval: int = 30,
    evolution_strategies: list[str] = None,
    mutation_rate: float = 0.1,
    model_fn: Optional[callable] = None,
):
```

Não existe:

```
memory=
bus=
```

Por isso o  lança:

```text
TypeError:
Orchestrator.__init__()
got an unexpected keyword argument 'memory'
```

---

# O que aconteceu

Durante algum refactor foi movido a criação de memória e event bus para dentro do próprio Orchestrator:

```
self.bus = EventBus()

self.memory = storage

self.memory_manager = MemoryManager(...)
```

Mas esqueceu de atualizar o Bootstrap.

Hoje existem DUAS arquiteturas brigando:

### Bootstrap

quer fazer DI (Dependency Injection)

```
Orchestrator(
    memory=...,
    bus=...
)
```

---

### Orchestrator

quer criar tudo sozinho

```
self.memory = storage
self.bus = EventBus()
```

---

# Correção rápida

No bootstrap:

troque:

```
self.orchestrator = Orchestrator(
    memory=self.memory,
    bus=self.bus
)
```

por:

```
self.orchestrator = Orchestrator()
```

Provavelmente o sistema volta a subir imediatamente.

---

# Mas existe um problema maior

O seu Orchestrator está cheio de sinais de corrupção por refactor.

Exemplo:

 instancia:

```
self.credit = CreditAssignmentEngine()
self.bandit = BanditPolicy(self.credit)
```

duas vezes.



---

instancia:

```
self.evolution_runtime = EvolutionRuntime(...)
```

duas vezes.

---

importa:

```
ExecutionGraph
```

mais de uma vez.



---

possui:

```
from iaglobal.graphs import ExecutionGraph

from iaglobal.graphs.execution_graph import ExecutionGraph
```

ao mesmo tempo.



Isso é extremamente perigoso porque podem ser classes diferentes dependendo do `__init__.py`.

---

# Outro bug escondido

Vi isto:

```
decision_store.start()
decision_dispatcher.start()
```

dentro do construtor.



Se por qualquer motivo o Orchestrator for criado duas vezes:

```
Orchestrator()
Orchestrator()
```

terá:

```
dispatcher.start()
dispatcher.start()
```

duas vezes.

---

# Outro problema sério

No bootstrap:

```
def initialize(self) -> 'Orchestrator':
```



Mas no log apareceu:

```
await bootstrap.initialize()
```

Se isso continuar existindo em `main.py`, tem um segundo bug esperando para explodir.

Porque:

```
def initialize()
```

não é coroutine.

---

# O que eu faria

## Curto prazo

Bootstrap:

```
self.orchestrator = Orchestrator()
```

---

## Médio prazo

Transformar o Orchestrator para aceitar DI:

```
def __init__(
    self,
    memory=None,
    bus=None,
    planner=None,
    ...
):
```

e usar:

```
self.memory = memory or storage
self.bus = bus or EventBus()
```

Assim Bootstrap e testes conseguem injetar dependências.

---

# Meu ranking de problemas

### Fatal (derruba o sistema)

✅ incompatibilidade

```
Bootstrap
↓
Orchestrator(memory=..., bus=...)
```

vs

```
Orchestrator.__init__()
```

---

### Muito grave

duplicação de:

```
EvolutionRuntime
BanditPolicy
CreditAssignmentEngine
```



---

### Grave

possível:

```
await bootstrap.initialize()
```

quando initialize não é async... vai ser preciso transformae em async...



---

### Arquitetural

Orchestrator virou um "God Object" de milhares de linhas que cria sozinho memória, eventos, runtime, CPU affinity, feedback engine, cognitive proxy, evolution runtime, graph e persistence. Isso torna cada refactor propenso a quebrar o bootstrap exatamente como aconteceu agora pois bootstrap não é async.. 

o venv está em /home/user

crie um passo a passo ... e a cada passo realise um teste.. e vá para o proximmo passo... depois de concuido... anote todos os eventos em ROADMAP


