# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Testes obrigatórios para AwarenessCache.

Cobertura:
1. Concorrência publish (100 agentes simultâneos)
2. Snapshot durante escrita
3. Backup concorrente
4. Recuperação (persistência -> restore)
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from iaglobal.cognition.awareness import (
    AwarenessCache,
    AwarenessPersistence,
    AgentActivity,
)


class TestAwarenessCacheConcurrency:
    """Teste 1: Concorrência publish - 100 agentes simultâneos."""

    @pytest.mark.asyncio
    async def test_concurrent_publish_100_agents(self):
        """100 agentes publicando simultaneamente - zero corrupção."""
        cache = AwarenessCache()
        execution_id = "exec_test_concurrent"

        async def publish_agent(node_id: int):
            await cache.publish(
                execution_id=execution_id,
                node_id=f"agent_{node_id}",
                status="running",
                summary=f"Agent {node_id} working",
                metadata={"skill": f"skill_{node_id}", "iteration": node_id},
            )

        # 100 publishes concorrentes
        await asyncio.gather(*[publish_agent(i) for i in range(100)])

        # Verifica estado final
        snapshot = await cache.snapshot(execution_id)
        assert len(snapshot) == 100

        # Todos devem ter status "running"
        for activity in snapshot.values():
            assert activity.status == "running"
            assert activity.metadata["skill"].startswith("skill_")

        await cache.close()

    @pytest.mark.asyncio
    async def test_concurrent_publish_last_write_wins(self):
        """Última escrita vence para mesmo node_id."""
        cache = AwarenessCache()
        execution_id = "exec_test_lww"

        # Publica primeiro valor
        await cache.publish(
            execution_id=execution_id,
            node_id="coder",
            status="running",
            summary="primeiro",
            metadata={"version": 1},
        )

        # Publica segundo valor (mesmo node_id)
        await cache.publish(
            execution_id=execution_id,
            node_id="coder",
            status="completed",
            summary="segundo",
            metadata={"version": 2},
        )

        snapshot = await cache.snapshot(execution_id)
        assert snapshot["coder"].status == "completed"
        assert snapshot["coder"].summary == "segundo"
        assert snapshot["coder"].metadata["version"] == 2

        await cache.close()


class TestAwarenessCacheSnapshotDuringWrite:
    """Teste 2: Snapshot durante escrita concorrente."""

    @pytest.mark.asyncio
    async def test_snapshot_during_continuous_publish(self):
        """Snapshot enquanto publishes contínuos acontecem."""
        cache = AwarenessCache()
        execution_id = "exec_test_snapshot_write"

        results = []
        errors = []

        async def continuous_publish():
            try:
                for i in range(50):
                    await cache.publish(
                        execution_id=execution_id,
                        node_id="coder",
                        status="running",
                        summary=f"iteration {i}",
                        metadata={"iteration": i},
                    )
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append(e)

        async def continuous_snapshot():
            try:
                for _ in range(50):
                    snapshot = await cache.snapshot(execution_id)
                    results.append(len(snapshot))
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append(e)

        await asyncio.gather(continuous_publish(), continuous_snapshot())

        assert len(errors) == 0, f"Erros durante concorrência: {errors}"
        assert all(r == 1 for r in results), "Snapshot sempre deve retornar 1 agente"

        await cache.close()


class TestAwarenessCacheBackupConcurrent:
    """Teste 3: Backup concorrente com publishes."""

    @pytest.mark.asyncio
    async def test_backup_during_publish(self):
        """Backup enquanto publishes acontecem - DB destino consistente."""
        cache = AwarenessCache()
        execution_id = "exec_test_backup"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"
            persistence = AwarenessPersistence(cache, db_path=db_path, interval=0.1)
            await persistence.start()

            # Publica enquanto backup roda em background
            async def continuous_publish():
                for i in range(100):
                    await cache.publish(
                        execution_id=execution_id,
                        node_id=f"agent_{i % 10}",
                        status="running",
                        summary=f"work {i}",
                        metadata={"iteration": i},
                    )

            await continuous_publish()

            # Aguarda pelo menos um backup
            await asyncio.sleep(0.3)

            await persistence.stop()

            # Verifica DB destino
            import sqlite3

            dest_db = sqlite3.connect(str(db_path))
            dest_db.row_factory = sqlite3.Row
            cursor = dest_db.execute(
                "SELECT COUNT(*) as cnt FROM activities WHERE execution_id = ?",
                (execution_id,),
            )
            row = cursor.fetchone()
            assert row["cnt"] == 10, f"Esperado 10 agentes únicos, got {row['cnt']}"

            dest_db.close()
        await cache.close()


