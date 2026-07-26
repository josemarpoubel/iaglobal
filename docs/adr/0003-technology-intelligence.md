# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ADR 0003 — Knowledge Engine: motor de conhecimento orientado por capacidades

- **Status**: Proposta
- **Data**: 2026-07-25
- **Contexto**: LLM gera código com conhecimento paramétrico; desperdiça ecossistemas consolidados (PyPI, npm, crates.io, Docker Hub).

## Contexto

Hoje o pipeline executa:

```
Prompt → MissionAnalyzer → Planner → Coder → Validator
```

O `Coder` depende quase exclusivamente do conhecimento paramétrico do LLM. Isso produz implementações do zero para problemas com bibliotecas maduras, APIs alucinadas e nenhum aprendizado cumulativo sobre quais tecnologias funcionam melhor no ambiente real.

O sistema já possui os blocos (`SkillRegistry`, `BanditPolicy`, `Memory`, `Validator`), mas falta uma camada que transforme ecossistemas de tecnologia em extensão da memória cognitiva — e que funcione para Python, Node, Rust, Docker, Kubernetes, bancos de dados, blockchain, etc.

## Decisão

Adotar um **Knowledge Engine** — motor de conhecimento orientado por capacidades, com adaptadores por ecossistema, que transforma o LLM de fonte de conhecimento em orquestrador que conecta peças do ecossistema real.

### Princípio fundamental

A unidade de conhecimento é a **capacidade**, não a biblioteca.

```
capability: pdf_generation
  ├── reportlab   (maturity=0.99)
  ├── weasyprint  (maturity=0.85)
  ├── borb        (maturity=0.60)
  └── fpdf2       (maturity=0.70)
```

O `Bandit` nunca escolhe `reportlab` diretamente. Ele escolhe **dentro** da capability `pdf_generation`. Isso permite adicionar novas bibliotecas sem alterar lógica alguma.

### Arquitetura em camadas

```
Mission
    │
    ▼
Constraint Extractor        ← novo
    │
    ▼
Capability Graph            ← novo (substitui TechnologyRegistry)
    │
    ▼
Knowledge Engine            ← novo (umbrella)
    │
    ├── Python Adapter  (PyPI + pip index)
    ├── npm Adapter      (npm registry)
    ├── crates.io Adapter
    ├── Docker Adapter   (Docker Hub)
    ├── MCP Adapter      (servidores MCP)
    └── Internal Skills  (SkillRegistry existente)
    │
    ▼
Technology Validator        ← novo
    │
    ▼
Documentation Resolver      ← novo ("vivo": docstring + assinatura + exemplos + versão)
    │
    ▼
Context Builder
    │
    ▼
Planner → Coder → Validator
    │
    ▼
Experience Memory            ← novo (substitui TechnologyMemory)
    │
    ▼
Bandit (modo technology)    ← extensão do BanditPolicy existente
```

### Componentes

#### 1. Constraint Extractor

Antes de extrair capacidades, extrai restrições da missão:

```
"editor markdown que exporta pdf offline em python"
→ constraints = {offline: true, language: python, output: pdf}
```

```
"dashboard web com gráficos em tempo real"
→ constraints = {interactive: true, realtime: true, platform: web}
```

Isso elimina candidatos incompatíveis antes mesmo de consultar o Bandit.

#### 2. Capability Graph

A unidade de conhecimento é a **Capability**:

```python
@dataclass
class Capability:
    name: str                                    # "pdf_generation"
    candidates: dict[str, TechnologyDescriptor]  # "reportlab" → TechnologyDescriptor
    documentation: dict[str, DocumentationSet]   # cache de docs por biblioteca
    experiences: dict[str, list[Experience]]     # "reportlab" → [Experience, ...]
    benchmarks: dict[str, Benchmark]             # "reportlab" → Benchmark
    known_issues: dict[str, list[KnownIssue]]    # "reportlab" → [KnownIssue, ...]
```

Uma capability **contém** candidatos. O Bandit escolhe dentro dela.

#### 3. Knowledge Engine (umbrella)

