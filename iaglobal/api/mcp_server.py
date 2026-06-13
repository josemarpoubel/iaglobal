#!/usr/bin/env python3
# iaglobal/api/mcp_server.py

"""
MCP Server para iaglobal — permite que opencode (ou qualquer cliente MCP)
execute tarefas de geracao de codigo, consulte status e aprendizado.

Uso direto:
    python -m iaglobal.api.mcp_server

Registro no opencode.json:
    {
        "mcp": {
            "iaglobal": {
                "type": "local",
                "command": ["python", "-m", "iaglobal.api.mcp_server"],
                "enabled": true,
                "timeout": 300000
            }
        }
    }
"""

import sys
import os
from contextlib import contextmanager

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

_original_stdout = sys.stdout
sys.stdout = sys.stderr

from mcp.server.fastmcp import FastMCP
from iaglobal.api import IAGlobalAPI
api = IAGlobalAPI(lazy_init=False)

sys.stdout = _original_stdout

mcp = FastMCP("iaglobal")

from iaglobal.providers.provider_metrics import metrics
from iaglobal.providers.provider_load_balancer import load_balancer
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.core.retry_handler import RetryHandler


@mcp.tool()
def run_task(prompt: str) -> str:
    """Executa uma tarefa de engenharia de software no pipeline completo iaglobal.

    O pipeline passa por 13 estagios: planner, web_classifier, search,
    multi_coder, critic, validator, ast_validator, tester,
    debugger, rank_final, final_gatekeeper, artifact_writer, reflexion.

    O resultado e um script Python salvo em disco com o caminho exibido.

    Args:
        prompt: Descricao da tarefa (ex: 'crie um bloco genesis em sha3_512 para Bit512')
    """
    result = api.run_task(prompt)
    lines = []
    if result["success"]:
        lines.append(f"✅ Tarefa concluida em {result['execution_time']}s")
        if result["script_path"]:
            lines.append(f"📁 Script salvo em: {result['script_path']}")
        if result["response"]:
            lines.append(f"📄 Codigo gerado ({len(result['response'])} caracteres)")
            lines.append("```python")
            lines.append(result["response"][:2000])
            if len(result["response"]) > 2000:
                lines.append("# ... (codigo truncado, veja o arquivo completo)")
            lines.append("```")
        if result["score"]:
            lines.append(f"🏆 Score: {result['score']:.2f}")
    else:
        lines.append(f"❌ Erro: {result['error']}")
    return "\n".join(lines)


