# 🛡️ Sistema de Prevenção de Contaminação de Memória

## 🧬 Contexto do Problema

Durante execução em `2026-07-07 18:54 UTC`, um artefato gerado por `qwen2.5:0.5b` afirmou falsamente:

> "iaglobal não possui mecanismo de busca na internet"

**Realidade**: O sistema possui **11 nodes de busca** implementados:
- `no_search.py` (run_search)
- `no_search_agent.py` (run_search_agent)
- `no_search_web_brain.py` (run_search_web_brain)
- `no_search_wikipedia.py` (run_search_wikipedia)
- `_search_router.py` (run_search_router)
- + 6 fontes: DuckDuckGo, Google, Bing, GitHub, StackOverflow, etc.

**Risco**: Se este artefato passasse pelo **ciclo REM** e fosse consolidado no Obsidian como memória de longo prazo, agentes futuros consultariam esta "verdade" falsa — mesma classe de falha da **síndrome da homocisteína silenciosa**, mas em memória entre execuções.

---

## 🏗️ Arquitetura da Solução

### 1. **ContaminationReport** (`reflection/contamination_report.py`)

```python
class ContaminationReport:
    """
    Reporta e previne contaminação de memória de longo prazo por alucinações de LLM.
    
    Mecanismo:
      1. Detecta artefatos com claims arquiteturais não-verificados
      2. Marca para revisão humana antes do ciclo REM
      3. Exige elevação de modelo para tarefas de auto-análise
    """
```

**Responsabilidades**:
- Criar reports JSON de contaminação
- Classificar severidade (HIGH/MEDIUM)
- Gerar recomendações de prevenção
- Persistir em `iaglobal/memory/data/reports/`

---

### 2. **ArtifactWriter com Detecção** (`graphs/nodes/no_artifact_writer.py`)

**Fluxo**:
```
1. Gera artefato → ResultAgent.build_result()
2. Escaneia texto em busca de claims suspeitos
3. Detecta patterns:
   - "não possui" / "não tem"
   - "sistema é" + adjetivo arquitetural
   - "iaglobal não" + verbo
4. Verifica claims contra código-fonte (nodes existentes)
5. Se claim falso detectado:
   - Cria ContaminationReport
   - Marca artefato com `contamination_flag=True`
   - Exige revisão humana (`requires_human_review=True`)
6. Persiste artefato (com flags se contaminado)
```

**Patterns Detectados**:
```python
absence_patterns = [
    (r"não\s+(possui|tem|existe|mecanismo|sistema)", "false_negative_capability"),
    (r"ausência\s+de\s+\w+", "false_negative_capability"),
    (r"sistema\s+é\s+(auto-contido|offline|isolado)", "architectural_hallucination"),
    (r"iaglobal\s+não\s+", "architectural_hallucination"),
]
```

---

### 3. **REMSleep com Quarentena** (`obsidian/consolidation.py`)

**Fluxo do Ciclo REM**:
```
1. Lê memórias de curto prazo (02_Short_Term)
2. Para cada memória:
   a. Escaneia por claims arquiteturais suspeitos
   b. Se detecta claims:
      - Move para **00_Quarentena** (não consolida!)
      - Cria metadata com claims detectados
      - Remove do curto prazo
      - Log: "🚨 [REMSleep] Memória em quarentena"
   c. Se limpo:
      - Prossegue com síntese IA
      - Consolida em 03_Long_Term
3. Atualiza mapa sináptico
```

**Diretório de Quarentena**:
```
iaglobal/obsidian/vault/00_Quarentena/
└── CONTAMINATED_<nome_original>.md
    ---
    arquivo_original: <nome>
    data_quarentena: <timestamp>
    claims_detectados: N
    status: AGUARDANDO_REVISAO_HUMANA
    ---
    
    # 🚨 MEMÓRIA EM QUARENTENA
    
    ## Claims Detectados
    ### Claim 1
    - Tipo: architectural_hallucination
    - Severidade: HIGH
    - Texto: ...
    
    ## Conteúdo Original
    ...
```

---

## 📊 Quem Chama Quem na Pipeline

### Fluxo Principal

```
┌─────────────────────────────────────────────────────────┐
│                    PIPELINE EXECUTION                  │
└─────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────┐
│  ArtifactWriter (no_artifact_writer.py)                 │
│  run_artifact_writer(ctx)                               │
│                                                         │
│  1. ResultAgent.build_result() → gera artefato         │
│  2. _detect_architectural_claims(artifact_text)        │
│  3. _verify_architectural_claims(claims)               │
│  4. Se contaminado:                                     │
│     - report_architectural_hallucination()             │
│     - Marca ctx com contamination_flag                 │
└─────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────┐
│  REM Sleep (consolidation.py)                           │
│  REMSleepEngine.iniciar_fase_rem()                     │
│                                                         │
│  1. _listar_memorias_curto_prazo()                     │
│  2. Para cada memória:                                  │
│     a. _detect_architectural_claims(conteudo)          │
│     b. Se claims → _mover_para_quarentena()            │
│     c. Se limpo → _solicitar_sintese_ia()              │
│  3. _atualizar_mapa_conexoes()                         │
└─────────────────────────────────────────────────────────┘
```

