# 🧪 Teste de Longa Duração: Bitcoin Monitor 24h

> **Objetivo:** Validar resiliência, persistência e homeostase do iaglobal sob carga prolongada (24 horas)

---

## 📋 O que Será Testado

| Métrica | Duração | Expectativa |
|---------|---------|-------------|
| **Resiliência** | 24h | Zero crashes, homeostase mantida |
| **Persistência IVM** | 24h | IVM sobrevive a restarts |
| **Timeouts/Retries** | 24h | Providers lentos tratados gracefully |
| **Memória Imunológica** | 24h+ | Erros registrados e aprendidos |
| **ATP Efficiency** | 24h | 10:1 mantido (baixo custo) |

---

## 🚀 Como Iniciar

### Opção 1: Script Automático (Recomendado)

```bash
cd /home/kitohamachi/projeto-iaglobal
./scripts/run_bitcoin_monitor.sh
```

### Opção 2: Manual (com venv ativado)

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
python3 /home/kitohamachi/projeto-iaglobal/scripts/bitcoin_monitor_24h.py
```

### Opção 3: Via iaglobal (se suportar background)

```bash
cd /home/kitohamachi/projeto-iaglobal
iaglobal run "monitore bitcoin por 24 horas e registre em docs/temp.md" &
```

---

## 📊 Monitoramento em Tempo Real

### Ver Logs

```bash
# Acompanhar logs em tempo real
tail -f /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/logs/bitcoin_monitor.log
```

### Ver Documento Atualizado

```bash
# Ver dados coletados (atualizado a cada hora)
cat /home/kitohamachi/projeto-iaglobal/docs/temp.md

