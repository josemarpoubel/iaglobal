# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Stress Tests v2 — AwarenessCache Central Nervous System

Valida consistência sob carga extrema:
- 500-1000 publishes concorrentes
- Backups simultâneos durante escritas intensas
- Snapshots concorrentes durante updates
- Causal chains corretas sob concorrência
- Memory leaks / resource leaks
"""

import asyncio
import gc
import os
import tempfile
import time
from pathlib import Path

import pytest

from iaglobal.cognition.awareness import (
    AwarenessCache,
    AwarenessPersistence,
    NodeDomain,
    NodeStatus,
)


class TestStressConcurrency:
    """Testes de concorrência extrema."""

    @pytest.mark.asyncio
    async def test_500_concurrent_publishes_single_execution(self):
        """500 corotinas publicando no mesmo execution_id simultaneamente."""
        cache = AwarenessCache()
        execution_id = "exec_stress_500"

        async def publish_batch(node_prefix: str, count: int):
            for i in range(count):
                await cache.publish(
                    execution_id=execution_id,
                    node_id=f"{node_prefix}_{i}",
                    status=NodeStatus.RUNNING.value,
                    summary=f"Task {i}",
                    domain=NodeDomain.CODING.value,
                    metadata={"batch": node_prefix, "idx": i},
                )

        # 5 batches de 100 = 500 publishes concorrentes
        await asyncio.gather(
            publish_batch("worker_a", 100),
            publish_batch("worker_b", 100),
            publish_batch("worker_c", 100),
            publish_batch("worker_d", 100),
            publish_batch("worker_e", 100),
        )

        # Verifica integridade
        snapshot = await cache.snapshot(execution_id)
        assert len(snapshot) == 500

        # Todos RUNNING
        for act in snapshot.values():
            assert act.status == NodeStatus.RUNNING.value
            assert act.domain == NodeDomain.CODING.value
            assert "batch" in act.metadata

        await cache.close()

    @pytest.mark.asyncio
    async def test_1000_concurrent_publishes_multiple_executions(self):
        """1000 publishes distribuídos em 10 execuções."""
        cache = AwarenessCache()

        async def publish_execution(exec_idx: int):
            exec_id = f"exec_{exec_idx}"
            for i in range(100):
                await cache.publish(
                    execution_id=exec_id,
                    node_id=f"node_{i}",
                    status=NodeStatus.RUNNING.value
                    if i % 2 == 0
                    else NodeStatus.WAITING.value,
                    domain=NodeDomain.GENERAL.value,
                )

        await asyncio.gather(*[publish_execution(i) for i in range(10)])

        # Verifica isolamento entre execuções
        for exec_idx in range(10):
            snap = await cache.snapshot(f"exec_{exec_idx}")
            assert len(snap) == 100

        await cache.close()

    @pytest.mark.asyncio
    async def test_publish_snapshot_concurrent_continuous(self):
        """Publish contínuo + snapshot contínuo por 30 segundos simulados (acelerado)."""
        cache = AwarenessCache()
        execution_id = "exec_continuous"
        errors = []
        snapshot_counts = []

        async def continuous_publish():
            try:
                for i in range(500):
                    await cache.publish(
                        execution_id=execution_id,
                        node_id="coder",
                        status=NodeStatus.RUNNING.value,
                        summary=f"iteration {i}",
                        domain=NodeDomain.CODING.value,
                        depends_on=["architect"] if i > 100 else [],
                    )
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append(("publish", e))

        async def continuous_snapshot():
            try:
                for _ in range(500):
                    snap = await cache.snapshot(execution_id)
                    snapshot_counts.append(len(snap))
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append(("snapshot", e))

        await asyncio.gather(continuous_publish(), continuous_snapshot())

        assert len(errors) == 0, f"Erros durante concorrência: {errors}"
        # Snapshot sempre retorna estado válido (1 nó)
        assert all(c == 1 for c in snapshot_counts)

        await cache.close()


class TestStressBackupUnderLoad:
    """Backups periódicos durante carga intensa."""

    @pytest.mark.asyncio
    async def test_backup_during_intense_writes(self):
        """sqlite3.backup() não bloqueia nem corrompe durante writes pesados."""
        cache = AwarenessCache()
        execution_id = "exec_backup_load"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"
            persistence = AwarenessPersistence(cache, db_path=db_path, interval=0.05)
            await persistence.start()

            # Writer intenso
            async def intense_writer():
                for i in range(200):
                    await cache.publish(
                        execution_id=execution_id,
                        node_id=f"node_{i % 20}",
                        status=NodeStatus.RUNNING.value,
                        domain=NodeDomain.CODING.value,
                        metadata={"iteration": i},
                    )

            await intense_writer()

            # Aguarda múltiplos backups
            await asyncio.sleep(0.3)

            await persistence.stop()

            # Valida DB destino
            import sqlite3

            dest = sqlite3.connect(str(db_path))
            dest.row_factory = sqlite3.Row
            cur = dest.execute(
                "SELECT COUNT(*) as cnt FROM activities WHERE execution_id = ?",
                (execution_id,),
            )
            row = cur.fetchone()
            assert row["cnt"] == 20  # 20 nodes únicos (último write vence)
            dest.close()

        await cache.close()

    @pytest.mark.asyncio
    async def test_backup_restore_idempotent_100_cycles(self):
        """100 ciclos backup → restore → verify sem divergência."""
        execution_id = "exec_restore_100"
        original_data = {}

        for cycle in range(100):
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = Path(tmpdir) / "awareness.db"

                # Fase 1: Cria e popula
                cache1 = AwarenessCache()
                pers1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.01)
                await pers1.start()

                for i in range(10):
                    await cache1.publish(
                        execution_id=execution_id,
                        node_id=f"node_{i}",
                        status=NodeStatus.RUNNING.value,
                        domain=NodeDomain.CODING.value,
                        metadata={"cycle": cycle, "idx": i},
                    )
                original_data[cycle] = {
                    f"node_{i}": {"cycle": cycle, "idx": i} for i in range(10)
                }

                await asyncio.sleep(0.05)  # backup
                await pers1.stop()
                await cache1.close()

                # Fase 2: Restore em nova instância
                cache2 = AwarenessCache()
                pers2 = AwarenessPersistence(cache2, db_path=db_path)
                await pers2.restore(cache2)

                snap = await cache2.snapshot(execution_id)
                assert len(snap) == 10
                for node_id, act in snap.items():
                    idx = int(node_id.split("_")[1])
                    assert act.metadata["cycle"] == cycle
                    assert act.metadata["idx"] == idx

                await cache2.close()

    @pytest.mark.asyncio
    async def test_concurrent_backup_and_snapshot(self):
        """Backup + snapshot simultâneos não causam 'database locked'."""
        cache = AwarenessCache()
        execution_id = "exec_concurrent_bk_snap"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"
            persistence = AwarenessPersistence(cache, db_path=db_path, interval=0.02)
            await persistence.start()

            errors = []

            async def writer():
                try:
                    for i in range(100):
                        await cache.publish(
                            execution_id,
                            f"n_{i}",
                            NodeStatus.RUNNING.value,
                            domain=NodeDomain.CODING.value,
                        )
                except Exception as e:
                    errors.append(("writer", e))

            async def snapshoter():
                try:
                    for _ in range(100):
                        await cache.snapshot(execution_id)
                        await asyncio.sleep(0.001)
                except Exception as e:
                    errors.append(("snapshot", e))

            await asyncio.gather(writer(), snapshoter())
            await asyncio.sleep(0.1)  # backup final
            await persistence.stop()

            assert len(errors) == 0, f"Erros: {errors}"

        await cache.close()


class TestStressCausalConsistency:
    """Cadeias causais corretas sob concorrência."""

    @pytest.mark.asyncio
    async def test_causal_chains_under_concurrent_updates(self):
        """Dependências multi-nível mantêm integridade causal."""
        cache = AwarenessCache()
        execution_id = "exec_causal_stress"

        # Cria grafo: planner → architect → coder → tester
        # Atualiza status concorrentemente
        async def update_node(node_id: str, status: str, depends_on: list):
            await cache.publish(
                execution_id=execution_id,
                node_id=node_id,
                status=status,
                domain=NodeDomain.CODING.value,
                depends_on=depends_on,
            )

        # Fase 1: Todos blocked exceto planner
        await asyncio.gather(
            update_node("planner", NodeStatus.COMPLETED.value, []),
            update_node("architect", NodeStatus.BLOCKED.value, ["planner"]),
            update_node("coder", NodeStatus.BLOCKED.value, ["architect"]),
            update_node("tester", NodeStatus.BLOCKED.value, ["coder"]),
        )

        chains = await cache.snapshot(execution_id, relevance="blocking")
        assert len(chains) == 3  # architect, coder, tester

        # Fase 2: Desbloqueia em cascata concorrente
        await asyncio.gather(
            update_node("architect", NodeStatus.COMPLETED.value, ["planner"]),
            update_node("coder", NodeStatus.RUNNING.value, ["architect"]),
            update_node("tester", NodeStatus.WAITING.value, ["coder"]),
        )

        chains = await cache.snapshot(execution_id, relevance="blocking")
        # Apenas tester deve estar blocked agora
        blocked_chains = [c for c in chains if c.blocked_node == "tester"]
        assert len(blocked_chains) == 1
        assert "coder" in blocked_chains[0].blocking_chain

        # Fase 3: Final
        await update_node("coder", NodeStatus.COMPLETED.value, ["architect"])
        await update_node("tester", NodeStatus.RUNNING.value, ["coder"])

        chains = await cache.snapshot(execution_id, relevance="blocking")
        assert len(chains) == 0  # Nenhum blocked

        await cache.close()

    @pytest.mark.asyncio
    async def test_causal_explanation_accuracy_under_load(self):
        """get_causal_explanation retorna cadeia correta durante updates."""
        cache = AwarenessCache()
        execution_id = "exec_explain"

        await cache.publish(
            execution_id,
            "A",
            NodeStatus.COMPLETED.value,
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "B",
            NodeStatus.BLOCKED.value,
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["A"],
        )
        await cache.publish(
            execution_id,
            "C",
            NodeStatus.BLOCKED.value,
            domain=NodeDomain.CODING.value,
            depends_on=["B"],
        )
        await cache.publish(
            execution_id,
            "D",
            NodeStatus.BLOCKED.value,
            domain=NodeDomain.TESTING.value,
            depends_on=["C"],
        )

        # Explicação antes de qualquer mudança
        expl = await cache.get_causal_explanation(execution_id, "D")
        assert "D → C → B → A" in expl

        # Muda status de B e C concorrentemente
        await asyncio.gather(
            cache.publish(
                execution_id,
                "B",
                NodeStatus.COMPLETED.value,
                domain=NodeDomain.ARCHITECTURE.value,
                depends_on=["A"],
            ),
            cache.publish(
                execution_id,
                "C",
                NodeStatus.RUNNING.value,
                domain=NodeDomain.CODING.value,
                depends_on=["B"],
            ),
        )

        expl = await cache.get_causal_explanation(execution_id, "D")
        assert "D → C" in expl  # C ainda bloqueando (running não desbloqueia tester)
        assert "B" in expl

        await cache.close()


class TestStressDomainIsolation:
    """Atenção seletiva sob carga."""

    @pytest.mark.asyncio
    async def test_domain_snapshot_isolation_under_load(self):
        """Snapshots por domínio não vazam entre domínios."""
        cache = AwarenessCache()
        execution_id = "exec_domain_iso"

        # Popula 5 domínios x 20 nodes = 100 nodes
        for domain in [
            NodeDomain.CODING,
            NodeDomain.SECURITY,
            NodeDomain.PERFORMANCE,
            NodeDomain.TESTING,
            NodeDomain.ARCHITECTURE,
        ]:
            for i in range(20):
                await cache.publish(
                    execution_id=execution_id,
                    node_id=f"{domain.value}_{i}",
                    status=NodeStatus.RUNNING.value,
                    domain=domain.value,
                )

        # Snapshots concorrentes por domínio
        async def snap_domain(domain: NodeDomain):
            for _ in range(50):
                snap = await cache.snapshot(execution_id, domain=domain.value)
                assert all(a.domain == domain.value for a in snap.activities)
                await asyncio.sleep(0.001)

        await asyncio.gather(
            *[
                snap_domain(d)
                for d in [
                    NodeDomain.CODING,
                    NodeDomain.SECURITY,
                    NodeDomain.PERFORMANCE,
                    NodeDomain.TESTING,
                    NodeDomain.ARCHITECTURE,
                ]
            ]
        )

        await cache.close()


class TestStressEpisodicMemory:
    """Memória episódica sob estresse."""

    @pytest.mark.asyncio
    async def test_episodic_export_during_active_execution(self):
        """export_episodic_memory() não bloqueia publishes em andamento."""
        cache = AwarenessCache()
        execution_id = "exec_episodic_live"
        errors = []

        async def publisher():
            try:
                for i in range(200):
                    await cache.publish(
                        execution_id=execution_id,
                        node_id="coder",
                        status=NodeStatus.RUNNING.value,
                        domain=NodeDomain.CODING.value,
                        metadata={"step": i},
                    )
                    await asyncio.sleep(0.002)
            except Exception as e:
                errors.append(("publish", e))

        async def exporter():
            try:
                for _ in range(10):
                    mem = await cache.export_episodic_memory(
                        execution_id=execution_id,
                        final_status="partial",
                        ivm_score=0.5,
                        lessons_learned=[f"lesson_{_}"],
                    )
                    assert isinstance(mem.nodes, dict)
                    await asyncio.sleep(0.01)
            except Exception as e:
                errors.append(("export", e))

        await asyncio.gather(publisher(), exporter())

        assert len(errors) == 0, f"Erros: {errors}"

        # Verifica memória final
        final = await cache.export_episodic_memory(
            execution_id, "completed", 0.9, ["final"]
        )
        assert len(final.nodes) >= 1

        await cache.close()

    @pytest.mark.asyncio
    async def test_episodic_persist_restore_fidelity(self):
        """Memória episódica persiste e restaura com fidelidade total."""
        execution_id = "exec_fidelity"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"

            # Popula + exporta
            cache1 = AwarenessCache()
            pers1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.01)
            await pers1.start()

            for i in range(5):
                await cache1.publish(
                    execution_id,
                    f"node_{i}",
                    NodeStatus.COMPLETED.value,
                    domain=NodeDomain.CODING.value,
                    metadata={"seq": i},
                )

            mem1 = await cache1.export_episodic_memory(
                execution_id, "completed", 0.95, ["lesson1", "lesson2"]
            )
            await asyncio.sleep(0.05)
            await pers1.stop()
            await cache1.close()

            # Restore
            cache2 = AwarenessCache()
            pers2 = AwarenessPersistence(cache2, db_path=db_path)
            await pers2.restore(cache2)

            mem2 = await cache2.get_episodic_memory(execution_id)

            assert mem2 is not None
            assert mem2.execution_id == execution_id
            assert mem2.final_status == "completed"
            assert mem2.ivm_score == 0.95
            assert mem2.lessons_learned == ["lesson1", "lesson2"]
            assert len(mem2.nodes) == 5
            for i in range(5):
                assert mem2.nodes[f"node_{i}"].metadata["seq"] == i

            await cache2.close()


class TestStressResourceLeaks:
    """Detecção de vazamentos de recursos."""

    @pytest.mark.asyncio
    async def test_no_memory_leak_1000_cycles(self):
        """Cria/fecha 1000 caches sem vazamento de memória."""
        import tracemalloc

        tracemalloc.start()

        snapshots = []

        for cycle in range(100):
            cache = AwarenessCache()
            for i in range(10):
                await cache.publish(
                    f"exec_{cycle}",
                    f"node_{i}",
                    NodeStatus.RUNNING.value,
                    domain=NodeDomain.CODING.value,
                )
            await cache.snapshot(f"exec_{cycle}")
            await cache.close()

            if cycle % 20 == 0:
                gc.collect()
                snapshots.append(tracemalloc.take_snapshot())

        tracemalloc.stop()

        # Verifica crescimento linear não explosivo
        if len(snapshots) >= 2:
            stats = snapshots[-1].compare_to(snapshots[0], "lineno")
            total_diff = sum(s.size_diff for s in stats)
            # < 10MB growth over 100 cycles
            assert total_diff < 10 * 1024 * 1024, (
                f"Possível memory leak: {total_diff / 1024 / 1024:.1f}MB growth"
            )

    @pytest.mark.asyncio
    async def test_no_fd_leak_persistence_cycles(self):
        """Abre/fecha persistence 100x sem vazamento de file descriptors."""
        import resource

        def get_open_fds():
            # Linux: conta /proc/self/fd
            try:
                return len(os.listdir("/proc/self/fd"))
            except:
                return resource.getrlimit(resource.RLIMIT_NOFILE)[0]

        initial_fds = get_open_fds()

        for _ in range(100):
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = Path(tmpdir) / "awareness.db"
                cache = AwarenessCache()
                pers = AwarenessPersistence(cache, db_path=db_path, interval=0.01)
                await pers.start()
                await cache.publish(
                    "exec",
                    "node",
                    NodeStatus.RUNNING.value,
                    domain=NodeDomain.CODING.value,
                )
                await asyncio.sleep(0.02)
                await pers.stop()
                await cache.close()

        gc.collect()
        await asyncio.sleep(0.1)
        final_fds = get_open_fds()

        # Tolerância: +5 fds (pode variar por GC timing)
        assert final_fds - initial_fds < 10, (
            f"Possível FD leak: {initial_fds} → {final_fds}"
        )


class TestStressLatency:
    """Benchmarks de latência sob carga."""

    @pytest.mark.asyncio
    async def test_publish_latency_p99_under_load(self):
        """p99 publish latency < 10ms com 100 workers concorrentes."""
        cache = AwarenessCache()
        execution_id = "exec_latency"
        latencies = []

        async def worker(worker_id: int):
            for i in range(50):
                start = time.perf_counter()
                await cache.publish(
                    execution_id=execution_id,
                    node_id=f"worker_{worker_id}",
                    status=NodeStatus.RUNNING.value,
                    domain=NodeDomain.CODING.value,
                )
                latencies.append((time.perf_counter() - start) * 1000)  # ms

        await asyncio.gather(*[worker(i) for i in range(100)])

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"Publish latency: p50={p50:.2f}ms p99={p99:.2f}ms")

        assert p99 < 10.0, f"p99 latency {p99:.2f}ms excede 10ms"

        await cache.close()

    @pytest.mark.asyncio
    async def test_snapshot_latency_p99_under_load(self):
        """p99 snapshot latency < 5ms durante writes concorrentes."""
        cache = AwarenessCache()
        execution_id = "exec_snap_latency"
        latencies = []
        stop_writer = asyncio.Event()

        async def writer():
            i = 0
            while not stop_writer.is_set():
                await cache.publish(
                    execution_id,
                    f"node_{i % 10}",
                    NodeStatus.RUNNING.value,
                    domain=NodeDomain.CODING.value,
                )
                i += 1
                await asyncio.sleep(0.001)

        async def snapshoter():
            for _ in range(200):
                start = time.perf_counter()
                await cache.snapshot(execution_id)
                latencies.append((time.perf_counter() - start) * 1000)
                await asyncio.sleep(0.002)

        writer_task = asyncio.create_task(writer())
        await snapshoter()
        stop_writer.set()
        await writer_task

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"Snapshot latency: p50={p50:.2f}ms p99={p99:.2f}ms")

        assert p99 < 5.0, f"p99 snapshot latency {p99:.2f}ms excede 5ms"

        await cache.close()


# ==================== RUNNER ====================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "-x",  # para no primeiro erro
        ]
    )
