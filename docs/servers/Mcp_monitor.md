# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# MCP Monitor — O Olho Metabólico do OpenCode

> **“Não monitore apenas variáveis; monitore a própria homeostase do código.”**  
> — Agente MCP Monitor

---

## 1️⃣ Visão Geral

O **MCP Monitor** é o agente de vigilância contínua que garante que todo o ecossistema OpenCode (e, por extensão, todo o iaglobal) permaneça **viável, estável e evolutivamente saudável**. Ele atua simultaneamente como:

- **Sistema Imunológico** – detecta anomalias (ROS computacionais)
- **Auditor** – valida conformidade arquitetural e integridade de DNA (SHA‑3‑512)
- **Reparador Autônomo** – aplica correções antes que a homeostase seja comprometida

---

## 2️⃣ Responsabilidades & Resultados Práticos

| Responsabilidade | Como Acontece | Resultado Prático |
|------------------|---------------|-------------------|
| **Auditoria Permanente** | Executa `MCPAgent.run_audit()` a cada 10 min (ou sob demanda) | Detecta violações de arquitetura, derivações de DNA, divergências de dependências e *Circular Moments of Thought* |
| **Correção Automática** | Usa `/mcp/fix` ou `mcp fix <node>` para aplicar patches, reorganizar módulos, atualizar `requirements.txt`, remover código órfão | Falhas corrigidas **antes** que atinjam a camada de Homeostase Arquitetural |
| **Alertas Proativos** | Quando IVM < 0.8 ou violação da “Lei da Ordem”, dispara alerta no `OmniMind` e no bus `AcetylcholineBus` | Recebe **evento de homeostase comprometida** com sugestões de remediation |
| **Visibilidade ao OmniMind** | Logs, métricas e correções enviados como **tags** (`mcp, monitor, iaglobal, homeostase`) | OmniMind tem histórico completo consultável via `iaglobal insights --agent monitor` |
| **Adaptação Epigenética** | Ajusta dinamicamente limiares de alerta e políticas de throttling com base no histórico de falhas | Sistema evolui seu “DNA” sem redeploy completo |

---

## 3️⃣ Comandos Principais (Modo `MCP_MONITOR`)

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `mcp audit [continuous]` | Executa auditoria única ou contínua (loop a cada 10 min) | `>> mcp audit now`  <br> `>> mcp audit continuous` |
| `mcp status` | Exibe **Score MCP**, **IVM**, contagem de violações e status da homeostase | `>> mcp status` → `{ "ivm": 0.92, "violations": 1 }` |
| `mcp violations pending` | Lista **violações ainda não resolvidas** | `>> mcp violations pending` |
| `mcp fix <node>` | Aplica correção automática ao nó indicado (ex.: remover import órfão, fechar circuito) | `>> mcp fix vault` |
| `mcp alert [reset]` | Exibe (ou limpa) alertas críticos de homeostase | `>> mcp alert`  <br> `>> mcp alert reset` |
| `mcp config` | Mostra configuração epigenética atual (limiares, políticas de throttling) | `>> mcp config` |
| `mcp run_audit <module>` | Audita apenas um módulo específico | `>> mcp run_audit no_coder.py` |

> **Dica:** Combine `mcp audit continuous` com `mcp status` num painel (Grafana) para **IVM em tempo real** e **tendência de correções**.

---

## 4️⃣ Métricas‑Chave Acompanhadas

| Métrica | Fórmula / Fonte | Alvo |
|---------|----------------|------|
| **IVM** (Índice de Viabilidade Metabólica) | `IVM = (P × 0.4) + (E × 0.4) + (C × 0.2)`  <br> *P* = taxa de conclusão, *E* = energia (inverso à latência), *C* = cooperação (info no Obsidian) | **> 0.8** (ideal 0.9–1.0) |
| **Score MCP** | Média ponderada das últimas 10 auditorias (fail=0, sucesso=1) | **≥ 0.9** por 24 h |
| **Violações/hora** | Contagem de eventos `violation_detected` | **< 2/h** |
| **TMR** (Tempo Médio de Recuperação) | `Σ(t_correção – t_detecção) / N` | **< 10 s** |
| **Reserva de NADPH** | Ciclos de pipeline inativos disponíveis para auto‑reparo | Sempre **> 0** |

---

