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