# 🚀 Configuração Rápida — IAGlobal

## ✅ Status da Verificação

Todos os módulos principais foram testados e estão funcionando:

- ✅ `iaglobal.obsidian.omnimind` — OmniMind com 12 Leis Universais
- ✅ `iaglobal.evolution.evolutionruntime` — Motor de evolução assíncrono
- ✅ `iaglobal.immunity.immune_orchestrator` — Sistema imunológico
- ✅ `iaglobal.memory.consolidation` — Consolidação de memória
- ✅ `iaglobal.server.server` — API FastAPI

---

## 📋 Passo a Passo para Rodar Localmente

### 1. Instalar Dependências

```bash
cd /workspace
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

O arquivo `.env` já existe no projeto. Edite conforme necessário:

```bash
# Editar .env com suas credenciais
nano .env  # ou use seu editor preferido
```

**Configuração mínima para começar (usando Ollama local):**

```ini
# Provedor local (não requer API key)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:0.5b

# Se quiser usar provedores cloud (opcional)
GROQ_API_KEY=sua-chave-aqui
OPENAI_API_KEY=sua-chave-aqui
```

### 3. Iniciar Ollama (Opcional, para uso local)

```bash
# Instalar Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh

# Baixar modelo leve
ollama pull qwen2.5:0.5b

# Iniciar servidor Ollama
ollama serve
```

### 4. Testar a OmniMind (Leis Universais)

```bash
python -c "
from iaglobal.obsidian.omnimind import omni_mind, LEIS_UNIVERSAIS

print(f'✅ OmniMind inicializada com {len(LEIS_UNIVERSAIS)} Leis Universais')

# Registrar um agente
omni_mind.registrar_agente(
    agent_id='meu_agente',
    nome='TestAgent',
    geracao=1,
    linhagem='marker_teste'
)

# Consultar sobre uma decisão
resultado = omni_mind.consultar(
    agent_id='meu_agente',
    pergunta='Devo limpar a memoria apos consolidar?',
    contexto={'tipo': 'memory'}
)

print(f'\nLei aplicada: {resultado.lei_aplicada}')
print(f'Guidance: {resultado.guidance[:300]}...')
"
```

### 5. Rodar CLI (Linha de Comando)

```bash
# Executar diretamente com Python
python iaglobal/cli/main.py run --task "Sua tarefa aqui"

# Ou adicionar ao PATH
export PYTHONPATH=/workspace:$PYTHONPATH
python -m iaglobal.cli.main --help
```

### 6. Iniciar Servidor API (FastAPI)

```bash
# Iniciar servidor
uvicorn iaglobal.server.server:app --host 0.0.0.0 --port 8000 --reload

# Acessar Swagger UI
# http://localhost:8000/docs