@mcp.tool()
def get_status() -> str:
    """Retorna o status atual do sistema iaglobal.

    Inclui: resumo do DAG (total/core/evo nodes), status da evolucao,
    metricas de memoria (insights, erros) e configuracao de seguranca.
    """
    status = api.get_status()
    lines = [
        "📊 IAGlobal Status",
        "=" * 40,
        "",
        f"  Graph gen: {status['version']['graph_gen']}",
        f"  Python: {status['version']['python']}",
        "",
        "── DAG ──",
        f"  Total nodes: {status['dag']['nodes_total']}",
        f"  Core: {status['dag']['nodes_core']} | EVO: {status['dag']['nodes_evo']}",
        f"  Strategies: {status['dag']['strategies']}",
        "",
        "── Evolution ──",
        f"  Running: {'yes' if status['evolution']['running'] else 'no'}",
        f"  Cycles: {status['evolution']['cycles']}",
        f"  Failures: {status['evolution']['failures']}",
        "",
        "── Memory ──",
        f"  Insights: {status['memory']['insights']}",
        f"  Errors: {status['memory']['errors']}",
        "",
        "── Security ──",
        f"  Modules: {status['security']['modules']}",
        f"  Read paths: {status['security']['read_paths']}",
        f"  Write paths: {status['security']['write_paths']}",
        f"  Blocked env vars: {status['security']['blocked_env']}",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_insights(agent: str = "", limit: int = 10, min_score: float = 0.0) -> str:
    """Recupera aprendizados armazenados pelos agentes do sistema.

    Os insights sao registros estruturados do que o sistema aprendeu
    durante execucoes anteriores (erros, correcoes, padroes).

    Args:
        agent: Filtrar por agente (ex: 'reflexion', 'orchestrator'). Vazio = todos.
        limit: Maximo de registros (default 10)
        min_score: Score minimo (0-100, default 0)
    """
    records = api.get_insights(
        agent=agent if agent else None,
        limit=limit,
        min_score=min_score if min_score > 0 else None,
    )
    if not records:
        return "Nenhum insight encontrado."

    lines = [f"📚 {len(records)} insights", "=" * 40, ""]
    for r in records:
        score_bar = "█" * max(1, int(r["score"] / 5)) + "░" * max(0, 20 - int(r["score"] / 5))
        lines.append(f"  [{r['agent']}] score={r['score']:.0f} {score_bar}")
        lines.append(f"  {r['content'][:120]}")
        lines.append(f"  task_id={r['task_id']} | {r['timestamp']}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def list_scripts() -> str:
    """Lista todos os scripts Python gerados e persistidos pelo sistema."""
    scripts = api.list_scripts()
    if not scripts:
        return "Nenhum script gerado ainda."

    lines = [f"📁 {len(scripts)} scripts gerados", "=" * 40, ""]
    for s in scripts:
        from datetime import datetime
        modified = datetime.fromtimestamp(s["modified"]).strftime("%H:%M:%S")
        size_kb = s["size"] / 1024
        lines.append(f"  {s['name']:<60} {size_kb:>6.1f}KB  {modified}")
    return "\n".join(lines)


@mcp.tool()
def get_provider_metrics() -> str:
    """Metricas de desempenho por provedor (chamadas, taxa de sucesso, latencia, custo).

    Os dados sao agregados pelo ProviderMetrics a partir de cada chamada
    de API realizada pelo pipeline.
    """
    stats = metrics.get_provider_stats()
    if not stats:
        return "Nenhuma metrica de provedor registrada ainda."

    lines = ["📊 Metricas por Provedor", "=" * 50, ""]
    lines.append(f"  {'Provedor':<20} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Custo':>8} {'Tokens':>8}")
    lines.append(f"  {'─'*20} {'─'*9} {'─'*8} {'─'*9} {'─'*8} {'─'*8}")
    for prov, data in sorted(stats.items(), key=lambda x: x[1].get("calls", 0), reverse=True):
        calls = data.get("calls", 0)
        sr = data.get("success_rate", 0)
        lat = data.get("avg_latency", 0)
        cost = data.get("total_cost", 0)
        tokens = data.get("avg_tokens", 0)
        lines.append(f"  {prov:<20} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms ${cost:<6.4f} {tokens:>8}")
    lines.append("")
    lines.append("── Disponibilidade ──")
    for prov, state in sorted(load_balancer.state.providers.items()):
        avail = "🟢" if load_balancer.state.is_available(prov) else "🔴"
        cooldown = ""
        if state.cooldown_until > 0:
            remaining = max(0, state.cooldown_until - __import__("time").time())
            cooldown = f" (cooldown: {remaining:.0f}s)"
        lines.append(f"  {avail} {prov:<18} sucesso={state.success} falhas={state.fail}{cooldown}")
    return "\n".join(lines)


@mcp.tool()
def get_model_metrics(min_calls: int = 1) -> str:
    """Metricas de desempenho por modelo (chamadas, taxa de sucesso, latencia, custo).

    Args:
        min_calls: Minimo de chamadas para incluir o modelo (default 1)
    """
    stats = metrics.get_model_stats()
    if not stats:
        return "Nenhuma metrica de modelo registrada ainda."

    lines = ["📊 Metricas por Modelo", "=" * 55, ""]
    filtered = {k: v for k, v in stats.items() if v.get("calls", 0) >= min_calls}
    if not filtered:
        return f"Nenhum modelo com {min_calls}+ chamadas."

    lines.append(f"  {'Modelo':<35} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Tokens':>8}")
    lines.append(f"  {'─'*35} {'─'*9} {'─'*8} {'─'*9} {'─'*8}")
    for model, data in sorted(filtered.items(), key=lambda x: x[1].get("calls", 0), reverse=True):
        calls = data.get("calls", 0)
        sr = data.get("success_rate", 0)
        lat = data.get("avg_latency", 0)
        tokens = data.get("avg_tokens", 0)
        lines.append(f"  {model:<35} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms {tokens:>8}")
    return "\n".join(lines)


@mcp.tool()
def get_bandit_scores() -> str:
    """Exibe os scores do BanditPolicy para cada modelo candidato.

    Mostra como o algoritmo ε-greedy esta classificando os modelos
    com base no historico de sucesso/falha do CreditAssignmentEngine.
    """
    try:
        orch = api.orchestrator
        bandit = orch.bandit
        credit = bandit.credit
    except Exception:
        return "BanditPolicy nao disponivel (orchestrator nao inicializado)."

    if not credit.stats:
        return "Nenhum score de bandit registrado ainda."

    lines = ["🎲 BanditPolicy — Scores por Modelo", "=" * 50, ""]
    lines.append(f"  {'Modelo':<35} {'Sucesso':>8} {'Falhas':>8} {'Score':>7} {'Latencia':>9}")
    lines.append(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*7} {'─'*9}")
    for key, data in sorted(credit.stats.items(), key=lambda x: x[1].get("success", 0), reverse=True):
        node, model, strategy = key
        suc = data.get("success", 0)
        fail = data.get("fail", 0)
        total = suc + fail
        score = suc / total if total > 0 else 0
        lat = data.get("latency", 0)
        avg_lat = lat / total if total > 0 else 0
        lines.append(f"  {model:<35} {suc:>8} {fail:>8} {score:>6.2f} {avg_lat:>8.0f}ms")
    return "\n".join(lines)


@mcp.tool()
def get_execution_history(limit: int = 10) -> str:
    """Historico das ultimas execucoes do pipeline.

    Args:
        limit: Numero de execucoes (default 10)
    """
    try:
        from iaglobal.events import store as decision_store
        events = decision_store.query(limit=limit)
    except Exception:
        return "DecisionEventStore nao disponivel."

    if not events:
        return "Nenhum evento de execucao registrado."

    lines = ["📜 Historico de Execucoes", "=" * 50, ""]
    for ev in events:
        step = ev.get("step", "?")
        action = ev.get("action", "")
        selected = ev.get("selected", "")
        result = ev.get("result", "")
        ts = ev.get("timestamp", "")[11:19] if ev.get("timestamp") else ""
        line = f"  [{ts}] {step:<18}"
        if action:
            line += f" {action:<20}"
        if selected:
            line += f" → {selected}"
        if result:
            line += f" = {result}"
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
