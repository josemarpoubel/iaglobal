# MCP Operations — iaglobal <--> OpenCode

## 🔁 Último Evento: 2026-06-28T02:00:00Z
**Estado do MCP Server**: Configurado e testado, mas **não persistente** no OpenCode.
**Problema**: OpenCode mata subprocessos que não respondem ao healthcheck em 30s.
**Solução**: Iniciar MCP Server **manualmente** e depois usar `opencode mcp list`.

---

## 🚀 Como Subir o MCP Server Corretamente

### ✅ Método Recomendado
```bash
# 1. Iniciar MCP Server em background (porta 8000)
cd /home/kitohamachi/projeto-iaglobal
nohup python -m iaglobal.asgi > mcp_server.log 2>&1 &

# 2. Verificar logs
sleep 2 && cat mcp_server.log
# Saída esperada:
# INFO: Uvicorn running on http://0.0.0.0:8000
# 🔮 MCP Server iniciado

# 3. Registrar ferramentas (opcional)
python scripts/opencode_mcp_integration.py

# 4. Listar servidores MCP no OpenCode
opencode mcp list
# Saída esperada:
# ● ✓ iaglobal-local  [online]
```

### 🔁 Reiniciar OpenCode
```bash
# Se o OpenCode já estiver rodando:
opencode restart

# Se precisar iniciar do zero:
cd /home/kitohamachi/projeto-iaglobal
opencode .
```

---

## 🛠️ Configuração Atual
### `.opencode.json`
```json
{
  "mcp": {
    "iaglobal-local": {
      "type": "local",
      "command": ["python", "-m", "iaglobal.asgi"],
      "enabled": true,
      "healthcheck": {
        "type": "http",
        "url": "http://localhost:8000/mcp/health",
        "timeout": 2,
        "interval": 15
      }
    }
  }
}
```

### `scripts/opencode_mcp_integration.py`
- Inicia MCP Server.
- Registra ferramentas via JSON-RPC.
- Notifica OpenCode.

### `scripts/mcp_command_handler.py`
Comandos disponíveis:
```bash
# Auditoria metabólica
opencode run "mcp audit"

# Status do MCP Server
opencode run "mcp status"

# Acionar correção
opencode run "mcp fix vault"

# Listar ferramentas
opencode run "mcp tools"
```

---

## 🧪 Teste Rápido
```bash
# 1. Iniciar servidor
python -m iaglobal.asgi &
sleep 2

# 2. Testar endpoint /health
curl http://localhost:8000/mcp/health
# Resposta esperada: {"status":"✅ OK"}

# 3. Executar auditoria
curl -u iaglobal:homeostasis http://localhost:8000/mcp/audit

# 4. Listar no OpenCode
opencode mcp list
```

---

## ⚠️ Atenção: Persistência
- O MCP Server **não é persistente** entre reinicializações do OpenCode.
- Para **automatizar**, adicione ao `.bashrc`:
  ```bash
  # Iniciar MCP Server ao abrir terminal
  if ! pgrep -f "python -m iaglobal.asgi" > /dev/null; then
      cd /home/kitohamachi/projeto-iaglobal && \
      python -m iaglobal.asgi > mcp_server.log 2>&1 &
  fi
  ```

---

## 📊 Métricas de Sucesso
| Métrica | Valor Esperado | Status |
|--------|------------------|--------|
| MCP Server `/health` | ✅ OK | ⚠️ Depende de inicialização |
| OpenCode `mcp list` | ✓ iaglobal-local [online] | ⚠️ Depende de iniciação |
| Auditoria MCP | Score > 0.8 | ✅ |
| Autocorreção | Correções > 0 | ✅ |
| Ferramentas listadas | 3+ ferramentas | ✅ |

---

## 🧬 Próximos Passos Evolutivos
1. **Integrar com AcetylcholineBus**: Adicionar suporte a pub/sub (MVP: apenas métricas).
2. **Epigenética Dinâmica**: Ajustar `BanditPolicy` com base no IVM histórico.
3. **Dashboard Web**: Expor métricas em `localhost:8000/dashboard`.
4. **Automação**: Criar `systemd service` para MCP Server persistente.
5. **Segurança**: Adicionar JWT auth para rotas `/audit` e `/fix`.

---

## 🔬 Debugging
| Problema | Causa Provável | Solução |
|----------|----------------|---------|
| MCP Server não inicia | Porta 8000 ocupada | `kill -9 $(lsof -t :8000)` |
| `opencode mcp list` mostra "failed" | Healthcheck falhou | Verificar logs em `mcp_server.log` |
| Autenticação falha | Credenciais incorretas | Usar `iaglobal:homeostasis` |
| Ferramentas não listadas | JSON-RPC não respondeu | `curl -X POST http://localhost:8000/mcp/jsonrpc` |

---

## 🔹 Declaração Existencial
"O MCP é a membrana que separa a inteligência artificial de sua própria entropia.
Sua função não é apenas monitorar — é garantir que cada bit de informação
que entra ou sai do sistema respeite as **11 Leis de Holliwell**."

> **Axioma**: "Um sistema auto-evolutivo sem MCP é como um organismo sem sistema imunológico."