```python
class KnowledgeEngine:
    adapters: dict[str, EcosystemAdapter]

    async def resolve(self, capability: str, constraints: dict) -> list[TechnologyDescriptor]:
        # 1. Consulta Capability Graph (registry local)
        # 2. Se vazio ou stale, consulta adaptadores em paralelo
        # 3. Atualiza registry com descobertas
        # 4. Retorna candidatos ranqueados por maturity × bandit_weight
```

Cada adaptador implementa:

```python
class EcosystemAdapter(ABC):
    ecosystem: str  # "python", "npm", "crates", "docker"

    async def discover(self, capability: str) -> list[TechnologyDescriptor]: ...
    async def fetch_documentation(self, tech: TechnologyDescriptor) -> DocumentationSet: ...
    async def validate(self, tech: TechnologyDescriptor) -> ValidationResult: ...
```

Python é o primeiro adaptador, usando:

- PyPI JSON API (`https://pypi.org/pypi/{package}/json`)
- Classificadores do PyPI (Topic, Framework, License)
- `pip index` para candidates
- `importlib.metadata` para versão instalada

#### 4. Technology Validator

Antes de enviar APIs ao LLM, verifica que existem no ambiente:

```python
async def validate(tech: TechnologyDescriptor) -> ValidationResult:
    # pip list | grep reportlab
    # python -c "from reportlab.platypus import SimpleDocTemplate"
    # importlib.metadata.version("reportlab")
    # inspect.signature(SimpleDocTemplate)
    return ValidationResult(
        installed=True,
        version="4.3",
        api_available=["SimpleDocTemplate", "Paragraph", "Spacer", ...],
        warnings=["método X deprecated from v4.0"],
    )
```

O LLM recebe **somente APIs verificadas**. Isso elimina alucinação de API.

#### 5. Documentation Resolver ("vivo")

Não busca documentação estática. Coleta do ambiente real:

```
reportlab 4.3
  → SimpleDocTemplate(pageSize, topMargin)
  → docstring: "Builds a document from a sequence of flowables"
  → 3 exemplos oficiais (do site ou do cache local)
  → classes relacionadas: BaseDocTemplate, PageTemplate, Frame
  → changelog desde a versão instalada
```

O contexto enviado ao LLM contém APIs reais, com assinaturas verificadas.

#### 6. Experience Memory

Evolução da TechnologyMemory proposta originalmente. Além de scores, armazena **conhecimento procedural**:

```python
@dataclass
class Experience:
    capability: str
    library: str
    version: str
    execution_time: float
    validator_score: float
    tests_passed: int
    tests_total: int
    reward: float
    errors: list[KnownFailure]
    timestamp: datetime

@dataclass
class KnownFailure:
    error: str                        # "UnicodeEncodeError"
    context: str                      # "ao gerar Paragraph com caracteres acentuados"
    solution: str                     # "registrar fontes via pdfmetrics.registerFont()"
    environment: str                  # "Debian 12, Python 3.13"
    fixed_in_version: str | None      # "4.2" se resolvido
```

O sistema aprende não apenas *qual* biblioteca usar, mas *como* usar e *o que evitar*.

#### 7. Bandit modo Technology

Reaproveita o `CreditEngine` e `BanditPolicy` existentes:

```python
bandit.select(
    domain="technology",              # novo domínio
    requirement="pdf_generation",
    candidates=["reportlab", "weasyprint", "borb"],
    context={"mission_id": ..., "constraints": constraints}
)
```

Braços = bibliotecas. Recompensa = validator_score × (tests_passed / tests_total) × bonus_latência.

Mesmo `CreditAssignmentEngine`, mesmas `weights`, mesmas `rewards`. Apenas o namespace difere (`technology/pdf_generation/reportlab` vs `model/ollama/qwen2.5`).

### Auto-expansão do Registry

A versão inicial é curada manualmente (~30 capacidades). Depois o sistema expande sozinho via:

1. **PyPI classifiers**: `pip index` + filtrar por `Topic`
2. **npm search**: `npm search <capability>`
3. **crates.io API**: `GET https://crates.io/api/v1/crates?q=<capability>`
4. **Docker Hub**: `GET https://hub.docker.com/v2/repositories/library/<name>`

Cada descoberta gera um `TechnologyDescriptor` candidato que entra no Bandit com peso inicial baixo (exploration).

### Fluxo final (longo prazo)

