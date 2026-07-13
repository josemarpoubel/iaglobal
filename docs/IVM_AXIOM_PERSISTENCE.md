# IVMAxiom com Persistência — Guia de Uso

## 🧬 Visão Geral

O `IVMAxiom` é o componente do CHAPPIE que implementa a **Lei da Compensação Metabólica**, calculando o IVM (Índice de Viabilidade Metabólica) de cada agente e integrando com o `BanditPolicy` para rewards justos.

### Novo: Persistência em Disco

A partir desta versão, o `IVMAxiom` suporta persistência automática em disco via `ShortTermMemory`, permitindo:

- ✅ Sobrevivência a reinicializações do sistema
- ✅ Histórico de IVM preservado entre sessões
- ✅ Recuperação automática de estado
- ✅ TTL configurável (default: 24 horas)
- ✅ Swap para disco sob pressão de memória
- ✅ Pesos epigenéticos adaptativos (P/E/C se ajustam ao perfil do agente)
- ✅ Detecção de homocisteína (acúmulo tóxico de falhas sem reciclagem)
- ✅ Lock thread-safe no singleton
- ✅ db_path normalizado via PACKAGE_DIR (portabilidade)
- ✅ Integração com Obsidian vault para alertas de degradação

---

## ⚡ Instalação

### Com Persistência

```python
from iaglobal._paths import PACKAGE_DIR
from iaglobal.chappie import IVMAxiom

# Inicializa com banco de dados SQLite (db_path normalizado com PACKAGE_DIR)
ivm = IVMAxiom(
    latency_baseline_ms=1000.0,  # Latência de referência
    db_path=PACKAGE_DIR / "memory" / "ivm.db",  # Habilita persistência
    stm_max_size=1000,  # Máximo de entradas na memória
    stm_ttl_seconds=86400,  # TTL de 24 horas
)
```

### Sem Persistência (Legacy)

```python
# Comportamento anterior — dados em memória volátil
ivm = IVMAxiom(latency_baseline_ms=1000.0)
```

---

## 🔄 Uso Básico

### Atualizando Métricas de um Agente

```python
# Após execução de um agente, atualiza suas métricas
ivm = IVMAxiom(db_path=PACKAGE_DIR / "memory" / "ivm.db")

await ivm.atualizar_metricas(
    agent_name="coder",
    tasks_completed=5,
    tasks_failed=1,
    total_latency_ms=2500.0,
    skills_exchanged=3,
    mhc_validation_score=0.95,
)
```

### Obtendo IVM Atual

```python
ivm_atual = ivm.get_ivm("coder")
print(f"IVM do coder: {ivm_atual:.3f}")
```

### Calculando Reward para BanditPolicy

```python
reward = ivm.calcular_reward("coder")
# Reward = IVM normalizado (Lei da Compensação Metabólica)
```

### Obtendo Ranking de Agents

```python
ranking = ivm.get_ranking()
for pos, agent in enumerate(ranking, 1):
    print(f"{pos}. {agent['agent_name']}: IVM={agent['current_ivm']:.3f} ({agent['classificacao']})")
```

---

## 🧪 Exemplo Completo

