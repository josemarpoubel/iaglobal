"""Benchmark: CPU Dispersion vs Single-Core."""
import time
import asyncio
import os
import sys
import hashlib
import statistics
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal.cpu_affinity import CpuAffinityManager


def _cpu_work(n: int = 50000) -> float:
    """CPU-bound work: hash computation loop. Returns elapsed time."""
    start = time.perf_counter()
    result = 0
    for i in range(n):
        h = hashlib.sha256(f"benchmark_data_{i}_{result}".encode()).hexdigest()
        result += int(h[:8], 16)
    return time.perf_counter() - start


def _cpu_work_pinned_single(args):
    """CPU work pinned to core 0 ONLY."""
    n, _ = args
    if sys.platform == "linux":
        try:
            os.sched_setaffinity(0, {0})
        except Exception:
            pass
    return _cpu_work(n)


def _cpu_work_pinned_disperse(args):
    """CPU work pinned to a rotating core."""
    n, wid = args
    mgr = CpuAffinityManager()
    mgr.pin_for_agent(f"bench_worker_{wid}")
    return _cpu_work(n)


def main():
    n_workers = os.cpu_count() or 4
    work_per_worker = 500000
    trials = 5

    print("=" * 60)
    print(f"  CPU Dispersion Benchmark")
    print(f"  Workers: {n_workers}  |  Work/worker: {work_per_worker} SHA256 hashes")
    print(f"  Trials:  {trials}")
    print("=" * 60)

    results_single = []
    results_disperse = []

    for trial in range(trials):
        # ── Single-core: all workers pinned to core 0 ──
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            start = time.perf_counter()
            list(pool.map(_cpu_work_pinned_single, [
                (work_per_worker, 0) for _ in range(n_workers)
            ]))
            t_single = time.perf_counter() - start
        results_single.append(t_single)

        # ── Dispersion: each worker on a different core ──
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            start = time.perf_counter()
            list(pool.map(_cpu_work_pinned_disperse, [
                (work_per_worker, i) for i in range(n_workers)
            ]))
            t_disperse = time.perf_counter() - start
        results_disperse.append(t_disperse)

        speedup = t_single / t_disperse if t_disperse > 0 else 0
        print(f"  Trial {trial+1}: single={t_single:.3f}s  "
              f"disperse={t_disperse:.3f}s  speedup={speedup:.2f}x")

    avg_single = statistics.mean(results_single)
    avg_disperse = statistics.mean(results_disperse)
    avg_speedup = avg_single / avg_disperse if avg_disperse > 0 else 0

    print("\n" + "-" * 60)
    print("  RESULTADOS FINAIS")
    print(f"  Média single-core:   {avg_single:.3f}s")
    print(f"  Média dispersão:     {avg_disperse:.3f}s")
    print(f"  Speedup médio:       {avg_speedup:.2f}x")
    if avg_disperse < avg_single:
        gain = (1 - avg_disperse / avg_single) * 100
        print(f"  Ganho observado:     {gain:.0f}% mais rápido")
    else:
        loss = (1 - avg_single / avg_disperse) * 100
        print(f"  Dispersão mais lenta: {loss:.0f}%")
    print("-" * 60)
    print(f"\n  Núcleos: {n_workers}")
    print(f"  Teórico (speedup):  até {n_workers}x para trabalho CPU-bound")
    print(f"  Observado:          {avg_speedup:.2f}x")


if __name__ == "__main__":
    main()
