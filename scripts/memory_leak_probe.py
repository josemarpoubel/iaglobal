#!/usr/bin/env python3
"""
memory_leak_probe.py

Harness de diagnostico de memory leak usando tracemalloc (stdlib,
zero dependencia nova). Roda uma carga sintetica contra uma instancia
de longa duracao (simulando o singleton real) e reporta os top
allocation sites por delta de memoria entre snapshots.

Por que isso decide entre as hipoteses (deque, swap_index, conexao
sqlite nao fechada, singletons duplicados) com dado real em vez de
mais leitura de codigo:

  - Se RSS do processo (medido via /proc ou psutil) cresce mas os
    snapshots do tracemalloc NAO mostram crescimento correspondente
    em objetos Python -> o leak esta em memoria nativa (C), fora do
    heap do CPython. Conexoes sqlite3 nao fechadas caem nessa
    categoria: o objeto Python Connection pode ser pequeno, mas o
    handle C do SQLite (page cache, mmap) fica fora da contabilidade
    do tracemalloc.

  - Se tracemalloc MOSTRA crescimento -> aponta o arquivo:linha exato
    do allocation site que mais cresce, sem ambiguidade sobre qual
    das hipoteses (swap_index, buffer, etc.) esta certa.

Uso:
    cd ~/iaglobal-main
    source venv/bin/activate
    python memory_leak_probe.py --iterations 5000 --snapshot-every 500

IMPORTANTE: edite o bloco marcado "TARGET_FACTORY" abaixo antes de
rodar -- precisa apontar pra classe/instancia real que se quer
investigar (ShortTermMemory, LongTermMemory, etc.).
"""

import argparse
import gc
import os
import sys
import tracemalloc

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def rss_mb() -> float:
    """RSS do processo atual em MB -- mede o que o SO ve, nao so o heap Python."""
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
    """Numero de file descriptors abertos -- sobe sem parar = conexao/arquivo
    nao fechado, e um sinal independente do tracemalloc (que nao ve isso)."""
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except FileNotFoundError:
        return -1