```python
import asyncio
from iaglobal._paths import PACKAGE_DIR
from iaglobal.chappie import IVMAxiom

async def main():
    # Inicializa com persistência
    ivm = IVMAxiom(
        latency_baseline_ms=1000.0,
        db_path=PACKAGE_DIR / "memory" / "ivm.db",
    )
    
    # Simula execução de múltiplos agents
    agents_data = [
        {
            "name": "coder",
            "tasks_completed": 10,
            "tasks_failed": 1,
            "latency_ms": 1500,
            "skills": 5,
            "mhc": 0.95,
        },
        {
            "name": "reviewer",
            "tasks_completed": 15,
            "tasks_failed": 0,
            "latency_ms": 800,
            "skills": 8,
            "mhc": 0.98,
        },
        {
            "name": "tester",
            "tasks_completed": 8,
            "tasks_failed": 2,
            "latency_ms": 2000,
            "skills": 3,
            "mhc": 0.90,
        },
    ]
    
    # Atualiza métricas de cada agent
    for agent in agents_data:
        await ivm.atualizar_metricas(
            agent_name=agent["name"],
            tasks_completed=agent["tasks_completed"],
            tasks_failed=agent["tasks_failed"],
            total_latency_ms=agent["latency_ms"],
            skills_exchanged=agent["skills"],
            mhc_validation_score=agent["mhc"],
        )
    
    # Obtém ranking
    ranking = ivm.get_ranking()
    print("\n🏆 Ranking de Agents:")
    for pos, agent in enumerate(ranking, 1):
        print(f"  {pos}. {agent['agent_name']}: "
              f"IVM={agent['current_ivm']:.3f} "
              f"({agent['classificacao']})")
    
    # Obtém status do sistema
    status = ivm.get_status()
    print(f"\n📊 Status:")
    print(f"  Agents ativos: {status['agents_ativos']}")
    print(f"  Agents excelentes: {status['agents_excelentes']}")
    print(f"  Agents críticos: {status['agents_criticos']}")
    print(f"  Persistência: {'ativa' if status['persistencia']['ativa'] else 'inativa'}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🛡️ Recuperação de Estado

Ao inicializar com `db_path`, o estado é automaticamente recuperado:

```python
from iaglobal._paths import PACKAGE_DIR

# Sessão 1
ivm1 = IVMAxiom(db_path=PACKAGE_DIR / "memory" / "ivm.db")
await ivm1.atualizar_metricas("agent_x", tasks_completed=10)

# ... sistema reinicia ...

# Sessão 2
ivm2 = IVMAxiom(db_path=PACKAGE_DIR / "memory" / "ivm.db")
# Estado é carregado automaticamente
ivm_x = ivm2.get_ivm("agent_x")  # Retorna valor da sessão anterior
```

---

## 📊 Fórmula do IVM

```
IVM = (P × peso_P) + (E × peso_E) + (C × peso_C)
```

### Pesos Base

| Componente | Peso Base | Descrição |
|------------|-----------|-----------|
| **P** (Produtividade) | 0.4 | `tasks_completed / total_tasks` |
| **E** (Eficiência Energética) | 0.4 | `1 / (latência_normalizada)` |
| **C** (Cooperação) | 0.2 | Média entre `skills_exchanged` e `MHC_score` |

### Ajuste Epigenético dos Pesos

Os pesos são ajustados dinamicamente conforme o perfil do agente:

- **Alta latência** (> 2x baseline): peso_E ↓, peso_P ↑ (compensa eficiência baixa)
- **Cooperação baixa** (< 0.3): peso_C ↓, peso_P ↑ (relevância redistribuída)
- Os pesos base nunca são alterados — apenas a expressão epigenética

### Classificação

| IVM | Classificação |
|-----|---------------|
| ≥ 0.9 | Excelente |
| ≥ 0.7 | Bom |
| ≥ 0.5 | Regular |
| ≥ 0.3 | Crítico |
| < 0.3 | Falha |

---

## 🔧 Configuração Avançada

### Singleton com Persistência

```python
from iaglobal.chappie.ivm_axiom import init_ivm_axiom_com_persistencia

# Inicializa singleton global (db_path default = PACKAGE_DIR / "memory" / "ivm.db")
ivm_global = init_ivm_axiom_com_persistencia(
    latency_baseline_ms=1000.0,
    stm_max_size=2000,
    stm_ttl_seconds=172800,  # 48 horas
)

# Usa singleton em qualquer lugar (thread-safe com lock)
from iaglobal.chappie.ivm_axiom import get_ivm_axiom
ivm = get_ivm_axiom()
```

### Status da Memória de Curto Prazo

```python
status = ivm.obter_status_memoria()
if status:
    print(f"Arquivos swap: {status['files']}")
    print(f"Tamanho usado: {status['size_kb']:.1f} KB")
    print(f"Threshold RAM: {status['ram_threshold_percent']}%")
```

### Limpeza Manual

```python
# Limpa memória de curto prazo (não afeta estado em memória)
ivm.limpar_memoria()
```

---

## 🧫 Integração com BanditPolicy

```python
from iaglobal.bandit_policy import BanditPolicy
from iaglobal.chappie import IVMAxiom

