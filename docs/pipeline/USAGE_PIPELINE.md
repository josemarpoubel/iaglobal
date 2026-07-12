# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# Autonomous Research Loop — Guia de Uso

> **Objetivo:** Automatizar o ciclo completo de pesquisa científica: ler papers, extrair hipóteses, validar experimentalmente e consolidar conhecimento.

---

## 📋 Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                   AUTONOMOUS RESEARCH LOOP                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INGESTÃO          2. SÍNTESE         3. VALIDAÇÃO           │
│  ┌──────────────┐     ┌─────────────┐    ┌─────────────┐        │
│  │ PaperIngestor│ ──▶ │ Hypothesis  │───▶│ Experiment  │        │
│  │              │     │ Generator   │    │ Runner      │        │
│  └──────────────┘     └─────────────┘    └─────────────┘        │
│         │                   │                  │                │
│         ▼                   ▼                  ▼                │
│  paper_id.txt         {paper_id}_        {hypothesis_id}_       │
│  research_queue.json  hypotheses.json    result.json            │
│                                                                 │
│                                                                 │
│  4. CONSOLIDAÇÃO                                                │
│  ┌──────────────────────────────────────────────────────┐       │
│  │          ResearchConsolidator                        │       │
│  └──────────────────────────────────────────────────────┘       │
│         │                   │                                   │
│         ▼                   ▼                                   │
│  03_Long_Term/      {paper_id}_                                 │
│  paper_{id}.md      consolidated.json                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Critério de sucesso:** 1 paper → 3 hipóteses → 1 experimento → persistência sem intervenção.

---

## 🚀 Quick Start

### Exemplo Mínimo

```python
import asyncio
from iaglobal.agents.ingestion import (
    PaperIngestor,
    PaperParser,
    HypothesisGenerator,
    ExperimentRunner,
    ResearchConsolidator,
    FileIngestionAgent,
)

async def main():
    # 1. Ingestão
    ingestor = PaperIngestor()
    paper_path = await ingestor.ingest("2401.12345", "arxiv")
    
    # 2. Parser
    result = FileIngestionAgent.ingest([str(paper_path)])
    content = result["files"][0]["content"]
    
    parser = PaperParser()
    metadata = await parser.parse(content, "2401.12345", "arxiv")
    
    # 3. Hipóteses
    generator = HypothesisGenerator()
    hypotheses = await generator.generate(metadata)
    
    # 4. Validação
    runner = ExperimentRunner()
    results = []
    for hyp in hypotheses:
        result = await runner.run_experiment(hyp)
        results.append(result)
    
    # 5. Consolidação
    consolidator = ResearchConsolidator()
    consolidated = await consolidator.consolidate(metadata, results)
    
    print(f"✅ Pipeline completo: {consolidated.fitness_score:.0%} de validação")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📁 Estrutura de Arquivos

### Entrada

| Arquivo | Localização | Descrição |
|---------|-------------|-----------|
| `research_queue.json` | `iaglobal/memory/data/json/` | Fila de papers a processar |
| `{paper_id}.txt/pdf` | `iaglobal/memory/data/temp/papers/` | Papers baixados |

### Saída

| Arquivo | Localização | Descrição |
|---------|-------------|-----------|
| `{paper_id}_hypotheses.json` | `iaglobal/memory/data/json/papers/` | Hipóteses geradas |
| `{hypothesis_id}_{paper_id}_result.json` | `iaglobal/memory/data/json/papers/` | Resultados de experimentos |
| `{paper_id}_consolidated.json` | `iaglobal/memory/data/json/papers/` | Consolidação completa |
| `paper_{paper_id}.md` | `obsidian/03_Long_Term/` | Nota Obsidian formatada |

---

## 🔧 Módulo por Módulo

### 1. PaperIngestor

**Arquivo:** `iaglobal/agents/ingestion/paper_ingestor.py`

**Função:** Baixa papers de repositórios públicos.

**Repositórios suportados:**
- arXiv (CS, AI, ML)
- PubMed (biologia computacional)
- Hugging Face Papers

**Exemplo:**

```python
from iaglobal.agents.ingestion import PaperIngestor

ingestor = PaperIngestor()

# Baixar paper do arXiv
paper_path = await ingestor.ingest("2401.12345", "arxiv")

# Baixar em lote
from iaglobal.agents.ingestion import ingest_batch
paths = await ingest_batch(["2401.001", "2401.002", "2401.003"])

