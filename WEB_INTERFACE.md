# 🖥️ Interface Web do IAGLOBAL

> **Organismo Computacional Auto-Evolutivo** — Interface própria 100% gratuita.
>
> Paradigma: Auto-Evolutionary Biological Computing  
> Compatibilidade: `iaglobal` · `SAMeEngine` · `GlutathioneLayer` · `AcetylcholineBus`

---

## 1. O que é esta interface

É a **membrana sensorial** do IAGLOBAL: uma interface web local para enviar tarefas, acompanhar execuções em tempo real e inspecionar resultados — sem depender de serviços pagos como GitHub Copilot.

A interface se comunica com o núcleo do organismo via:

- **REST API** (`/api/task`, `/api/tasks`, `/api/metrics`, `/api/health`)
- **WebSocket** (`/ws/progress/{execution_id}`) para progresso em tempo real
- **Workspaces Git isolados** por tarefa, com commits automáticos dos resultados

---

## 2. Pré-requisitos

- Python 3.10+
- Ambiente virtual do projeto ativado
- Dependências instaladas:

```bash
source /home/kitohamachi/projeto-iaglobal/venv/bin/activate
pip install -e .
```

---

## 3. Iniciando a interface

### Comando principal

```bash
iaglobal ui --port 8001
```

### Parâmetros opcionais

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `--port` | `8001` | Porta do servidor HTTP |
| `--host` | `127.0.0.1` | Endereço de bind |
| `--reload` | `false` | Auto-reload para desenvolvimento |

### Exemplos

```bash
# Iniciar na porta padrão
iaglobal ui

# Porta customizada
iaglobal ui --port 8080

# Acessível de qualquer interface
iaglobal ui --host 0.0.0.0 --port 8001
```

### Acesso

| Recurso | URL |
|---------|-----|
| **Dashboard** | `http://localhost:8001/` |
| **API Docs** | `http://localhost:8001/docs` |
| **Health Check** | `http://localhost:8001/api/health` |
| **WebSocket** | `ws://localhost:8001/ws/progress/{execution_id}` |

---

## 4. Usando a interface

### 4.1. Enviando uma tarefa

1. Abra `http://localhost:8001/`
2. No campo **"Nova Tarefa"**, descreva o que deseja executar
3. Clique em **Executar** ou pressione `Enter`

Exemplos de tarefas:

```
Crie uma API REST em FastAPI com endpoints CRUD para usuários
Implemente um componente React que exiba uma lista de tarefas
Escreva um script Python que automatize backup de arquivos
```

### 4.2. Acompanhando o progresso

Após enviar uma tarefa:

- A página atualiza automaticamente a lista de execuções
- O status muda de `pending` → `running` → `completed` ou `failed`
- O WebSocket envia atualizações em tempo real

### 4.3. Visualizando resultados

Quando uma tarefa termina, o resultado aparece na lista de execuções. O conteúdo principal é salvo automaticamente em:

```
/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/result/{execution_id}.txt
```

Essa pasta é servida estaticamente em `/result` quando existe.

---

## 5. Comandos de gerenciamento

### Parar o servidor

```bash
pkill -f "iaglobal.cli.ui_cli"
```

### Verificar se está rodando

```bash
curl -s http://127.0.0.1:8001/api/health
```

### Ver execuções ativas

```bash
curl -s http://127.0.0.1:8001/api/tasks | python3 -m json.tool
```

### Ver métricas

```bash
curl -s http://127.0.0.1:8001/api/metrics | python3 -m json.tool
```

### Limpar workspaces antigos

Os workspaces são limpos automaticamente após o TTL configurado (padrão: 24h).

---

## 6. Estrutura da interface

```
iaglobal/ui/
├── fastapi_app.py          # Servidor FastAPI principal
├── git_workspace.py        # Workspaces Git isolados por tarefa
├── workspace_runner.py     # Integração ExecutionGraph + Git
├── templates/
│   ├── index.html          # Dashboard principal
│   └── dashboard.html      # Página de execução individual
├── static/
│   ├── css/
│   └── js/
└── __init__.py
```

---

## 7. Integração com o ecossistema IAGLOBAL

A interface web se integra com os seguintes componentes:

| Componente | Função |
|------------|--------|
| **ExecutionGraph** | Orquestra os nós do pipeline |
| **BanditPolicy** | Seleciona provedores de IA otimizados |
| **GlutathionePool** | Defesa antioxidante contra falhas |
| **AcetylcholineBus** | Sinalização celular entre agentes |
| **WorkspaceRunner** | Executa tarefas em workspaces isolados |
| **ObsidianVault** | Memória de longo prazo (opcional) |

---

## 8. Troubleshooting

### Porta já em uso

```bash
pkill -f "iaglobal.cli.ui_cli"
pkill -f "uvicorn"
sleep 2
iaglobal ui --port 8001
```

### Servidor não responde

```bash
# Verificar se o processo está rodando
ps aux | grep iaglobal.cli.ui_cli

# Verificar logs
curl -s http://127.0.0.1:8001/api/health
```

### Tarefa trava em running

- Verifique se o provedor de IA está configurado no `.env`
- Verifique logs do servidor para erros de timeout
- Aumente o timeout via variável de ambiente:

```bash
export RUNNER_TASK_TIMEOUT=600
iaglobal ui --port 8001
```

### Resultado não aparece em `memory/data/result`

- O arquivo só é criado após a tarefa terminar (`completed`, `failed` ou `cancelled`)
- Verifique se o `final_output` foi preenchido na resposta da API
- Tarefas que falham podem não gerar arquivo de resultado

---

## 9. Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `RUNNER_TASK_TIMEOUT` | `300` | Timeout de tarefa em segundos |
| `RUNNER_MAX_WORKSPACES` | `50` | Máximo de workspaces ativos |
| `RUNNER_WORKSPACE_TTL_HOURS` | `24` | TTL de workspaces em horas |
| `UI_RATE_LIMIT` | `120` | Requisições por minuto por IP |
| `UI_MAX_EXECUTIONS` | `1000` | Máximo de execuções em memória |
| `UI_EXECUTION_TTL_HOURS` | `24` | TTL de execuções em horas |

---

## 10. Segurança

- A interface roda apenas em `localhost` por padrão (`127.0.0.1`)
- Não exponha a porta 8001 para a internet sem autenticação
- O rate limiter protege contra abuso (`120 req/min` por IP)
- Circuit breaker bloqueia requisições em caso de falhas em cascata

---

## 11. Próximos passos

Melhorias planejadas:

- [ ] Template engine para HTML/CSS
- [ ] Cache de assets estáticos
- [ ] Pipeline de otimização automática
- [ ] Integração mais profunda com ObsidianVault
- [ ] Visualização de grafo de execução

---

*"A célula que não evolui, morre. O sistema que não aprende, entra em entropia."*
