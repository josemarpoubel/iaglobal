#!/usr/bin/env python3
# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/api/mcp_server.py

"""
MCP Server para iaglobal — permite que opencode (ou qualquer cliente MCP)
execute tarefas de geracao de codigo, consulte status e aprendizado.

DEPRECATED: Este servidor foi consolidado em iaglobal/mcp/server.py

Uso direto:
    python -m iaglobal.mcp.server --mode both

Registro no opencode.json:
    {
        "mcp": {
            "iaglobal": {
                "type": "local",
                "command": ["python", "-m", "iaglobal.mcp.server", "--mode", "both"],
                "enabled": true,
                "timeout": 300000
            }
        }
    }
"""

import asyncio
import sys
import logging
from mcp.server.fastmcp import FastMCP

# WARNING: DEPRECATED - Este servidor foi consolidado em iaglobal/mcp/server.py
# Use: python -m iaglobal.mcp.server --mode both
# Este arquivo será removido em futura versão.

from iaglobal.api import IAGlobalAPI
from iaglobal.core.orchestrator import get_orchestrator
from iaglobal.providers.provider_metrics import metrics

# Definição Global do Servidor
mcp = FastMCP("iaglobal")

# Inicialização da API
api = IAGlobalAPI(lazy_init=True)

# Variável única para controlar o estado da tarefa
_init_task = None


async def ensure_system_ready():
    """Garante que o orquestrador seja inicializado apenas uma vez e em background."""
    global _init_task

    # Se ainda não existe tarefa, cria uma
    if _init_task is None:
        orchestrator = get_orchestrator()
        _init_task = asyncio.create_task(orchestrator.initialize())
        # Opcional: log para monitorar o início do carregamento
        print("[MCP Server] Background initialization started.")

    return _init_task


async def _ensure_api_async() -> None:
    """Versão async — usa initialize_async() que respeita event loop ativo."""
    if not api._initialized:
        await api.initialize_async()


def _ensure_api() -> None:
    """Versão sync — para contexts sem event loop ativo."""
    api.initialize()


