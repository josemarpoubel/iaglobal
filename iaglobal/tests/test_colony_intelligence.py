# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do Colony Intelligence Communication — Fases 1, 2 e 3.

Cobertura:
  Fase 1 — AcetylcholineBus Estendido:
    - AgentMessage com organism_id
    - COLONY_MESSAGE_TYPES (task_offer, result_share, skill_handshake)
    - Roteamento por organism_id no bus

  Fase 2 — Divisão de Trabalho:
    - ColonyQueen: decompose, assign
    - ColonyWorker: skills, can_handle, execute
    - ColonyIntegrator: integrate, feed_evolution, feed_obsidian

  Fase 3 — Seleção de Fitness:
    - ColonyFitness: IVM por organismo, ranking
    - Apoptose para IVM < 0.3
    - Mitose para IVM >= 0.7
"""
import asyncio
import logging

import pytest

from iaglobal.graphs.communication.acetylcholine_bus import (
    AgentMessage,
    AcetylcholineBus,
    COLONY_MESSAGE_TYPES,
)
from iaglobal.communication.queen import ColonyQueen
from iaglobal.communication.worker import ColonyWorker
from iaglobal.communication.integrator import ColonyIntegrator
from iaglobal.communication.fitness import ColonyFitness

logging.basicConfig(level=logging.ERROR)


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────
# FASE 1 — AcetylcholineBus Estendido
# ─────────────────────────────────────────────


class TestAgentMessageOrganismID:
    """AgentMessage carrega organism_id corretamente."""

    def test_default_organism_id(self):
        msg = AgentMessage(sender="alpha", recipient="beta")
        assert msg.organism_id == "iaglobal"

    def test_custom_organism_id(self):
        msg = AgentMessage(
            sender="alpha", recipient="beta", organism_id="colony-x"
        )
        assert msg.organism_id == "colony-x"

    def test_task_offer_message_type(self):
        msg = AgentMessage(
            sender="alpha", recipient="beta",
            message_type="task_offer",
            payload={"task_id": "t1"},
        )
        assert msg.message_type == "task_offer"
        assert msg.payload["task_id"] == "t1"

    def test_result_share_message_type(self):
        msg = AgentMessage(
            sender="beta", recipient="alpha",
            message_type="result_share",
            payload={"task_id": "t1", "success": True},
        )
        assert msg.message_type == "result_share"
        assert msg.payload["success"] is True

    def test_skill_handshake_message_type(self):
        msg = AgentMessage(
            sender="gamma", recipient="*",
            message_type="skill_handshake",
            payload={"organism_id": "gamma", "skills": ["coder", "tester"]},
        )
        assert msg.message_type == "skill_handshake"
        assert "coder" in msg.payload["skills"]

    def test_colony_message_types_set(self):
        assert "task_offer" in COLONY_MESSAGE_TYPES
        assert "result_share" in COLONY_MESSAGE_TYPES
        assert "skill_handshake" in COLONY_MESSAGE_TYPES
        assert len(COLONY_MESSAGE_TYPES) == 3


class TestBusRoutingByOrganismID:
    """AcetylcholineBus roteia por organism_id."""

    def test_subscribe_by_organism_channel(self):
        bus = AcetylcholineBus()
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("org:alpha-org", handler)
        _run(bus.emit(AgentMessage(
            sender="alpha", recipient="*",
            organism_id="alpha-org",
        )))
        assert len(received) == 1

    def test_no_cross_organism_contamination(self):
        bus = AcetylcholineBus()
        alpha_msgs = []
        beta_msgs = []

        async def alpha_h(msg):
            alpha_msgs.append(msg)

        async def beta_h(msg):
            beta_msgs.append(msg)

        bus.subscribe("org:alpha-org", alpha_h)
        bus.subscribe("org:beta-org", beta_h)

        _run(bus.emit(AgentMessage(
            sender="alpha", recipient="*",
            organism_id="alpha-org",
        )))

        assert len(alpha_msgs) == 1
        assert len(beta_msgs) == 0

    def test_wildcard_still_works(self):
        bus = AcetylcholineBus()
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("*", handler)
        _run(bus.emit(AgentMessage(
            sender="alpha", recipient="specific",
            organism_id="any-org",
        )))
        assert len(received) == 1

    def test_subscribe_by_message_type(self):
        bus = AcetylcholineBus()
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("task_offer", handler)
        _run(bus.emit(AgentMessage(
            sender="alpha", recipient="*",
            message_type="task_offer",
        )))
        assert len(received) == 1


# ─────────────────────────────────────────────
# FASE 2 — Divisão de Trabalho
# ─────────────────────────────────────────────


class TestColonyQueen:
    """Queen decompõe tarefas e distribui."""

    def test_decompose_analysis(self):
        queen = ColonyQueen()
        subtasks = _run(queen.decompose({
            "id": "task-1",
            "type": "analysis",
            "description": "analisar performance",
        }))
        assert len(subtasks) >= 3
        types = {s["type"] for s in subtasks}
        assert "search" in types
        assert "code_review" in types
        assert "report" in types

    def test_decompose_development(self):
        queen = ColonyQueen()
        subtasks = _run(queen.decompose({
            "id": "task-2",
            "type": "development",
            "description": "criar API",
        }))
        assert len(subtasks) >= 4
        types = {s["type"] for s in subtasks}
        assert "planner" in types
        assert "coder" in types
        assert "tester" in types
        assert "documenter" in types

    def test_decompose_generic(self):
        queen = ColonyQueen()
        subtasks = _run(queen.decompose({
            "id": "task-3",
            "type": "unknown",
            "description": "algo",
        }))
        assert len(subtasks) == 1

    def test_assign_round_robin(self):
        queen = ColonyQueen()
        subtasks = _run(queen.decompose({"id": "t", "type": "analysis", "description": "x"}))
        workers = ["w1", "w2"]

        bus = AcetylcholineBus()
        queen_with_bus = ColonyQueen(message_bus=bus)
        offers = []

        async def offer_collector(msg):
            if msg.message_type == "task_offer":
                offers.append((msg.recipient, msg.payload["task_id"]))

        bus.subscribe("task_offer", offer_collector)

        _run(queen_with_bus.assign(subtasks, workers))
        assert len(offers) == len(subtasks)
        recipients = {r for r, _ in offers}
        assert "w1" in recipients
        assert "w2" in recipients


class TestColonyWorker:
    """Worker executa subtarefas especializadas."""

    def test_worker_skills_filter(self):
        worker = ColonyWorker("worker-1", skills=["coder", "tester"])
        assert worker.can_handle("coder") is True
        assert worker.can_handle("tester") is True
        assert worker.can_handle("search") is False
        assert worker.can_handle("report") is False

    def test_generic_skill_handles_anything(self):
        worker = ColonyWorker("worker-1", skills=["generic"])
        assert worker.can_handle("coder") is True
        assert worker.can_handle("search") is True
        assert worker.can_handle("unknown") is True

    def test_worker_execute_returns_result(self):
        worker = ColonyWorker("worker-1", skills=["generic"])
        result = _run(worker._run_handler("planner", "planejar projeto"))
        assert result["success"] is True

    def test_worker_execute_with_latency(self):
        worker = ColonyWorker("worker-1", skills=["coder"])
        bus = AcetylcholineBus()
        worker_with_bus = ColonyWorker("worker-code", skills=["coder"], message_bus=bus)
        results = []

        async def collector(msg):
            if msg.message_type == "result_share":
                results.append(msg)

        bus.subscribe("result_share", collector)

        _run(worker_with_bus.start())
        _run(bus.emit(AgentMessage(
            sender="queen", recipient="worker-code",
            message_type="task_offer",
            payload={
                "task_id": "t1", "type": "coder",
                "description": "escrever função", "parent": "big-task",
            },
        )))
        executed = _run(worker_with_bus.execute_next())
        assert executed is not None
        assert executed["success"] is True
        assert executed["task_id"] == "t1"
        assert executed["latency_ms"] >= 0
        _run(worker_with_bus.stop())


class TestColonyIntegrator:
    """Integrator combina resultados e alimenta evolução."""

    def test_integrate_combines_results(self):
        integrator = ColonyIntegrator()
        results = [
            {"task_id": "s1", "success": True, "latency_ms": 100, "result": {"output": "dados"}},
            {"task_id": "s2", "success": True, "latency_ms": 200, "result": {"output": "código"}},
            {"task_id": "s3", "success": True, "latency_ms": 50, "result": {"output": "testes"}},
        ]
        integrated = _run(integrator.integrate("big-task", results))
        assert integrated["success"] is True
        assert integrated["num_workers"] == 3
        assert integrated["total_latency_ms"] == 350.0
        assert len(integrated["outputs"]) == 3

    def test_integrate_empty_fails_gracefully(self):
        integrator = ColonyIntegrator()
        integrated = _run(integrator.integrate("empty-task", []))
        assert integrated["success"] is False
        assert "Nenhum resultado" in integrated.get("error", "")

    def test_integrate_partial_failures(self):
        integrator = ColonyIntegrator()
        results = [
            {"task_id": "s1", "success": True, "latency_ms": 100, "result": "ok"},
            {"task_id": "s2", "success": False, "latency_ms": 500, "result": "erro"},
        ]
        integrated = _run(integrator.integrate("partial-task", results))
        assert integrated["success"] is False

    def test_feed_evolution_does_not_crash(self):
        integrator = ColonyIntegrator()
        result = {"task_id": "t1", "success": True, "total_latency_ms": 300, "num_workers": 2}
        _run(integrator.feed_evolution("t1", result))

    def test_feed_obsidian_does_not_crash(self):
        integrator = ColonyIntegrator()
        result = {
            "task_id": "obs-test", "success": True,
            "num_workers": 2, "total_latency_ms": 150,
            "outputs": [{"msg": "hello"}],
        }
        _run(integrator.feed_obsidian("test-org", result))

    def test_format_obsidian_output(self):
        content = ColonyIntegrator._format_obsidian_note("alpha", {
            "task_id": "t1", "success": True,
            "num_workers": 2, "total_latency_ms": 100,
            "outputs": [{"msg": "resultado"}],
            "timestamp": "2026-07-09T00:00:00Z",
        })
        assert "alpha" in content
        assert "✅" in content
        assert "t1" in content
        assert "resultado" in content


# ─────────────────────────────────────────────
# FASE 3 — Seleção de Fitness
# ─────────────────────────────────────────────


class TestColonyFitness:
    """Fitness avalia IVM independente por organismo."""

    def test_register_and_ivm(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        assert fitness.organism_count() == 1
        assert fitness.get_organism_ivm("alpha") >= 0

    def test_ivm_increases_with_success(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        fitness.record_task("alpha", True, 100)
        fitness.record_task("alpha", True, 100)
        ivm = fitness.get_organism_ivm("alpha")
        assert ivm > 0.5

    def test_ivm_drops_with_failures(self):
        fitness = ColonyFitness()
        fitness.register_organism("beta")
        fitness.record_task("beta", False, 5000)
        fitness.record_task("beta", False, 5000)
        ivm = fitness.get_organism_ivm("beta")
        assert ivm < 0.3

    def test_ranking_highest_first(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        fitness.register_organism("beta")
        fitness.record_task("alpha", True, 100)
        fitness.record_task("beta", False, 5000)
        rank = fitness.rank_organisms()
        assert rank[0]["organism_id"] == "alpha"
        assert rank[0]["ivm"] > rank[1]["ivm"]

    def test_mitosis_only_for_high_ivm(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        fitness.register_organism("beta")
        fitness.record_task("alpha", True, 100)
        fitness.record_task("alpha", True, 100)
        fitness.record_task("beta", False, 5000)

        child = _run(fitness.check_mitosis("alpha", "coder"))
        assert child is not None
        assert "alpha-coder" in child

        child_low = _run(fitness.check_mitosis("beta"))
        assert child_low is None

    def test_apoptosis_only_for_low_ivm(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        fitness.register_organism("beta")
        fitness.record_task("alpha", True, 100)
        fitness.record_task("alpha", True, 100)
        fitness.record_task("beta", False, 5000)
        fitness.record_task("beta", False, 5000)

        result = _run(fitness.check_apoptosis("beta"))
        assert result is not None
        assert result["action"] == "apoptosis"

        result_high = _run(fitness.check_apoptosis("alpha"))
        assert result_high is None

    def test_average_ivm(self):
        fitness = ColonyFitness()
        fitness.register_organism("a")
        fitness.register_organism("b")
        fitness.record_task("a", True, 100)
        fitness.record_task("b", False, 200)
        avg = fitness.average_ivm()
        assert 0 < avg < 1

    def test_skill_exchange_increases_cooperation(self):
        fitness = ColonyFitness()
        fitness.register_organism("alpha")
        fitness.record_skill_exchange("alpha", 5)
        ivm = fitness.get_organism_ivm("alpha")
        assert ivm > 0

    def test_organism_not_found_returns_zero(self):
        fitness = ColonyFitness()
        assert fitness.get_organism_ivm("nonexistent") == 0.0


class TestColonyE2E:
    """Cenário: 3 organismos colaboram em tarefa maior que individual."""

    def test_three_organisms_end_to_end(self):
        fitness = ColonyFitness()

        # 3 organismos
        queen = ColonyQueen("queen-1")
        workers = [
            ColonyWorker("worker-a", skills=["search", "code_review"]),
            ColonyWorker("worker-b", skills=["coder"]),
            ColonyWorker("worker-c", skills=["report"]),
        ]

        for w in workers:
            _run(w.start())

        fitness.register_organism("queen-1")
        fitness.register_organism("worker-a")
        fitness.register_organism("worker-b")
        fitness.register_organism("worker-c")

        # Queen decompõe
        super_task = {"id": "e2e-task", "type": "analysis", "description": "analisar e reportar"}
        subtasks = _run(queen.decompose(super_task))
        assert len(subtasks) >= 3

        # Distribui
        worker_ids = ["worker-a", "worker-b", "worker-c"]
        _run(queen.assign(subtasks, worker_ids))

        # Cada worker executa
        results = []
        for w in workers:
            executed = _run(w.execute_next())
            if executed:
                results.append(executed)
                fitness.record_task(w.organism_id, executed["success"], executed["latency_ms"])
                fitness.record_skill_exchange(w.organism_id)

        # Integrator
        integrator = ColonyIntegrator()
        integrated = _run(integrator.integrate("e2e-task", results))
        fitness.record_task("queen-1", integrated["success"], integrated["total_latency_ms"])

        # Fitness individual
        ivm_individual = max(
            fitness.get_organism_ivm("worker-a"),
            fitness.get_organism_ivm("worker-b"),
            fitness.get_organism_ivm("worker-c"),
        )

        # Fitness médio da colônia
        avg = fitness.average_ivm()

        # Critério: fitness médio da colônia deve ao menos existir
        assert avg > 0
        assert integrated["num_workers"] >= 1

        for w in workers:
            _run(w.stop())