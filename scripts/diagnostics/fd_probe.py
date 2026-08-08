#!/usr/bin/env python3
"""
fd_probe.py — Passo 1 do diagnóstico de leak do STM/LTM.

Reproduz o padrão exato do pipeline/engine.py:_learn_sync (instância nova
de STM+LTM+SemanticCache a cada iteração, igual ao que produção faz) e
mede apenas o file descriptor count + RSS do processo atual. Sem
tracemalloc — isso aqui é o teste mais barato que existe, e se fd count
subir proporcional às iterações, confirma leak de conexões antes mesmo
de precisarmos de algo mais sofisticado.

Uso:
    cd ~/iaglobal-main
    source venv/bin/activate
    python scripts/diagnostics/fd_probe.py --iterations 2000
"""

import argparse
import gc
import os
import sys
import tempfile
from pathlib import Path

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def rss_mb() -> float:
    if HAS_PSUTIL:
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except FileNotFoundError:
        pass
    return -1.0


def fd_count() -> int:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except FileNotFoundError:
        return -1.0


def run_probe(iterations: int, snapshot_every: int, warmup: int = 50):
    sys.path.insert(0, ".")

    from iaglobal._paths import DB_DIR
    from iaglobal.memory.term_short import ShortTermMemory
    from iaglobal.memory.term_long import LongTermMemory
    from iaglobal.memory.semantic_cache import SemanticCache

    test_db = DB_DIR / "fd_probe_tmp.db"
    if test_db.exists():
        test_db.unlink()

    def learn_one(i: int) -> None:
        stm = ShortTermMemory(db_path=test_db)
        ltm = LongTermMemory(db_path=test_db)
        cache = SemanticCache()
        stm.add(f"Q: {i}", {"type": "query", "source": "probe"})
        stm.add(f"A: {('x' * 200)}", {"type": "response", "source": "probe"})
        ltm.store(f"response {i}", {"prompt": str(i)}, source="probe")
        cache.set(str(i), f"response {i}")

    for i in range(warmup):
        learn_one(i)

    gc.collect()
    baseline_rss = rss_mb()
    baseline_fd = fd_count()
    print(f"[probe] baseline RSS = {baseline_rss:.1f} MB | fd count = {baseline_fd}")

    results = []

    for i in range(1, iterations + 1):
        learn_one(i)

        if i % snapshot_every == 0:
            gc.collect()
            current_rss = rss_mb()
            current_fd = fd_count()
            rss_delta = current_rss - baseline_rss
            fd_delta = current_fd - baseline_fd
            print(
                f"[probe] iter {i}/{iterations} | RSS={current_rss:.1f} MB "
                f"(delta {rss_delta:+.1f}) | fd={current_fd} (delta {fd_delta:+d})"
            )
            results.append({
                "iteration": i,
                "rss_delta": rss_delta,
                "fd_delta": fd_delta,
            })

    print("\n[probe] === RESUMO ===")
    final = results[-1]
    print(f"RSS delta: {final['rss_delta']:+.1f} MB | fd delta: {final['fd_delta']:+d}")

    fd_per_iter = final["fd_delta"] / iterations if iterations else 0
    if fd_per_iter > 0.1:
        print(f"⚠️  fd cresce {fd_per_iter:.3f}/iter — conexão/arquivo não fechado confirmado.")
    elif final["fd_delta"] > 5:
        print("⚠️  fd subiu um pouco — investigar, mas não dominante.")
    else:
        print("✅ fd estável — descarta leak de conexão como causa dominante.")

    if len(results) >= 4:
        second_half_deltas = [
            results[i]["rss_delta"] - results[i - 1]["rss_delta"]
            for i in range(len(results) // 2, len(results))
        ]
        avg_growth = sum(second_half_deltas) / len(second_half_deltas)
        print(f"Crescimento médio de RSS por snapshot (segunda metade): {avg_growth:+.3f} MB")
        if avg_growth > 0.5:
            print("⚠️  RSS continua subindo — consistente com leak real, não warmup.")
        else:
            print("✅ RSS estabilizou — consistente com bounded growth.")

    try:
        test_db.unlink()
        test_db.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--snapshot-every", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=50)
    args = parser.parse_args()
    run_probe(args.iterations, args.snapshot_every, args.warmup)