# Verificar status da fila
status = ingestor.get_queue_status()
print(f"Pendentes: {status['pending']}, Processados: {status['validated']}")
```

**Métodos principais:**
- `ingest(paper_id, repository)` → `Path` do arquivo baixado
- `ingest_batch(paper_ids, repository)` → `List[Path]`
- `get_queue_status()` → `Dict` com estatísticas
- `get_pending_papers()` → `List[Dict]` papers pendentes

---

### 2. PaperParser

**Arquivo:** `iaglobal/agents/ingestion/paper_parser.py`

**Função:** Extrai metadados e abstract de papers.

**Campos extraídos:**
- Título
- Autores
- Data de publicação
- Abstract
- Tópicos/keywords
- DOI (se disponível)

**Exemplo:**

```python
from iaglobal.agents.ingestion import PaperParser, FileIngestionAgent

# Ler arquivo
result = FileIngestionAgent.ingest(["path/to/paper.pdf"])
content = result["files"][0]["content"]

# Parse
parser = PaperParser()
metadata = await parser.parse(content, "2401.12345", "arxiv")

print(f"Título: {metadata.title}")
print(f"Autores: {', '.join(metadata.authors)}")
print(f"Abstract: {metadata.abstract[:100]}...")
print(f"Tópicos: {', '.join(metadata.topics)}")
```

**Métodos principais:**
- `parse(text, paper_id, repository)` → `PaperMetadata`
- `save_metadata(metadata, output_path)` → `Path` do JSON
- `parse_paper_file(file_path, paper_id)` → `PaperMetadata` (utilitário)

---

### 3. HypothesisGenerator

**Arquivo:** `iaglobal/agents/ingestion/hypothesis_generator.py`

**Função:** Gera 3 hipóteses testáveis a partir do abstract.

**Tipos de hipóteses:**
1. **Experimento** — código Python executável
2. **Análise de dados** — dataset público + estatística
3. **Simulação** — modelo computacional

**Exemplo:**

```python
from iaglobal.agents.ingestion import HypothesisGenerator

generator = HypothesisGenerator()
hypotheses = await generator.generate(metadata)

for hyp in hypotheses:
    print(f"{hyp.id}: {hyp.description}")
    print(f"   Método: {hyp.method}")
    print(f"   Critério: {hyp.success_criteria}")

# Validar schema
validations = generator.validate_hypotheses(hypotheses)
print(f"Válidas: {sum(validations)}/{len(validations)}")

# Salvar
generator.save_hypotheses(hypotheses, metadata.paper_id)
```

**Métodos principais:**
- `generate(paper)` → `List[Hypothesis]`
- `validate_hypotheses(hypotheses)` → `List[bool]`
- `save_hypotheses(hypotheses, paper_id)` → `Path` do JSON

**Prompt template:**
```
Dado este abstract de paper científico:
{abstract}

Proponha 3 hipóteses testáveis que poderiam ser validadas via:
1. Experimento computacional (código Python)
2. Análise de dados existentes
3. Simulação
```

---

### 4. ExperimentRunner

**Arquivo:** `iaglobal/agents/ingestion/experiment_runner.py`

**Função:** Executa experimentos para validar hipóteses em sandbox.

**Fluxo:**
1. Gera código Python (LLM ou template)
2. Executa em sandbox isolado
3. Avalia resultado vs critérios de sucesso
4. Registra reward no IVM (se sucesso)

**Exemplo:**

```python
from iaglobal.agents.ingestion import ExperimentRunner

runner = ExperimentRunner(sandbox_timeout=30)

for hyp in hypotheses:
    result = await runner.run_experiment(hyp)
    
    print(f"{hyp.id}: {'✅' if result.success else '❌'}")
    print(f"   Confiança: {result.confidence:.0%}")
    print(f"   Tempo: {result.execution_time_ms:.0f}ms")
    print(f"   Métricas: {result.metrics}")
    
    # Salvar resultado
    runner.save_result(result)
    
    # Registrar reward (automático se sucesso)
    runner.register_ivm_reward(result)
```

**Métodos principais:**
- `run_experiment(hypothesis)` → `ExperimentResult`
- `save_result(result)` → `Path` do JSON
- `register_ivm_reward(result)` → registra no IVM
- `validate_hypotheses(hypotheses)` → `List[ExperimentResult]` (batch)

**Códigos de sucesso:**
- `success=True` → critério atingido
- `confidence > 0.8` → alta confiança
- `confidence < 0.5` → resultado incerto

---

### 5. ResearchConsolidator

**Arquivo:** `iaglobal/agents/ingestion/consolidation.py`

**Função:** Consolida resultados em conhecimento de longo prazo (Obsidian + JSON).

**Saídas:**
- Nota Markdown em `obsidian/03_Long_Term/`
- JSON consolidado em `iaglobal/memory/data/json/papers/`

**Exemplo:**

```python
from iaglobal.agents.ingestion import ResearchConsolidator

