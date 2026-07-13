# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# 🧬 ROADMAP — MCP Protocol Expansion

> **Objetivo:** Conectar iaglobal a ferramentas externas via Model Context Protocol (MCP) e criar um ecossistema de tools MCP end-to-end.

---

## 🔵 Fase 1 — Serviços de Cliente MCP

### Diagnóstico
O `iaglobal/mcp/` atual contém apenas `mcp_agent.py` (meta-circular agent para auto-reparo). Não há:
- Servidor MCP (`mcp_server.py`) para expor tools como FastMCP
- Clientes MCP para ferramentas externas (web search, file system, code execution)
- Descoberta dinâmica de tools
- Cache de registro de tools MCP

| Arquivo | Status | Localização |
|---------|--------|-------------|
| `mcp_server.py` | ❌ ausente | `iaglobal/mcp/mcp_server.py` |
| `search_web.py` | ❌ ausente | `iaglobal/mcp/search_web.py` |
| `file_system.py` | ❌ ausente | `iaglobal/mcp/file_system.py` |
| `code_executor.py` | ❌ ausente | `iaglobal/mcp/code_executor.py` |
| `client.py` | ❌ ausente | `iaglobal/mcp/client.py` |
| `discovery.py` | ❌ ausente | `iaglobal/mcp/discovery.py` |
| `mcp_tools.json` | ❌ ausente | `iaglobal/memory/data/json/mcp_tools.json` |

---

### 1.1 — `mcp_server.py`: FastMCP Server

**Problema:** `MCPAgent` em `mcp_agent.py` (L275) comenta que `_get_ivm()` é chamado de forma síncrona em `mcp_server.py`, mas este arquivo nunca foi criado.

**Correção:** Criar `iaglobal/mcp/mcp_server.py` usando `FastMCP` do pacote `mcp`:

```python
from mcp.server.fastmcp import FastMCP
from iaglobal.mcp.mcp_agent import MCPAgent

mcp = FastMCP("iaglobal", instructions="Sistema imunológico evolutivo com ferramentas MCP integradas")
agent = MCPAgent()

@mcp.tool()
async def metabolic_audit() -> dict:
    """Executa auditoria metabólica completa."""
    audit = await agent.run_audit()
    return {"score": audit.score, "findings": audit.findings}

@mcp.tool()
async def get_ivm() -> float:
    """Retorna o Índice de Viabilidade Metabólica atual."""
    return agent._get_ivm()
```

**Critério:** `mcp_server.py` é importável e expõe 2+ tools via FastMCP sem erro.

---

### 1.2 — `search_web.py` — Web Search Tool

**Problema:** O sistema não tem uma tool MCP encapsulada para busca web. O `search_agent.py` existe mas é interno ao pipeline.

**Arquivo:** `iaglobal/mcp/search_web.py`

```python
import aiohttp
from typing import Optional

class WebSearchTool:
    """Tool MCP para busca web usando duckduckgo-search ou fallback aiohttp."""

    def __init__(self, cache_ttl: int = 300):
        self._cache: dict = {}
        self._cache_ttl = cache_ttl

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Busca web e retorna lista de {title, url, snippet}."""
        ...

    async def fetch_page(self, url: str, timeout: int = 15) -> Optional[str]:
        """Fetch content de uma URL."""
        ...
```

**Critério:** `WebSearchTool.search("iaglobal")` retorna resultados estruturados.

---

### 1.3 — `file_system.py` — File System Tool Segura

**Arquivo:** `iaglobal/mcp/file_system.py`

```python
from iaglobal.security.sandbox_rules import SandboxRules

class FileSystemTool:
    """Leitura/escrita segura via SandboxRules whitelist de paths."""

    ALLOWED_READ = {"iaglobal/", "tests/", "docs/", "memory/data/json/"}
    ALLOWED_WRITE = {"memory/data/json/", "memory/data/script/"}

    async def read_file(self, path: str) -> Optional[str]:
        """Lê arquivo se path está na whitelist."""
        ...

    async def write_file(self, path: str, content: str) -> bool:
        """Escreve arquivo se path está na whitelist."""
        ...

    async def list_dir(self, path: str) -> list[str]:
        """Lista diretório se path está na whitelist."""
        ...
```

**Critério:** `read_file("iaglobal/mcp/mcp_agent.py")` retorna conteúdo; `read_file("/etc/passwd")` é bloqueado.

---

### 1.4 — `code_executor.py` — Sandbox Wrapper

**Arquivo:** `iaglobal/mcp/code_executor.py`

```python
from iaglobal.security.sandbox_executor import SandboxExecutor

class CodeExecutorTool:
    """Wrapper MCP do SandboxExecutor para execução segura de código."""

    def __init__(self, timeout: int = 30):
        self.executor = SandboxExecutor(timeout=timeout)

    async def execute(self, code: str, language: str = "python") -> dict:
        """Executa código em sandbox isolado."""
        ...
```

**Critério:** `execute("print('hello')")` retorna `{"sucesso": True, "stdout": "hello"}`.

---

### 1.5 — `client.py` — Cliente MCP para Servidores Externos

**Arquivo:** `iaglobal/mcp/client.py`

```python
class MCPClient:
    """Conecta a servidores MCP externos (stdio ou SSE)."""

    async def connect_stdio(self, command: str, args: list[str]) -> dict:
        """Conecta via subprocess stdio."""
        ...

    async def connect_sse(self, url: str) -> dict:
        """Conecta via Server-Sent Events."""
        ...

    async def list_tools(self) -> list[dict]:
        """Lista tools do servidor conectado."""
        ...

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Chama uma tool do servidor conectado."""
        ...
```

**Critério:** `MCPClient().connect_stdio("python3", ["-m", "mcp_server"])` retorna lista de tools.

---

### 1.6 — `discovery.py` — Descoberta de Tools

**Arquivo:** `iaglobal/mcp/discovery.py`

```python
class MCPDiscovery:
    """Descoberta dinâmica de tools MCP internas e externas."""

    def __init__(self):
        self._tools_cache: dict = {}
        self._cache_path = PATH / "memory" / "data" / "json" / "mcp_tools.json"

    async def discover_all(self) -> dict:
        """Descobre tools de todos os servidores registrados."""
        ...

    async def get_tool(self, name: str) -> Optional[dict]:
        """Retorna schema de uma tool pelo nome."""
        ...
```

**Critério:** `MCPDiscovery().discover_all()` popula `mcp_tools.json` com tools disponíveis.

---

### 1.7 — Cache `mcp_tools.json`

**Arquivo:** `iaglobal/memory/data/json/mcp_tools.json`

Schema:
```json
{
  "version": 1,
  "updated_at": "ISO8601",
  "tools": [
    {
      "name": "metabolic_audit",
      "description": "...",
      "server": "internal",
      "parameters": {}
    }
  ]
}
```

---

## 🟠 Fase 2 — Integração com Agentes

### 2.1 — `tool_caller_agent.py`

**Arquivo:** `iaglobal/agents/tool_caller_agent.py`

Agente que recebe um plano de ação e decide qual tool MCP chamar baseado no schema do `MCPDiscovery`.

```python
class ToolCallerAgent(AgentBase):
    """Seleciona e chama tools MCP baseado no plano do orchestrator."""

    async def run(self, task: dict) -> dict:
        """Analisa task, seleciona tool, executa via discovery."""
        ...
```

**Integração com BanditPolicy:** cada chamada de tool registra `execution_metrics` com `success`, `latency`, `model` para o `JointOptimizationLoop`.

### 2.2 — Integração Chappie

- `IVMAxiom` registra custo de ATP das chamadas MCP (E=eficiência energética, C=cooperação)
- `VacuumDaemon` coleta logs de tools MCP na autofagia STM→LTM

### 2.3 — Validação de Schema em `validation/engine.py`

Adicionar validação de schema JSON contra schemas MCP:

```python
# Em iaglobal/validation/engine.py
class FeedbackEngine:
    def validate_mcp_call(self, tool_schema: dict, arguments: dict) -> bool:
        """Valida argumentos de chamada MCP contra schema da tool."""
        ...
```

---

## 🔴 Fase 3 — Segurança

### 3.1 — `security/mcp_sandbox.py`

**Arquivo:** `iaglobal/security/mcp_sandbox.py`

Sandbox específico para execução de tools MCP externas:

```python
class MCPSandbox:
    """Sandbox de tools MCP: whitelist de tools, rate limit, audit."""

    ALLOWED_TOOLS = {"search_web", "read_file", "write_file", "execute_code"}

    async def validate_call(self, tool_name: str, arguments: dict) -> bool:
        """Verifica se a tool está na whitelist."""
        ...

    async def audit_call(self, tool_name: str, arguments: dict, result: dict):
        """Registra chamada no audit trail."""
        ...
```

### 3.2 — Rate Limiting em `glutathione_guardrails.py`

Adicionar rate limiting por agente para chamadas MCP:

```python
# Em GlutathioneGuardrails
RATE_LIMITS = {
    "search_web": {"calls_per_minute": 10, "cooldown_seconds": 6},
    "execute_code": {"calls_per_minute": 5, "cooldown_seconds": 12},
}
```

### 3.3 — Audit Trail em `memory/data/json/audit.json`

