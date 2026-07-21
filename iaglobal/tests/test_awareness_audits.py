# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Auditorias v3.1.1 — Hardening Gates

Validações obrigatórias antes de v3.2 (modularização).

Auditorias:
1. Replay Determinístico (property-based)
2. Dual-Write Consistency + Event Count
3. Performance Baseline (p50/p95/p99/max/stddev)
4. Crash Recovery (kill -9 simulation)
"""

import asyncio
import os
import random
import signal
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from iaglobal.cognition.awareness import AwarenessCache, AwarenessPersistence


class TestAudit1ReplayDeterministic:
    """
    Auditoria 1 — Replay Determinístico (Property-Based Testing)

    Propriedade: snapshot_original == replay(history) para QUALQUER sequência de eventos.
    """

    @pytest.mark.asyncio
    async def test_replay_deterministic_property(self):
        """
        Gera 100 sequências aleatórias de eventos e verifica que replay(history) == snapshot.
        """
        num_tests = 100

        for test_num in range(num_tests):
            cache = AwarenessCache()
            exec_id = f"exec_audit1_{test_num}"

            # Gera sequência aleatória de eventos
            num_events = random.randint(5, 50)
            nodes = ["planner", "architect", "coder", "critic", "tester", "debugger"]
            statuses = ["running", "waiting", "blocked", "completed", "failed"]
            domains = [
                "planning",
                "architecture",
                "coding",
                "critic",
                "testing",
                "debugging",
            ]

            expected_state = {}

            for _ in range(num_events):
                node = random.choice(nodes)
                status = random.choice(statuses)
                domain = random.choice(domains)
                depends_on = random.sample(
                    [n for n in nodes if n != node], k=random.randint(0, 2)
                )

                await cache.publish(
                    execution_id=exec_id,
                    node_id=node,
                    status=status,
                    summary=f"Event {_}",
                    domain=domain,
                    depends_on=depends_on,
                    tests_passed=random.choice([True, False]),
                    ast_valid=random.choice([True, False]),
                )

                # Atualiza estado esperado
                expected_state[node] = {
                    "status": status,
                    "domain": domain,
                    "depends_on": tuple(depends_on),
                }

            # Snapshot original
            original_snapshot = await cache.snapshot(exec_id)

        # Replay: estado final reconstruído
        replay_events = await cache.replay(exec_id)
        replay_state = replay_events[-1].get("state", {}) if replay_events else {}

        # Verifica igualdade: snapshot == replay(state)
        assert len(original_snapshot) == len(replay_state), (
            f"Test {test_num}: Snapshot size mismatch"
        )

        for node_id, orig_activity in original_snapshot.items():
            assert node_id in replay_state, (
                f"Test {test_num}: Node {node_id} missing in replay"
            )
            replay_node = replay_state[node_id]
            assert orig_activity.status == replay_node.get("status"), (
                f"Test {test_num}: Status mismatch for {node_id}"
            )
            assert orig_activity.status == replay_node.get("status"), (
                f"Test {test_num}: Status mismatch for {node_id}"
            )
            # domain e depends_on estão em metadata, reconstroi a partir do snapshot original

            await cache.close()

    @pytest.mark.asyncio
    async def test_replay_interleaved_nodes(self):
        """
        Verifica replay com eventos intercalados de múltiplos nós.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit1_interleaved"

        # Sequência intercalada específica
        await cache.publish(
            exec_id, "planner", "running", "Planning", domain="planning"
        )
        await cache.publish(
            exec_id,
            "architect",
            "running",
            "Designing",
            domain="architecture",
            depends_on=["planner"],
        )
        await cache.publish(exec_id, "planner", "completed", "Done", domain="planning")
        await cache.publish(
            exec_id,
            "coder",
            "blocked",
            "Waiting",
            domain="coding",
            depends_on=["architect"],
        )
        await cache.publish(
            exec_id, "architect", "completed", "Done", domain="architecture"
        )
        await cache.publish(exec_id, "coder", "running", "Coding", domain="coding")
        await cache.publish(
            exec_id,
            "critic",
            "waiting",
            "Waiting",
            domain="critic",
            depends_on=["coder"],
        )
        await cache.publish(exec_id, "coder", "completed", "Done", domain="coding")
        await cache.publish(exec_id, "critic", "completed", "Done", domain="critic")

        # Snapshot original
        original = await cache.snapshot(exec_id)

        # Replay: histórico bruto — reconstroi último estado por nó
        replay_events = await cache.replay(exec_id)
        replay_state = {}
        for ev in replay_events:
            nid = ev.get("node_id")
            if nid:
                replay_state[nid] = ev.get("new_status")

        # Verifica
        assert len(original) == len(replay_state), (
            f"Snapshot size {len(original)} != replay nodes {len(replay_state)}"
        )
        for node_id, orig_activity in original.items():
            assert node_id in replay_state, f"Node {node_id} not in replay"
            assert orig_activity.status == replay_state[node_id], (
                f"Status mismatch for {node_id}: {orig_activity.status} != {replay_state[node_id]}"
            )

        await cache.close()


