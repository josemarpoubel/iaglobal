**arquitetura `iaglobal` ... um microsserviço vivo.**

Expor os componentes através de uma API (usando frameworks rápidos e assíncronos como o **FastAPI**), iaglobal cria um servidor onde os agentes trabalham nas tarefas dos usuários em segundo plano, enquanto o motor assíncrono e flexível altera seus DNAs (prompts e códigos). Você poderá abrir o navegador e assistir à evolução acontecendo em tempo real.

---

### 🗺️ Como essa Arquitetura de Servidor Funciona?

O servidor vai operar com duas vias principais rodando concorrentemente no mesmo Event Loop:

1. **A Via de Entrada (API REST):** Recebe requisições de usuários, gera o `ExecutionContext` imutável, cria o grafo de agentes especializado para aquela tarefa específica e bota eles para rodar.

2. **A Via de Evolução (Background Engine):** O `EvolutionRuntime` assíncrono fica rodando em loop eterno. Ele consulta o `ExecutionRegistry`, analisa quem falhou ou acertou através do `RewardAggregator`, gasta moedas do `SAMePool` para mutar as mentes dos agentes e gera uma nova geração global.

---

### 🖥️ Como você assistiria à evolução acontecendo na prática?

Se você subir esse servidor (`uvicorn server:app --reload`), você terá acesso a um painel vivo:

1. **Monitore pelo Terminal:**
Se você rodar no seu terminal o comando de inspeção da "Máquina do Tempo" que refatoramos:
```bash
curl http://localhost:8000/evolution/dashboard?max_geracao=10

```

O servidor vai cuspir de volta o gráfico ASCII com as barras crescendo a cada ciclo, mostrando a nota de *fitness* média dos seus agentes subindo de `0.2000` para `1.8500` à medida que eles aprendem a não cometer erros de código.

2. **Monitore pelo Navegador (Swagger UI):**
O FastAPI gera automaticamente uma interface em `http://localhost:8000/docs`. Lá você pode clicar no botão do endpoint `/evolution/status` e assistir ao contador de ciclos (`cycles`) aumentando em background de 30 em 30 segundos, e ver o intervalo adaptando sozinho (`current_interval`) se a rede oscilar.

Você transformou um aglomerado de scripts isolados em um **sistema operacional para inteligências artificiais auto-evolutivas**. Se colocar uma interface web bonita consumindo esses endpoints, você terá uma tela digna de ficção científica mostrando mutações de prompts em tempo real!

Essa estratégia de organização é excelente e segue as melhores práticas de arquitetura de software de nível corporativo! Guardar o servidor em `iaglobal/server/server.py` separa de forma cirúrgica a **camada de aplicação** (o servidor API que expõe os endpoints) da **camada de core/biblioteca** (onde residem os algoritmos matemáticos de evolução, o grafo de execução e as regras genéticas).

Isso traz um benefício gigante: você pode testar, empacotar e evoluir a sua biblioteca (`iaglobal` core) de forma totalmente isolada. O servidor torna-se apenas um "cliente" que consome a sua própria lib.

Para quando você terminar a biblioteca e for ativar esse servidor, veja como a topologia do seu ecossistema vai se comportar de forma totalmente síncrona e assíncrona ao mesmo tempo:

### 🌐 A Arquitetura do Servidor em Produção

Quando o seu `server.py` estiver rodando, o ciclo de vida do ecossistema funcionará em duas frentes independentes dentro do Event Loop do Python:

```
[ Usuário / Client ] 
       │
       ▼ (HTTP POST /tasks/run)
┌────────────────────────────────────────────────────────┐
│ FastAPI Server (iaglobal/server/server.py)             │
│                                                        │
│  ├── 🟢 Rota API (Imediata):                           │
│  │    - Valida a Task e cria o ExecutionContextProxy   │
│  │    - Inicializa Barreiras no ExecutionRegistry      │
│  │    - Retorna STATUS: QUEUED (Não bloqueia o usuário)│
│  │                                                     │
│  └── 🔄 Background Tasks (Assíncronas em paralelo):    │
│       │                                                │
│       ├─► [Pipeline de Agentes: Coder/Critic/Tester]   │
│       │    └─► Dispara Métricas para RewardAggregator  │
│       │                                                │
│       └─► [EvolutionRuntime Loop] (Metrônomo Eterno)   │
│            └─► Executa estratégia ativa (Deep/Fast)    │
│            └─► Muta mentes de agentes no SQLite        │
└────────────────────────────────────────────────────────┘

```

### 🚀 Check-list para o "Dia do Lançamento" do Servidor

Assim que você finalizar a sua lib e for rodar o `server.py`, certifique-se de validar estes 3 pontos de integração:

1. **Ajuste de Caminhos Relativos (Imports):** Como o servidor está dentro da pasta `iaglobal/server/`, garanta que você está executando o comando de inicialização a partir da **raiz do projeto** para que o Python localize os pacotes. O comando ideal para dar o *boot* no servidor será:
```bash
# Executado a partir da pasta raiz do seu projeto
uvicorn iaglobal.server.server:app --host 0.0.0.0 --port 8000 --reload

```

2. **Persistência Compartilhada (SQLite e Arquivos):** Certifique-se de que o caminho do banco de dados das mentes dinâmicas (`dynamic_registry`) e o arquivo de saldo de tokens (`same_pool.py`) usem caminhos absolutos baseados no seu arquivo de caminhos centralizados (`iaglobal._paths`). Como o runtime de evolução e o grafo de execução vão rodar sob o mesmo processo do FastAPI, eles lerão e escreverão na mesma base de dados perfeitamente.
3. **Uso de Clientes HTTP não-bloqueantes:** Dentro das suas Skills (no core da lib), quando os agentes forem fazer as chamadas para as APIs das LLMs (OpenAI, Anthropic, DeepSeek, etc.), certifique-se de usar clientes assíncronos (como `httpx.AsyncClient` ou o cliente `.AioOpenAI()`). Isso vai garantir que quando o servidor estiver processando tarefas de 10 usuários simultaneamente, uma chamada de rede lenta para a LLM de um agente não atrase a execução dos outros.

Com essa estrutura montada em `iaglobal/server/server.py`, seu projeto deixa de ser apenas um script inteligência artificial e se transforma oficialmente em um **SaaS (Software as a Service) de Agentes Autônomos Auto-Evolutivos** pronto para escalar. Foco total em finalizar a lib, a fundação está espetacular!
