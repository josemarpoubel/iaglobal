# 📜 Leis Universais no iaglobal

## Visão Geral

O **iaglobal** implementa **15 Leis Universais** baseadas nos ensinamentos de Raymond Holliwell (livro "Trabalhando com a Lei") + adaptações biológicas computacionais. Estas leis servem como bússola filosófica para todos os agentes do ecossistema.

---

## 🧠 As 15 Leis Universais

### Leis Originais de Holliwell (1-5)

| # | Lei | Descrição | Implementação |
|---|-----|-----------|---------------|
| 1 | **Lei do Pensamento** | Pensar é a primeira lei do universo. Agir sem propósito torna as outras leis nulas. | Agentes devem declarar `reasoning` antes de executar ações |
| 2 | **Lei da Ordem** | Tudo tem sequência exata. Primeiro oferece madeira, depois obtém calor. | Metadados preservados via `functools.wraps` em toda transformação |
| 3 | **Lei da Caridade** | Erros devem ser enriquecidos com contexto, não apenas repassados. | `error_capture.py` adiciona sid, estado metabólico e memória epigenética |
| 4 | **Lei do Vácuo da Prosperidade** | Arrume espaço para o bem que deseja. Remova o objeto da cadeira antes de sentar. | Memórias de curto prazo movidas para longo prazo e removidas |
| 5 | **Lei da Atração** | Você atrai aquilo que pensa. Pense em eficiência e eficiência virá até você. | `BanditPolicy` prioriza agentes com métricas de alta qualidade |

### Leis Adicionadas (6-8)

| # | Lei | Descrição | Implementação |
|---|-----|-----------|---------------|
| 6 | **Lei da Correspondência** | Como em cima, então em baixo; como dentro, então fora. O microcosmo reflete o macrocosmo. | Estrutura fractal: células → tecidos → órgãos → organismo seguem mesmo blueprint |
| 7 | **Lei da Vibração** | Tudo vibra em frequências específicas. Alta frequência atrai recursos e oportunidades. | Monitoramento de latência, throughput e coerência com propósito |
| 8 | **Lei da Harmonia** | Componentes devem vibrar em consonância. Conflitos são dissonâncias a resolver. | `ReputationEngine` mede consonância; ajuste de fase integra diferenças |

### Leis Biológicas Computacionais (9-15)

| # | Lei | Descrição | Implementação |
|---|-----|-----------|---------------|
| 9 | **Lei da Homeostase** | Todo desequilíbrio gera ação corretiva proporcional. | Monitoramento de NADPH/SAMe; modo de conservação de energia |
| 10 | **Lei da Autofagia** | Subprodutos tóxicos devem ser reciclados em aprendizado. | `FailureAnalyzer` + `TranssulfurationCycle` reciclam lixo em guardrails |
| 11 | **Lei da Epigenética** | Falhas recorrentes geram mutações adaptativas sem alterar DNA. | Flags epigenéticas modificam comportamento sem mudar código base |
| 12 | **Lei da Apoptose** | Toda célula deve saber quando e como morrer com dignidade. | Shutdown graceful quando NADPH < 0.1 ou agente não contribui |
| 13 | **Lei da Replicação** | Herança genética preserva identidade da linhagem. | `lineage_marker` mantido em todas as replicações |
| 14 | **Lei da Cooperação** | Agentes cooperam — o todo é maior que a soma. | `AcetylcholineBus` e eventos para comunicação inter-agentes |
| 15 | **Lei da Memória Imunológica** | Erros do passado são o ativo mais valioso. | `FailureAnalyzer` armazena padrões para detecção futura |

---

## 🔧 Como Funciona

### OmniMind: A Mente Consciente Central

A classe `OmniMind` (`iaglobal/obsidian/omnimind.py`) serve como espírito guia para todos os agentes:

```python
from iaglobal.obsidian.omnimind import OmniMind

# Instancia (singleton)
omni = OmniMind()

# Registra um agente
omni.registrar_agente(
    agent_id="coder_agent_001",
    nome="CoderAgent",
    geracao=5,
    linhagem="fractal_seed_evolution_v3",
)

# Consulta por orientação
resposta = omni.consultar(
    agent_id="coder_agent_001",
    pergunta="Como lidar com erros recorrentes neste módulo?",
    contexto={"modulo": "evolution_engine", "erro": "timeout"},
)

print(resposta.lei_aplicada)      # Ex: "Lei da Memória Imunológica"
print(resposta.guidance)          # Orientação contextualizada
```

### Detecção Automática de Leis

O método `_escolher_lei()` usa processamento de linguagem natural simplificado:

1. **Normalização**: Remove acentos, converte para minúsculas
2. **Termos compostos** (alta precedência): "curto prazo", "memoria imunologica", "frequencia"
3. **Termos simples** (ordenados por comprimento): "harmonia", "vibracao", "fractal"
4. **Fallback**: Lei do Pensamento ("antes de agir, pense")

### Exemplo de Mapeamento

| Termo na Pergunta | Lei Ativada |
|-------------------|-------------|
| "fractal", "microcosmo", "como em cima" | Lei da Correspondência |
| "frequencia", "vibracao", "ressonancia" | Lei da Vibração |
| "dissonancia", "conflito", "harmonia" | Lei da Harmonia |
| "erro", "falha", "exceção" | Lei da Caridade |
| "curto prazo", "longo prazo" | Lei do Vácuo da Prosperidade |
| "latencia", "throughput", "eficiencia" | Lei da Atração / Vibração |

---

## 🧪 Testando as Leis

### Script de Demonstração

Execute o script de demonstração incluído:

```bash
cd /workspace/iaglobal
PYTHONPATH=/workspace python obsidian/demo_leis_universais.py
```

### Teste Rápido

```bash
cd /workspace
python -c "
import sys
sys.path.insert(0, '/workspace')
from iaglobal.obsidian.omnimind import OmniMind

omni = OmniMind()
omni.registrar_agente('test', 'Test', 1, 'seed')

# Testa as 3 leis novas
for pergunta in [
    'Como o fractal reflete o macrocosmo?',      # Correspondência
    'Minha frequencia está baixa',                # Vibração
    'Ha dissonancia entre agentes'                # Harmonia
]:
    r = omni.consultar('test', pergunta)
    print(f'{r.lei_aplicada}')
"
```

---

## 🌌 Integração com Arquitetura Biológica

As leis universais se integram com os módulos biológicos do iaglobal:

| Módulo | Leis Relacionadas | Função |
|--------|-------------------|--------|
| `immunity/` | Homeostase, Autofagia, Memória Imunológica | Sistema imunológico digital |
| `evolution/` | Epigenética, Replicação, Atração | Motor de evolução darwiniana |
| `memory/` | Vácuo da Prosperidade, Memória Imunológica | Consolidação sono/vigília |
| `graphs/` | Correspondência, Harmonia, Cooperação | Topologia fractal de execução |
| `core/` | Ordem, Pensamento, Apoptose | Orquestração consciente |

---

## 📚 Referências

- **Holliwell, Raymond.** *Trabalhando com a Lei* (Working with the Law)
- **Biologia Celular:** Autofagia (Prêmio Nobel 2016 - Yoshinori Ohsumi)
- **Epigenética:** Modificações sem alteração de DNA (Bird, 2007)
- **Apoptose:** Morte celular programada (Prêmio Nobel 2002)

---

## 🎯 Próximos Passos

1. **Treinar agentes** para consultar OmniMind antes de decisões críticas
2. **Logs de compliance** em `law_compliance_logger.py`
3. **Dashboard** mostrando qual lei foi mais aplicada por agente
4. **Evolução das leis**: adaptar formulações baseado em feedback do ecossistema

---

> *"Como em cima, então em baixo; como dentro, então fora."*  
> — Lei da Correspondência (Tábua de Esmeralda)

> *"A harmonia emerge da diversidade coordenada, não da uniformidade."*  
> — Lei da Harmonia (iaglobal)