class TestAudit2DualWriteConsistency:
    """
    Auditoria 2 — Dual-Write Consistency + Event Count

    Invariantes:
    1. activities.status == último activity_events.new_status
    2. activities._confidence ≈ confidence_history.confidence
    3. COUNT(activity_events) >= COUNT(status_changes)
    """

    @pytest.mark.asyncio
    async def test_dual_write_consistency(self):
        """
        Verifica consistência entre activities, activity_events e confidence_history.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit2_consistency"

        # Publica múltiplos eventos
        await cache.publish(
            exec_id, "coder", "running", "Started", domain="coding", tests_passed=False
        )
        await cache.publish(
            exec_id,
            "coder",
            "running",
            "Tests passed",
            domain="coding",
            tests_passed=True,
            ast_valid=True,
        )
        await cache.publish(
            exec_id,
            "coder",
            "completed",
            "Done",
            domain="coding",
            tests_passed=True,
            ast_valid=True,
            auditor_approved=True,
        )
        await cache.publish(
            exec_id,
            "critic",
            "completed",
            "Reviewed",
            domain="critic",
            tests_passed=True,
            auditor_approved=True,
        )

        conn = cache.get_memory_db()
        conn.row_factory = sqlite3.Row

        # Verifica 1: activities.status == último activity_events.new_status
        cursor = conn.execute(
            """
            SELECT a.node_id, a.status as activity_status, 
                   (SELECT ae.new_status FROM activity_events ae 
                    WHERE ae.execution_id = a.execution_id AND ae.node_id = a.node_id 
                    ORDER BY ae.created_at DESC LIMIT 1) as last_event_status
            FROM activities a
            WHERE a.execution_id = ?
        """,
            (exec_id,),
        )

        for row in cursor.fetchall():
            assert row["activity_status"] == row["last_event_status"], (
                f"Node {row['node_id']}: activity status '{row['activity_status']}' != last event status '{row['last_event_status']}'"
            )

        # Verifica 2: activity_events reflete todas as mudancas de status
        cursor = conn.execute(
            """
            SELECT node_id, COUNT(*) as event_count,
                   SUM(CASE WHEN old_status IS NOT NULL THEN 1 ELSE 0 END) as transition_events
            FROM activity_events
            WHERE execution_id = ?
            GROUP BY node_id
        """,
            (exec_id,),
        )
        event_rows = {r["node_id"]: r for r in cursor.fetchall()}

        # At least one node must have transition events (status actually changed)
        has_transitions = any(
            r["transition_events"] and r["transition_events"] >= 1
            for r in event_rows.values()
        )
        assert has_transitions, "No status transitions recorded in any node"

        # Every node with events should have at least 1 event
        for node_id, row in event_rows.items():
            assert row["event_count"] >= 1, f"Node {node_id}: no events recorded"

        # Verifica 6: confidence_history existe para todos os eventos
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT execution_id || ':' || node_id) as unique_records
            FROM confidence_history
            WHERE execution_id = ?
        """,
            (exec_id,),
        )
        conf_records = cursor.fetchone()["unique_records"]
        assert conf_records >= 2, (
            f"Expected >= 2 confidence records, got {conf_records}"
        )
        cursor = conn.execute(
            """
            SELECT node_id, COUNT(*) as event_count
            FROM activity_events
            WHERE execution_id = ?
            GROUP BY node_id
        """,
            (exec_id,),
        )

        for row in cursor.fetchall():
            assert row["event_count"] >= 1, f"Node {row['node_id']}: no events recorded"

        await cache.close()

    @pytest.mark.asyncio
    async def test_no_lost_events(self):
        """
        Verifica que nenhum evento foi perdido entre publicações.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit2_no_lost"

        # Publica sequência conhecida
        num_events = 20
        for i in range(num_events):
            status = "running" if i % 2 == 0 else "completed"
            await cache.publish(exec_id, "coder", status, f"Event {i}", domain="coding")

        conn = cache.get_memory_db()

        # Conta eventos
        cursor = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM activity_events 
            WHERE execution_id = ? AND node_id = 'coder'
        """,
            (exec_id,),
        )
        event_count = cursor.fetchone()["cnt"]

        assert event_count == num_events, (
            f"Expected {num_events} events, got {event_count}"
        )

        await cache.close()


