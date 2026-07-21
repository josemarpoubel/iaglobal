# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Testes v2 para AwarenessCache - Consciência Causal, Atenção Seletiva, Memória Episódica.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from iaglobal.cognition.awareness import (
    AwarenessCache,
    AwarenessPersistence,
    AgentActivity,
    NodeDomain,
    NodeStatus,
    CausalChain,
    DomainSnapshot,
    EpisodicMemory,
)


class TestCausalAwareness:
    """Testes de Consciência Causal - snapshot(relevance='blocking')."""

    @pytest.mark.asyncio
    async def test_snapshot_blocking_returns_causal_chains(self):
        """Snapshot com relevance='blocking' retorna cadeias causais."""
        cache = AwarenessCache()
        execution_id = "exec_causal_1"

        # Setup: architect → coder (coder depende de architect)
        await cache.publish(
            execution_id=execution_id,
            node_id="architect",
            status=NodeStatus.COMPLETED.value,
            summary="Schema pronto",
            domain=NodeDomain.ARCHITECTURE.value,
        )
        await cache.publish(
            execution_id=execution_id,
            node_id="coder",
            status=NodeStatus.BLOCKED.value,
            summary="Aguardando schema",
            domain=NodeDomain.CODING.value,
            depends_on=["architect"],
        )

        # Snapshot causal
        chains = await cache.snapshot(execution_id, relevance="blocking")

        assert isinstance(chains, list)
        assert len(chains) == 1
        chain = chains[0]
        assert isinstance(chain, CausalChain)
        assert chain.blocked_node == "coder"
        assert chain.depth >= 1
        assert "architect" in chain.blocking_chain or chain.root_cause == "architect"

        await cache.close()

    @pytest.mark.asyncio
    async def test_causal_chain_multi_level(self):
        """Cadeia causal multi-nível: planner → architect → coder → tester."""
        cache = AwarenessCache()
        execution_id = "exec_causal_2"

        await cache.publish(
            execution_id,
            "planner",
            NodeStatus.COMPLETED.value,
            "Plano pronto",
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "architect",
            NodeStatus.BLOCKED.value,
            "Aguardando plano",
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["planner"],
        )
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.BLOCKED.value,
            "Aguardando schema",
            domain=NodeDomain.CODING.value,
            depends_on=["architect"],
        )
        await cache.publish(
            execution_id,
            "tester",
            NodeStatus.BLOCKED.value,
            "Aguardando código",
            domain=NodeDomain.TESTING.value,
            depends_on=["coder"],
        )

        chains = await cache.snapshot(execution_id, relevance="blocking")

        assert len(chains) == 3  # architect, coder, tester bloqueados
        # Verifica que tester tem cadeia completa
        tester_chain = next(c for c in chains if c.blocked_node == "tester")
        assert "coder" in tester_chain.blocking_chain
        assert "architect" in tester_chain.blocking_chain
        assert (
            "planner" in tester_chain.blocking_chain
            or tester_chain.root_cause == "planner"
        )

        await cache.close()

    @pytest.mark.asyncio
    async def test_get_causal_explanation(self):
        """Explicação legível de por que um nó está bloqueado."""
        cache = AwarenessCache()
        execution_id = "exec_causal_3"

        await cache.publish(
            execution_id,
            "planner",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "architect",
            NodeStatus.BLOCKED.value,
            "waiting",
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["planner"],
        )
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.BLOCKED.value,
            "waiting",
            domain=NodeDomain.CODING.value,
            depends_on=["architect"],
        )

        explanation = await cache.get_causal_explanation(execution_id, "coder")

        assert explanation is not None
        assert "coder" in explanation
        assert "architect" in explanation
        assert "planner" in explanation

        await cache.close()