def run_probe(target_factory, iterations: int, snapshot_every: int, warmup: int = 100):
    """
    target_factory: callable que retorna um objeto com metodo .add(content, metadata=...).
    Chamado UMA VEZ no inicio -- simula um singleton de longa duracao, nao uma
    instancia nova por iteracao (proliferacao de instancias e uma hipotese
    diferente, testada separadamente via o grep de instantiation sites).
    """
    target = target_factory()

    # warmup fora da medicao -- evita contar alocacoes de inicializacao
    # (import de libs, primeira conexao sqlite) como "leak"
    for i in range(warmup):
        target.add(f"warmup entry {i}", metadata={"probe": True})

    gc.collect()
    tracemalloc.start(25)  # profundidade de 25 frames -- da o call site real

    baseline_snapshot = tracemalloc.take_snapshot()
    baseline_rss = rss_mb()
    baseline_fd = fd_count()
    print(f"[probe] baseline RSS = {baseline_rss:.1f} MB | fd count = {baseline_fd}")

    last_snapshot = baseline_snapshot
    results = []

    for i in range(1, iterations + 1):
        target.add(f"probe entry {i} " + ("x" * 200), metadata={"probe": True, "seq": i})

        if i % snapshot_every == 0:
            gc.collect()
            current_snapshot = tracemalloc.take_snapshot()
            current_rss = rss_mb()
            current_fd = fd_count()

            diff_from_last = current_snapshot.compare_to(last_snapshot, "lineno")
            top_growth = sorted(diff_from_last, key=lambda s: s.size_diff, reverse=True)[:5]

            print(f"\n[probe] iteracao {i}/{iterations} | RSS={current_rss:.1f} MB "
                  f"(delta baseline: {current_rss - baseline_rss:+.1f} MB) "
                  f"| fd={current_fd} (delta: {current_fd - baseline_fd:+d})")
            print("  top 5 crescimentos Python desde o snapshot anterior:")
            for stat in top_growth:
                if stat.size_diff > 0:
                    frame = stat.traceback[0]
                    print(f"    +{stat.size_diff / 1024:.1f} KB ({stat.count_diff:+d} objs)"
                          f"  {frame.filename}:{frame.lineno}")

            results.append({
                "iteration": i,
                "rss_mb": current_rss,
                "rss_delta": current_rss - baseline_rss,
                "fd_delta": current_fd - baseline_fd,
            })
            last_snapshot = current_snapshot

    print("\n[probe] === RESUMO ===")
    final = results[-1]
    print(f"RSS: {baseline_rss:.1f} -> {final['rss_mb']:.1f} MB "
          f"(delta {final['rss_delta']:+.1f} MB) | fd delta: {final['fd_delta']:+d}")

    if final["fd_delta"] > iterations * 0.5:
        print("⚠️  fd count cresce proporcional as iteracoes -- conexao/arquivo nao fechado confirmado.")
    elif final["fd_delta"] > 5:
        print("⚠️  fd count cresceu um pouco -- investigar, mas nao necessariamente proporcional.")
    else:
        print("✅ fd count estavel -- descarta conexao nao fechada como causa dominante.")

    if len(results) >= 4:
        deltas = [results[i]["rss_mb"] - results[i - 1]["rss_mb"] for i in range(1, len(results))]
        second_half = deltas[len(deltas) // 2:]
        avg_growth = sum(second_half) / len(second_half) if second_half else 0
        print(f"Crescimento medio de RSS por snapshot na segunda metade: {avg_growth:+.3f} MB")
        if avg_growth > 0.5:
            print("⚠️  RSS continua subindo na segunda metade -- consistente com leak real, nao warmup/enchimento de buffer.")
        else:
            print("✅ RSS estabilizou -- consistente com buffer bounded (deque cheio), nao leak.")

    top_final = tracemalloc.take_snapshot().compare_to(baseline_snapshot, "lineno")
    print("\n[probe] top 10 allocation sites Python (delta total desde baseline):")
    for stat in sorted(top_final, key=lambda s: s.size_diff, reverse=True)[:10]:
        if stat.size_diff > 0:
            frame = stat.traceback[0]
            print(f"  +{stat.size_diff / 1024:.1f} KB ({stat.count_diff:+d} objs)  {frame.filename}:{frame.lineno}")

    if final["rss_delta"] > 5 and top_final and sum(s.size_diff for s in top_final if s.size_diff > 0) / 1024 < final["rss_delta"] * 0.3:
        print("\n⚠️  RSS cresceu bem mais do que os objetos Python rastreados -- forte indicio de "
              "alocacao nativa (C) fora do heap do CPython. Bate com hipotese de conexao sqlite "
              "nao fechada (page cache/mmap do SQLite nao contabilizado pelo tracemalloc).")

    tracemalloc.stop()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--snapshot-every", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=100)
    args = parser.parse_args()

    # ============ TARGET_FACTORY -- editar antes de rodar ============
    # Exemplo apontando pro singleton real de async_memory.py (isolado
    # num db de teste pra nao poluir o stm.db de producao):
    #
    # sys.path.insert(0, ".")

    # ============ TARGET_FACTORY -- editar antes de rodar ============
    from iaglobal.memory.term_short import ShortTermMemory
    from iaglobal._paths import MEMORY_SWAP_DIR

    target_factory = lambda: ShortTermMemory(db_path=MEMORY_SWAP_DIR / "probe_test.db")
    # ===================================================================

    # from iaglobal.memory.term_short import ShortTermMemory
    # from iaglobal._paths import MEMORY_SWAP_DIR
    # target_factory = lambda: ShortTermMemory(db_path=MEMORY_SWAP_DIR / "probe_test.db")
    target_factory = None
    # ===================================================================

    if target_factory is None:
        print("Edite o bloco TARGET_FACTORY antes de rodar -- precisa apontar "
              "pra classe real que voce quer investigar.")
        sys.exit(1)

    run_probe(target_factory, args.iterations, args.snapshot_every, args.warmup)