Schema:
```json
{
  "audits": [
    {
      "timestamp": "ISO8601",
      "agent_id": "string",
      "tool": "string",
      "arguments": {},
      "result_summary": "string",
      "sandbox_decision": "allowed/blocked",
    }
  ]
}
```

---

## 📋 Ordem de Execução

| Ordem | Item | Arquivo | Esforço | Risco |
|-------|------|---------|---------|-------|
| 1 | 1.1 — `mcp_server.py` | `iaglobal/mcp/mcp_server.py` | Baixo | Baixo |
| 2 | 1.5 — `client.py` | `iaglobal/mcp/client.py` | Médio | Baixo |
| 3 | 1.2 — `search_web.py` | `iaglobal/mcp/search_web.py` | Médio | Baixo |
| 4 | 1.3 — `file_system.py` | `iaglobal/mcp/file_system.py` | Baixo | Baixo |
| 5 | 1.4 — `code_executor.py` | `iaglobal/mcp/code_executor.py` | Baixo | Baixo |
| 6 | 1.6 — `discovery.py` | `iaglobal/mcp/discovery.py` | Médio | Baixo |
| 7 | 1.7 — `mcp_tools.json` | `iaglobal/memory/data/json/mcp_tools.json` | Baixo | Baixo |
| 8 | 2.1 — `tool_caller_agent.py` | `iaglobal/agents/tool_caller_agent.py` | Alto | Médio |
| 9 | 2.2 — Integração Chappie | `iaglobal/chappie/` | Médio | Médio |
| 10 | 2.3 — Schema validation | `iaglobal/validation/engine.py` | Baixo | Baixo |
| 11 | 3.1 — `mcp_sandbox.py` | `iaglobal/security/mcp_sandbox.py` | Médio | Alto |
| 12 | 3.2 — Rate limiting | `iaglobal/immunity/glutathione_guardrails.py` | Baixo | Baixo |
| 13 | 3.3 — Audit trail | `iaglobal/memory/data/json/audit.json` | Baixo | Baixo |

---

## 🧪 Estratégia de Verificação

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
python -m pytest tests/ -q --tb=short

# Testes MCP específicos
python -c "from iaglobal.mcp.mcp_server import mcp; print('MCP server OK')"
python -c "from iaglobal.mcp.search_web import WebSearchTool; print('WebSearch OK')"
python -c "from iaglobal.mcp.file_system import FileSystemTool; print('FileSystem OK')"
python -c "from iaglobal.mcp.code_executor import CodeExecutorTool; print('CodeExecutor OK')"
python -c "from iaglobal.mcp.client import MCPClient; print('MCPClient OK')"
python -c "from iaglobal.mcp.discovery import MCPDiscovery; print('MCPDiscovery OK')"
```

---

## 🔭 Vetor Evolutivo (pós-MCP)

- Tools MCP externas permitem que iaglobal opere como orquestrador de serviços reais (não apenas gerador de código)
- Cache `mcp_tools.json` alimenta o `BanditPolicy` com opções de ferramentas, criando um grafo de decisão mais rico
- Audit trail em `audit.json` alimenta o `ImmuneMemoryExchange` com padrões de ataque via tools externas
- Próximo passo natural: `MCP Gateway` como membrana semi-permeável seletiva (Axioma 3 — Membrana Inteligente)

---

# 🟣 Colony Intelligence Communication

> **Objetivo:** Múltiplos organismos iaglobal colaborando como colônia — divisão de tarefas, comunicação entre organismos, seleção de fitness coletivo.

---

## 🔵 Fase 1 — Integração (AcetylcholineBus Estendido)

### Diagnóstico
O `AcetylcholineBus` atual roteia mensagens entre agentes do mesmo organismo. Não há:
- Campo `organism_id` nas mensagens para distinguir origem
- Tipos de mensagem para coordenação entre organismos (`task_offer`, `result_share`, `skill_handshake`)
- Roteamento multi-organismo no bus

| Componente | Status | Localização |
|------------|--------|-------------|
| `AgentMessage.organism_id` | ❌ ausente | `iaglobal/graphs/communication/acetylcholine_bus.py` |
| `task_offer` message_type | ❌ ausente | `iaglobal/graphs/communication/acetylcholine_bus.py` |
| `result_share` message_type | ❌ ausente | `iaglobal/graphs/communication/acetylcholine_bus.py` |
| `skill_handshake` message_type | ❌ ausente | `iaglobal/graphs/communication/acetylcholine_bus.py` |

---

### 1.1 — `organism_id` em AgentMessage

**Arquivo:** `iaglobal/graphs/communication/acetylcholine_bus.py`

```python
@dataclasses.dataclass
class AgentMessage:
    organism_id: str = "iaglobal"  # NOVO
    ...
```

O `AcetylcholineBus.emit()` passa a rotear também por `organism_id` quando o recipient for `"*"` ou channel específico.

### 1.2 — Tipos de Mensagem

| Tipo | Descrição | Payload Esperado |
|------|-----------|------------------|
| `task_offer` | Um organismo oferece subtarefa para outro | `{task_id, description, required_skills, reward_ivm}` |
| `result_share` | Um organismo devolve resultado processado | `{task_id, result, metrics, ivm_contribution}` |
| `skill_handshake` | Troca de capacidades entre organismos | `{organism_id, skills: [...], lineage_marker}` |

### 1.3 — Roteamento Multi-Organismo

```python
class AcetylcholineBus:
    async def emit(self, message: AgentMessage):
        # NOVO: rotear também por organism_id
        listeners = (
            list(self._subscribers[message.recipient]) +
            list(self._subscribers[message.message_type]) +
            list(self._subscribers.get(f"org:{message.organism_id}", set())) +
            list(self._subscribers["*"])
        )
```

**Critério:** Organismo `"alpha"` envia `task_offer` → organismo `"beta"` inscrito em `"org:beta"` recebe a mensagem.

---

## 🟠 Fase 2 — Divisão de Trabalho

### 2.1 — `communication/queen.py` — Rainha da Colônia

**Arquivo:** `iaglobal/communication/queen.py`

A Rainha recebe uma tarefa grande e a divide em subtarefas especializadas:

```python
class ColonyQueen:
    """Divide tarefas grandes em subtarefas e distribui para worker organisms."""

    def __init__(self, organism_id: str = "queen"):
        self.organism_id = organism_id
        self._pending_tasks: dict[str, list[dict]] = {}
        self._completed: dict[str, list[dict]] = {}

    async def decompose(self, super_task: dict) -> list[dict]:
        """Decompõe tarefa grande em subtarefas atômicas."""
        ...

    async def assign(self, subtasks: list[dict], workers: list[str]):
        """Distribui subtarefas via task_offer nos workers disponíveis."""
        ...

    async def collect(self, task_id: str) -> list[dict]:
        """Aguarda todos os resultados das subtarefas."""
        ...
```

### 2.2 — `communication/worker.py` — Trabalhador da Colônia

**Arquivo:** `iaglobal/communication/worker.py`

```python
class ColonyWorker:
    """Executa subtarefas especializadas e reporta resultados."""

    def __init__(self, organism_id: str, skills: list[str]):
        self.organism_id = organism_id
        self.skills = skills

    async def accept_task(self, offer: dict) -> bool:
        """Aceita tarefa se tem as skills necessárias."""
        ...

    async def execute(self, task: dict) -> dict:
        """Executa subtarefa e retorna resultado com métricas."""
        ...
```

### 2.3 — `communication/integrator.py` — Integrador de Resultados

**Arquivo:** `iaglobal/communication/integrator.py`

Junta resultados parciais em artefato final e alimenta evolução:

```python
class ColonyIntegrator:
    """Junta resultados de workers e alimenta evolução + obsidian."""

    async def integrate(self, task_id: str, results: list[dict]) -> dict:
        """Combina resultados parciais em artefato final."""
        ...

    async def feed_evolution(self, task_id: str, final_result: dict):
        """Registra aprendizado no Obsidian e alimenta evolution engine."""
        ...

    async def feed_obsidian(self, organism_id: str, result: dict):
        """Escreve resultado consolidado no vault Obsidian."""
        ...
```

**Critério:** Queen → 3 Workers → Integrator produzem artefato final em menos tempo que 1 organismo sozinho.

---

## 🔴 Fase 3 — Seleção de Fitness entre Organismos

### 3.1 — IVM Independente por Organismo

Cada organismo mantém seu próprio `IVMAxiom` com métricas independentes:

```python
class ColonyFitness:
    """Avalia fitness de múltiplos organismos na colônia."""

    def get_organism_ivm(self, organism_id: str) -> float:
        """Retorna IVM independente do organismo."""
        ...

    def rank_organisms(self) -> list[dict]:
        """Ranking dos organismos por IVM."""
        ...
```

### 3.2 — Apoptose para IVM < Threshold

Organismos com IVM abaixo do threshold são sacrificados:

| Threshold | Ação |
|-----------|------|
| IVM ≥ 0.7 | Saudável — pode participar de mitose |
| 0.3 ≤ IVM < 0.7 | Monitoramento — recebe tarefas mais simples |
| IVM < 0.3 | Apoptose — organismo eliminado, lições extraídas |

### 3.3 — Mitose de Organismos Saudáveis

Organismos com IVM ≥ 0.7 podem gerar novos organismos (mitose):

```python
async def mitosis(parent_organism_id: str, specialization: str) -> str:
    """Cria novo organismo a partir de um saudável, com diferenciação."""
    ...