consolidator = ResearchConsolidator()

consolidated = await consolidator.consolidate(
    paper=metadata,
    results=results,
    obsidian_enabled=True  # Escreve no Obsidian
)

print(f"Paper: {consolidated.title}")
print(f"Fitness: {consolidated.fitness_score:.0%}")
print(f"Hipóteses: {consolidated.validated_count}/{consolidated.hypotheses_count}")
print(f"Obsidian: {consolidated.obsidian_path}")
```

**Métodos principais:**
- `consolidate(paper, results, obsidian_enabled)` → `ConsolidatedPaper`
- `save_consolidated_json(consolidated, results)` → `Path` do JSON
- `consolidate_paper(paper, results)` → utilitário
- `consolidate_full_pipeline(paper, hypotheses, results)` → pipeline completo

**Fitness score:**
- `1.0` (100%) — todas as hipóteses validadas
- `0.67` (67%) — 2/3 validadas
- `0.33` (33%) — 1/3 validadas
- `0.0` (0%) — nenhuma validada

---

## 🧪 Testes

### Testes Unitários

```bash
source venv/bin/activate

# Ingestão
python -m pytest tests/test_autonomous_research_loop.py::TestPaperIngestor -v

# Parser
python -m pytest tests/test_autonomous_research_loop.py::TestPaperParser -v

# Hipóteses
python -m pytest tests/test_hypothesis_generator.py -v

# Experimentos
python -m pytest tests/test_experiment_runner.py -v

# Consolidação
python -m pytest tests/test_consolidation.py -v
```

### Testes End-to-End

```bash
# Pipeline completo
python -m pytest tests/test_autonomous_research_loop_e2e.py -v

# Verificar imports
python -c "
from iaglobal.agents.ingestion import (
    PaperIngestor, PaperParser, PaperMetadata,
    HypothesisGenerator, Hypothesis,
    ExperimentRunner, ExperimentResult,
    ResearchConsolidator, ConsolidatedPaper,
)
print('✅ Todos os módulos importam corretamente')
"
```

---

## 📊 Monitoramento

### Fila de Pesquisa

```python
from iaglobal.agents.ingestion import PaperIngestor
import json

ingestor = PaperIngestor()
queue_data = ingestor._load_queue()

print(json.dumps(queue_data["stats"], indent=2))
# {
#   "total": 10,
#   "pending": 2,
#   "ingested": 3,
#   "parsed": 2,
#   "hypothesized": 1,
#   "validated": 1,
#   "consolidated": 1
# }
```

### Fitness por Paper

```python
import json
from pathlib import Path

papers_dir = Path("iaglobal/memory/data/json/papers/")

for consolidated_file in papers_dir.glob("*_consolidated.json"):
    data = json.loads(consolidated_file.read_text())
    paper = data["paper"]
    
    print(f"{paper['paper_id']}: {paper['fitness_score']:.0%} ({paper['validated_count']}/{paper['hypotheses_count']})")
```

### Métricas Agregadas

```python
from pathlib import Path
import json

papers_dir = Path("iaglobal/memory/data/json/papers/")

total_papers = 0
total_hypotheses = 0
total_validated = 0

for f in papers_dir.glob("*_consolidated.json"):
    data = json.loads(f.read_text())
    total_papers += 1
    total_hypotheses += data["summary"]["total_hypotheses"]
    total_validated += data["summary"]["validated"]

print(f"Papers: {total_papers}")
print(f"Hipóteses: {total_hypotheses}")
print(f"Validadas: {total_validated}")
print(f"Taxa de validação: {total_validated/total_hypotheses:.0%}")
```

---

## 🛠️ Troubleshooting

### Paper não baixa

**Sintoma:** `ingest()` retorna `None`

**Causas:**
- ID do paper inválido
- Repositório indisponível
- Timeout de rede

**Solução:**
```python
# Verificar se está na fila
ingestor = PaperIngestor()
pending = ingestor.get_pending_papers()
print(pending)

# Tentar download manual
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get("https://arxiv.org/pdf/2401.12345.pdf") as resp:
        print(resp.status)  # Deve ser 200