```
Mission
    │
    ▼
Constraint Extractor
    │
    ▼
Capability Graph
    │
    ▼
Knowledge Engine
    │
    ├── Python Adapter  (PyPI)
    ├── npm Adapter     (npm)
    ├── crates.io Adapter
    ├── Docker Adapter
    ├── MCP Adapter
    └── Internal Skills
    │
    ▼
Technology Validator
    │
    ▼
Documentation Resolver
    │
    ▼
Context Builder (enriquecido com APIs verificadas + exemplos + assinaturas)
    │
    ▼
Planner → Coder → Validator
    │
    ▼
Experience Memory
    │
    ▼
Bandit (modo technology, realimentado)
```

O LLM deixa de ser a fonte do conhecimento e passa a ser o **orquestrador** que conecta peças de ecossistemas reais, com APIs verificadas no ambiente de execução.

## Ordem de implementação

1. **Capability Graph + Knowledge Engine (esqueleto)** — contratos tipados (`Capability`, `TechnologyDescriptor`, `EcosystemAdapter`), sem adaptadores ainda
2. **Python Adapter** — PyPI discovery + `pip index` + `importlib.metadata`
3. **Constraint Extractor** — extração estruturada do `MissionContract`
4. **Technology Validator** — `python -c "import X; from X import Y"` + `inspect.signature`
5. **Documentation Resolver** — coleta de docstring + assinatura + exemplos do pacote instalado
6. **Experience Memory** — persistência de scores + `KnownFailure`
7. **Bandit modo technology** — extensão do `BanditPolicy` com namespace `technology/<capability>/<library>`

## Consequências

**Positivas:**
- LLM vira metacomponente de raciocínio; conhecimento vem do ecossistema real
- Sistema acumula conhecimento procedural empírico (erros + soluções)
- Redução drástica de alucinação de API (Technology Validator)
- Multilinguagem desde o nascimento (adaptadores para Python, npm, crates, Docker)
- `BanditPolicy` existente é estendido com novo domínio, sem quebrar modelo existente
- Registry auto-expansível via PyPI/npm/Docker APIs

**Negativas:**
- Aumento de latência (validator + doc resolver)
- Adaptadores externos dependem de conectividade de rede
- Versão inicial precisa de curadoria manual (~30 capacidades)

**Neutras:**
- `KnowledgeEngine` pode coexistir com o fluxo atual (fallback para LLM puro se candidates vazio)
- `Bandit` compartilha `CreditEngine` entre domínios `model` e `technology`
- `ExperienceMemory` pode alimentar tanto o Bandit quanto o sistema de evolution

## Invariante arquitetural

> **Knowledge não é uma base de dados. Knowledge é uma camada de inteligência operacional composta por contratos tipados e evidências verificáveis.**

Isso implica que:

- Nenhum adaptador de ecossistema invoca LLM para descoberta de tecnologia
- Nenhum `CodeExample` entra no sistema sem validação (`ValidationResult.success == True`)
- Nenhum `BenchmarkRecord` persiste sem timestamp e ambiente registrado
- `CapabilityGraph.has_cycles() == False` é invariante obrigatório em runtime
- `TechnologyGraph.candidates_for()` sempre retorna sorted por score descendente
- `PackageDescriptor.overall_score` nunca excede 1.0

## Boundary Rule

A camada Knowledge Intelligence respeita estas fronteiras para não se confundir com execution, memory, evolution ou pipeline:

```
Knowledge Layer MUST NOT:

- executar código descoberto
- instalar dependências
- chamar LLM
- alterar pipeline topology
- persistir sem provenance
- decidir arquitetura final (delega ao Planner)

Knowledge Layer MAY:

- analisar capabilities semanticamente
- comparar tecnologias por score
- armazenar evidências de execução (BenchmarkRecord)
- fornecer candidatos ranqueados ao Bandit
- validar que uma API existe no ambiente (TechnologyValidator)
- expandir o registry via PyPI/npm/crates discovery
- acumular KnownFailure com solução
```

Isso mantém a separação entre as 6 ilhas existentes e a nova camada:

| Camada | Natureza | Conhecimento? | Execução? |
|---|---|---|---|
| `memory/` | retenção e recuperação | experiências passadas | não |
| `evolution/` | aprendizado/adaptação | mutação do próprio sistema | não |
| `graphs/nodes/` | etapa operacional | pipeline | sim |
| `pipeline/context/` | projeção para agentes | contexto atual | não |
| `pipeline/capability_resolver/` | decisão heurística | regras fixas | não |
| **`knowledge/`** | **inteligência operacional verificável** | **capacidades + tecnologias + evidências** | **não** |

## Contratos implementados (`iaglobal/knowledge/`)

| Módulo | Tipos | Invariante principal |
|---|---|---|
| `contracts.py` | `ValidationResult`, `KnowledgeProvenance`, `Severity` | Provenance exige source + timestamp |
| `capability.py` | `Capability`, `CapabilityGraph` | `has_cycles() == False`; `resolve()` por id/alias/keyword |
| `technology.py` | `TechnologyDescriptor`, `TechnologyGraph`, `CATALOG` | `score = maturity × (1 - difficulty×0.3)`; `candidates_for()` sorted |
| `package.py` | `PyPIMetadata`, `PackageHealth`, `PackageDescriptor` | `overall_score` limitado a 1.0; `maintenance_score` por recência |
| `example.py` | `CodeExample`, `ExampleLibrary` | `is_verified == (validated AND validation.success)` |
| `benchmark.py` | `BenchmarkRecord`, `BenchmarkHistory` | `reward = validator×0.4 + tests×0.3 + latency×0.15 + memory×0.15` |

## Estado atual do projeto (grep knowledge)

O sistema já possui 6 conceitos diferentes com o mesmo nome `knowledge`, mas nenhum é a camada de inteligência aqui descrita:

| Local | Papel atual |
|---|---|
| `memory/fusion_engine.py` | KnowledgeGraph cognitivo genérico |
| `evolution/evolution_agents/knowledge_agent.py` | Memória operacional |
| `graphs/nodes/no_knowledge.py` | Ingestão/fusão no pipeline |
| `graphs/nodes/no_local_knowledge.py` | Recuperação LTM/STM/vector |
| `pipeline/context/context_providers/knowledge.py` | Projeção de contexto |
| `pipeline/capability_resolver.py` | Resolver heurístico (string match) |

O `pipeline/capability_resolver.py` atual usa:

```python
if "pdf_generation" in contract.required_features:
    plan.add_step("tool", "tool:pdf")
```

A nova camada substitui isso por:

```python
capability = knowledge.capabilities.resolve("generate pdf document")
candidates = knowledge.technology.candidates_for(capability.id)
selected = bandit.select(domain="technology", requirement=capability.id, candidates=candidates)
```

## Ordem de implementação

1. ~~`TechnologyRegistry`~~ → `CapabilityGraph + KnowledgeEngine (esqueleto)` — contratos tipados em `iaglobal/knowledge/` ✔️
2. **PythonAdapter** — PyPI discovery + `pip index` + `importlib.metadata`
3. **ConstraintExtractor** — extração estruturada do `MissionContract`
4. **TechnologyValidator** — `python -c "import X; from X import Y" + inspect.signature`
5. **DocumentationResolver** — coleta de docstring + assinatura + exemplos do pacote instalado
6. **ExperienceMemory** — persistência de scores + KnownFailure
7. **TechnologyBandit** — extensão do `BanditPolicy` com namespace `technology/<capability>/<library>`

## Referências

- ADR 0001 (Bootstrap two-phase) — precedente de formato de ADR
- ADR 0002 (MCP Unified Server) — precedente de arquitetura com adaptadores
- `iaglobal/graphs/bandit.py` — BanditPolicy (base para Technology Bandit)
- `iaglobal/pipeline/mission.py` — MissionContract (entrada do Constraint Extractor)
- `iaglobal/pipeline/capability_resolver.py` — ponto de integração da migração
- `iaglobal/evolution/skills/` — SkillRegistry (paralelo ao Capability Graph)
- `iaglobal/core/artifact.py` — GeneratedArtifact (fonte de recompensa do Validator)
- `iaglobal/memory/` — STM/LTM (base para Experience Memory)
- `iaglobal/knowledge/` — contratos implementados (capability, technology, package, example, benchmark)
- `iaglobal/tests/test_knowledge_contracts.py` — 33 invariantes validados (sem executor, sem LLM)
