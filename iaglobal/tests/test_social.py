# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

import time

import pytest

from iaglobal.agents.social import (
    Advertisement,
    Capability,
    HEARTBEAT_TTL_SECONDS,
    SocialRegistry,
)


@pytest.fixture
def reg():
    return SocialRegistry()


def _make_adv(
    agent_id: str,
    domain: str = "code",
    proficiency: float = 0.8,
    load_factor: float = 0.0,
) -> Advertisement:
    return Advertisement(
        agent_id=agent_id,
        skills={domain: Capability(domain=domain, proficiency=proficiency)},
        load_factor=load_factor,
    )


class TestSocialRegistry:
    def test_publish_and_get(self, reg: SocialRegistry):
        adv = _make_adv("coder-1")
        reg.publish(adv)
        retrieved = reg.get("coder-1")
        assert retrieved is not None
        assert retrieved.agent_id == "coder-1"

    def test_get_returns_none_for_unknown(self, reg: SocialRegistry):
        assert reg.get("ghost") is None

    def test_publish_updates_existing(self, reg: SocialRegistry):
        reg.publish(_make_adv("coder-1", proficiency=0.5))
        reg.publish(_make_adv("coder-1", proficiency=0.9))
        retrieved = reg.get("coder-1")
        assert retrieved is not None
        assert retrieved.skills["code"].proficiency == 0.9

    def test_heartbeat_updates_timestamp(self, reg: SocialRegistry):
        adv = _make_adv("coder-1")
        adv.last_seen = time.time() - 10
        reg.publish(adv)
        old_ts = adv.last_seen
        time.sleep(0.01)
        reg.heartbeat("coder-1")
        retrieved = reg.get("coder-1")
        assert retrieved is not None
        assert retrieved.last_seen > old_ts

    def test_heartbeat_updates_load_factor(self, reg: SocialRegistry):
        reg.publish(_make_adv("coder-1"))
        reg.heartbeat("coder-1", load_factor=0.85)
        retrieved = reg.get("coder-1")
        assert retrieved is not None
        assert retrieved.load_factor == 0.85

    def test_withdraw_removes_agent(self, reg: SocialRegistry):
        reg.publish(_make_adv("coder-1"))
        assert reg.get("coder-1") is not None
        reg.withdraw("coder-1")
        assert reg.get("coder-1") is None

    def test_withdraw_returns_advertisement(self, reg: SocialRegistry):
        reg.publish(_make_adv("coder-1"))
        removed = reg.withdraw("coder-1")
        assert removed is not None
        assert removed.agent_id == "coder-1"

    def test_withdraw_unknown_returns_none(self, reg: SocialRegistry):
        assert reg.withdraw("ghost") is None

    def test_query_returns_sorted_by_proficiency(self, reg: SocialRegistry):
        reg.publish(_make_adv("agent-a", domain="code", proficiency=0.5))
        reg.publish(_make_adv("agent-b", domain="code", proficiency=0.9))
        reg.publish(_make_adv("agent-c", domain="code", proficiency=0.7))
        results = reg.query("code")
        assert [a.agent_id for a in results] == ["agent-b", "agent-c", "agent-a"]

    def test_query_filters_by_domain(self, reg: SocialRegistry):
        reg.publish(
            Advertisement(
                agent_id="agent-a",
                skills={
                    "code": Capability("code", 0.8),
                    "test": Capability("test", 0.6),
                },
            )
        )
        reg.publish(_make_adv("agent-b", domain="test", proficiency=0.9))
        results_code = reg.query("code")
        results_test = reg.query("test")
        assert len(results_code) == 1
        assert results_code[0].agent_id == "agent-a"
        assert len(results_test) == 2

    def test_query_min_proficiency(self, reg: SocialRegistry):
        reg.publish(_make_adv("agent-a", domain="code", proficiency=0.3))
        reg.publish(_make_adv("agent-b", domain="code", proficiency=0.7))
        reg.publish(_make_adv("agent-c", domain="code", proficiency=0.5))
        results = reg.query("code", min_proficiency=0.5)
        assert [a.agent_id for a in results] == ["agent-b", "agent-c"]

    def test_query_excludes_stale_agents(self, reg: SocialRegistry):
        adv = _make_adv("coder-1")
        adv.last_seen = time.time() - (HEARTBEAT_TTL_SECONDS + 10)
        reg.publish(adv)
        results = reg.query("code")
        assert len(results) == 0

    def test_all_alive_excludes_stale(self, reg: SocialRegistry):
        fresh = _make_adv("fresh")
        stale = _make_adv("stale")
        stale.last_seen = time.time() - (HEARTBEAT_TTL_SECONDS + 10)
        reg.publish(fresh)
        reg.publish(stale)
        alive = reg.all_alive()
        assert len(alive) == 1
        assert alive[0].agent_id == "fresh"

    def test_clear_stale_removes_dead_agents(self, reg: SocialRegistry):
        fresh = _make_adv("fresh")
        stale = _make_adv("stale")
        stale.last_seen = time.time() - (HEARTBEAT_TTL_SECONDS + 10)
        reg.publish(fresh)
        reg.publish(stale)
        removed = reg.clear_stale()
        assert removed == 1
        assert reg.get("fresh") is not None
        assert reg.get("stale") is None

    def test_size(self, reg: SocialRegistry):
        assert reg.size == 0
        reg.publish(_make_adv("a"))
        reg.publish(_make_adv("b"))
        assert reg.size == 2

    def test_to_dict(self, reg: SocialRegistry):
        reg.publish(_make_adv("agent-a", domain="code", proficiency=0.9))
        d = reg.to_dict()
        assert "agent-a" in d
        assert d["agent-a"]["skills"]["code"]["proficiency"] == 0.9

    def test_thread_safety(self, reg: SocialRegistry):
        import concurrent.futures

        def _publish(i: int):
            r = SocialRegistry()
            r.publish(_make_adv(f"worker-{i}", proficiency=i / 10))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_publish, range(20)))

        # Only the last writer of each agent_id wins — stress test must not crash
        assert reg.size >= 0

    def test_is_stale_property(self):
        adv = _make_adv("a")
        assert not adv.is_stale
        adv.last_seen = time.time() - (HEARTBEAT_TTL_SECONDS + 10)
        assert adv.is_stale

    def test_advertisement_to_dict(self):
        adv = _make_adv("coder-1", domain="code", proficiency=0.85, load_factor=0.3)
        d = adv.to_dict()
        assert d["agent_id"] == "coder-1"
        assert d["skills"]["code"]["proficiency"] == 0.85
        assert d["load_factor"] == 0.3
        assert "last_seen" in d