class TestAwarenessCacheRecovery:
    """Teste 4: Recuperação - execução -> backup -> restart -> restore."""

    @pytest.mark.asyncio
    async def test_recovery_publish_backup_restore(self):
        """100 publishes -> backup -> restore -> estado idêntico."""
        execution_id = "exec_test_recovery"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"

            # Fase 1: Publica 100 eventos
            cache1 = AwarenessCache()
            persistence1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.1)
            await persistence1.start()

            for i in range(100):
                await cache1.publish(
                    execution_id=execution_id,
                    node_id=f"agent_{i % 10}",
                    status="running" if i < 90 else "completed",
                    summary=f"task {i}",
                    metadata={"iteration": i, "skill": f"skill_{i % 5}"},
                )

            await asyncio.sleep(0.3)  # aguarda backup
            await persistence1.stop()
            await cache1.close()

            # Fase 2: Nova instância, restaura
            cache2 = AwarenessCache()
            persistence2 = AwarenessPersistence(cache2, db_path=db_path)
            await persistence2.restore(cache2)

            # Verifica estado restaurado
            snapshot = await cache2.snapshot(execution_id)
            assert len(snapshot) == 10

            # Verifica metadados preservados (CBOR2)
            for node_id, activity in snapshot.items():
                assert "skill" in activity.metadata
                assert activity.metadata["skill"].startswith("skill_")

            await cache2.close()


class TestAwarenessCacheBasic:
    """Testes básicos adicionais."""

    @pytest.mark.asyncio
    async def test_publish_and_snapshot_basic(self):
        """Publish e snapshot básicos funcionam."""
        cache = AwarenessCache()

        await cache.publish(
            execution_id="exec_1",
            node_id="coder",
            status="running",
            summary="Gerando código",
            metadata={"file": "main.py"},
        )

        snapshot = await cache.snapshot("exec_1")
        assert "coder" in snapshot
        assert snapshot["coder"].status == "running"
        assert snapshot["coder"].summary == "Gerando código"
        assert snapshot["coder"].metadata["file"] == "main.py"

        await cache.close()

    @pytest.mark.asyncio
    async def test_multiple_executions_isolated(self):
        """Execuções diferentes são isoladas."""
        cache = AwarenessCache()

        await cache.publish("exec_1", "coder", "running", "exec 1")
        await cache.publish("exec_2", "coder", "completed", "exec 2")

        snap1 = await cache.snapshot("exec_1")
        snap2 = await cache.snapshot("exec_2")

        assert snap1["coder"].summary == "exec 1"
        assert snap2["coder"].summary == "exec 2"

        await cache.close()

    @pytest.mark.asyncio
    async def test_get_node_activity(self):
        """Busca atividade de nó específico."""
        cache = AwarenessCache()

        await cache.publish("exec_1", "coder", "running", "working", {"key": "value"})

        activity = await cache.get_node_activity("exec_1", "coder")
        assert activity is not None
        assert activity.status == "running"
        assert activity.metadata["key"] == "value"

        # Nó inexistente
        activity = await cache.get_node_activity("exec_1", "nonexistent")
        assert activity is None

        await cache.close()

    @pytest.mark.asyncio
    async def test_get_active_waiting_blocked_nodes(self):
        """Filtros por status."""
        cache = AwarenessCache()

        await cache.publish("exec_1", "coder", "running", "working")
        await cache.publish("exec_1", "critic", "waiting", "waiting")
        await cache.publish("exec_1", "planner", "blocked", "blocked")

        active = await cache.get_active_nodes("exec_1")
        waiting = await cache.get_waiting_nodes("exec_1")
        blocked = await cache.get_blocked_nodes("exec_1")

        assert active == ["coder"]
        assert waiting == ["critic"]
        assert blocked == ["planner"]

        await cache.close()

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Close pode ser chamado múltiplas vezes."""
        cache = AwarenessCache()
        await cache.close()
        await cache.close()  # não deve falhar

    @pytest.mark.asyncio
    async def test_publish_after_close_raises(self):
        """Publish após close levanta erro."""
        cache = AwarenessCache()
        await cache.close()

        with pytest.raises(RuntimeError):
            await cache.publish("exec_1", "coder", "running")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