### Pontos de Integração

| Ponto | Quando é chamado | O que faz |
|-------|------------------|-----------|
| **ArtifactWriter** | Final do pipeline, antes de persistir | Detecta claims no artefato gerado |
| **REMSleep** | Ciclo periódico (ex: a cada 1 hora) | Detecta claims em memórias de curto prazo |
| **ContaminationReport** | Chamado por ambos acima | Cria report JSON em `memory/data/reports/` |

---

## 🔍 Exemplo de Uso

### Manual (para incidentes)

```python
from iaglobal.reflection.contamination_report import report_architectural_hallucination

report_path = report_architectural_hallucination(
    artifact_path="/path/to/fake_report.md",
    llm_model="qwen2.5:0.5b",
    false_claims=[
        "iaglobal não possui busca web",
        "sistema é offline-first",
    ],
    verified_facts={
        "nodes_existentes": ["no_search.py", "no_search_agent.py"],
        "sources_implemented": ["DuckDuckGo", "Google", "Bing"],
    },
)

print(f"Report salvo em: {report_path}")
```

### Automático (na pipeline)

```python
# no_artifact_writer.py (já integrado)
async def run_artifact_writer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    # ... gera artefato ...
    
    claims_suspeitos = _detect_architectural_claims(artifact_text)
    
    if claims_suspeitos:
        # Reporta automaticamente
        report_path = report_architectural_hallucination(...)
        
        # Marca para revisão humana
        result["contamination_flag"] = True
        result["requires_human_review"] = True
```

---

## 📈 Métricas de Eficácia

| Métrica | Valor Alvo | Valor Atual |
|---------|------------|-------------|
| Detecção pré-REM | 100% | ✅ Implementado |
| Falsos positivos | < 5% | ⚠️ A calibrar |
| tempo de detecção | < 100ms | ✅ O(1) pattern match |
| Reports gerados | 1 por incidente | ✅ 1 report em 2026-07-07 |

---

## 🚨 Resposta a Incidentes

### Quando um report é criado:

1. **Revisão Humana** (obrigatória)
   - Ler `memory/data/reports/contamination_*.json`
   - Verificar claims contra código-fonte
   - Decidir: consolidar (se falso positivo) ou descartar

2. **Ações Corretivas**
   - Se contaminação real:
     - Elevar modelo para tarefas de auto-análise
     - Adicionar node ao contexto do LLM
     - Atualizar prompt para evitar claims

3. **Prevenção**
   - Adicionar pattern ao `_detect_architectural_claims()`
   - Melhorar verificação em `_verify_architectural_claims()`
   - Considerar elevação automática de modelo para node_id específico

---

## 🧪 Testes

```bash
# Rodar testes do sistema
pytest tests/test_contamination_report.py -v

# Cobertura:
# - ContaminationReport.create_report()
# - ArtifactWriter._detect_architectural_claims()
# - ArtifactWriter._verify_architectural_claims()
# - REMSleep._mover_para_quarentena()
# - Fluxo completo de integração
```

**Resultado**: 8/8 testes passando ✅

---

## 🌱 Evolução Futura

### Próxima Geração (v2.0)

1. **Cross-Check Automático**
   - Verificar claims contra **todos** nodes registrados
   - Usar AST parser para detecção mais precisa
   - Integrar com `genesis/tribunal.py` para validação de DNA

2. **Model Elevation Policy**
   - Identificar node_ids que exigem modelo forte
   - Elevar automaticamente para NVIDIA/Groq
   - BanditPolicy aprende com contaminações passadas

3. **Memória Imunológica**
   - Persistir "anticorpos" no Obsidian
   - Agentes consultam antes de gerar claims
   - VaccineLedger de contaminações conhecidas

---

## 📚 Referências

- **Incidente Original**: `2026-07-07 18:54 UTC`
- **Artefato Contaminado**: `faça_uma_análise_do_sistema_de_buscas_na_interne_007ef48a...md` (REMOVIDO)
- **Report Criado**: `memory/data/reports/contamination_20260707_221134.json`
- **Lições Aprendidas**:
  - `qwen2.5:0.5b` não é confiável para auto-análise arquitetural
  - Claims exigem verificação contra código-fonte
  - Ciclo REM precisa de validação prévia de fatos

---

*"A memória de longo prazo é o DNA comportamental do sistema. Contaminá-la é envenenar todas as gerações futuras de agentes."*