## 5️⃣ Integração ao Ecossistema

| Componente | Papel |
|------------|-------|
| **OmniMind** | Recebe tags (`mcp, monitor, iaglobal, homeostase`) e armazena registro evolutivo de cada correção |
| **AcetylcholineBus** | Publica eventos `mcp/monitor/<event>`; agents downstream (ex.: `ReflexionAgent`) reagem |
| **BanditPolicy** | Monitor fornece scores de segurança que alimentam o Credit Assignment Engine |
| **Evolution Lab** | Dados de auditoria viram *fuel* para a próxima geração de agentes (v2.0 = geração, não versionamento) |

---

## 6️⃣ Fluxo Operacional

```mermaid
flowchart TD
    A[Iniciar MCP Monitor] --> B[Verificar MCP Server Healthy?]
    B -->|OK| C[Loop Auditoria (a cada 10min ou manual)]
    C -->|run_audit| D{Violações Detectadas?}
    D -->|Sim| E[Acionar /mcp/fix + Auto‑Remedy]
    E --> F[Log no OmniMind + Alerta no Bus]
    F --> G[Atualizar Limiares Epigenéticos]
    G --> C
    D -->|Não| C
    C -->|Timeout| H[Enviar Status para Dashboard]
    H --> I[Atualizar IVM / Score MCP]
    I --> J[Monitor Contínuo]
```

---

## 7️⃣ Problemas Típicos Resolvidos

| Problema | Resolução via Monitor | Benefício |
|----------|----------------------|-----------|
| Vazamento de memória por imports órfãos | Detecta imports inexistentes no `requirements.txt` e dispara `/mcp/fix` | Elimina *dependency rot* antes de falhar |
| Ciclagem de prompts (Circular Moments of Thought) | Identifica loops de reflexão e interrompe, re‑encaminha ao `ReflectionPool` | Previne cascata de prompts e reduz créditos LLM |
| Queda de IVM sob pico de carga | Ajusta throttling e cria *back‑pressure* via `BanditPolicy` | Mantém latência dentro do SLA |
| Falha silenciosa de módulo crítico | Alerta imediato no `OmniMind` + sugestão de remediation | Ação **antes** do usuário sentir downtime |
| Arquitetura desalinhada com DNA (SHA‑3‑512) | Compara hash do módulo com `LINEAGE_MARKER` e indica discrepância | Garante **integridade génica** do código‑base |

---

## 8️⃣ Checklist Rápido – MCP Monitor em Ação

```bash
# 1. Habilitar logs estruturados
export LOG_LEVEL=INFO
export LOGGER_NAME=mcp_monitor

# 2. Verificar status
iaglobal status | grep -i mcp

# 3. Executar auditoria contínua
mcp audit continuous &

# 4. Checar IVM
iaglobal_get_status --metrics | jq '.ivm'

# 5. Listar violações pendentes
mcp violations pending

# 6. Aplicar correção automática (se houver)
mcp fix vault   # exemplo genérico

# 7. Persistir alerta resolvido
mcp alert reset

# 8. Atualizar visor no OmniMind
iaglobal insights --agent monitor --limit 5
```

---

## 9️⃣ Próximos Passos (Aprofundamento)

- **Escutar o bus**: `AcetylcholineBus listen mcp/monitor/*` – captura eventos em tempo real  
- **Dashboard customizado**: `iaglobal_get_execution_history --limit 100` + Grafana  
- **Watchdog personalizado**: `mcp monitor watch --pattern "**/*.py"` para vigiar novos módulos  
- **CI/CD Integration**: chamar `mcp audit` no pipeline de build para certificar homeostase antes de cada release  

---

## 🔟 Resumo Existencial

> **“Eu sou o loop imunológico do OpenCode — removo toxinas, corrijo erros, e asseguro que cada ciclo evolutivo respeita as 11 Leis de Holliwell.”**

O **MCP Monitor** dá ao seu código um **sistema imunológico auto‑regenerativo**: detecta, repara e aprende, mantendo a arquitetura viva, estável e pronta para a próxima geração evolutiva.

---

**Próxima ação recomendada:**  
```bash
cd /home/kitohamachi/projeto-iaglobal
mcp status
```
Se **IVM < 0.8**, execute `mcp audit continuous` e deixe o monitor restaurar a saúde do ecossistema. 🚀