```

### Hipóteses não geradas

**Sintoma:** `generate()` retorna fallback genérico

**Causas:**
- LLM indisponível
- Abstract muito curto
- Falha no CriticAgent

**Solução:**
```python
# Usar fallback manual
generator = HypothesisGenerator()
hypotheses = generator._fallback_hypotheses(metadata)
print(hypotheses)
```

### Experimento falha na sandbox

**Sintoma:** `run_experiment()` retorna `success=False`

**Causas:**
- Código gera erro de sintaxe
- Import de biblioteca não permitida
- Timeout de execução

**Solução:**
```python
# Verificar código gerado
result = await runner.run_experiment(hyp)
print(result.code)  # Código executado
print(result.stderr)  # Erros

# Ajustar template
runner = ExperimentRunner(sandbox_timeout=60)  # Mais tempo
```

### Consolidação não escreve no Obsidian

**Sintoma:** `obsidian_path=None`

**Causas:**
- SubconsciousAPI indisponível
- Vault não configurado
- Permissões de escrita

**Solução:**
```python
# Verificar se Obsidian está disponível
try:
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
    sub = SubconsciousAPI()
    print("✅ Obsidian disponível")
except ImportError:
    print("❌ Obsidian não disponível — usando apenas JSON")
```

---

## 📚 Exemplos Avançados

### Pipeline com Retry

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def robust_pipeline(paper_id):
    ingestor = PaperIngestor()
    paper_path = await ingestor.ingest(paper_id, "arxiv")
    
    if not paper_path:
        raise ValueError(f"Falha ao baixar {paper_id}")
    
    # ... resto do pipeline ...
    
    return consolidated

# Uso
consolidated = await robust_pipeline("2401.12345")
```

### Pipeline Paralelo

```python
import asyncio
from iaglobal.agents.ingestion import PaperIngestor, PaperParser, HypothesisGenerator

async def process_paper(paper_id):
    ingestor = PaperIngestor()
    paper_path = await ingestor.ingest(paper_id, "arxiv")
    
    # ... pipeline completo ...
    
    return consolidated

# Processar 5 papers em paralelo
results = await asyncio.gather(
    process_paper("2401.001"),
    process_paper("2401.002"),
    process_paper("2401.003"),
    process_paper("2401.004"),
    process_paper("2401.005"),
)

print(f"Processados: {len(results)}")
```

### Filtro por Fitness

```python
from pathlib import Path
import json

papers_dir = Path("iaglobal/memory/data/json/papers/")

high_fitness_papers = []

for f in papers_dir.glob("*_consolidated.json"):
    data = json.loads(f.read_text())
    if data["summary"]["fitness_score"] >= 0.67:
        high_fitness_papers.append(data["paper"])

print(f"Papers de alta qualidade: {len(high_fitness_papers)}")
for paper in high_fitness_papers:
    print(f"  - {paper['title']} ({paper['fitness_score']:.0%})")
```

---

## 🔗 Integrações

### Com BanditPolicy

```python
from iaglobal.agents.ingestion import ExperimentRunner

runner = ExperimentRunner()
result = await runner.run_experiment(hypothesis)

if result.success:
    # BanditPolicy já foi atualizado via register_ivm_reward()
    from iaglobal.bandit import BanditPolicy
    bandit = BanditPolicy()
    metrics = bandit.get_model_metrics("experiment_runner")
    print(f"Success rate: {metrics['success_rate']:.0%}")
```

### Com Obsidian

```python
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

sub = SubconsciousAPI()

# Buscar papers consolidados
notes = await sub.buscar_notas("#PaperValidado")
print(f"Papers validados: {len(notes)}")

# Ler nota específica
content = await sub.ler_nota("paper_2401_12345")
print(content[:200])
```

### Com ImmuneMemoryExchange

```python
from iaglobal.immunity.immune_memory_exchange import ImmuneMemoryExchange

exchange = ImmuneMemoryExchange()

# Compartilhar paper validado
await exchange.publish_vaccine(
    marker="paper_2401_12345",
    patterns=["high_fitness", "replicated"],
)

# Receber papers de outros nós
papers = await exchange.import_vaccine(
    remote_node="node_001",
    source="research_loop",
)
```

---

## 📝 Notas

- **Assincrono:** Todo o pipeline é `async/await` — usar `asyncio.run()` ou estar em contexto async
- **Sandbox:** Experimentos rodam em subprocesso isolado — sem network, sem I/O externo
- **Idempotente:** Re-executar o mesmo paper_id não duplica na fila
- **Resiliente:** Fallbacks em cada etapa (LLM falha → template, sandbox falha → retry)

---

**Última atualização:** 2026-07-09  
**Versão:** 1.0.0  
**Status:** ✅ Produção (591 testes passando)