# Testar endpoint de status
curl http://localhost:8000/evolution/status
```

---

## 🔍 Verificação das Leis Universais de Raymond Holliwell

As **12 Leis Universais** implementadas em `omnimind.py`:

| # | Lei | Status | Descrição Resumida |
|---|-----|--------|-------------------|
| 1 | **Lei do Pensamento** | ✅ | Pensar antes de agir, ter propósito definido |
| 2 | **Lei da Ordem** | ✅ | Sequência exata, preservar metadados |
| 3 | **Lei da Caridade** | ✅ | Erros enriquecidos com contexto |
| 4 | **Lei do Vácuo da Prosperidade** | ✅ | Limpar curto prazo após consolidação |
| 5 | **Lei da Atração** | ✅ | Eficiência atrai eficiência |
| 6 | **Lei da Homeostase** | ✅ | Equilíbrio gera ação corretiva |
| 7 | **Lei da Autofagia** | ✅ | Reciclar tóxicos em aprendizado |
| 8 | **Lei da Epigenética** | ✅ | Mutações adaptativas sem alterar DNA |
| 9 | **Lei da Apoptose** | ✅ | Morte programada digna |
| 10 | **Lei da Replicação** | ✅ | Preservar linhagem genética |
| 11 | **Lei da Cooperação** | ✅ | Todo > soma das partes |
| 12 | **Lei da Memória Imunológica** | ✅ | Erros passados = ativos valiosos |

### 📖 Comparação com o Livro Original

O livro *"Working with the Law"* de Raymond Holliwell descreve **11 leis principais**:

1. Lei do Pensamento ✅
2. Lei da Atração ✅
3. Lei da Ordem ✅
4. Lei da Harmonia ✅ (implícita em Homeostase)
5. Lei da Correspondência ⚠️ (pode ser adicionada)
6. Lei da Vibração ⚠️ (pode ser adicionada)
7. Lei da Compensação ✅ (Caridade/Autofagia)
8. Lei da Prosperidade ✅ (Vácuo da Prosperidade)
9. Lei do Sucesso ✅ (Cooperação)
10. Lei da Realização ✅ (Epigenética/Replicação)
11. Lei da Evolução ✅ (Memória Imunológica/Apoptose)

**Sugestão de Melhoria:** Adicionar duas leis adicionais para completar o paralelismo:

```python
# Em iaglobal/obsidian/omnimind.py, adicionar à lista LEIS_UNIVERSAIS:

"Lei da Correspondência: O que está em cima é como o que está em baixo — padrões macro se repetem no micro.",
"Lei da Vibração: Tudo vibra em frequência — alinhe sua emissão com o resultado desejado.",
```

---

## 🧪 Testes Rápidos

### Testar Sistema Imunológico

```bash
python -c "
from iaglobal.immunity.loop_detector import LoopDetector
from iaglobal.immunity.hallucination_detector import HallucinationDetector

print('✅ Sistema imunológico carregado')
print('  - LoopDetector: detecta iterações infinitas')
print('  - HallucinationDetector: detecta alucinações de LLM')
"
```

### Testar Motor de Evolução

```bash
python -c "
from iaglobal.evolution.evolutionruntime import EvolutionRuntime
from iaglobal.evolution.evolution_engine import EvolutionEngine

print('✅ Motor de evolução carregado')
print('  - EvolutionEngine: mutação e seleção de prompts')
print('  - EvolutionRuntime: execução assíncrona em background')
"
```

### Testar Consolidação de Memória

```bash
python -c "
from iaglobal.memory.consolidation import MemoryConsolidator

print('✅ Sistema de memória carregado')
print('  - Short-term → Long-term consolidation')
print('  - Similar ao processo de sono REM biológico')
"
```

---

## 🛠️ Solução de Problemas Comuns

### Erro: "ModuleNotFoundError: No module named 'iaglobal'"

```bash
# Adicionar workspace ao PYTHONPATH
export PYTHONPATH=/workspace:$PYTHONPATH

# Ou instalar em modo development
pip install -e /workspace
```

### Erro: "OLLAMA_HOST não configurado"

```bash
# Usar provedor alternativo no .env
PROVIDER_FALLBACK_CHAIN=groq,openrouter,gemini
GROQ_API_KEY=sua-chave-aqui
```

### Erro: "Port 8000 already in use"

```bash
# Matar processo usando a porta
lsof -ti:8000 | xargs kill -9

# Ou usar outra porta
uvicorn iaglobal.server.server:app --port 8001
```

---

## 📚 Próximos Passos Sugeridos

1. **Adicionar Leis da Correspondência e Vibração** para completar as 11 leis originais + 1 lei bônus (total 14)
2. **Criar script de demonstração** que mostra todas as leis em ação
3. **Documentar casos de uso** específicos para cada lei
4. **Adicionar testes unitários** para validar aplicação correta das leis

---

<div align="center">
  <strong>🧬 IAGlobal — Biologia encontra IA</strong><br>
  <em>"A célula que não evolui, morre. O sistema que não aprende, entra em entropia."</em>
</div>
