# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ADR 0004 — Contrato de Linhagem de Eventos (Event Lineage Contract)

- **Status**: Proposta
- **Data**: 2026-07-25
- **Supersede**: nenhum
- **Superseded by**: —
- **Depende de**:
  - ADR 0001 (Bootstrap two-phase) — evento precisa ser emitido cedo.
  - ADR 0003 (Knowledge Engine) — `CAPABILITY_SELECTED` é a primeira
    instanciação concreta deste contrato.

## Contexto

A partir de `866a034 feat(events): introduce capability decision telemetry contract`,
o iaglobal passou a emitir seu **primeiro evento de domínio**
(`CAPABILITY_SELECTED`) carregando:

- `mission_id` (identifica a missão);
- `capability`, `selected_technology`, `decision_confidence`
  (corpo da decisão);
- `evidence` (`MappingProxyType`, imutável);
- `timestamp` ISO-8601.

Sem uma política de linhagem, o próximo evento natural
(`CAPABILITY_RESULT`) só pode ser correlacionado ao seu predecessor por
heurística:

```python
# correlação por convenção — frágil
events = store.replay(mission_id="m-42")
decision = next(e for e in events if e.type == "capability_selected")
result = next(e for e in events
              if e.type == "capability_result"
              and e.mission_id == decision.mission_id
              and e.timestamp > decision.timestamp)
```

É **correlação**, não causalidade. Os problemas:

1. **Ambiguidade**: vários eventos podem satisfazer a condição acima
   em janelas temporais próximas.
2. **Replay fraco**: ordem temporal não é ordem causal — pode-se inferir
   errado se o relógio do produtor oscilar entre regiões.
3. **Auditoria falsa**: o auditor confunde causa com coincidência.
4. **Crescimento caótico**: cada novo tipo de evento decide sua própria
   estratégia de correlação — sem contrato comum, o sistema vira
   *bag of loosely correlated logs*.

Hoje já temos o esqueleto no `models/event_bus.py`:

```python
@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(...)
```

O campo `Event.id` existe mas é anônimo — sem tipo, sem contrato, sem
documentação pública. É o embrião do que este ADR formaliza.

---

## Decisão

Adotar um **contrato único de linhagem de eventos** com quatro
invariantes:

1. **Identidade opaca** — toda referência a um evento é um
   `EventId(value: str)` simples. O formato (UUID8, ULID, hash
   causal, UUIDv7) é detalhe de implementação, não contrato público.
2. **Identidade rica para auditoria** — cada evento carrega uma
   `EventIdentity` que adiciona tipo, timestamp e provenance; o
   `EventId` sozinho serve para referências cruzadas.
3. **Linhagem explícita** — eventos derivados citam seu predecessor
   pelo `predecessor_event_id` (não por `mission_id` + timestamp).
4. **Imutabilidade do contrato** — todo evento de domínio é uma
   dataclass `frozen=True` com `evidence` em `MappingProxyType`,
   serialização manual via `to_dict()` (sem `dataclasses.asdict()`),
   herança de `DomainEvent` (não herança livre).

### Modelo de dados

```python
# events/event_id.py
from dataclasses import dataclass

@dataclass(frozen=True)
class EventId:
    """Identidade opaca de um evento no sistema.

    O conteúdo de ``value`` é determinado pela implementação (UUID8,
    ULID, UUIDv7, hash causal). Consumidores tratam como string
    comparável.
    """
    value: str


@dataclass(frozen=True)
class EventIdentity:
    """Identidade completa — para auditoria e replay.

    Inclui tipo, timestamp e provenance. ``id`` por si só basta para
    referência cruzada; este wrapper torna a verdade auto-descritiva.
    """
    id: EventId
    event_type: "EventType"
    created_at: datetime
    provenance: Mapping[str, Any] = MappingProxyType({})


# events/domain_event.py
from types import MappingProxyType
from typing import Any, Mapping

@dataclass(frozen=True)
class DomainEvent:
    """Base class de todo evento de domínio do iaglobal.

    Campos invariantes:
    - ``id``: identidade opaca (única por evento).
    - ``event_type``: discriminador semântico.
    - ``mission_id``: identificador da missão (string vazia para
      eventos de sistema).
    - ``created_at``: ISO-8601 UTC.
    - ``evidence``: MappingProxyType, imutável.

    Subclasses adicionam corpo específico. Subclasses que derivam de
    outra subclasse devem incluir ``predecessor_event_id`` para fechar
    a cadeia causal.
    """
    id: EventId
    event_type: "EventType"
    mission_id: str
    created_at: datetime
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence", MappingProxyType(dict(self.evidence))
        )

    def to_dict(self) -> Dict[str, Any]:
        # Manual — asdict() não lida com MappingProxyType/frozen.
        ...
```

