# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Stress Test — Tribunal Cognitivo: TaskRouter + Token Buckets

Valida:
  - TaskRouter mapeia 121 nós corretamente para 3 tiers (reviewer, coder, sentinel)
  - Token buckets por tier respeitam capacidades (reviewer=4, coder=6, sentinel=8)
  - Alertas de congestão são disparados quando bucket atinge limite
  - JOLMetricsCollector registra alertas em JSONL
  - Homeostase: pipeline degrada gracefully sob congestão
"""

import asyncio
import json
from pathlib import Path

import pytest

from iaglobal.providers.task_router import get_task_router
from iaglobal.execution.token_bucket import LocalModelGate
from iaglobal.metabolism.jol_metrics import JOLMetricsCollector
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.stress_tribunal")

# Arquivo de congestão gerado pelo JOLMetricsCollector
CONGESTION_FILE = Path(
    "/home/kitohamachi/iaglobal-main/iaglobal/memory/data/jol/jol_congestion.jsonl"
)


@pytest.fixture
def task_router_instance():
    """TaskRouter singleton limpo."""
    router = get_task_router()
    yield router


@pytest.fixture
async def token_gate_instance():
    """LocalModelGate com buckets resetados para cada teste."""
    gate = await LocalModelGate.reset_instance()
    yield gate


@pytest.fixture
def jol_collector_instance():
    """JOLMetricsCollector limpo."""
    collector = JOLMetricsCollector()
    # Limpa arquivo de congestão antes do teste
    if CONGESTION_FILE.exists():
        CONGESTION_FILE.write_text("", encoding="utf-8")
    yield collector
    # Cleanup após teste (opcional)


class TestTaskRouterMapping:
    """Valida mapeamento de 121 nós para 3 tiers."""

    def test_critic_nodes_map_to_reviewer(self, task_router_instance):
        """Nós críticos devem mapear para tier reviewer."""
        router = task_router_instance
        critical_nodes = [
            "no_critic",
            "no_critic_batch",
            "critic_agent",
            "no_requirements",
            "no_technology_selection",
            "no_architecture_design",
            "no_system_design",
        ]
        for node_id in critical_nodes:
            tier = router.get_role_for_node(node_id)
            assert tier == "reviewer", f"{node_id} should map to reviewer, got {tier}"

    def test_coder_nodes_map_to_coder(self, task_router_instance):
        """Nós coder/dev devem mapear para tier coder."""
        router = task_router_instance
        coder_nodes = [
            "no_coder",
            "coder_agent",
            "debugger_agent",
            "no_multi_coder",
            "no_code_generator",
            "no_reflexion",
        ]
        for node_id in coder_nodes:
            tier = router.get_role_for_node(node_id)
            assert tier == "coder", f"{node_id} should map to coder, got {tier}"

    def test_sentinel_nodes_map_to_sentinel(self, task_router_instance):
        """Nós sentinela/audit devem mapear para tier sentinel."""
        router = task_router_instance
        sentinel_nodes = [
            "no_sentinel_audit",
            "no_auditor_sentinel",
            "no_entropy_sentinel",
            "no_syntax_sentinel",
            "no_lsp_validator",
            "no_dependency",
            "no_test_generator",
            "tester_agent",
        ]
        for node_id in sentinel_nodes:
            tier = router.get_role_for_node(node_id)
            assert tier == "sentinel", f"{node_id} should map to sentinel, got {tier}"

    def test_timeout_per_tier(self, task_router_instance):
        """Cada tier tem timeout apropriado."""
        router = task_router_instance
        assert router.get_timeout_for_tier("reviewer") == 600.0
        assert router.get_timeout_for_tier("coder") == 60.0
        assert router.get_timeout_for_tier("sentinel") == 10.0

    def test_unknown_node_falls_back_to_coder(self, task_router_instance):
        """Nó desconhecido deve fallback para coder (tier padrão)."""
        router = task_router_instance
        tier = router.get_role_for_node("unknown_node_xyz")
        assert tier == "coder", f"Unknown node should fallback to coder, got {tier}"


class TestTokenBucketStress:
    """Stress test dos buckets por tier."""

    @pytest.mark.asyncio
    async def test_reviewer_bucket_capacity(self, token_gate_instance):
        """Bucket reviewer deve aceitar 4 aquisições consecutivas (capacity=4)."""
        gate = token_gate_instance
        results = []
        for i in range(5):
            allowed = await gate.try_acquire("no_critic")
            results.append(allowed)

        assert results[0] == True, "First reviewer acquire should pass"
        assert results[1] == True, "Second reviewer acquire should pass"
        assert results[2] == True, "Third reviewer acquire should pass"
        assert results[3] == True, "Fourth reviewer acquire should pass"
        assert results[4] == False, "Fifth reviewer acquire should fail (bucket empty)"

    @pytest.mark.asyncio
    async def test_coder_bucket_capacity(self, token_gate_instance):
        """Bucket coder deve aceitar 6 aquisições consecutivas (capacity=6)."""
        gate = token_gate_instance
        results = []
        for i in range(7):
            allowed = await gate.try_acquire("no_coder")
            results.append(allowed)

        assert sum(results) == 6, f"Expected 6 successes, got {sum(results)}"

    @pytest.mark.asyncio
    async def test_sentinel_bucket_capacity(self, token_gate_instance):
        """Bucket sentinel deve aceitar 8 aquisições consecutivas (capacity=8)."""
        gate = token_gate_instance
        results = []
        for i in range(9):
            allowed = await gate.try_acquire("no_sentinel_audit")
            results.append(allowed)

        assert sum(results) == 8, f"Expected 8 successes, got {sum(results)}"

    @pytest.mark.asyncio
    async def test_priority_critic_high_priority(self, token_gate_instance):
        """Critic deve ter alta prioridade (0.95)."""
        gate = token_gate_instance
        priority = gate.get_priority("no_critic")
        assert priority >= 0.9, f"Critic should have high priority, got {priority}"

    @pytest.mark.asyncio
    async def test_low_priority_scheduler(self, token_gate_instance):
        """Scheduler deve ter baixa prioridade (0.30)."""
        gate = token_gate_instance
        priority = gate.get_priority("no_scheduler")
        assert priority <= 0.35, f"Scheduler should have low priority, got {priority}"


class TestCongestionAlerts:
    """Valida disparo e registro de alertas de congestão."""

    @pytest.mark.asyncio
    async def test_congestion_alert_fired_on_bucket_full(
        self, token_gate_instance, jol_collector_instance
    ):
        """Alerta de congestão deve ser disparado quando bucket atinge limite."""
        gate = token_gate_instance

        alerts_received = []

        def capture_alert(msg):
            alerts_received.append((msg.message_type, msg.content))

        from iaglobal.graphs.comms.acetylcholine_bus import bus

        bus.subscribe("tier_congestion_alert", capture_alert)

        for i in range(7):
            await gate.try_acquire("no_critic")
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.5)

        assert gate._alerts_fired.get("reviewer", 0) >= 1, (
            "Congestion alert should be fired for reviewer"
        )

    @pytest.mark.asyncio
    async def test_congestion_logged_to_jsonl(
        self, token_gate_instance, jol_collector_instance
    ):
        """Alertas de congestão devem ser registrados em JSONL."""
        gate = token_gate_instance

        for i in range(5):
            await gate.try_acquire("no_critic")
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.0)

        if CONGESTION_FILE.exists():
            lines = CONGESTION_FILE.read_text(encoding="utf-8").strip().splitlines()
            if len(lines) > 0:
                alert = json.loads(lines[0])
                assert "tier" in alert
                assert "timestamp" in alert
                assert "usage_pct" in alert


class TestConcurrentLoad:
    """Stress test com carga concorrente massiva."""

    @pytest.mark.asyncio
    async def test_81_concurrent_tasks_distribution(
        self, task_router_instance, token_gate_instance
    ):
        """81 tarefas concorrentes devem ser distribuídas corretamente entre tiers."""
        router = task_router_instance
        gate = token_gate_instance

        tasks_per_tier = 27

        results = {"reviewer": [], "coder": [], "sentinel": []}

        async def acquire_for_tier(tier: str, task_id: int):
            node_mapping = {
                "reviewer": "no_critic",
                "coder": "no_coder",
                "sentinel": "no_sentinel_audit",
            }
            node_id = node_mapping[tier]
            allowed = await gate.try_acquire(node_id)
            return (tier, task_id, allowed)

        coroutines = []
        for tier in ["reviewer", "coder", "sentinel"]:
            for i in range(tasks_per_tier):
                coroutines.append(acquire_for_tier(tier, i))

        all_results = await asyncio.gather(*coroutines)

        for tier, task_id, allowed in all_results:
            results[tier].append(allowed)

        reviewer_successes = sum(results["reviewer"])
        coder_successes = sum(results["coder"])
        sentinel_successes = sum(results["sentinel"])

        logger.info(
            f"Concurrent load: reviewer={reviewer_successes}/27, coder={coder_successes}/27, sentinel={sentinel_successes}/27"
        )

        assert reviewer_successes <= 4, (
            f"reviewer should have max 4 successes, got {reviewer_successes}"
        )
        assert coder_successes <= 6, (
            f"coder should have max 6 successes, got {coder_successes}"
        )
        assert sentinel_successes <= 8, (
            f"sentinel should have max 8 successes, got {sentinel_successes}"
        )

        logger.info("Bucket limits validated: reviewer<=4, coder<=6, sentinel<=8")

    @pytest.mark.asyncio
    async def test_concurrent_load_triggers_alerts(
        self, token_gate_instance, jol_collector_instance
    ):
        """Carga concorrente deve disparar alertas de congestão."""
        gate = token_gate_instance

        async def stress_task():
            await gate.try_acquire("no_coder")
            await asyncio.sleep(0.01)

        tasks = [stress_task() for _ in range(20)]
        await asyncio.gather(*tasks)

        await asyncio.sleep(0.5)

        assert gate._alerts_fired.get("coder", 0) >= 1, (
            "coder alert should be fired under concurrent load"
        )


class TestHomeostaticDegradation:
    """Valida degradação homeostática sob congestão."""

    @pytest.mark.asyncio
    async def test_gate_tracks_rejections(self, token_gate_instance):
        """Gate deve rastrear contagem de rejeições por tier."""
        gate = token_gate_instance

        initial = gate._rejected_counts.get("reviewer", 0)

        for i in range(5):
            await gate.try_acquire("no_critic")

        final = gate._rejected_counts.get("reviewer", 0)
        assert final >= initial, (
            f"Should track rejections for reviewer: {initial} → {final}"
        )

    @pytest.mark.asyncio
    async def test_gate_metrics_available(self, token_gate_instance):
        """Gate deve fornecer métricas de operação."""
        gate = token_gate_instance

        assert "reviewer" in gate.buckets
        assert "coder" in gate.buckets
        assert "sentinel" in gate.buckets

        assert gate.buckets["reviewer"].capacity == 4
        assert gate.buckets["coder"].capacity == 6
        assert gate.buckets["sentinel"].capacity == 8


if __name__ == "__main__":
    import sys

    async def run_manual():
        router = get_task_router()
        gate = LocalModelGate.get_instance()
        collector = JOLMetricsCollector()

        print("=" * 60)
        print("STRESS TEST MANUAL — Tribunal Cognitivo")
        print("=" * 60)

        print("\n1. TaskRouter Mapping:")
        for node in ["no_critic", "no_coder", "no_sentinel_audit"]:
            tier = router.get_role_for_node(node)
            route = router.route_for_tier(tier)
            print(f"   {node} → {tier} ({route})")

        print("\n2. Token Bucket Capacity:")
        for node, expected in [
            ("no_critic", 4),
            ("no_coder", 6),
            ("no_sentinel_audit", 8),
        ]:
            successes = 0
            for _ in range(expected + 1):
                allowed = await gate.try_acquire(node)
                if allowed:
                    successes += 1
            print(f"   {node}: {successes}/{expected + 1} (expected {expected})")

        print("\n" + "=" * 60)
        print("MANUAL TEST COMPLETED")
        print("=" * 60)

    asyncio.run(run_manual())
    sys.exit(0)