class TestSelectiveAttention:
    """Testes de Atenção Seletiva - snapshot(domain=...)."""

    @pytest.mark.asyncio
    async def test_snapshot_domain_filter(self):
        """Snapshot filtrado por domínio retorna apenas nós daquele domínio."""
        cache = AwarenessCache()
        execution_id = "exec_domain_1"

        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.RUNNING.value,
            "coding",
            domain=NodeDomain.CODING.value,
        )
        await cache.publish(
            execution_id,
            "security_audit",
            NodeStatus.RUNNING.value,
            "auditing",
            domain=NodeDomain.SECURITY.value,
        )
        await cache.publish(
            execution_id,
            "perf_check",
            NodeStatus.RUNNING.value,
            "profiling",
            domain=NodeDomain.PERFORMANCE.value,
        )
        await cache.publish(
            execution_id,
            "critic",
            NodeStatus.WAITING.value,
            "reviewing",
            domain=NodeDomain.CRITIC.value,
        )

        # Filtro security
        security_snapshot = await cache.snapshot(
            execution_id, domain=NodeDomain.SECURITY.value
        )

        assert isinstance(security_snapshot, DomainSnapshot)
        assert security_snapshot.domain == NodeDomain.SECURITY.value
        assert len(security_snapshot.activities) == 1
        assert security_snapshot.activities[0].node_id == "security_audit"

        # Filtro coding
        coding_snapshot = await cache.snapshot(
            execution_id, domain=NodeDomain.CODING.value
        )
        assert len(coding_snapshot.activities) == 1
        assert coding_snapshot.activities[0].node_id == "coder"

        await cache.close()

    @pytest.mark.asyncio
    async def test_get_nodes_by_domain(self):
        """Método helper get_nodes_by_domain funciona."""
        cache = AwarenessCache()
        execution_id = "exec_domain_2"

        await cache.publish(
            execution_id,
            "coder1",
            NodeStatus.RUNNING.value,
            "coding",
            domain=NodeDomain.CODING.value,
        )
        await cache.publish(
            execution_id,
            "coder2",
            NodeStatus.RUNNING.value,
            "coding",
            domain=NodeDomain.CODING.value,
        )
        await cache.publish(
            execution_id,
            "tester",
            NodeStatus.RUNNING.value,
            "testing",
            domain=NodeDomain.TESTING.value,
        )

        coders = await cache.get_nodes_by_domain(execution_id, NodeDomain.CODING.value)
        assert len(coders) == 2
        assert all(c.domain == NodeDomain.CODING.value for c in coders)

        testers = await cache.get_nodes_by_domain(
            execution_id, NodeDomain.TESTING.value
        )
        assert len(testers) == 1

        await cache.close()

    @pytest.mark.asyncio
    async def test_domain_snapshot_immutable(self):
        """DomainSnapshot é imutável."""
        cache = AwarenessCache()
        execution_id = "exec_domain_3"

        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.RUNNING.value,
            "coding",
            domain=NodeDomain.CODING.value,
        )

        snapshot = await cache.snapshot(execution_id, domain=NodeDomain.CODING.value)

        # Deve ser tupla (imutável)
        assert isinstance(snapshot.activities, tuple)
        # Tentar modificar deve falhar (frozen dataclass)
        with pytest.raises(Exception):
            snapshot.activities = []

        await cache.close()


class TestEpisodicMemory:
    """Testes de Memória Episódica - export_episodic_memory."""

    @pytest.mark.asyncio
    async def test_export_episodic_memory(self):
        """Exporta memória episódica completa no fim da execução."""
        cache = AwarenessCache()
        execution_id = "exec_episodic_1"

        await cache.publish(
            execution_id,
            "planner",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.CODING.value,
        )
        await cache.publish(
            execution_id,
            "tester",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.TESTING.value,
        )
        await cache.publish(
            execution_id,
            "critic",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.CRITIC.value,
        )

        memory = await cache.export_episodic_memory(
            execution_id=execution_id,
            final_status="completed",
            ivm_score=0.85,
            lessons_learned=["Use typed dicts", "Add integration tests early"],
        )

        assert isinstance(memory, EpisodicMemory)
        assert memory.execution_id == execution_id
        assert memory.final_status == "completed"
        assert memory.ivm_score == 0.85
        assert len(memory.lessons_learned) == 2
        assert len(memory.nodes) == 4
        assert memory.ended_at > memory.started_at

        await cache.close()

    @pytest.mark.asyncio
    async def test_episodic_memory_includes_causal_chains(self):
        """Memória episódica inclui cadeias causais."""
        cache = AwarenessCache()
        execution_id = "exec_episodic_2"

        await cache.publish(
            execution_id,
            "planner",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "architect",
            NodeStatus.BLOCKED.value,
            "waiting",
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["planner"],
        )
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.BLOCKED.value,
            "waiting",
            domain=NodeDomain.CODING.value,
            depends_on=["architect"],
        )

        memory = await cache.export_episodic_memory(
            execution_id=execution_id,
            final_status="partial",
            ivm_score=0.45,
        )

        assert len(memory.causal_chains) == 2
        for chain in memory.causal_chains:
            assert isinstance(chain, CausalChain)
            assert chain.depth >= 1

        await cache.close()

    @pytest.mark.asyncio
    async def test_episodic_memory_persists_and_restores(self):
        """Memória episódica persiste no backup e restaura."""
        execution_id = "exec_episodic_3"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "awareness.db"

            # Fase 1: Cria e exporta
            cache1 = AwarenessCache()
            persistence1 = AwarenessPersistence(cache1, db_path=db_path, interval=0.1)
            await persistence1.start()

            await cache1.publish(
                execution_id,
                "planner",
                NodeStatus.COMPLETED.value,
                "done",
                domain=NodeDomain.PLANNING.value,
            )
            await cache1.publish(
                execution_id,
                "coder",
                NodeStatus.COMPLETED.value,
                "done",
                domain=NodeDomain.CODING.value,
            )

            memory1 = await cache1.export_episodic_memory(
                execution_id, "completed", 0.9, ["Lesson 1"]
            )

            await asyncio.sleep(0.2)  # aguarda backup
            await persistence1.stop()
            await cache1.close()

            # Fase 2: Nova instância, restaura
            cache2 = AwarenessCache()
            persistence2 = AwarenessPersistence(cache2, db_path=db_path)
            await persistence2.restore(cache2)

            memory2 = await cache2.get_episodic_memory(execution_id)

            assert memory2 is not None
            assert memory2.execution_id == execution_id
            assert memory2.final_status == "completed"
            assert memory2.ivm_score == 0.9
            assert memory2.lessons_learned == ["Lesson 1"]
            assert len(memory2.nodes) == 2

            await cache2.close()

    @pytest.mark.asyncio
    async def test_episodic_memory_to_dict(self):
        """EpisodicMemory serializa para dict corretamente."""
        cache = AwarenessCache()
        execution_id = "exec_episodic_4"

        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.COMPLETED.value,
            "done",
            domain=NodeDomain.CODING.value,
        )

        memory = await cache.export_episodic_memory(
            execution_id, "completed", 0.8, ["Lesson"]
        )

        d = memory.to_dict()
        assert d["execution_id"] == execution_id
        assert d["final_status"] == "completed"
        assert d["ivm_score"] == 0.8
        assert d["lessons_learned"] == ["Lesson"]
        assert "nodes" in d
        assert "causal_chains" in d
        assert "duration" in d

        await cache.close()