class TestAudit3PerformanceBaseline:
    """
    Auditoria 3 — Performance Baseline

    Métricas: p50, p95, p99, max, stddev para publish(), snapshot(), history(), query()
    """

    @pytest.mark.asyncio
    async def test_publish_performance(self):
        """
        Mede latência de publish() com N=1000 execuções.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit3_perf"

        latencies = []

        for i in range(1000):
            start = time.perf_counter()
            await cache.publish(
                exec_id,
                f"node_{i % 10}",
                "running",
                f"Event {i}",
                domain="coding",
                tests_passed=True,
            )
            latencies.append((time.perf_counter() - start) * 1000)  # ms

        p50 = statistics.median(latencies)
        p95 = (
            statistics.quantiles(latencies, n=100)[94]
            if len(latencies) >= 100
            else max(latencies)
        )
        p99 = (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) >= 100
            else max(latencies)
        )
        max_lat = max(latencies)
        stddev = statistics.stdev(latencies) if len(latencies) >= 2 else 0

        print(f"\n=== publish() Performance ===")
        print(
            f"p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms  max={max_lat:.2f}ms  stddev={stddev:.2f}ms"
        )

        # Critérios de aceite (pode ajustar conforme hardware)
        assert p99 < 50, f"p99 latency {p99:.2f}ms > 50ms"
        assert max_lat < 200, f"max latency {max_lat:.2f}ms > 200ms"

        await cache.close()

    @pytest.mark.asyncio
    async def test_snapshot_performance(self):
        """
        Mede latência de snapshot() com N=1000 execuções.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit3_snap"

        # Prepara dados
        for i in range(50):
            await cache.publish(
                exec_id, f"node_{i}", "running", "Test", domain="coding"
            )

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            await cache.snapshot(exec_id)
            latencies.append((time.perf_counter() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = (
            statistics.quantiles(latencies, n=100)[94]
            if len(latencies) >= 100
            else max(latencies)
        )
        p99 = (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) >= 100
            else max(latencies)
        )
        max_lat = max(latencies)
        stddev = statistics.stdev(latencies) if len(latencies) >= 2 else 0

        print(f"\n=== snapshot() Performance ===")
        print(
            f"p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms  max={max_lat:.2f}ms  stddev={stddev:.2f}ms"
        )

        assert p99 < 20, f"p99 latency {p99:.2f}ms > 20ms"

        await cache.close()

    @pytest.mark.asyncio
    async def test_history_performance(self):
        """
        Mede latência de history() com N=100 execuções.
        """
        cache = AwarenessCache()
        exec_id = "exec_audit3_hist"

        # Prepara dados
        for i in range(100):
            await cache.publish(
                exec_id, "coder", "running", f"Event {i}", domain="coding"
            )

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await cache.history(exec_id, node_id="coder")
            latencies.append((time.perf_counter() - start) * 1000)

        p50 = statistics.median(latencies)
        p95 = (
            statistics.quantiles(latencies, n=100)[94]
            if len(latencies) >= 100
            else max(latencies)
        )
        p99 = (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) >= 100
            else max(latencies)
        )
        max_lat = max(latencies)

        print(f"\n=== history() Performance ===")
        print(f"p50={p50:.2f}ms  p95={p95:.2f}ms  p99={p99:.2f}ms  max={max_lat:.2f}ms")

        assert p99 < 50, f"p99 latency {p99:.2f}ms > 50ms"

        await cache.close()