```

### 3.4 — Integração com ApoptosisEngine + MitosisEngine

Reutilizar `ApoptosisEngine` (já existente em `iaglobal/immunity/apoptosis_engine.py`) e `AgentMitosisEngine` (em `iaglobal/agents/mitosis_engine.py`), mas operando no nível de **organismo** (não de agente).

**Critério:** 3 organismos colaboram em 1 tarefa maior que a capacidade individual — IVM médio da colônia > IVM individual de cada um.

---

## 📋 Ordem de Execução

| Ordem | Item | Arquivo | Esforço | Risco |
|-------|------|---------|---------|-------|
| 1 | 1.1 — `organism_id` em AgentMessage | `acetylcholine_bus.py` | Baixo | Baixo |
| 2 | 1.2 — Novos message_types | `acetylcholine_bus.py` | Baixo | Baixo |
| 3 | 1.3 — Roteamento multi-organismo | `acetylcholine_bus.py` | Baixo | Baixo |
| 4 | 2.1 — `queen.py` | `iaglobal/communication/queen.py` | Alto | Médio |
| 5 | 2.2 — `worker.py` | `iaglobal/communication/worker.py` | Alto | Médio |
| 6 | 2.3 — `integrator.py` | `iaglobal/communication/integrator.py` | Alto | Médio |
| 7 | 3.1 — ColonyFitness | `iaglobal/communication/fitness.py` | Médio | Baixo |
| 8 | 3.2 — Apoptose por organismo | `iaglobal/communication/fitness.py` | Médio | Médio |
| 9 | 3.3 — Mitose por organismo | `iaglobal/communication/fitness.py` | Médio | Médio |

---

## 🧪 Estratégia de Verificação

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
python -m pytest tests/test_colony_intelligence.py -v --tb=short
python -m pytest tests/ -q --tb=short
```

### Cenários de Teste

| Teste | Descrição |
|-------|-----------|
| `test_agent_message_organism_id` | Mensagem carrega organism_id corretamente |
| `test_message_type_task_offer` | task_offer é roteada para organismos inscritos |
| `test_message_type_result_share` | result_share é recebido pelo caller |
| `test_queen_decompose` | Queen divide tarefa em ≥2 subtarefas |
| `test_worker_accept_by_skills` | Worker aceita só tarefas compatíveis com suas skills |
| `test_integrator_merge` | Integrator combina N resultados em 1 artefato |
| `test_integrator_feed_evolution` | Integrator registra aprendizado no Obsidian |
| `test_colony_fitness_ivm` | Fitness calcula IVM independente por organismo |
| `test_colony_apoptosis_low_ivm` | Organismo com IVM < 0.3 é eliminado |
| `test_colony_mitosis_high_ivm` | Organismo com IVM ≥ 0.7 gera filho |
| `test_e2e_three_organisms` | 3 organismos colaboram em tarefa maior que individual |

---

## 🔭 Vetor Evolutivo (pós-Colônia)

- Colônia de organismos especializados permite execução paralela real de tarefas complexas
- Ranking de fitness entre organismos cria pressão seletiva natural para evolução
- Memória imunológica compartilhada entre organismos via `ImmuneMemoryExchange`
- Próximo passo: `Swarm Intelligence` — organismos que se auto-organizam sem rainha central

---

# 🟡 PhospholipidRegistry — Load Balancing Dinâmico

> **Objetivo:** Balanceamento de carga dinâmico em nível de serviço, com descoberta, weighted round-robin, detecção de falhas e recuperação automática.

---

## 🔵 Fase 1 — Descoberta de Serviços

| Componente | Status | Localização |
|------------|--------|-------------|
| `registry.py` | ❌ ausente | `iaglobal/observability/registry.py` |
| Heartbeat via `health.py` (5s) | ❌ ausente | `iaglobal/observability/registry.py` |
| Campos: endpoint, peso, saúde, capacidade | ❌ ausente | `iaglobal/observability/registry.py` |

### 1.1 — `registry.py` — Registro de Serviços

**Arquivo:** `iaglobal/observability/registry.py`

```python
@dataclass
class ServiceInstance:
    name: str
    endpoint: str
    weight: float = 1.0      # peso para balanceamento
    health: bool = True       # saudável?
    capacity: int = 10        # requisições simultâneas máximas
    active_requests: int = 0  # reqs em andamento
    last_heartbeat: float = 0.0
    latency_p95_ms: float = 0.0
    error_rate: float = 0.0
```

Heartbeat a cada 5s atualiza `last_heartbeat`. Se ausente por >15s, serviço marcado como `unhealthy`.

---

## 🟠 Fase 2 — Balanceamento

| Componente | Status | Localização |
|------------|--------|-------------|
| `load_balancer.py` | ❌ ausente | `iaglobal/observability/load_balancer.py` |
| Algoritmo: weighted round-robin com adaptive decay | ❌ ausente | `iaglobal/observability/load_balancer.py` |
| Integração com `chappie` | ❌ ausente | `iaglobal/observability/load_balancer.py` |

### 2.1 — `load_balancer.py` — Weighted Round-Robin com Adaptive Decay

**Arquivo:** `iaglobal/observability/load_balancer.py`

Algoritmo:
1. Lista serviços saudáveis ordenados por peso
2. Seleciona via weighted round-robin (pesos decaem com falhas)
3. Adaptive decay: cada falha reduz peso em 20% (mínimo 0.1)
4. Cada sucesso aumenta peso em 5% (máximo 1.0)

Integração com `chappie/ivm_axiom.py`: o IVM do agente serve como peso inicial.
Integração com `critic_agent`: o `critic_agent` usa o load balancer para selecionar provider.

---

## 🔴 Fase 3 — Falha e Recuperação

| Componente | Status | Localização |
|------------|--------|-------------|
| Detecção unhealthy via `glutathione_pool` | ❌ ausente | `iaglobal/observability/load_balancer.py` |
| Remoção automática do pool | ❌ ausente | `iaglobal/observability/registry.py` |
| Reintrodução após recuperação | ❌ ausente | `iaglobal/observability/registry.py` |

### 3.1 — Ciclo de Falha e Recuperação

```
Serviço falha N vezes consecutivas
    ↓
GlutathionePool.respond("service_failure", {...})
    ↓
Peso reduzido via adaptive decay
    ↓
Se peso < 0.2 → serviço marcado unhealthy → removido do pool
    ↓
Heartbeat contínuo (5s) monitora recuperação
    ↓
Se 3 heartbeats consecutivos OK → reintroduz com peso 0.5
    ↓
Peso retorna gradualmente ao original via sucessos
```

---

## 🟢 Fase 4 — Observabilidade

| Componente | Status | Localização |
|------------|--------|-------------|
| Dashboard | ❌ ausente | `iaglobal/dashboard/phospholipid_dashboard.py` |
| Métricas: requests/s, latency p95, error rate | ❌ ausente | `iaglobal/dashboard/phospholipid_dashboard.py` |
| Audit trail | ❌ ausente | `iaglobal/memory/data/json/phospholipid_audit.json` |

### 4.1 — Dashboard

```python
class PhospholipidDashboard:
    """Dashboard de métricas do PhospholipidRegistry."""

    def summary(self) -> dict:
        """Retorna resumo: serviços ativos, requests/s, latência p95, error rate."""
        ...

    def render_text(self) -> str:
        """Renderiza dashboard em formato texto para CLI."""
        ...
```

### 4.2 — Audit Trail

**Arquivo:** `iaglobal/memory/data/json/phospholipid_audit.json`

```json
{
  "events": [
    {
      "timestamp": "ISO8601",
      "event": "service_registered / health_changed / request_routed / failure_detected / recovery",
      "service": "string",
      "details": {}
    }
  ]
}
```

---

## 📋 Ordem de Execução

| Ordem | Item | Arquivo | Esforço | Risco |
|-------|------|---------|---------|-------|
| 1 | 1.1 — `registry.py` | `iaglobal/observability/registry.py` | Médio | Baixo |
| 2 | 1.2 — Heartbeat (5s) | `iaglobal/observability/registry.py` | Baixo | Baixo |
| 3 | 2.1 — `load_balancer.py` | `iaglobal/observability/load_balancer.py` | Alto | Médio |
| 4 | 2.2 — Chappie integration | `iaglobal/observability/load_balancer.py` | Baixo | Baixo |
| 5 | 3.1 — GlutathionePool falha | `iaglobal/observability/load_balancer.py` | Baixo | Baixo |
| 6 | 3.2 — Remoção/reintrodução | `iaglobal/observability/registry.py` | Médio | Médio |
| 7 | 4.1 — Dashboard | `iaglobal/dashboard/phospholipid_dashboard.py` | Médio | Baixo |
| 8 | 4.2 — Audit trail | `iaglobal/memory/data/json/phospholipid_audit.json` | Baixo | Baixo |

---

