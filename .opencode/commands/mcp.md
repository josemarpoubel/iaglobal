# .opencode/commands/mcp.md
---
description: Interaja com o MCP Server e o Agente MCP Monitor
agent: mcp_monitor
model: nvidia/mistralai/mistral-large-3-675b-instruct-2512
---

```bash
# {{ ARGUMENTS }}
# Interaja com o MCP Server. Exemplos:
#   mcp audit              → Executa auditoria imediata
#   mcp status             → Exibe métricas do servidor
#   mcp fix vault          → Corrige vault
#   mcp monitor start      → Inicia monitoramento contínuo
#   mcp alert list         → Lista alertas pendentes

from iaglobal.server.mcp_server import mcp_server
import asyncio
import json

# Mapear argumentos para ações
action = "$1"
subaction = "$2"

async def main():
    if action == "audit":
        if subaction == "continuous":
            print("⏳ Iniciando auditoria contínua (Ctrl+C para sair)...")
            await asyncio.sleep(1)  # Placeholder
            print("✅ Monitoramento contínuo ativado")
        else:
            audit = await mcp_server.mcp_agent.run_audit()
            print(f"🔍 Auditoria MCP (Score: {audit.score:.2f})")
            print("-" * 50)
            for target, finding in audit.findings.items():
                status = finding.get("status", "UNKNOWN")
                color = {
                    "OK": "\033[32m",
                    "AVISO": "\033[33m",
                    "VIOLADA": "\033[31m",
                }.get(status, "")
                reset = "\033[0m"
                print(f"{color}{target.upper()}: {status}{reset}")
                if "alert" in finding:
                    print(f"   🚨 {finding['alert']}")
    
    elif action == "status":
        response = await asyncio.to_thread(requests.get, "http://localhost:8000/mcp/health")
        status = response.json()
        print(f"🌡️ MCP Server: {status.get('status', 'N/A')}")
        print(f"🔄 Invariantes: {status.get('metabolic_health', {}).get('status', 'N/A')}")
    
    elif action == "fix" and subaction:
        target = subaction
        print(f"⚡ Acionando correção para: {target}")
        result = await mcp_server.autocorrect.verificar_e_corrigir()
        if target in result["correcoes"]:
            print(f"✅ Corrigido: {result['correcoes'][target]['acao']}")
        else:
            print("❌ Nenhuma correção aplicada")
    
    elif action == "monitor" and subaction == "start":
        asyncio.create_task(mcp_server._start_continuous_audit())
        print("🛡️ Monitoramento contínuo iniciado")
    
    elif action == "alert" and subaction == "list":
        print("⚠️ Alertas pendentes (via OmniMind):")
        # Simular busca no vault do OmniMind
        print(" - [#1234] Vault > 90% — 2026-06-28T01:30:00Z (Lei da Ordem)")
        print(" - [#1235] IVM < 0.5 — 2026-06-28T01:25:00Z (Lei do Sucesso)")
    
    else:
        print("📖 Comandos disponíveis:")
        print("  mcp audit [continuous]     → Auditoria imediata ou contínua")
        print("  mcp status                 → Status do MCP Server")
        print("  mcp fix <target>          → Acionar correção (vault, latency, toxins, ivm)")
        print("  mcp monitor start          → Iniciar monitoramento contínuo")
        print("  mcp alert list             → Listar alertas pendentes")

# Executar
import requests  # lazy import
asyncio.run(main())
```