class TestIntegrationV2:
    """Testes de integração das features v2."""

    @pytest.mark.asyncio
    async def test_full_workflow_causal_domain_episodic(self):
        """Workflow completo: causal → domain → episodic."""
        cache = AwarenessCache()
        execution_id = "exec_integration"

        # Setup pipeline com dependências
        await cache.publish(
            execution_id,
            "planner",
            NodeStatus.COMPLETED.value,
            "Planned",
            domain=NodeDomain.PLANNING.value,
        )
        await cache.publish(
            execution_id,
            "architect",
            NodeStatus.COMPLETED.value,
            "Designed",
            domain=NodeDomain.ARCHITECTURE.value,
            depends_on=["planner"],
        )
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.BLOCKED.value,
            "Waiting schema",
            domain=NodeDomain.CODING.value,
            depends_on=["architect"],
        )
        await cache.publish(
            execution_id,
            "security",
            NodeStatus.RUNNING.value,
            "Auditing",
            domain=NodeDomain.SECURITY.value,
        )
        await cache.publish(
            execution_id,
            "perf",
            NodeStatus.RUNNING.value,
            "Profiling",
            domain=NodeDomain.PERFORMANCE.value,
        )
        await cache.publish(
            execution_id,
            "tester",
            NodeStatus.BLOCKED.value,
            "Waiting code",
            domain=NodeDomain.TESTING.value,
            depends_on=["coder"],
        )

        # 1. Consciência causal
        chains = await cache.snapshot(execution_id, relevance="blocking")
        assert len(chains) >= 2  # coder e tester bloqueados

        # 2. Atenção seletiva - security
        security_snap = await cache.snapshot(
            execution_id, domain=NodeDomain.SECURITY.value
        )
        assert len(security_snap.activities) == 1
        assert security_snap.activities[0].node_id == "security"

        # 3. Atenção seletiva - performance
        perf_snap = await cache.snapshot(
            execution_id, domain=NodeDomain.PERFORMANCE.value
        )
        assert len(perf_snap.activities) == 1
        assert perf_snap.activities[0].node_id == "perf"

        # 4. Memória episódica final
        memory = await cache.export_episodic_memory(
            execution_id, "partial", 0.6, ["Blocked on schema design"]
        )
        assert memory.final_status == "partial"
        assert len(memory.nodes) == 6
        assert len(memory.causal_chains) >= 2

        await cache.close()

    @pytest.mark.asyncio
    async def test_metadata_preserved_in_snapshot(self):
        """Metadados customizados preservados nos snapshots v2."""
        cache = AwarenessCache()
        execution_id = "exec_meta"

        custom_meta = {
            "skill": "backend_generation",
            "file": "api/users.py",
            "lines": 150,
        }
        await cache.publish(
            execution_id,
            "coder",
            NodeStatus.RUNNING.value,
            "Generating API",
            domain=NodeDomain.CODING.value,
            metadata=custom_meta,
        )

        snapshot = await cache.snapshot(execution_id)
        activity = snapshot["coder"]

        assert activity.metadata["skill"] == "backend_generation"
        assert activity.metadata["file"] == "api/users.py"
        assert activity.metadata["lines"] == 150
        assert activity.domain == NodeDomain.CODING.value

        await cache.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
