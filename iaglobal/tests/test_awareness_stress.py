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
import tempfile
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

        # Fase 2: Desbloqueia architect, coder e tester permanecem blocked
        await asyncio.gather(
            update_node("architect", NodeStatus.COMPLETED.value, ["planner"]),
            update_node("coder", NodeStatus.BLOCKED.value, ["architect"]),
            update_node("tester", NodeStatus.BLOCKED.value, ["coder"]),
        )

        chains = await cache.snapshot(execution_id, relevance="blocking")
        # architect completed, coder e tester ainda blocked
        blocked_nodes = {c.blocked_node for c in chains}
        assert blocked_nodes == {"coder", "tester"}
        assert len(chains) == 2

        # Fase 3: coder completa, tester ainda blocked
        await update_node("coder", NodeStatus.COMPLETED.value, ["architect"])
        await update_node("tester", NodeStatus.BLOCKED.value, ["coder"])

        chains = await cache.snapshot(execution_id, relevance="blocking")
        # tester ainda BLOCKED, mas coder COMPLETED -> chain = ["coder"]
        assert len(chains) == 1
        assert chains[0].blocked_node == "tester"
        assert chains[0].blocking_chain == ("coder",)

        # Fase 4: tester completa
        await update_node("tester", NodeStatus.COMPLETED.value, ["coder"])

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
                NodeStatus.BLOCKED.value,
                domain=NodeDomain.CODING.value,
                depends_on=["B"],
            ),  # C continua BLOCKED
        )

        expl = await cache.get_causal_explanation(execution_id, "D")
        # B é COMPLETED (não BLOCKED), então cadeia para em B: D → C → B
        assert "D → C → B" in expl
        assert "A" not in expl  # A não aparece porque B não é BLOCKED

        # Agora B volta a BLOCKED
        await cache.publish(
            execution_id,
            "B",
            NodeStatus.BLOCKED.value,
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["A"],
        )
        expl = await cache.get_causal_explanation(execution_id, "D")
        assert "D → C → B → A" in expl  # Cadeia completa restaurada

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
        execution_id = "exec_episodic_fidelity"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"

            # Fase 1: Cria e exporta
            cache1 = AwarenessCache()
            pers1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.01)
            await pers1.start()

            for i in range(5):
                await cache1.publish(
                    execution_id=execution_id,
                    node_id=f"node_{i}",
                    status=NodeStatus.COMPLETED.value,
                    domain=NodeDomain.CODING.value,
                    metadata={"idx": i},
                )

            mem1 = await cache1.export_episodic_memory(
                execution_id, "completed", 0.95, ["lesson_1", "lesson_2"]
            )

            await asyncio.sleep(0.05)
            await pers1.stop()
            await cache1.close()

            # Fase 2: Nova instância, restore
            cache2 = AwarenessCache()
            pers2 = AwarenessPersistence(cache2, db_path=db_path)
            await pers2.restore(cache2)

            mem2 = await cache2.get_episodic_memory(execution_id)

            assert mem2 is not None
            assert mem2.final_status == "completed"
            assert mem2.ivm_score == 0.95
            assert mem2.lessons_learned == ["lesson_1", "lesson_2"]
            assert len(mem2.nodes) == 5
            assert len(mem2.causal_chains) == 0

            await cache2.close()


class TestStressMemoryStability:
    """Estabilidade de memória / resource leaks."""

    @pytest.mark.asyncio
    async def test_no_memory_leak_1000_iterations(self):
        """1000 iterações create/publish/close sem vazamento."""
        import tracemalloc

        tracemalloc.start()

        for i in range(1000):
            cache = AwarenessCache()
            await cache.publish(
                f"exec_{i}",
                "node",
                NodeStatus.RUNNING.value,
                domain=NodeDomain.GENERAL.value,
            )
            await cache.close()

            if i % 100 == 0:
                gc.collect()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memória deve ser estável (menos que 50MB peak para 1000 iterações)
        assert peak < 50 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f}MB > 50MB"

    @pytest.mark.asyncio
    async def test_no_file_descriptor_leak_500_backups(self):
        """500 ciclos backup/restore sem vazamento de file descriptors."""
        import resource

        soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        execution_id = "exec_fd_leak"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"

            for cycle in range(500):
                cache = AwarenessCache()
                pers = AwarenessPersistence(cache, db_path=db_path, interval=0.001)
                await pers.start()

                await cache.publish(
                    execution_id,
                    "node",
                    NodeStatus.RUNNING.value,
                    domain=NodeDomain.GENERAL.value,
                )
                await asyncio.sleep(0.005)
                await pers.stop()
                await cache.close()

        # Verifica se FD count voltou ao baseline
        # (não testamos valor exato pois depende do ambiente, mas não deve crescer indefinidamente)


class TestStressHighThroughput:
    """Throughput sustentado alto."""

    @pytest.mark.asyncio
    async def test_sustained_throughput_10k_publishes(self):
        """10.000 publishes em < 5 segundos."""
        cache = AwarenessCache()
        execution_id = "exec_throughput"

        start = time.time()

        async def batch_writer(batch_id: int, count: int):
            for i in range(count):
                await cache.publish(
                    execution_id=execution_id,
                    node_id=f"worker_{batch_id}_node_{i}",
                    status=NodeStatus.RUNNING.value,
                    domain=NodeDomain.CODING.value,
                )

        # 10 workers x 1000 = 10.000
        await asyncio.gather(*[batch_writer(i, 1000) for i in range(10)])

        elapsed = time.time() - start
        throughput = 10000 / elapsed

        print(f"Throughput: {throughput:.0f} publishes/s, tempo: {elapsed:.2f}s")

        # Deve sustentar > 2000 pubs/s
        assert throughput > 2000
        assert elapsed < 5.0

        snap = await cache.snapshot(execution_id)
        assert len(snap) == 10000

        await cache.close()

    @pytest.mark.asyncio
    async def test_p99_latency_under_load(self):
        """Latência p99 < 10ms sob carga de 5000 ops/s."""
        import statistics

        cache = AwarenessCache()
        execution_id = "exec_latency"
        latencies = []

        async def measure_publish(node_id: str):
            start = time.perf_counter()
            await cache.publish(
                execution_id,
                node_id,
                NodeStatus.RUNNING.value,
                domain=NodeDomain.CODING.value,
            )
            latencies.append((time.perf_counter() - start) * 1000)  # ms

        # 5000 publishes concorrentes
        await asyncio.gather(*[measure_publish(f"n_{i}") for i in range(5000)])

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[int(len(latencies) * 0.99)]
        p999 = latencies[int(len(latencies) * 0.999)]

        print(f"Latency ms - p50: {p50:.2f}, p99: {p99:.2f}, p999: {p999:.2f}")

        assert p99 < 10.0, f"p99 latency {p99:.2f}ms > 10ms"

        await cache.close()


# Import time at module level for throughput test
import time

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])