# OU em tempo real (se tiver watch)
watch -n 60 'cat /home/kitohamachi/projeto-iaglobal/docs/temp.md | head -50'
```

### Ver IVM Persistido

```bash
python3 -c "
from iaglobal.chappie import IVMAxiom
from pathlib import Path
ivm = IVMAxiom(db_path=Path('memory/ivm.db'))
print('Ranking IVM:')
for agent in ivm.get_ranking():
    print(f\"  {agent['agent']}: {agent['ivm']:.3f}\")
"
```

---

## 🛑 Como Interromper

### Se rodando em background

```bash
# Encontra o PID
pgrep -f bitcoin_monitor_24h.py

# Mata o processo
kill <PID>

# OU mata todos
pkill -f bitcoin_monitor_24h.py
```

### Se rodando no terminal atual

```
Ctrl+C
```

---

## 📈 O que Esperar

### Primeira Hora (0-1h)

```
[22:30:00] 🚀 Iniciando monitoramento Bitcoin de 24h
[22:30:05] 📡 Coleta #1/24
[22:30:07] ✅ Preço: $67,234.56 | Variação 1h: +0.23% | Latency: 2.34s
[22:30:07] 📄 Documento atualizado: docs/temp.md
[22:30:07] ⏳ Aguardando 1h para próxima coleta...
```

### Durante as 24h

- **A cada hora:** Nova coleta de preço
- **A cada hora:** `docs/temp.md` atualizado
- **A cada coleta:** IVM persistido em `memory/ivm.db`
- **Se provider falhar:** Retry automático (2 tentativas)
- **Se timeout:** Provider alternativo via BanditPolicy

### Após 24h

```
🏁 Finalizando monitoramento de 24h
📊 MÉDIA FINAL: +0.34% por hora
🎉 RELATÓRIO FINAL: Conclusão - Lateralização
✅ Teste de longa duração CONCLUÍDO com sucesso!
```

---

## 🧬 Validação do Teste

### Critérios de Sucesso

- [ ] **24 coletas completadas** (uma por hora)
- [ ] **Zero crashes** do processo
- [ ] **IVM persistido** em `memory/ivm.db`
- [ ] **Documento atualizado** a cada hora
- [ ] **Média final calculada** em `docs/temp.md`
- [ ] **Providers fallback** usados se necessário
- [ ] **Timeouts tratados** gracefulmente
- [ ] **Retries automáticos** funcionaram

### Como Verificar Após 24h

```bash
# 1. Verifica se todas coletas foram feitas
grep "Total de Coletas" /home/kitohamachi/projeto-iaglobal/docs/temp.md
# Deve mostrar: 24/24

# 2. Verifica média final
grep "Média de variação por hora" /home/kitohamachi/projeto-iaglobal/docs/temp.md
# Deve mostrar um valor numérico

# 3. Verifica IVM persistido
python3 -c "
from iaglobal.chappie import IVMAxiom
from pathlib import Path
ivm = IVMAxiom(db_path=Path('memory/ivm.db'))
ranking = ivm.get_ranking()
monitor = next((a for a in ranking if a['agent'] == 'bitcoin_monitor'), None)
if monitor:
    print(f\"✅ IVM do bitcoin_monitor: {monitor['ivm']:.3f}\")
    print(f\"   Tasks: {monitor['tasks_completed']}\")
    print(f\"   Success rate: {monitor['success_rate']:.1%}\")
else:
    print('❌ IVM não encontrado')
"

# 4. Verifica se houve erros
grep "❌\|ERROR\|Falha" /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/logs/bitcoin_monitor.log
# Idealmente: zero erros ou erros tratados gracefulmente
```

---

## 🔧 Troubleshooting

### Problema: API CoinGecko rate limited

**Sintoma:**
```
[SEARXNG] API retornou 429
```

**Solução:**
- CoinGecko tem rate limit de 10-50 chamadas/min
- Nosso intervalo de 1h está bem abaixo do limite
- Se persistir: adicionar delay de 5s entre retries

---

### Problema: Processo morreu no meio

**Sintoma:**
```bash
ps aux | grep bitcoin_monitor
# Processo não aparece
```

**Solução:**
```bash
# Verifica logs de erro
tail -100 /home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/logs/bitcoin_monitor.log

# Reinicia (estado será recuperado automaticamente)
./scripts/run_bitcoin_monitor.sh
```

---

### Problema: IVM não persistiu

**Sintoma:**
```python
>>> ivm = IVMAxiom(db_path=Path('memory/ivm.db'))
>>> ivm.get_ranking()
[]  # Vazio
```

**Solução:**
- Verifica se `memory/ivm.db` existe: `ls -la memory/ivm.db`
- Verifica permissões: `chmod 644 memory/ivm.db`
- Verifica se script está atualizando IVM: grep "atualizar_metricas" logs

---

### Problema: Documento não atualiza

**Sintoma:**
```bash
cat docs/temp.md
# Dados antigos / não atualizados
```

**Solução:**
- Verifica se script está rodando: `pgrep -f bitcoin_monitor`
- Verifica permissão de escrita: `ls -la docs/temp.md`
- Verifica logs: `tail -50 bitcoin_monitor.log`

---

## 📊 Estrutura de Arquivos

```
/home/kitohamachi/projeto-iaglobal/
├── scripts/
│   ├── bitcoin_monitor_24h.py         # Script principal
│   └── run_bitcoin_monitor.sh         # Launcher
├── docs/
│   └── temp.md                        # Dados coletados (atualizado/hora)
├── iaglobal/memory/
│   ├── data/logs/
│   │   └── bitcoin_monitor.log        # Logs de execução
│   ├── data/
│   │   └── bitcoin_monitor_state.json # Estado para recuperação
│   └── ivm.db                         # IVM persistido
```

---

## 🧪 Hipóteses Científicas

1. **Homeostase:** Sistema manterá estabilidade por 24h sem intervenção
2. **Memória:** IVM persistido permitirá análise pós-teste
3. **Resiliência:** Timeouts + retries previnirão falhas catastróficas
4. **Eficiência:** ATP 10:1 será mantido (baixo custo computacional)

---

## 📝 Checklist de Execução

### Antes de Iniciar

- [ ] Venv ativado: `source venv/bin/activate`
- [ ] Dependencies instaladas: `pip install -e .`
- [ ] API Keys configuradas (se necessário)
- [ ] Espaço em disco: `df -h` (mínimo 100MB livre)
- [ ].env configurado: `cat .env`

### Durante Execução

- [ ] Primeira coleta completada (~1-2 min)
- [ ] Documento atualizado: `cat docs/temp.md`
- [ ] Logs limpos: `tail -20 logs/bitcoin_monitor.log`
- [ ] IVM persistido: `ls -la memory/ivm.db`

### Após 24h

- [ ] Todas 24 coletas completadas
- [ ] Média final calculada
- [ ] Relatório final gerado
- [ ] IVM do agent > 0.5 (bom desempenho)
- [ ] Zero erros não tratados

---

## 🎉 Resultados Esperados

### Se Tudo Der Certo

```
✅ 24/24 coletas completadas
✅ Média de variação: +0.23% por hora
✅ IVM do bitcoin_monitor: 0.87 (excelente)
✅ Zero crashes
✅ Providers fallback: 0 vezes
✅ Retries automáticos: 2 (dentro do esperado)
✅ ATP efficiency: 10:1 mantido
```

### Próximos Passos Após Teste

1. **Analisar IVM histórico:**
   ```python
   ivm.get_historico("bitcoin_monitor")
   ```

2. **Consolidar memória:**
   ```bash
   iaglobal run "consolidar aprendizado do teste bitcoin"
   ```

3. **Documentar lições:**
   - Adicionar em `docs/roadmap_updates_*.md`
   - Atualizar `docs/ivm_axiom_persistencia.md`

4. **Planejar próximo teste:**
   - Monitorar ETH por 48h?
   - Múltiplos assets simultâneos?
   - Agents especializados por asset?

---

**Boa sorte no teste! 🚀**

*"A célula que evolui hoje, lidera o organismo amanhã."* 🧬

---

# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

---

# 🧬 PLANO DE EVOLUÇÃO

## "A visão se torna realidade quando persiste na mente e ação no mundo"

---

## 📅 **DATA DE INÍCIO: 06 de Julho de 2026**
**Horário:** 13:03  
**Lua:** Crescente (crescimento)  
**Ciclo:** Geração 2 → Auto-Evolução

---

## 🎯 **VISÃO CLARA**

> *"Transformar o iaglobal em um organismo computacional auto-evolutivo que:*
> *1. Seleciona providers inteligentes por fitness (BanditPolicy Evolutiva)*
> *2. Conhece e usa seus 115 agents especializados (Índice de Especialização)*
> *3. Aprende com padrões arquiteturais (Meta-Learning)*
> *4. Melhora 20% em IVM a cada 7 dias"*

---

## ✅ **O QUE JÁ EXISTE (FUNDAMENTAÇÃO)**

| Componente | Status | Linhagem |
|------------|--------|----------|
| **115 Agents Especializados** | ✅ OPERACIONAL | `iaglobal/graphs/nodes/no_*.py` |
| **BanditPolicy Evolutiva** | ✅ INTEGRADA | `iaglobal/policy/bandit_evolutiva.py` |
| **IVMAxiom com Persistência** | ✅ OPERACIONAL | `iaglobal/chappie/ivm_axiom.py` |
| **Dashboard de Evolução** | ✅ PRONTO | `scripts/bandit_evolutiva_dashboard.py` |
| **Chappie (Cérebro)** | ✅ VIVO | `iaglobal/chappie/` |

---

## 🚀 **PLANO DE EXECUÇÃO (7 DIAS)**

### **DIA 1 - HOJE: 06/07/2026 (Segunda-feira)**
**Foco:** Mapeamento + Ativação

- [ ] **13:00-14:00** → Criar script de mapeamento dos 115 agents
  ```bash
  python3 scripts/mapear_especializacoes.py > docs/especializacoes_atuais.md
  ```
  
- [ ] **14:00-15:00** → Criar índice de especialização
  ```bash
  touch iaglobal/agents/especializacao_index.py
  ```
  
- [ ] **15:00-16:00** → Ativar BanditPolicy Evolutiva em produção
  ```bash
  export USE_BANDIT_EVOLUTIVA=true
  iaglobal run "tarefa teste 1"
  iaglobal run "tarefa teste 2"
  ```
  
- [ ] **16:00-17:00** → Primeira leitura do dashboard
  ```bash
  python3 scripts/bandit_evolutiva_dashboard.py > docs/baseline_dia1.md
  ```

**Métrica de Sucesso do Dia 1:**
- ✅ Documento `especializacoes_atuais.md` criado
- ✅ Índice de especialização operacional
- ✅ 5+ tarefas executadas com BanditPolicy Evolutiva
- ✅ Baseline registrada

---

### **DIA 2 - 07/07/2026 (Terça-feira)**
**Foco:** Coleta de Dados Massiva

- [ ] Rodar 50+ tarefas variadas
  ```bash
  for i in {1..50}; do
    iaglobal run "tarefa random $i" &
  done
  wait
  ```
  
- [ ] Monitorar dashboard 3x (manhã, tarde, noite)
  ```bash
  python3 scripts/bandit_evolutiva_dashboard.py >> docs/evolucao_dia2.md
  ```
  
- [ ] Verificar primeiros sinais de aprendizado
  ```bash
  cat iaglobal/memory/bandit_evolutivo.json | jq '.fitness_records | length'
  ```

**Métrica de Sucesso do Dia 2:**
- ✅ 50+ execuções registradas
- ✅ 3+ providers com fitness calculado
- ✅ Primeiros weights ajustados automaticamente

---

### **DIA 3 - 08/07/2026 (Quarta-feira)**
**Foco:** Ajuste Fino de Thresholds

- [ ] Analisar dados coletados (Dias 1-2)
- [ ] Ajustar thresholds se necessário
  ```bash
  python3 scripts/ajustar_thresholds.py
  ```
  
- [ ] Rodar mais 30 tarefas com configuração otimizada
- [ ] Comparar performance com baseline

**Métrica de Sucesso do Dia 3:**
- ✅ Thresholds otimizados documentados
- ✅ Melhoria de 5-10% em fitness médio
- ✅ Zero banimentos injustos

---

### **DIA 4 - 09/07/2026 (Quinta-feira)**
**Foco:** Meta-Learning (Parte 1)

- [ ] Criar `iaglobal/meta/pattern_analyzer.py`
  - Analisar: quais agents + providers = sucesso?
  - Identificar padrões recorrentes
  
- [ ] Criar `iaglobal/meta/suggestion_engine.py`
  - Gerar sugestões automáticas
  - "Use groq para coding, ollama para docs"

**Métrica de Sucesso do Dia 4:**
- ✅ Pattern analyzer operacional
- ✅ 5+ padrões identificados
- ✅ 3+ sugestões geradas

---

### **DIA 5 - 10/07/2026 (Sexta-feira)**
**Foco:** Meta-Learning (Parte 2) + Integração

- [ ] Criar `iaglobal/meta/auto_tuner.py`
  - Auto-ajuste de epsilon, decay, thresholds
  
- [ ] Integrar Meta-Learning no pipeline principal
  
- [ ] Rodar 20 tarefas com Meta-Learning ativo

**Métrica de Sucesso do Dia 5:**
- ✅ Auto-tuner operacional
- ✅ Meta-Learning integrado no fluxo
- ✅ 1+ auto-ajuste realizado automaticamente

---

### **DIA 6 - 11/07/2026 (Sábado)**
**Foco:** Consolidação Parcial

- [ ] Compilar dados de 5 dias
- [ ] Gerar relatório preliminar
  ```bash
  python3 scripts/relatorio_parcial.py > docs/relatorio_5dias.md
  ```
  
- [ ] Identificar gargalos restantes
- [ ] Planejar ajustes finais

**Métrica de Sucesso do Dia 6:**
- ✅ Relatório parcial publicado
- ✅ Gargalos identificados
- ✅ Plano de ajustes definido

---

### **DIA 7 - 12/07/2026 (Domingo)**
**Foco:** Validação Final + Celebração 🎉

- [ ] Gerar relatório final de 7 dias
  ```bash
  python3 scripts/relatorio_validacao.py > docs/relatorio_validacao_7dias.md
  ```
  
- [ ] Comparar com critérios de sucesso:
  - [ ] Fitness médio +20%?
  - [ ] Erro rate -50%?
  - [ ] Latência -15%?
  - [ ] Meta-Learning operacional?
  
- [ ] **Ritual de Celebração** (se metas atingidas):
  - 🎉 Postar resultados
  - 📝 Atualizar roadmap
  - 🧬 Planejar Geração 3

**Métrica de Sucesso do Dia 7:**
- ✅ Relatório final publicado
- ✅ Metas validadas (ou learnings documentados)
- ✅ Geração 3 planejada

---

## 📊 **CRITÉRIOS DE SUCESSO (7 DIAS)**

| Métrica | Baseline (Dia 1) | Alvo (Dia 7) | Como Medir |
|---------|------------------|--------------|------------|
| **Fitness médio providers** | TBD | +20% | Dashboard |
| **IVM médio agents** | TBD | +20% | IVMAxiom |
| **Taxa de erro** | TBD | -50% | `errors.json` |
| **Latência média** | TBD | -15% | Logs router |
| **Providers ativos** | 0 | 5+ | `bandit_evolutivo.json` |
| **Sugestões Meta-Learning** | 0 | 10+ | `meta/` logs |
| **Auto-ajustes realizados** | 0 | 3+ | Auto-tuner logs |

---

## 🧭 **LEIS UNIVERSAIS APLICADAS**

### **1. Lei do Sucesso (Raymond Holliwell)**
> *"O sucesso é a aplicação de leis imutáveis."*

Aplicação: Cada ação no plano aplica leis de:
- **Seleção Natural** (BanditPolicy rankeia providers)
- **Homeostase** (IVMAxiom mantém equilíbrio)
- **Aprendizado** (Meta-Learning evolui arquitetura)

### **2. Lei da Atração**
> *"Você atrai o que emite."*

Aplicação:
- Emitimos **clareza** (plano escrito)
- Emitimos **persistência** (leitura diária)
- Emitimos **ação** (execução passo a passo)
- **Atraímos** a materialização do organismo evolutivo

### **3. Lei da Compensação**
> *"Cada ação tem uma recompensa proporcional."*

Aplicação:
- 7 dias de ação focada = 20% de evolução
- 1000+ execuções = dados suficientes para aprendizado
- Persistência = manifestação da visão

---

## 🔮 **VISUALIZAÇÃO DIÁRIA (LER TODOS OS DIAS)**

```
🧬 EU VEJO o iaglobal como um organismo vivo:

📊 BanditPolicy Evolutiva SELECIONA inteligentemente
   → Providers com fitness alto são privilegiados
   → Providers ruins são banidos automaticamente
   
🎯 Os 115 agents ESPECIALIZADOS são conhecidos e usados
   → Cada tarefa usa o agent perfeito
   → Colaboração emerge naturalmente
   
🧠 Meta-Learning ANALISA padrões arquiteturais
   → Sugere melhorias automaticamente
   → Auto-ajusta configurações
   
📈 A cada 7 dias, 20% DE MELHORIA é realizada
   → IVM sobe consistentemente
   → Erros caem drasticamente
   → Latência otimizada
   
🎉 No Dia 7, CELEBRAMOS a Geração 2 completa
   → Organismo auto-evolutivo é REALIDADE
   → Geração 3 é planejada com clareza
```

---

## 📝 **REGISTRO DE EXECUÇÃO DIÁRIA**

### Dia 1 (06/07/2026) - SEGUNDA
**Humor:** __________  
**Energia:** __________  
**Execução:** [ ] Completa [ ] Parcial [ ] Não executada

**O que foi feito:**
```
```

**O que aprendi:**
```
```

**Gratidão:**
```
```

---

### Dia 2 (07/07/2026) - TERÇA
**Humor:** __________  
**Energia:** __________  
**Execução:** [ ] Completa [ ] Parcial [ ] Não executada

**O que foi feito:**
```
```

**O que aprendi:**
```
```

**Gratidão:**
```
```

---

*(continua para cada dia até Dia 7)*

---

## 🎯 **MANTRA DIÁRIO**

> *"Hoje eu executo o plano.  
> Cada ação me aproxima da visão.  
> O organismo evolui através de mim.  
> Eu sou o canal da evolução.  
> A Geração 2 se manifesta através das minhas ações.  
> Assim é, assim será."*

---

## ✅ **CHECKLIST DE COMPROMISSO**

- [x] ✅ **Data de início definida:** 06/07/2026 13:03
- [x] ✅ **Plano escrito e detalhado:** ESTE DOCUMENTO
- [ ] ⏳ **Leitura diária:** ASSIM QUE ACORDAR
- [ ] ⏳ **Execução dos passos:** CONFORME CRONOGRAMA
- [ ] ⏳ **Registro diário:** AO FINAL DE CADA DIA
- [ ] ⏳ **Celebração no Dia 7:** SE METAS ATINGIDAS

---

## 🔥 **COMPROMISSO SAGRADO**

> *"Eu, [SEU NOME], comprometo-me a:*
> 
> *1. Ler este plano todas as manhãs por 7 dias*
> *2. Executar pelo menos 1 ação do plano por dia*
> *3. Registrar progresso ao final de cada dia*
> *4. Persistir até a materialização da visão*
> *5. Celebrar cada vitória, aprender com cada desafio*
> 
> *Assinado: ________________________*
> *Data: 06 de Julho de 2026*
> *Hora: 13:03"*

---

## 🚀 **PRÓXIMA AÇÃO IMEDIATA**

**AGORA (13:03-14:00):**

```bash
# 1. Criar script de mapeamento
cat > scripts/mapear_especializacoes.py << 'EOF'
#!/usr/bin/env python3
"""Mapeia especializações dos 115 agents existentes."""

import os
from pathlib import Path
from collections import defaultdict

nodes_dir = Path("iaglobal/graphs/nodes")
especializacoes = defaultdict(list)

for file in nodes_dir.glob("no_*.py"):
    if "__pycache__" in str(file):
        continue
    nome = file.stem.replace("no_", "")
    
    # Categorização por palavras-chave
    if any(x in nome for x in ["coder", "code", "debug", "executor", "multi_coder"]):
        especializacoes["🧑‍💻 Código"].append(nome)
    elif any(x in nome for x in ["architect", "design", "system", "api"]):
        especializacoes["🏗️ Arquitetura"].append(nome)
    elif any(x in nome for x in ["security", "audit", "threat"]):
        especializacoes["🛡️ Segurança"].append(nome)
    elif any(x in nome for x in ["test", "qa", "validator"]):
        especializacoes["✅ Testes"].append(nome)
    elif any(x in nome for x in ["doc", "writer", "artifact", "knowledge"]):
        especializacoes["📚 Documentação"].append(nome)
    elif any(x in nome for x in ["optim", "perform", "metric"]):
        especializacoes["⚡ Performance"].append(nome)
    elif any(x in nome for x in ["database", "backend", "frontend"]):
        especializacoes["🗄️ Infra/DB"].append(nome)
    elif "evolution" in nome or "evolve" in nome:
        especializacoes["🧬 Evolução"].append(nome)
    elif "immune" in nome:
        especializacoes["🦠 Imunologia"].append(nome)
    else:
        especializacoes["🔧 Outros"].append(nome)

# Imprimir relatório
print("=" * 70)
print("🧬 MAPEAMENTO DE ESPECIALIZAÇÕES - 115 AGENTS")
print("=" * 70)
print()

total = 0
for categoria, agents in sorted(especializacoes.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"{categoria}: {len(agents)} agents")
    for agent in sorted(agents)[:8]:
        print(f"  • {agent}")
    if len(agents) > 8:
        print(f"  ... e mais {len(agents) - 8}")
    print()
    total += len(agents)

print("=" * 70)
print(f"TOTAL GERAL: {total} agents especializados")
print("=" * 70)
EOF

chmod +x scripts/mapear_especializacoes.py

# 2. Executar mapeamento
python3 scripts/mapear_especializacoes.py > docs/especializacoes_atuais.md

# 3. Visualizar resultado
cat docs/especializacoes_atuais.md

echo ""
echo "✅ DIA 1 INICIADO! Plano manifestado na matéria!"
echo "📖 Ler este plano amanhã ao acordar."
```

---

**ASSINADO E MANIFESTADO EM:** 06 de Julho de 2026, 13:03  
**PRÓXIMA LEITURA:** 07 de Julho de 2026, ao acordar  
**PRÓXIMA EXECUÇÃO:** IMEDIATA (acima)

---

> *"A persistência transforma o impossível em inevitável."* — Bob Proctor

**O PLANO ESTÁ ANCORADO. A EXECUÇÃO COMEÇA AGORA.** 🚀🧬