## 🧪 Estratégia de Verificação

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
python -m pytest tests/test_phospholipid_registry.py -v --tb=short
python -m pytest tests/ -q --tb=short
```

### Cenários de Teste

| Teste | Descrição |
|-------|-----------|
| `test_register_service` | Serviço é registrado com campos corretos |
| `test_heartbeat_updates` | Heartbeat atualiza last_heartbeat |
| `test_heartbeat_timeout` | Heartbeat >15s marca unhealthy |
| `test_weighted_round_robin` | Serviços com peso maior recebem mais reqs |
| `test_adaptive_decay` | Falhas reduzem peso gradualmente |
| `test_remove_unhealthy` | Serviço unhealthy é removido do pool |
| `test_reintroduce_after_recovery` | Serviço recuperado volta ao pool |
| `test_dashboard_summary` | Dashboard retorna métricas agregadas |
| `test_audit_trail` | Eventos são registrados no audit.json |
| `test_integration_chappie` | Load balancer usa IVM como peso inicial |
| `test_e2e_two_services` | 2 serviços com balanceamento + falha + redistribuição |

---

## 🔭 Vetor Evolutivo (pós-Phospholipid)

- Substituto natural para `BanditPolicy` em cenários multi-serviço
- `PhospholipidRegistry` como membrana entre organismos na colônia
- Métricas históricas alimentam `Genetic Algorithm` para otimização de pesos (ver seção abaixo)
- Integração com `MembraneKey` para autenticação de serviços externos

---

# 🟢 Genetic Algorithm Tuning — Otimização Evolutiva dos Pesos IVM

> **Objetivo:** Otimizar os pesos do IVM (Índice de Viabilidade Metabólica) via seleção natural. Cada geração testa uma combinação de `[P, E, C, I]`, avalia o fitness via métricas reais do `BanditPolicy`, e evolui a população através de crossover e mutação.

**Arquivos:**

| Módulo | Caminho | Função |
|--------|---------|--------|
| `population.py` | `iaglobal/evolution/ga/population.py` | Indivíduo `[P, E, C, I]`, população 50, clamp |
| `selector.py` | `iaglobal/evolution/ga/selector.py` | Torneio, BLX-α crossover, mutação gaussiana |
| `ga_runner.py` | `iaglobal/evolution/ga/ga_runner.py` | Ciclo evolutivo, persistência, epigenética |
| Testes | `tests/test_ga_tuning.py` | 33 testes de unidade + persistência |

**Arquivos de Dados:**

| Arquivo | Localização |
|---------|-------------|
| Melhor genoma | `iaglobal/memory/data/json/best_genome.json` |
| Telemetria | `iaglobal/memory/data/json/ga_telemetry.json` |

---

## 🔵 Fase 1 — Instrumentação

**Problema:** O `genomic_reflection.py` não exporta métricas estruturadas de IVM para o observability system. Sem telemetria consistente, o GA não tem um sinal de fitness confiável.

**Correção:** O `GARunner._compute_fitness_from_metrics()` lê dados do `BanditPolicy` diretamente — usa `rewards` por modelo e `CreditAssignmentEngine` stats para calcular:

```
fitness = (P_contrib × 0.5) + (E_contrib × 0.3) + (C_contrib × 0.2)

P_contrib = sum(recent_rewards) × IVM_P
E_contrib = (1 / max(0.1, len(recent))) × IVM_E
C_contrib = (total_calls / max(1, unique_stats)) × IVM_C × 0.01
```

**Critério:** Fitness ∈ [0.0, 1.0] calculado sem exceções.

---

## 🟠 Fase 2 — Population

**Arquivo:** `iaglobal/evolution/ga/population.py`

Os indivíduos são vetores `[P, E, C, I]` com bounds `[0.0, 1.0]`:

```python
@dataclass
class Individual:
    weights: list[float]  # [P, E, C, I]
    fitness: float = 0.0
    generation: int = 0

    def clamp(self, lo=0.0, hi=1.0):
        for i in range(len(self.weights)):
            self.weights[i] = max(lo, min(hi, self.weights[i]))
```

A `Population` gerencia 50 indivíduos, calcula `best()`, `avg_fitness()`, `top_n()`.

**Critério:** População inicial de 50 indivíduos com pesos aleatórios uniformes.

---

## 🔴 Fase 3 — Seleção e Cruzamento

**Arquivo:** `iaglobal/evolution/ga/selector.py`

| Operador | Função | Parâmetros |
|----------|--------|------------|
| Torneio | `tournament_select()` | `tournament_size=3` |
| Crossover BLX-α | `blend_crossover()` | `alpha=0.5` |
| Mutação Gaussiana | `gaussian_mutate()` | `rate=0.15`, `sigma=0.05` |
| Evolução completa | `evolve_population()` | `elite_ratio=0.2` |

```python
def evolve_population(population, elite_ratio=0.2, ...):
    elite = sorted_pop[:elite_count]       # top 20% preservados
    while len(child) < pop_size:
        p1 = tournament_select(population) # torneio
        p2 = tournament_select(population)
        child = blend_crossover(p1, p2)    # BLX-α
        gaussian_mutate(child)             # mutação
        new_pop.append(child)
```

**Critério:** Elitismo preserva top 20%, crossover gera filhos com variação controlada.

---

## 🟢 Fase 4 — Ciclo Evolutivo

**Arquivo:** `iaglobal/evolution/ga/ga_runner.py`

O `GARunner` gerencia o ciclo completo:

1. **Inicialização:** Carrega genoma salvo ou cria 50 indivíduos aleatórios
2. **Fitness:** Para cada indivíduo, `_compute_fitness_from_metrics()` consulta BanditPolicy
3. **Evolução:** Aplica `evolve_population()` com elitismo 20%
4. **Persistência:** Salva `best_genome.json` com melhor indivíduo
5. **Telemetria:** Acumula histórico em `ga_telemetry.json`
6. **Epigenética:** Aplica pesos via `set_flag("ga_weight_P", valor)`

**Hook automático:** `runner.task_hook()` é chamado a cada `GENERATION_INTERVAL=10` tasks do pipeline.

```python
# No pipeline (ex: após cada execução):
from iaglobal.evolution.ga.ga_runner import runner
runner.task_hook()  # a cada 10 chamadas, evolui 1 geração
```

**Critério de conclusão:** IVM médio sobe 10% após 100 gerações.

---

### 📋 Ordem de Execução

| Passo | Ação | Verificação |
|-------|------|-------------|
| 1 | `GARunner().ensure_initialized()` | População de 50 indivíduos criada ou carregada |
| 2 | `runner.step()` | 1 geração: fitness + seleção + crossover + mutação |
| 3 | `runner.run_n_generations(10)` | 10 gerações consecutivas |
| 4 | Verificar `best_genome.json` | Pesos `[P, E, C, I]` salvos |
| 5 | Verificar `ga_telemetry.json` | `generations`, `best_fitness_history` |
| 6 | `get_flag("ga_weight_P")` | Pesos aplicados na epigenética |
| 7 | `runner.task_hook()` × 10 | Hook automático a cada 10 tasks |

---

### 🧪 Estratégia de Verificação

```python
# test_ga_tuning.py (33 testes)

# Phase 1: Individual
test_default_weights           # [0,0,0,0]
test_properties                # ivm_p, ivm_e, ivm_c, ivm_i
test_clamp_lower/upper         # bounds [0,1]
test_to_dict                   # {"P": 0.46, "E": 0.3, ...}
test_fitness_default           # 0.0

# Phase 2: Population
test_initialize_default_size   # 50 indivíduos
test_best                      # fitness máximo
test_avg_fitness               # média da população
test_top_n                     # top N por fitness

# Phase 3: Selection
test_tournament_select         # melhor do torneio
test_blend_crossover           # filho com variação
test_gaussian_mutate            # mutação altera pesos
test_evolve_population         # tamanho preservado, elite mantida

# Phase 4: GA Runner
test_step                      # resultado com best_weights/generation
test_run_n_generations         # N = 3
test_task_hook                 # dispara a cada 10 chamadas
test_persist_genome            # best_genome.json salvo
test_persist_telemetry         # ga_telemetry.json salvo
test_apply_epigenetic          # get_flag("ga_weight_P")
test_clone_genome              # carregar população do genoma salvo
```

---

### 🔭 Vetor Evolutivo (pós-GA)

- `Adaptive IVM Weight` — pesos evoluem em tempo real sem reinicialização
- `Multi-objective GA` — Pareto front entre P, E, C, I ao invés de fitness único
- `GA + BanditPolicy híbrido` — ε-greedy usa os pesos evoluídos como prior
- `Island Model` — múltiplas populações evoluindo em paralelo em diferentes provedores

---

# 🔮 Autonomous Research Loop — Leitura, Síntese e Validação Automática de Papers

> **Objetivo:** O organismo lê papers científicos, extrai hipóteses testáveis e valida automaticamente via experimentação em sandbox — ciclo completo sem intervenção humana.

---

## 🔵 Fase 1 — Ingestão

| Componente | Status | Localização |
|------------|--------|-------------|
| `paper_ingestor.py` | ❌ ausente | `iaglobal/agents/ingestion/paper_ingestor.py` |
| Integração com `file_ingestion_agent.py` | ❌ ausente | `iaglobal/agents/ingestion/` |
| `paper_parser.py` | ❌ ausente | `iaglobal/agents/ingestion/paper_parser.py` |
| `research_queue.json` | ❌ ausente | `iaglobal/memory/data/json/research_queue.json` |

### 1.1 — `paper_ingestor.py`: Download de PDFs/HTML

**Arquivo:** `iaglobal/agents/ingestion/paper_ingestor.py`

```python
class PaperIngestor(AgentBase):
    """Baixa papers de repositórios públicos (arXiv, PubMed, Hugging Face)."""

    REPOSITORIES = {
        "arxiv": "https://arxiv.org/abs/",
        "pubmed": "https://pubmed.ncbi.nlm.nih.gov/",
        "hf": "https://huggingface.co/papers/",
    }

    async def ingest(self, paper_id: str, repository: str = "arxiv") -> Path:
        """Baixa paper e retorna caminho do arquivo local."""
        ...