@mcp.tool()
async def run_task(prompt: str) -> str:
    """Executa uma tarefa de engenharia de software no pipeline completo iaglobal.

    O pipeline passa por 13 estagios: planner, web_classifier, search,
    multi_coder, critic, validator, ast_validator, tester,
    debugger, rank_final, final_gatekeeper, artifact_writer, reflexion.

    O resultado e um script Python salvo em disco com o caminho exibido.

    Args:
        prompt: Descricao da tarefa (ex: 'crie um bloco genesis em sha3_512 para Bit512')
    """
    await _ensure_api_async()
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
async def get_status() -> str:
    """Retorna o status atual do sistema iaglobal.

    Inclui: resumo do DAG (total/core/evo nodes), status da evolucao,
    metricas de memoria (insights, erros) e configuracao de seguranca.
    """

    asyncio.create_task(ensure_system_ready())

    # Garante a inicialização, mas evita travar o loop principal se ainda carregando
    await _ensure_api_async()

    status = api.get_status()

    # Verifica se o orquestrador está pronto (caso o dict retorne vazio ou erro)
    if not status:
        return "⚠️ IAGlobal: Sistema em fase de inicialização ou sem resposta da API."

    # Helper para facilitar o acesso seguro aos dados
    def get_val(path: list, default="N/A"):
        curr = status
        for key in path:
            curr = curr.get(key, {})
        return curr if curr != {} else default

    def safe_len(val):
        return len(val) if isinstance(val, (list, dict, str)) else val

    lines = [
        "📊 IAGlobal Status",
        "=" * 40,
        "",
        f"  Graph gen: {get_val(['version', 'graph_gen'])}",
        f"  Python:    {get_val(['version', 'python'])}",
        "",
        "── DAG ──",
        f"  Total nodes: {get_val(['dag', 'nodes_total'])}",
        f"  Core: {get_val(['dag', 'nodes_core'])} | EVO: {get_val(['dag', 'nodes_evo'])}",
        f"  Strategies: {get_val(['dag', 'strategies'])}",
        "",
        "── Evolution ──",
        f"  Running: {'yes' if get_val(['evolution', 'running']) else 'no'}",
        f"  Cycles: {get_val(['evolution', 'cycles'])}",
        f"  Failures: {get_val(['evolution', 'failures'])}",
        "",
        "── Memory ──",
        f"  Insights: {get_val(['memory', 'insights'])}",
        f"  Errors: {get_val(['memory', 'errors'])}",
        "",
        "── Security ──",
        f"  Modules: {safe_len(get_val(['security', 'modules'], []))}",
        f"  Read paths: {safe_len(get_val(['security', 'read_paths'], []))}",
        f"  Write paths: {safe_len(get_val(['security', 'write_paths'], []))}",
        f"  Blocked env: {safe_len(get_val(['security', 'blocked_env'], []))}",
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_insights(agent: str = "", limit: int = 10, min_score: float = 0.0) -> str:
    """Recupera aprendizados armazenados pelos agentes do sistema.

    Os insights sao registros estruturados do que o sistema aprendeu
    durante execucoes anteriores (erros, correcoes, padroes).

    Args:
        agent: Filtrar por agente (ex: 'reflexion', 'orchestrator'). Vazio = todos.
        limit: Maximo de registros (default 10)
        min_score: Score minimo (0-100, default 0)
    """
    await _ensure_api_async()
    records = api.get_insights(
        agent=agent if agent else None,
        limit=limit,
        min_score=min_score if min_score > 0 else None,
    )
    if not records:
        return "Nenhum insight encontrado."

    lines = [f"📚 {len(records)} insights", "=" * 40, ""]
    for r in records:
        score_bar = "█" * max(1, int(r["score"] / 5)) + "░" * max(
            0, 20 - int(r["score"] / 5)
        )
        lines.append(f"  [{r['agent']}] score={r['score']:.0f} {score_bar}")
        lines.append(f"  {r['content'][:120]}")
        lines.append(f"  task_id={r['task_id']} | {r['timestamp']}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def list_scripts() -> str:
    """Lista todos os scripts Python gerados e persistidos pelo sistema."""
    await _ensure_api_async()
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
async def get_provider_metrics() -> str:
    """Metricas de desempenho por provedor (chamadas, taxa de sucesso, latencia, custo).

    Os dados sao agregados pelo ProviderMetrics a partir de cada chamada
    de API realizada pelo pipeline.
    """
    await _ensure_api_async()
    stats = metrics.get_provider_stats()
    if not stats:
        return "Nenhuma metrica de provedor registrada ainda."

    lines = ["📊 Metricas por Provedor", "=" * 50, ""]
    lines.append(
        f"  {'Provedor':<20} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Custo':>8} {'Tokens':>8}"
    )
    lines.append(f"  {'─' * 20} {'─' * 9} {'─' * 8} {'─' * 9} {'─' * 8} {'─' * 8}")
    for prov, data in sorted(
        stats.items(), key=lambda x: x[1].get("calls", 0), reverse=True
    ):
        calls = data.get("calls", 0)
        sr = data.get("success_rate", 0)
        lat = data.get("avg_latency", 0)
        cost = data.get("total_cost", 0)
        tokens = data.get("avg_tokens", 0)
        lines.append(
            f"  {prov:<20} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms ${cost:<6.4f} {tokens:>8}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_model_metrics(min_calls: int = 1) -> str:
    """Metricas de desempenho por modelo (chamadas, taxa de sucesso, latencia, custo).

    Args:
        min_calls: Minimo de chamadas para incluir o modelo (default 1)
    """
    await _ensure_api_async()
    stats = metrics.get_model_stats()
    if not stats:
        return "Nenhuma metrica de modelo registrada ainda."

    lines = ["📊 Metricas por Modelo", "=" * 55, ""]
    filtered = {k: v for k, v in stats.items() if v.get("calls", 0) >= min_calls}
    if not filtered:
        return f"Nenhum modelo com {min_calls}+ chamadas."

    lines.append(
        f"  {'Modelo':<35} {'Chamadas':>9} {'Sucesso':>8} {'Lat.Media':>9} {'Tokens':>8}"
    )
    lines.append(f"  {'─' * 35} {'─' * 9} {'─' * 8} {'─' * 9} {'─' * 8}")
    for model, data in sorted(
        filtered.items(), key=lambda x: x[1].get("calls", 0), reverse=True
    ):
        calls = data.get("calls", 0)
        sr = data.get("success_rate", 0)
        lat = data.get("avg_latency", 0)
        tokens = data.get("avg_tokens", 0)
        lines.append(f"  {model:<35} {calls:>9} {sr:>7.1%} {lat:>8.0f}ms {tokens:>8}")
    return "\n".join(lines)


@mcp.tool()
async def get_bandit_scores() -> str:
    """Exibe os scores do BanditPolicy para cada modelo candidato.

    Mostra como o algoritmo ε-greedy esta classificando os modelos
    com base no historico de sucesso/falha do CreditAssignmentEngine.
    """
    await _ensure_api_async()
    try:
        orch = api.orchestrator
        bandit = orch.bandit
        credit = bandit.credit
    except Exception:
        return "BanditPolicy nao disponivel (orchestrator nao inicializado)."

    if not credit.stats:
        return "Nenhum score de bandit registrado ainda."

    lines = ["🎲 BanditPolicy — Scores por Modelo", "=" * 50, ""]
    lines.append(
        f"  {'Modelo':<35} {'Sucesso':>8} {'Falhas':>8} {'Score':>7} {'Latencia':>9}"
    )
    lines.append(f"  {'─' * 35} {'─' * 8} {'─' * 8} {'─' * 7} {'─' * 9}")
    for key, data in sorted(
        credit.stats.items(), key=lambda x: x[1].get("success", 0), reverse=True
    ):
        node, model, strategy = key
        suc = data.get("success", 0)
        fail = data.get("fail", 0)
        total = suc + fail
        score = suc / total if total > 0 else 0
        lat = data.get("latency", 0)
        avg_lat = lat / total if total > 0 else 0
        lines.append(
            f"  {model:<35} {suc:>8} {fail:>8} {score:>6.2f} {avg_lat:>8.0f}ms"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_execution_history(limit: int = 10) -> str:
    """Historico das ultimas execucoes do pipeline.

    Args:
        limit: Numero de execucoes (default 10)
    """
    await _ensure_api_async()
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


@mcp.tool()
async def get_system_health(max_age_seconds: int = 3600) -> str:
    """Relatório de saúde do sistema baseado em life-signals.

    Mostra o status ALIVE/HIBERNATING/DEAD das funções instrumentadas
    que compõem o metabolismo do iaglobal.

    Args:
        max_age_seconds: Idade máxima para considerar função viva (default: 3600s)
    """
    try:
        from iaglobal.utils.life_signal_collector import collector
    except Exception:
        return "LifeSignalCollector nao disponivel."

    report = collector.get_report()
    if report["total_functions"] == 0:
        return "Nenhum life-signal registrado ainda. Instrumentacao ativa mas sem invocacoes."

    lines = ["🩺 Saúde do Sistema — Life Signals", "=" * 50, ""]
    lines.append(f"Funções monitoradas: {report['total_functions']}")
    lines.append(f"Total de sinais: {report['total_signals']}")
    lines.append("")

    alive = 0
    hibernating = 0
    dead = 0

    for func, data in sorted(report["functions"].items()):
        status = data["status"]
        if "ALIVE" in status:
            icon = "✅"
            alive += 1
        elif "HIBERNATING" in status:
            icon = "🌡️"
            hibernating += 1
        else:
            icon = "❌"
            dead += 1

        lines.append(f"  {icon} {func}")
        lines.append(f"      {status}")
        if data.get("last_seen_iso"):
            lines.append(f"      Último sinal: {data['last_seen_iso']}")

    lines.append("")
    lines.append("── Resumo ─-")
    lines.append(f"  ALIVE: {alive}")
    lines.append(f"  HIBERNATING: {hibernating}")
    lines.append(f"  DEAD: {dead}")

    if dead > 0:
        lines.append("")
        lines.append(
            "⚠️  Funções mortas podem ser candidatas a remoção (requer confirmação)."
        )

    return "\n".join(lines)


async def run_server():
    """Inicializa o MCP Server de forma assíncrona e responsiva."""

    # 1. Cria uma tarefa de fundo para carregar o sistema pesado
    # Isso libera o loop principal para responder ao handshake do OpenCode imediatamente
    asyncio.create_task(load_system_components())

    # 2. Inicia o MCP Server imediatamente
    logging.warning("Iniciando MCP Server via run_stdio_async...")
    try:
        await mcp.run_stdio_async()
    except Exception as e:
        logging.error(f"Erro fatal no MCP Server: {e}")
        sys.exit(1)


async def load_system_components():
    """Carrega os componentes pesados em background."""
    orchestrator = get_orchestrator()
    await orchestrator.initialize()
    logger = logging.getLogger("iaglobal.api.mcp_server")
    logger.info("Componentes IAGlobal carregados em background.")

    logging.warning("Sistema IAGlobal carregado com sucesso em background.")


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        sys.exit(0)