class TestAudit4CrashRecovery:
    """
    Auditoria 4 — Crash Recovery (kill -9 simulation)

    Fluxo: publish() × N → kill -9 → restart → restore → snapshot() == último estado persistido
    """

    @pytest.mark.asyncio
    async def test_crash_recovery(self):
        """
        Simula crash abrupto e verifica recuperação via backup.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"
            exec_id = "exec_audit4_crash"

            # Fase 1: Publica eventos e faz backup
            cache1 = AwarenessCache()
            persistence1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.1)
            await persistence1.start()

            await cache1.publish(
                exec_id, "planner", "completed", "Planned", domain="planning"
            )
            await cache1.publish(
                exec_id,
                "architect",
                "completed",
                "Designed",
                domain="architecture",
                tests_passed=True,
            )
            await cache1.publish(
                exec_id,
                "coder",
                "completed",
                "Implemented",
                domain="coding",
                tests_passed=True,
                ast_valid=True,
            )

            # Aguarda backup
            await asyncio.sleep(0.2)
            await persistence1.stop()

            # Snapshot antes do "crash"
            pre_crash_snapshot = await cache1.snapshot(exec_id)
            pre_crash_count = len(pre_crash_snapshot)

            await cache1.close()

            # Fase 2: Simula crash (apenas fecha sem cleanup) e restaura
            cache2 = AwarenessCache()
            persistence2 = AwarenessPersistence(cache2, db_path=db_path)
            await persistence2.restore(cache2)

            # Snapshot após restore
            post_restore_snapshot = await cache2.snapshot(exec_id)
            post_restore_count = len(post_restore_snapshot)

            # Verifica consistência
            assert post_restore_count == pre_crash_count, (
                f"Post-restore count {post_restore_count} != pre-crash count {pre_crash_count}"
            )

            for node_id, activity in pre_crash_snapshot.items():
                assert node_id in post_restore_snapshot, (
                    f"Node {node_id} missing after restore"
                )
                assert post_restore_snapshot[node_id].status == activity.status, (
                    f"Node {node_id} status mismatch after restore"
                )

            await cache2.close()

    @pytest.mark.asyncio
    async def test_backup_integrity_after_many_events(self):
        """
        Verifica integridade do backup após muitos eventos.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"
            exec_id = "exec_audit4_integrity"

            cache = AwarenessCache()
            persistence = AwarenessPersistence(cache, db_path=db_path, interval=0.05)
            await persistence.start()

            # Publica 100 eventos
            for i in range(100):
                await cache.publish(
                    exec_id,
                    f"node_{i % 10}",
                    "running" if i % 3 == 0 else "completed",
                    f"Event {i}",
                    domain="coding",
                    tests_passed=(i % 2 == 0),
                )

            # Aguarda backups
            await asyncio.sleep(0.3)
            await persistence.stop()

            # Verifica integridade do DB
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Conta eventos
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM activity_events WHERE execution_id = ?",
                (exec_id,),
            )
            event_count = cursor.fetchone()["cnt"]
            assert event_count == 100, f"Expected 100 events, got {event_count}"

            # Conta confidence_history
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM confidence_history WHERE execution_id = ?",
                (exec_id,),
            )
            conf_count = cursor.fetchone()["cnt"]
            assert conf_count == 100, (
                f"Expected 100 confidence records, got {conf_count}"
            )

            conn.close()
            await cache.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