```

**Fontes suportadas:**
- arXiv (CS, AI, ML)
- PubMed (biologia computacional)
- Hugging Face Papers
- RSS feeds de conferências (NeurIPS, ICML, ICLR)

### 1.2 — Integração com `file_ingestion_agent.py`

**Arquivo:** `iaglobal/agents/ingestion/file_ingestion_agent.py`

O `file_ingestion_agent.py` existente ganha suporte a PDF/HTML:

```python
# Adicionar no file_ingestion_agent.py
SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".txt", ".md"}

async def extract_text_from_pdf(path: Path) -> str:
    """Extrai texto de PDF via pymupdf ou pdfplumber."""
    ...
```

### 1.3 — `paper_parser.py`: Extração de Abstracts e Metadados

**Arquivo:** `iaglobal/agents/ingestion/paper_parser.py`

```python
@dataclass
class PaperMetadata:
    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    published_date: str
    repository: str
    topics: list[str]
    full_text: Optional[str] = None

class PaperParser:
    """Extrai metadados e abstract de paper."""

    async def parse(self, text: str, paper_id: str) -> PaperMetadata:
        """Extrai metadados via LLM + regex."""
        ...
```

**Campos extraídos:**
- Título, autores, data
- Abstract (obrigatório)
- Tópicos/keywords
- Texto completo (se disponível)

### 1.4 — Fila de Pesquisa `research_queue.json`

**Arquivo:** `iaglobal/memory/data/json/research_queue.json`

Schema:
```json
{
  "queue": [
    {
      "paper_id": "arxiv:2401.12345",
      "status": "pending|ingested|parsed|hypothesized|validated|consolidated",
      "metadata": {...},
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ],
  "stats": {
    "total": 0,
    "pending": 0,
    "completed": 0
  }
}
```

**Critério:** Paper baixado → fila atualizada → status `ingested`.

---

## 🟠 Fase 2 — Síntese

| Componente | Status | Localização |
|------------|--------|-------------|
| `hypothesis_generator.py` | ❌ ausente | `iaglobal/agents/ingestion/hypothesis_generator.py` |
| Prompt template | ❌ ausente | `iaglobal/agents/ingestion/hypothesis_generator.py` |
| Validação via `validation/engine.py` | ❌ ausente | `iaglobal/validation/engine.py` |

### 2.1 — `hypothesis_generator.py`: Geração de Hipóteses

**Arquivo:** `iaglobal/agents/ingestion/hypothesis_generator.py`

```python
class HypothesisGenerator(AgentBase):
    """Gera hipóteses testáveis a partir de abstracts."""

    PROMPT_TEMPLATE = """
Dado este abstract de paper científico:

{abstract}

Proponha 3 hipóteses testáveis que poderiam ser validadas via:
1. Experimento computacional (código Python)
2. Análise de dados existentes
3. Simulação

Formato de saída (JSON):
{{
  "hypotheses": [
    {{
      "id": "H1",
      "description": "...",
      "method": "experiment|data_analysis|simulation",
      "expected_outcome": "...",
      "success_criteria": "..."
    }}
  ]
}}
"""

    async def generate(self, paper: PaperMetadata) -> list[dict]:
        """Gera 3 hipóteses testáveis."""
        ...
```

### 2.2 — Saída em `memory/data/json/{paper_id}.json`

**Schema:**
```json
{
  "paper_id": "arxiv:2401.12345",
  "hypotheses": [
    {
      "id": "H1",
      "description": "...",
      "method": "experiment",
      "expected_outcome": "...",
      "success_criteria": "...",
      "status": "pending|running|passed|failed"
    }
  ],
  "generated_at": "ISO8601"
}
```

### 2.3 — Validação via `validation/engine.py`

**Arquivo:** `iaglobal/validation/engine.py`

Adicionar validação de hipóteses:

```python
class FeedbackEngine:
    def validate_hypothesis(self, hypothesis: dict) -> bool:
        """Valida se hipótese é testável (tem método + critérios)."""
        required = {"description", "method", "success_criteria"}
        return required.issubset(hypothesis.keys())
```

**Critério:** 1 paper → 3 hipóteses geradas → validadas → salvas.

---

## 🔴 Fase 3 — Validação

| Componente | Status | Localização |
|------------|--------|-------------|
| `experiment_runner.py` | ❌ ausente | `iaglobal/agents/ingestion/experiment_runner.py` |
| Integração com `execution/sandbox.py` | ❌ ausente | `iaglobal/agents/ingestion/experiment_runner.py` |
| Métricas por hipótese | ❌ ausente | `iaglobal/memory/data/json/{hypothesis_id}.json` |
| Reward via `ivm_axiom.py` | ❌ ausente | `iaglobal/chappie/ivm_axiom.py` |

### 3.1 — `experiment_runner.py`: Execução em Sandbox

**Arquivo:** `iaglobal/agents/ingestion/experiment_runner.py`

```python
class ExperimentRunner(AgentBase):
    """Executa experimentos para validar hipóteses."""

    async def run_experiment(self, hypothesis: dict) -> dict:
        """Gera código e executa em sandbox."""
        code = await self._generate_code(hypothesis)
        result = await self._execute_in_sandbox(code)
        return self._evaluate(result, hypothesis)

    async def _generate_code(self, hypothesis: dict) -> str:
        """Gera código Python para testar hipótese."""
        ...

    async def _execute_in_sandbox(self, code: str) -> dict:
        """Executa código em sandbox isolado."""
        from iaglobal.security.sandbox_executor import SandboxExecutor
        executor = SandboxExecutor(timeout=60)
        return await executor.execute(code)
```

### 3.2 — Métricas em `{hypothesis_id}.json`

**Arquivo:** `iaglobal/memory/data/json/H1_arxiv2401_12345.json`

Schema:
```json
{
  "hypothesis_id": "H1",
  "paper_id": "arxiv:2401.12345",
  "experiment_code": "...",
  "execution_result": {
    "success": true,
    "stdout": "...",
    "stderr": "",
    "metrics": {...}
  },
  "validation": {
    "passed": true,
    "confidence": 0.85,
    "notes": "..."
  },
  "executed_at": "ISO8601"
}
```

### 3.3 — Reward para Chappie via `ivm_axiom.py`

**Arquivo:** `iaglobal/chappie/ivm_axiom.py`

Cada hipótese validada com sucesso gera reward:

```python
# No ExperimentRunner, após validação:
if result["validation"]["passed"]:
    from iaglobal.chappie.ivm_axiom import IVMAxiom
    ivm = IVMAxiom()
    ivm.registrar_sucesso(
        agent_id="experiment_runner",
        task_id=hypothesis["id"],
        confidence=result["validation"]["confidence"]
    )
```

**Critério:** 1 hipótese → código gerado → executado → validado → reward registrado.

---

## 🟢 Fase 4 — Consolidação

| Componente | Status | Localização |
|------------|--------|-------------|
| `consolidation.py` | ❌ ausente | `iaglobal/agents/ingestion/consolidation.py` |
| Integração com Obsidian `03_Long_Term/` | ❌ ausente | `iaglobal/agents/ingestion/consolidation.py` |
| Tags por tópico | ❌ ausente | `iaglobal/obsidian/subconsciousapi.py` |

### 4.1 — `consolidation.py`: Resultados → Conhecimento

**Arquivo:** `iaglobal/agents/ingestion/consolidation.py`

```python
class ResearchConsolidator(AgentBase):
    """Consolida resultados em conhecimento de longo prazo."""

    async def consolidate(self, paper: PaperMetadata, results: list[dict]) -> Path:
        """Gera nota Obsidian com paper + hipóteses + resultados."""
        content = self._generate_markdown(paper, results)
        return await self._write_to_obsidian(content, paper)

    def _generate_markdown(self, paper: PaperMetadata, results: list[dict]) -> str:
        """Gera markdown estruturado."""
        validated = [r for r in results if r["validation"]["passed"]]
        return f"""---
id: "{paper.paper_id}"
tipo: "PaperValidado"
topics: [{", ".join(f'"{t}"' for t in paper.topics)}]
fitness_score: {len(validated) / len(results):.2f}
---

# {paper.title}

## Metadados
- **Autores**: {", ".join(paper.authors)}
- **Data**: {paper.published_date}
- **Repositório**: {paper.repository}

## Abstract
{paper.abstract}

## Hipóteses Validadas
{self._format_hypotheses(validated)}

## Conclusão
{len(validated)}/{len(results)} hipóteses validadas.
"""
```

### 4.2 — Integração com Obsidian `03_Long_Term/`

**Arquivo:** `iaglobal/obsidian/subconsciousapi.py`

```python
# No consolidator:
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

sub = SubconsciousAPI()
await sub.escrever_longo_prazo(
    nome=paper.paper_id.replace(":", "_"),
    conteudo=content,
    tipo="PaperValidado",
    tags=paper.topics,
    fitness_score=len(validated) / len(results),
)
```

### 4.3 — Tags por Tópico

Cada paper consolidado recebe tags dos tópicos extraídos:
- `#machine_learning`
- `#genetic_algorithms`
- `#evolutionary_computation`
- `#metabolic_architecture`

**Critério:** Paper → consolidado → Obsidian `03_Long_Term/` → tags indexadas.

---

## 📋 Ordem de Execução

| Ordem | Item | Arquivo | Esforço | Risco |
|-------|------|---------|---------|-------|
| 1 | 1.1 — `paper_ingestor.py` | `iaglobal/agents/ingestion/paper_ingestor.py` | Médio | Baixo |
| 2 | 1.2 — PDF/HTML support | `iaglobal/agents/ingestion/file_ingestion_agent.py` | Baixo | Baixo |
| 3 | 1.3 — `paper_parser.py` | `iaglobal/agents/ingestion/paper_parser.py` | Médio | Baixo |
| 4 | 1.4 — `research_queue.json` | `iaglobal/memory/data/json/` | Baixo | Baixo |
| 5 | 2.1 — `hypothesis_generator.py` | `iaglobal/agents/ingestion/hypothesis_generator.py` | Alto | Médio |
| 6 | 2.2 — Schema JSON | `iaglobal/memory/data/json/` | Baixo | Baixo |
| 7 | 2.3 — Validação | `iaglobal/validation/engine.py` | Baixo | Baixo |
| 8 | 3.1 — `experiment_runner.py` | `iaglobal/agents/ingestion/experiment_runner.py` | Alto | Alto |
| 9 | 3.2 — Métricas | `iaglobal/memory/data/json/` | Baixo | Baixo |
| 10 | 3.3 — Reward IVM | `iaglobal/chappie/ivm_axiom.py` | Baixo | Baixo |
| 11 | 4.1 — `consolidation.py` | `iaglobal/agents/ingestion/consolidation.py` | Alto | Baixo |
| 12 | 4.2 — Obsidian LTM | `iaglobal/obsidian/subconsciousapi.py` | Baixo | Baixo |
| 13 | 4.3 — Tags | `iaglobal/obsidian/subconsciousapi.py` | Baixo | Baixo |

---

## 🧪 Estratégia de Verificação

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate

# Testes de ingestão
python -c "from iaglobal.agents.ingestion.paper_ingestor import PaperIngestor; print('Ingestor OK')"
python -c "from iaglobal.agents.ingestion.paper_parser import PaperParser; print('Parser OK')"

# Testes de síntese
python -c "from iaglobal.agents.ingestion.hypothesis_generator import HypothesisGenerator; print('Hypothesis OK')"

# Testes de validação
python -c "from iaglobal.agents.ingestion.experiment_runner import ExperimentRunner; print('Runner OK')"

# Testes de consolidação
python -c "from iaglobal.agents.ingestion.consolidation import ResearchConsolidator; print('Consolidator OK')"

# Testes end-to-end
python -m pytest tests/test_autonomous_research_loop.py -v --tb=short
```

### Cenários de Teste

| Teste | Descrição |
|-------|-----------|
| `test_ingest_arxiv_paper` | Baixa paper do arXiv |
| `test_parse_abstract` | Extrai abstract + metadados |
| `test_generate_3_hypotheses` | Gera 3 hipóteses testáveis |
| `test_validate_hypothesis_schema` | Valida schema de hipótese |
| `test_run_experiment_sandbox` | Executa código em sandbox |
| `test_evaluate_hypothesis` | Avalia resultado vs critérios |
| `test_consolidate_to_obsidian` | Escreve nota em `03_Long_Term/` |
| `test_e2e_full_loop` | 1 paper → 3 hipóteses → 1 experimento → Obsidian |

---

## 🔭 Vetor Evolutivo (pós-Research Loop)

- **Auto-curadoria**: Papers com baixo fitness (0/3 hipóteses validadas) são marcados como "baixa qualidade"
- **Recomendação ativa**: Sistema sugere novos papers baseado em tópicos de alto fitness
- **Citação cruzada**: Papers consolidados linkam entre si via `[[paper_id]]` no Obsidian
- **Meta-análise**: Após N papers, sistema gera review automático de tendências
- **Colaboração externa**: Papers validados podem ser compartilhados via `ImmuneMemoryExchange` com outros nós iaglobal

---

## ✅ Critério de Conclusão

**1 paper → 3 hipóteses → 1 experimento → persistência sem intervenção.**

| Etapa | Critério | Status |
|-------|----------|--------|
| Ingestão | Paper baixado + fila atualizada | ✅ COMPLETO |
| Síntese | 3 hipóteses geradas + validadas | ✅ COMPLETO |
| Validação | 1+ experimento executado + resultado registrado | ✅ COMPLETO |
| Consolidação | Nota Obsidian em `03_Long_Term/` com tags | ✅ COMPLETO |
| E2E Pipeline | Pipeline completo sem intervenção | ✅ COMPLETO |

---

## 📊 Resumo Final — Autonomous Research Loop

| Fase | Arquivos Criados | Testes | Status |
|------|------------------|--------|--------|
| **1. Ingestão** | `paper_ingestor.py`, `paper_parser.py` | 9 | ✅ |
| **2. Síntese** | `hypothesis_generator.py` | 16 | ✅ |
| **3. Validação** | `experiment_runner.py` | 17 | ✅ |
| **4. Consolidação** | `consolidation.py` | 12 | ✅ |
| **5. E2E Pipeline** | `test_autonomous_research_loop_e2e.py` | 4 | ✅ |
| **Total** | **5 módulos** | **58 testes** | ✅ |

**Métricas do Pipeline:**
- Papers ingeridos: `iaglobal/memory/data/json/research_queue.json`
- Hipóteses geradas: `iaglobal/memory/data/json/{paper_id}_hypotheses.json`
- Resultados: `iaglobal/memory/data/json/{hypothesis_id}_{paper_id}_result.json`
- Papers consolidados: `iaglobal/memory/data/json/{paper_id}_consolidated.json`
- Obsidian: `obsidian/03_Long_Term/paper_{paper_id}.md`

**Integrações:**
- ✅ `FileIngestionAgent` (leitura de PDF/HTML)
- ✅ `SandboxExecutor` (execução segura de código)
- ✅ `SubconsciousAPI` (Obsidian 03_Long_Term)
- ✅ `IVMAxiom` (reward por sucesso experimental)
- ✅ `validation/engine.py` (validação de schema)

---

## 🔭 Vetor Evolutivo (pós-Research Loop)

- **Auto-curadoria**: Papers com baixo fitness (0/3 hipóteses validadas) são marcados como "baixa qualidade"
- **Recomendação ativa**: Sistema sugere novos papers baseado em tópicos de alto fitness
- **Citação cruzada**: Papers consolidados linkam entre si via `[[paper_id]]` no Obsidian
- **Meta-análise**: Após N papers, sistema gera review automático de tendências
- **Colaboração externa**: Papers validados podem ser compartilhados via `ImmuneMemoryExchange` com outros nós iaglobal
- **Replicação automática**: Hipóteses não validadas disparam nova rodada de experimentos com parâmetros ajustados

---

## 🧪 Verificação Final

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate

# Verificar todos os módulos
python -c "
from iaglobal.agents.ingestion import (
    PaperIngestor, PaperParser, PaperMetadata,
    HypothesisGenerator, Hypothesis,
    ExperimentRunner, ExperimentResult,
    ResearchConsolidator, ConsolidatedPaper,
    MetaLearner, MetaAnalysis, PaperRecommendation,
)
print('✅ Todos os módulos do Autonomous Research Loop + Meta-aprendizado importam corretamente')
"

# Rodar testes end-to-end
python -m pytest tests/test_autonomous_research_loop_e2e.py tests/test_meta_learner.py -v --tb=short
```

**Critério de conclusão atingido:**
> ✅ 1 paper → 3 hipóteses → 1 experimento → persistência sem intervenção
> ✅ Meta-aprendizado: curadoria, recomendações, citações cruzadas

**Total de testes do iaglobal:** 591+ passed

---

# 🔮 RAG Autônomo — Evolução do SearchMiddleware

> **Objetivo:** Evoluir o SearchMiddleware de "RAG reativo" para "RAG autônomo" com meta-cognição, validação de fontes, e aprendizado contínuo.

**Status atual:** RAG Híbrido Reativo (Web + Local)
**Status alvo:** RAG Autônomo com 6 capacidades avançadas

**Progresso:**
- ✅ **Fase 1 — Threshold de Confiança**: `confidence_tracker.py` (20 testes), integrado no SearchMiddleware
- ✅ **Fase 2 — Query Expansion**: `query_expander.py` (17 testes), busca multi-query em paralelo
- ✅ **Fase 3 — Validação de Fontes**: `source_validator.py` (26 testes), filtro por credibilidade
- ✅ **Fase 4 — Síntese com LLM**: `snippet_synthesizer.py` (23 testes), resumo coerente
- 🔵 **Fase 5 — Persistência Obsidian**: Pendente
- 🔵 **Fase 6 — Feedback Loop**: Pendente

**Total testes:** 86 testes passando (Fases 1-4)

---

## 🔵 Fase 1 — Threshold de Confiança

**Problema:** SearchMiddleware busca **sempre** que o agente é chamado, mesmo se o agente já tem alta confiança.

**Solução:** Adicionar `confidence_threshold` — só buscar se confiança < 0.8.

### 1.1 — Adicionar ConfidenceTracker

**Arquivo:** `iaglobal/search/confidence_tracker.py` (NOVO)

```python
@dataclass
class AgentConfidence:
    agent_id: str
    task_hash: str
    confidence: float  # 0.0 - 1.0
    last_updated: float
    search_helped: bool = None  # feedback pós-busca

class ConfidenceTracker:
    """Rastreia confiança por agente + tarefa."""
    
    def should_search(self, agent_id: str, task_hash: str, threshold: float = 0.8) -> bool:
        """Retorna True se confiança < threshold."""
        confidence = self._get_confidence(agent_id, task_hash)
        return confidence < threshold if confidence is not None else True
    
    def record_search_outcome(self, agent_id: str, task_hash: str, helped: bool):
        """Registra se a busca ajudou (feedback loop)."""
        ...
```

### 1.2 — Integrar no SearchMiddleware

**Arquivo:** `iaglobal/search/search_middleware.py` (MODIFICAR)

```python
@classmethod
async def enrich(cls, prompt: str, node_id: str) -> str:
    # NOVO: Check de confiança antes de buscar
    task_hash = hashlib.sha3_512(prompt.encode()).hexdigest()[:16]
    
    if not cls._confidence_tracker.should_search(node_id, task_hash):
        logger.debug("[SEARCH] Skip — confiança alta para %s", node_id)
        return prompt
    
    # ... busca normal ...
    
    # Após usar resultados, agendar feedback
    asyncio.ensure_future(cls._record_feedback(node_id, task_hash))
```

**Critério:** Agentes com confiança > 0.8 não disparam busca.

---

## 🟠 Fase 2 — Query Expansion

**Problema:** Query extraída via regex é literal — não captura sinônimos ou conceitos relacionados.

**Solução:** Usar LLM local para gerar 2-3 queries relacionadas.

### 2.1 — QueryExpander

**Arquivo:** `iaglobal/search/query_expander.py` (NOVO)

```python
class QueryExpander:
    """Gera queries relacionadas via LLM."""
    
    PROMPT = """
Dada esta query de busca: "{query}"

Gere 2-3 queries relacionadas que podem encontrar informações complementares.
Formato JSON: {{"queries": ["query1", "query2", "query3"]}}
"""

    async def expand(self, query: str) -> List[str]:
        """Gera queries relacionadas."""
        # Chamar LLM local (Ollama) via BanditPolicy
        # Parse JSON de resposta
        # Retornar lista de queries
```

### 2.2 — Busca Paralela Multi-Query

**Arquivo:** `iaglobal/search/search_middleware.py` (MODIFICAR)

```python
@classmethod
async def _search_cached(cls, query: str) -> str:
    # NOVO: Query expansion
    expanded_queries = await cls._expander.expand(query)
    all_queries = [query] + expanded_queries[:2]  # Original + 2 relacionadas
    
    # Buscar todas em paralelo
    tasks = [cls._search_single_query(q) for q in all_queries]
    results = await asyncio.gather(*tasks)
    
    # Deduplicar resultados
    return cls._deduplicate(results)
```

**Critério:** Cada busca gera 3x mais resultados potenciais.

---

## 🔴 Fase 3 — Validação de Fontes ✅ COMPLETA

**Problema:** Snippets da web são aceitos sem validação de credibilidade.

**Solução:** Score de credibilidade por domínio, data, e consistência cruzada.

**Status:** ✅ Implementado e testado (26 testes passando)

### 3.1 — SourceValidator

**Arquivo:** `iaglobal/search/source_validator.py` ✅ CRIADO

```python
@dataclass
class SourceScore:
    url: str
    domain: str
    credibility: float  # 0.0 - 1.0
    recency: float  # 0.0 - 1.0
    consistency: float  # 0.0 - 1.0 (concorda com outras fontes?)
    overall: float

class SourceValidator:
    """Valida credibilidade de fontes web."""
    
    TRUSTED_DOMAINS = {
        "arxiv.org": 0.95,
        "wikipedia.org": 0.85,
        "github.com": 0.80,
        "stackoverflow.com": 0.85,
        "medium.com": 0.60,  # User-generated
    }
    
    def validate(self, snippet: dict) -> SourceScore:
        domain = self._extract_domain(snippet["url"])
        credibility = self.TRUSTED_DOMAINS.get(domain, 0.50)
        
        recency = self._score_recency(snippet.get("date"))
        consistency = self._score_consistency(snippet, all_snippets)
        
        overall = (credibility * 0.5) + (recency * 0.3) + (consistency * 0.2)
        return SourceScore(..., overall=overall)
```

### 3.2 — Filtrar por Score

**Arquivo:** `iaglobal/search/search_middleware.py` ✅ MODIFICADO

```python
@classmethod
async def _search_single_query(cls, query: str) -> str:
    results = await cls._search_web(query)
    
    # NOVO: Validar fontes
    validated = []
    for snippet in results:
        score = cls._validator.validate(snippet)
        if score.overall >= 0.6:  # Threshold mínimo
            validated.append((snippet, score))
    
    # Ordenar por score
    validated.sort(key=lambda x: x[1].overall, reverse=True)
    return validated[:cls._WEB_MAX_RESULTS]
```

**Critério:** ✅ Fontes com score < 0.6 são descartadas.

**Testes:**
- `tests/test_source_validator.py`: 26 testes passando
- Cobertura: `_extract_domain`, `_score_domain`, `_score_recency`, `_score_consistency`, `validate()`, `filter_by_score()`

**Integração:**
- `SearchMiddleware._search_web_with_validation()` chama `SourceValidator.filter_by_score()`
- Snippets incluem `score=X.XX` no output para debugging

---

## 🟢 Fase 4 — Síntese com LLM ✅ COMPLETA

**Problema:** Snippets são concatenados sem síntese — pode haver contradições ou redundância.

**Solução:** Usar LLM para resumir snippets em 1 parágrafo coerente.

**Status:** ✅ Implementado e testado (23 testes passando)

### 4.1 — SnippetSynthesizer

**Arquivo:** `iaglobal/search/snippet_synthesizer.py` ✅ CRIADO

```python
class SnippetSynthesizer:
    """Sintetiza múltiplos snippets em resumo coerente."""
    
    PROMPT = """
Dados estes snippets de busca:

{snippets}

1. Identifique informações consistentes entre as fontes
2. Detecte contradições (se houver)
3. Gere um resumo coerente de 3-4 frases
4. Liste fontes usadas

Formato:
{{
  "summary": "resumo em português",
  "contradictions": ["contradição1 ou null"],
  "sources_used": ["url1", "url2"]
}}
"""

    async def synthesize(self, snippets: List[dict]) -> dict:
        # Chamar LLM via BanditPolicy
        # Parse JSON
        # Retornar resumo + metadados
```

### 4.2 — Injetar Síntese no Prompt

**Arquivo:** `iaglobal/search/search_middleware.py` ✅ MODIFICADO

```python
@classmethod
async def enrich(cls, prompt: str, node_id: str) -> str:
    # FASE 4: Síntese (opcional, desabilitado por padrão)
    if cls._enable_synthesis and context:
        context = await cls._synthesize_context(context)
    
    enriched = cls._inject(prompt, context)
```

**Critério:** ✅ Contexto é 50% menor mas mais coerente (quando habilitado)

**Testes:**
- `tests/test_snippet_synthesizer.py`: 23 testes passando
- Cobertura: `synthesize()`, `_parse_json_response()`, `_fallback_synthesis()`, cache, stats

**Integração:**
- `SearchMiddleware._synthesize_context()` chama `SnippetSynthesizer.synthesize()`
- `_parse_context_snippets()` extrai snippets do contexto bruto
- `_format_synthesis()` formata resumo + contradições + fontes

**Nota:** Síntese está **desabilitada por padrão** (`_enable_synthesis = False`) devido ao custo de chamada LLM. Pode ser habilitada via `SearchMiddleware.enable_synthesis(True)`.

---
def _inject(cls, prompt: str, context: str) -> str:
    # NOVO: Síntese em vez de concatenação bruta
    if cls._enable_synthesis:
        synthesis = await cls._synthesizer.synthesize(context)
        context = f"## Síntese\n{synthesis['summary']}\n\n## Fontes\n{synthesis['sources_used']}"
    
    return f"[CONTEXTO]\n{context}\n\n[INSTRUÇÃO]\n{prompt}"
```

**Critério:** Contexto é 50% menor mas mais coerente.

---

## 🔵 Fase 5 — Persistência no Obsidian

**Problema:** Cache dura 5min e não persiste entre sessões.

**Solução:** Salvar buscas bem-sucedidas em `obsidian/04_Synapses/` para reuso.

### 5.1 — SearchMemory

**Arquivo:** `iaglobal/search/search_memory.py` (NOVO)

```python
class SearchMemory:
    """Persiste buscas no Obsidian para reuso."""
    
    def __init__(self):
        self.obsidian = SubconsciousAPI()
        self.synapses_dir = "04_Synapses/searches"
    
    async def save_search(self, query: str, results: dict, helped: bool):
        """Salva busca bem-sucedida."""
        if not helped:
            return  # Não salvar buscas inúteis
        
        note_content = f"""---
query: "{query}"
timestamp: {datetime.now(UTC).isoformat()}
helped: true
sources: {results['sources_used']}
---

# Busca: {query}

## Síntese
{results['summary']}

## Fontes
{results['sources_used']}
"""
        await self.obsidian.escrever_nota(
            self.synapses_dir,
            f"search_{hashlib.sha3_512(query.encode()).hexdigest()[:12]}",
            note_content,
        )
    
    async def find_similar(self, query: str) -> Optional[dict]:
        """Busca notas similares no Obsidian."""
        # Usar similaridade de texto (TF-IDF ou embedding)
        # Retornar nota mais similar se > threshold
```

### 5.2 — Check Memória Antes de Buscar

**Arquivo:** `iaglobal/search/search_middleware.py` (MODIFICAR)

```python
@classmethod
async def _search_cached(cls, query: str) -> str:
    # NOVO: Check Obsidian antes de buscar
    cached = await cls._memory.find_similar(query)
    if cached:
        logger.info("[SEARCH] Cache Obsidian: %s", query[:40])
        return cached['summary']
    
    # ... busca normal ...
    
    # Salvar se ajudou
    await cls._memory.save_search(query, results, helped=True)
```

**Critério:** Buscas repetidas (mesma query) são resolvidas em <100ms via Obsidian.

---

## 🟠 Fase 6 — Feedback Loop com CreditAssignmentEngine

**Problema:** Sistema não aprende se a busca ajudou ou atrapalhou.

**Solução:** Registrar outcome no `CreditAssignmentEngine` e ajustar threshold.

### 6.1 — Integrar com BanditPolicy

**Arquivo:** `iaglobal/search/search_middleware.py` (MODIFICAR)

```python
@classmethod
async def _record_feedback(cls, node_id: str, task_hash: str):
    """Registra se busca ajudou (chamado após agente completar tarefa)."""
    # Aguardar agente completar
    await asyncio.sleep(1)  # Simplificação — ideal: hook no ResultAgent
    
    # Pedir ao agente: "a busca ajudou?"
    helped = await cls._ask_agent_if_search_helped(node_id)
    
    # Registrar no CreditAssignmentEngine
    from iaglobal.bandit import BanditPolicy
    bandit = BanditPolicy()
    bandit.credit_engine.record_search_outcome(
        agent_id=node_id,
        task_hash=task_hash,
        helped=helped,
    )
    
    # Ajustar threshold dinamicamente
    if helped:
        cls._confidence_tracker.increase_threshold(node_id)
    else:
        cls._confidence_tracker.decrease_threshold(node_id)
```

### 6.2 — Métricas de Eficácia

**Arquivo:** `iaglobal/search/search_metrics.py` (NOVO)

```python
class SearchMetrics:
    """Métricas de eficácia do RAG."""
    
    def get_search_success_rate(self) -> float:
        """% de buscas que ajudaram."""
        ...
    
    def get_avg_confidence_gain(self) -> float:
        """Ganho médio de confiança pós-busca."""
        ...
    
    def get_top_queries(self) -> List[str]:
        """Queries mais frequentes com alto sucesso."""
        ...
```

**Critério:** Sistema ajusta threshold automaticamente baseado em feedback.

---

## 📋 Ordem de Execução

| Ordem | Fase | Item | Arquivo | Esforço | Risco |
|-------|------|------|---------|---------|-------|
| 1 | Fase 1 | 1.1 — ConfidenceTracker | `iaglobal/search/confidence_tracker.py` | Médio | Baixo |
| 2 | Fase 1 | 1.2 — Integrar no SearchMiddleware | `iaglobal/search/search_middleware.py` | Baixo | Baixo |
| 3 | Fase 2 | 2.1 — QueryExpander | `iaglobal/search/query_expander.py` | Médio | Baixo |
| 4 | Fase 2 | 2.2 — Busca Multi-Query | `iaglobal/search/search_middleware.py` | Médio | Baixo |
| 5 | Fase 3 | 3.1 — SourceValidator | `iaglobal/search/source_validator.py` | Alto | Médio |
| 6 | Fase 3 | 3.2 — Filtrar por Score | `iaglobal/search/search_middleware.py` | Baixo | Baixo |
| 7 | Fase 4 | 4.1 — SnippetSynthesizer | `iaglobal/search/snippet_synthesizer.py` | Alto | Médio |
| 8 | Fase 4 | 4.2 — Injetar Síntese | `iaglobal/search/search_middleware.py` | Baixo | Baixo |
| 9 | Fase 5 | 5.1 — SearchMemory | `iaglobal/search/search_memory.py` | Alto | Baixo |
| 10 | Fase 5 | 5.2 — Check Obsidian | `iaglobal/search/search_middleware.py` | Baixo | Baixo |
| 11 | Fase 6 | 6.1 — Feedback Loop | `iaglobal/search/search_middleware.py` | Alto | Alto |
| 12 | Fase 6 | 6.2 — SearchMetrics | `iaglobal/search/search_metrics.py` | Médio | Baixo |

---

## 🧪 Estratégia de Verificação

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate

# Testes unitários por fase
python -m pytest tests/test_rag_autonomo/ -v --tb=short

# Testes de integração
python -m pytest tests/test_search_middleware_enhanced.py -v --tb=short

# Teste E2E: Agente Coder com RAG vs sem RAG
python -m pytest tests/test_rag_e2e_comparison.py -v --tb=short
```

### Cenários de Teste

| Teste | Descrição | Critério |
|-------|-----------|----------|
| `test_confidence_threshold_skip` | Agente com confiança > 0.8 não busca | Busca skipada |
| `test_query_expansion_generates_3` | QueryExpander gera 3 queries | 3 queries retornadas |
| `test_source_validator_filters_low_score` | Fonte com score < 0.6 é filtrada | Fonte excluída |
| `test_synthesis_reduces_context_size` | Síntese reduz contexto em 50% | Contexto menor |
| `test_obsidian_cache_hits` | Busca repetida acha no Obsidian | Cache hit |
| `test_feedback_loop_adjusts_threshold` | Feedback ajusta threshold | Threshold muda |

---

## 🔭 Vetor Evolutivo (pós-RAG Autônomo)

- **Auto-otimização contínua** — Thresholds ajustados via BanditPolicy
- **Memória coletiva** — Obsidian compartilhado entre organismos na colônia
- **Detecção de desinformação** — Fontes contraditórias disparam flag de alerta
- **RAG multi-modal** — Busca de imagens, diagramas, código além de texto
- **Integração com Research Loop** — Papers validados alimentam base de conhecimento do RAG

---

## ✅ Critérios de Conclusão

| Fase | Critério | Status |
|------|----------|--------|
| 1. Threshold | Busca skipada se confiança > 0.8 | ✅ COMPLETO |
| 2. Query Expansion | 3x mais resultados por busca | ⏳ Pendente |
| 3. Validação | Fontes < 0.6 descartadas | ⏳ Pendente |
| 4. Síntese | Contexto 50% menor, mais coerente | ⏳ Pendente |
| 5. Persistência | Cache Obsidian < 100ms | ⏳ Pendente |
| 6. Feedback Loop | Threshold ajusta automaticamente | ⏳ Pendente |

**Total de fases:** 6  
**Fases completas:** 1/6  
**Total de arquivos novos:** 1/7 (`confidence_tracker.py` ✅)  
**Total de arquivos modificados:** 1/2 (`search_middleware.py` ✅)  
**Testes adicionados:** 20  
**Total de testes do iaglobal:** 622 passed

---

## 📊 Fase 1 — Resumo da Implementação

**Arquivos criados:**
- `iaglobal/search/confidence_tracker.py` (280 linhas)
- `tests/test_confidence_tracker.py` (20 testes)

**Arquivos modificados:**
- `iaglobal/search/search_middleware.py` (+30 linhas)

**Funcionalidades:**
- ✅ `should_search(agent_id, task_hash)` → skip se confiança > 0.8
- ✅ `record_confidence()` → persiste confiança por tarefa
- ✅ `record_search_outcome()` → ajusta confiança (+0.1 se ajudou, -0.15 se atrapalhou)
- ✅ `adjust_threshold(agent_id, delta)` → ajuste dinâmico
- ✅ Persistência em `search_confidence.json`
- ✅ Stats por agente (`get_stats()`)

**Impacto:**
- Buscas desnecessárias reduzidas em ~40% (estimativa para agentes com alta confiança)
- Latência de busca evitada: ~1-2s por tarefa skipada
- Primeira etapa do RAG Autônomo: sistema começa a **decidir quando buscar**

---
| Reward | IVM do `experiment_runner` atualizado |

---