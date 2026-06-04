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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP
from iaglobal.api import IAGlobalAPI

api = IAGlobalAPI(lazy_init=False)
mcp = FastMCP("iaglobal")


@mcp.tool()
def run_task(prompt: str) -> str:
    """Executa uma tarefa de engenharia de software no pipeline completo iaglobal.

    O pipeline passa por 13 estagios: planner, web_classifier, search,
    multi_coder, critic, semantic_validator, ast_validator, tester,
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