### Subclasse concreta já existente (refatorada)

```python
# events/decision_event.py
@dataclass(frozen=True)
class CapabilityDecisionEvent(DomainEvent):
    """CAPABILITY_SELECTED — emitida quando o CapabilityResolver escolhe tecnologia."""
    capability: str
    selected_technology: str | None
    validation_confidence: float
    effective_score: float
    bandit_score: float
    reason: tuple[str, ...]
    fallback_used: bool
    candidate_count: int
    filtered_count: int
    selected_provider: str | None = None
    predecessor_event_id: EventId | None = None  # futuro
    evidence: Mapping[str, Any] = field(default_factory=dict)
```

Note que a `evidence` da subclasse é **sobrescrita pelo `__post_init__`
do pai** (que sempre re-freeze). Cada subclasse não precisa redefinir o
freeze; basta declarar `evidence` com default `{}` e herdar o
`__post_init__`.

### Subclasse futura

```python
# events/result_event.py
@dataclass(frozen=True)
class CapabilityResultEvent(DomainEvent):
    """CAPABILITY_RESULT — emitida quando a execução da tecnologia escolhida termina."""
    decision_event_id: EventId     # predecessor explícito
    capability: str
    success: bool
    artifact_kind: str
    validation_status: str
    quality_score: float
    repair_count: int
    latency_ms: float
    provider: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
```

Linhagem causal:

```text
Mission ─── mission_id ───┐
                          │
                          ▼
                CapabilityDecisionEvent
                  │    id=EventId("evt_a81f")
                  │
                  │  decision_event_id
                  ▼
                CapabilityResultEvent
                  id=EventId("evt_b402")
```

### Modelo de publicação

```python
# models/event_bus.py (refatorado, não quebra contrato atual)
def publish(
    self,
    event: DomainEvent,                 # antes: type: str + data: dict
    source: str = "",
) -> None:
    """Publica um evento de domínio idêntico ao sistema.

    Carimba EventIdentity (id+type+timestamp+provenance), faz dispatch
    aos subscribers e persiste no EventStore.
    """
    ...

# EventStore auto-subscreve via:
bus.subscribe("*", event_store.append)   # recebe DomainEvent completo
```

### Compatibilidade retroativa

Eventos legados (emitidos como `Dict[str, Any]`) continuam chegando
via subscription por `event_type` string até cutover. Após este ADR:

| Forma | Como recebe | Status |
|---|---|---|
| Novo: `DomainEvent` (frozen, com `id: EventId`) | Subscribers recebem o dataclass diretamente | Canônico |
| Legado: `bus.publish("task.created", data={...})` | Subscribers recebem dict `{type, data, id, timestamp}` | Compat (deprecating) |

A deprecação dos `dict`-based publishes será feita incremental — cada
emissor migrado remove uma fatia.

---

## Consequências

### Positivas

- **Linhagem causal explícita**: substitui heurística de timestamp por
  referência direta. `decision_event_id == "evt_a81f"` é uma junção,
  não uma inferência estatística.
- **Replay confiável**: dado um `mission_id`, reconstruir a cadeia
  causal é determinístico mesmo que `created_at` esteja bagunçado.
- **Auditoria forte**: o auditor vê a flecha causal no `Evidence`,
  não em logs adjacentes.
- **Imutabilidade verificável**: dataclass frozen + MappingProxyType
  — consumidor não consegue mutar o evento após emissão.
- **Polimorfismo seguro**: subclasses reaproveitam `__post_init__`,
  serialização, e convenções de identidade. Não há "duas ou três formas"
  de evento no sistema.
- **Pronto para CAPABILITY_RESULT**: a próxima fronteira já tem
  contrato + predecessor explícito.
- **Migração gradual**: legados `dict` continuam funcionando; cutover
  por evento, não big-bang.

### Custos

- Refactor de todos os publishers existentes: cada `bus.publish("xyz",
  data={...})` vira emissão de dataclass concreta. Estimativa:
  ~15-20 emitters legados para migrar.
- `events/event_id.py` e `events/domain_event.py` adicionados
  (~80 linhas).
- Migração dos dataclasses legados (`DecisionEvent`, `DecisionLock`)
  para herdar de `DomainEvent` é opcional mas recomendada.
- Testes precisam cobrir: identidade única, predecessor chain imutável,
  MappingProxyType imutável.

### Tradeoffs documentados