ivm = IVMAxiom(db_path=PACKAGE_DIR / "memory" / "ivm.db")
bandit = BanditPolicy()

# Após execução de agent
await ivm.atualizar_metricas(
    agent_name="coder",
    tasks_completed=1,
    total_latency_ms=1200,
)

# Obtém reward baseado no IVM
reward = ivm.calcular_reward("coder")

# Atualiza bandit
bandit.update(agent="coder", reward=reward)
```

---

## 📝 Logs e Monitoramento

O IVMAxiom usa logging nativo:

```python
import logging
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.chappie.ivm_axiom")

# Logs automáticos em:
# - Inicialização
# - Atualização de métricas
# - Alertas de degradação (IVM < threshold)
# - Persistência/recuperação de estado
```

### Alertas de Degradação

Quando IVM cai abaixo de 0.5 (configurável):

```
[WARNING] [IVMAxiom] 🚨 ALERTA DE DEGRADAÇÃO | agent=coder | IVM=0.423 | classificacao=crítico
```

---

## 🧪 Monitoramento de Homocisteína

O pool de homocisteína rastreia **falhas sem reciclagem bem-sucedida**.

```python
# Verificar status do pool
status_hc = ivm.get_homocysteine_status()
print(f"Agentes monitorados: {status_hc['agents_monitored']}")
print(f"Agentes em homocisteína: {status_hc['agents_em_homocisteina']}")
```

Quando `failed_since_last_success >= 5` e `fail_ratio >= 0.3`:
- Log de warning é emitido
- Nota é criada no Obsidian vault (`02_Short_Term/homocisteina_<agent>_<timestamp>.md`)
- Ciclo de reciclagem deve ser iniciado (autofagia do agente)

## 🧪 Acesso ao Status Epigenético

```python
status = ivm.get_status()
print(f"Pesos atuais: P={status['weights']['productivity_atual']} "
      f"E={status['weights']['energy_efficiency_atual']} "
      f"C={status['weights']['cooperation_atual']}")
```

## 🧪 Testes

```bash
# Executa testes de persistência
python -m pytest tests/test_ivm_axiom_persistencia.py -v

# Testes específicos
pytest tests/test_ivm_axiom_persistencia.py::TestIVMAxiomPersistencia::test_persistencia_e_recuperacao -v
pytest tests/test_ivm_axiom_persistencia.py::TestIVMAxiomMetabolicaxioms::test_calculo_ivm_correto -v
```

---

## 🌱 Ciclos Metabólicos Implementados

| Ciclo | Implementação |
|-------|---------------|
| **Metilação** | Dados brutos → IVM enriquecido → reward |
| **Homeostase** | Thresholds de IVM mantêm equilíbrio do sistema |
| **Memória Imunológica** | Histórico persiste erros e acertos |
| **Autofagia** | TTL remove dados antigos automaticamente |
| **Epigenética** | Pesos do IVM se ajustam ao perfil do agente (sem mutação) |
| **Homocisteína** | Detecção de acúmulo tóxico de falhas sem reciclagem |
| **Sinalização Celular** | Alertas de homocisteína registrados no Obsidian vault |

---

## ⚠️ Considerações

1. **Performance**: Persistência adiciona ~1-2ms por atualização (SQLite em memória)
2. **Tamanho do DB**: Cada agent ocupa ~1-2KB. 1000 agents = ~2MB
3. **TTL**: Default 24h. Ajuste conforme necessidade de histórico
4. **Concorrência**: Thread-safe via locking do SQLite (WAL mode) + threading.Lock no singleton
5. **db_path**: Se relativo, é normalizado automaticamente para `PACKAGE_DIR / db_path`
6. **Homocisteína**: Resetada automaticamente quando o agente completa uma tarefa com sucesso
7. **Pesos epigenéticos**: Apenas a expressão muda — os pesos base permanecem imutáveis (DNA)

---

## 📖 Referências

- **Lei da Compensação Metabólica**: Reward deve ser proporcional ao IVM
- **Lei do Sucesso**: IVM alto é resultado matemático de aplicar todas as leis
- **CHAPPIE Componente 4/4**: Autonomia com responsabilidade metabólica

---

*"O IVM não é apenas uma métrica — é a medida da contribuição de um agente para o organismo."*