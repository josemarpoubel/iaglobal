# IAGlobal

Multi-agent cognitive system with deterministic DAG pipeline, genetic evolution, persistent memory, and hybrid local/cloud LLM orchestration.

## Features

- **25-node DAG pipeline** — intake → enhancement → orchestrator → pm → requirements → architect → search → knowledge → dependency → risk → security/performance design → planner → coder → reviewer → semantic/security/performance audit → tester → debug loop → documentation → release → metrics → optimization → result
- **Hybrid LLM routing** — BanditPolicy selects best model per task (Ollama local, Groq, OpenRouter, NVIDIA, OpenCode) with fallback chain
- **Genetic evolution** — autonomous pipeline optimization via selection, mutation, and crossover with collapse detection
- **Persistent memory** — STM + LTM + vector embeddings + semantic cache + knowledge graph + error learning
- **Agent governance** — formal contracts with authority limits; critic is passive sensor, proxy decides
- **Cognitive proxy** — deterministic 6-stage orchestrator: normalize → build context → compile prompt → route → validate → store
- **536 tests** — 0 failures

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env (Ollama works without API keys)
cp .env.example .env

# Run a task
python -m iaglobal run "your task here"

# Run tests
python -m pytest iaglobal/tests/ -q
```

## Pipeline

```
User → prompt_intake → enhancement → orchestrator_agent → pm
→ requirements → architect → search → knowledge → dependency
→ risk_analysis → security_design → performance_design → planner
→ coder → reviewer → semantic_validator → security_audit
→ performance_audit → tester → [debug_coder → coder ↺]
→ documentation → release → metrics → optimization → result_agent
```

Six phases: Definition → Planning → Construction → Quality → Correction → Delivery.

## Project Structure

```
iaglobal/
├── agents/           — 19 specialized agents
├── providers/        — LLM providers (Ollama, Groq, OpenRouter, NVIDIA, OpenCode, Gemini)
├── graphs/           — DAG, nodes, bandit policy, credit assignment, execution engine
├── evolution/        — Genetic evolution engine, skills registry, replay, collapse detection
├── memory/           — Short/long-term memory, vector store, semantic cache, fusion engine, knowledge base
├── core/             — Cognitive proxy, governance layer, retry handler, assistant, orchestrator
├── cli/              — Command-line interface
├── pipeline/         — Pipeline engine
└── tests/            — 536 tests
```

## Configuration

Minimum `.env` for local-only operation (Ollama):

```env
DEFAULT_OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_URL=http://localhost:11434
```

Optional cloud providers (add corresponding API keys):

```env
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
NVIDIA_API_KEY=nvapi-...
GEMINI_API_KEY=AIza...
```

## Documentation

- **[ROADMAP.md](docs/ROADMAP.md)** — Full implementation history and development log
- **[AGENTS.md](AGENTS.md)** — System context for LLM agents

## License

MIT
