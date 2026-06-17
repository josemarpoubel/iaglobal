"""Benchmark oficial de latência do pipeline completo."""
import asyncio
import time
import statistics
import sys

from iaglobal.cli.bootstrap import bootstrap


TASKS = [
    "Criar uma função Python que calcula fibonacci recursivamente",
    "Criar uma API REST simples com FastAPI com rota /hello",
    "Ordenar uma lista de números em Python usando quicksort",
]

TRIALS = 2


async def benchmark():
    print("=" * 65)
    print("  BENCHMARK OFICIAL DE LATÊNCIA — Pipeline Completo")
    print("=" * 65)

    orch = bootstrap.initialize()
    pipeline = orch.pipeline

    all_results = {}

    for task in TASKS:
        print(f"\n{'─' * 65}")
        print(f"  Tarefa: {task[:60]}")
        print(f"{'─' * 65}")

        times = []
        successes = 0
        char_counts = []

        for trial in range(TRIALS):
            start = time.perf_counter()
            try:
                result = await pipeline.execute(task, force=True)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                success = result.success if hasattr(result, 'success') else bool(result.response)
                if success:
                    successes += 1
                response = result.response if hasattr(result, 'response') else str(result)
                char_counts.append(len(response or ''))
                status = "✅" if success else "❌"
                print(f"    Trial {trial + 1}: {elapsed:8.2f}s  {status}  ({len(response or ''):5d} chars)")
            except Exception as e:
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                print(f"    Trial {trial + 1}: {elapsed:8.2f}s  ❌  {type(e).__name__}: {str(e)[:80]}")

        avg = statistics.mean(times)
        best = min(times)
        worst = max(times)
        all_results[task] = {
            "avg": avg, "min": best, "max": worst,
            "successes": successes, "trials": TRIALS,
        }

        print(f"  ───────────────────────────────────────────")
        print(f"  Média: {avg:7.2f}s  |  Mín: {best:7.2f}s  |  Máx: {worst:7.2f}s  |  {successes}/{TRIALS} OK")

    print(f"\n{'=' * 65}")
    print("  RESUMO FINAL")
    print(f"{'=' * 65}")
    print(f"{'Tarefa':<50} {'Média':>8} {'Mín':>8} {'Máx':>8} {'OK':>5}")
    print(f"{'─' * 79}")
    for task, r in all_results.items():
        short = task[:48]
        print(f"{short:<50} {r['avg']:>8.2f}s {r['min']:>8.2f}s {r['max']:>8.2f}s {r['successes']}/{r['trials']}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    asyncio.run(benchmark())
