"""
Re-benchmark oficial de latência do pipeline completo após integração do provider cascade.
Valida performance do DAG com handlers reais e providers cloud + Ollama.
"""
import asyncio
import json
import time
from pathlib import Path


async def run_pipeline_through_orchestrator(task_prompt: str) -> tuple[bool, float, dict]:
    """Executa um prompt pelo orchestrator completo e retorna métricas de latência."""
    from iaglobal.core.orchestrator import Orchestrator
    from iaglobal.graphs.execution_graph import ExecutionGraph

    # Instancia orchestrator e graph sem argumentos (correção da 8ª rodada)
    orchestrator = Orchestrator()
    graph = ExecutionGraph(tool_router=None)
    orchestrator.graph = graph
    orchestrator.evolution_runtime.running = False  # Garante que não rode evolucionário automático

    start = time.time()
    try:
        result = await orchestrator.async_run_graph_task(
            task_prompt,
            chosen_model="",  # Auto-selection pelo bandit
            parallel=True,
        )
        latency = time.time() - start
        success = result.get("success", False)
        execution_time = result.get("execution_time", latency)
        return success, execution_time, result
    except Exception as e:
        latency = time.time() - start
        return False, latency, {"error": str(e), "raw": None}
    finally:
        from iaglobal.core.graceful_shutdown import graceful_shutdown
        graceful_shutdown.sync_cleanup()


async def main():
    print("🚀 Iniciando Re-benchmark Oficial de Latência do Pipeline Completo\n")
    print("-" * 60)

    task_prompt = (
        "Crie um CLI Python que receba um argumento --repo e baixe todos os issues"
        " abertos de um repositório público do GitHub para um arquivo JSON, incluindo"
        " título, número, data de criação e link."
    )

    print(f"📌 Prompt:\n{task_prompt}\n")

    # Executa pipeline via orchestrator
    success, total_latency, result = await run_pipeline_through_orchestrator(task_prompt)

    # Salva resultados
    Path("/tmp").mkdir(exist_ok=True)
    output = {
        "prompt": task_prompt,
        "success": success,
        "total_latency_seconds": total_latency,
        "execution_time_ms": result.get("execution_time", 0) * 1000,
        "execution_result": result.get("final_output", "")[:3000],
        "raw_results_nodes": {k: v for k, v in result.get("raw_results", {}).items() if isinstance(v, dict)},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open("/tmp/rebenchmark_pipeline_latency.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Resumo
    print("=" * 60)
    print("📊 RESULTADO DO RE-BENCHMARK")
    print("=" * 60)
    print(f"✅ Sucesso: {'SIM' if success else 'NÃO'}")
    print(f"⏱️  Latência total (Orchestrator + Providers): {total_latency:.2f}s ({total_latency*1000:.0f}ms)")
    print(f"⚡ execution_time do DAG: {output['execution_time_ms']:.0f}ms")
    if result.get("error"):
        print(f"❌ Erro final: {result['error']}")

    # Nó winners
    raw = output.get("raw_results_nodes", {})
    node_lats = {k: v.get("latency", 0) for k, v in raw.items()}
    sorted_nodes = sorted(node_lats.items(), key=lambda kv: kv[1], reverse=True)[:5]

    print("\n⏱️  Top 5 nós mais lentos (ms):")
    for name, lat_ms in sorted_nodes:
        print(f"  - {name}: {lat_ms:.0f}ms")

    if "final_output" in output and len(output["final_output"]) > 100:
        print(f"\n✨ Código gerado (primeiros 800 chars):\n" + "=" * 60)
        print(output["final_output"][:800] + "...\n" + "=" * 60)

    print(f"\n📁 Arquivo de re-benchmark salvo em: /tmp/rebenchmark_pipeline_latency.json")


if __name__ == "__main__":
    asyncio.run(main())