- **Identidade opaca**: escolhemos `EventId(value: str)` em vez de um
  esquema "tipo+instance+timestamp" porque o consumidor **não deve
  depender do formato** (UUID8 hoje, ULID ou UUIDv7 amanhã). O custo
  é que order-of-magnitude debugging exige acesso a `event.identity`
  em vez da string.
- **`mission_id` continua no payload**: apesar da linhagem ser por
  `predecessor_event_id`, o `mission_id` permanece útil como
  agrupador de auditoria (queries do tipo "todos os eventos da missão
  X"). Remover quebraria relatórios.
- **`timestamp` continua sendo ISO-8601**: humanos precisam de
  timestamps legíveis; ID puro não substitui leitura.

---

## Alternativas consideradas

1. **Causal-id hash derivado (`sha256(type+mission_id+timestamp+...)`)**:
   rejeitada — torna a identidade dependente do conteúdo; refactor
   semântico do evento (mesmo tipo, mesmo id) é hoje silenciosamente
   permitida.
2. **`predecessor_event_id` facultativo**: rejeitada — opcional
   rapidamente vira ignorado; quebra o invariante causal.
3. **`mission_id` como chave primária em vez de `event_id`**:
   rejeitada — uma missão emite N decisões; `mission_id` colapsa
   N→1.
4. **Event sourcing completo (replay reconstitui estado)**: rejeitada
   neste ADR — é horizonte distante. Hoje o ADR é apenas o **contrato
   de linhagem**, não o armazenamento de eventos como source-of-truth
   do sistema.
5. **Catálogo central de eventos (`events/types.py` com TODOS os
   `DomainEvent`s registrados)**: rejeitado por enquanto — a
   estabilidade de tipos é o ganha-pão do `dataclass(frozen=True)`.
   Catálogo vira ADR posterior se a família crescer >10.

---

## Reversibilidade

Total enquanto não migrarmos os publishers legados. Após migração,
ainda reversível — basta:

1. Adicionar adapter que reconstrói `DomainEvent` a partir de dict.
2. Re-publicar via `bus.publish(event_type, data=...)`.
3. Subclasses de `DomainEvent` mantêm compatibilidade binária
   porque são frozen dataclasses; podem ser deserializadas no formato
   antigo se necessário.

Se descobrirmos que o formato de `EventId.value` é inadequado
(ex.: UUID8 colide), basta trocar o factory — todos os Holdings
de `EventId` permanecem válidos como referências forward-only.

---

## Validação automatizada

Suite de testes proposta (não inclui nesta ADR; vira trabalho após
aceitação):

| Teste | Contrato verificado |
|---|---|
| `test_event_id_uniqueness` | IDs diferentes para N publicações consecutivas. |
| `test_domain_event_frozen` | `__setattr__` levanta; `evidence["k"]=v` levanta. |
| `test_predecessor_chain` | `CapabilityResultEvent.decision_event_id == CapabilityDecisionEvent.id`. |
| `test_event_round_trip` | `to_dict()` → `from_dict()` recria evento byte-equivalente. |
| `test_legacy_publish_compat` | Publishers `dict` ainda funcionam durante janela de migração. |
| `test_replay_with_predecessor` | `DecisionEventReplay.summary(execution_id)` retorna cadeia causal. |

Gate de aceitação:

```bash
python -m pytest iaglobal/tests/test_event_lineage.py -v
# Deve passar com exit 0 antes de qualquer evento derivado novo.
```

---

## Quando revisar

- Quando quisermos **promover event-store a source-of-truth** (sair
  de "log de auditoria" para "estado reconstruível").
- Quando o primeiro evento de **sistema** (não missão — ex.:
  immune alert global) precisar existir. Hoje todos os eventos
  alinham a `mission_id`; system-level events ainda são
  exceção e devem abrir nova ADR.
- Se появиться necessidade de compactação / retenção diferente por
  tipo — atualmente uniforme.
- Se um schema registry externo (Protobuf/Avro) for introduzido.

---

## Próximo passo operacional

Sequência proposta (não é decisão deste ADR; é roadmap acordado
para evitar crescimento caótico):

```text
1. ADR-0004                          ← este ADR (proposta)
       |
       v
2. events/event_id.py + domain_event.py
       |
       v
3. CapabilityDecisionEvent herda de DomainEvent
       |
       v
4. test_event_lineage.py (gate)
       |
       v
5. CAPABILITY_RESULT (CapabilityResultEvent)
       |
       v
6. Bandit feedback loop (Commit 3 do plano original)
       |
       v
7. Memory causal integration (Commit 4)
```

Cada passo é uma única alteração pequena + testes + commit.
Semanas 1-2: passo 1-4. Passos 5-7 só avançam após esses quatro
estarem verdes.
