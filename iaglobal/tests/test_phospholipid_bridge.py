# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do PhospholipidBanditBridge e PhospholipidSearchBridge.

Cobertura:
  - BanditBridge: auto_report, select_instance, execute_with_health
  - SearchBridge: auto_report_search, search_with_lb, search_and_learn_with_lb
  - Hook no BanditPolicy.generate()
  - Hook no SearchAgent.pesquisar_e_aprender()
"""

import asyncio
import logging
import time


from iaglobal.observability.registry import PhospholipidRegistry
from iaglobal.observability.load_balancer import PhospholipidLoadBalancer
from iaglobal.observability.phospholipid_bridge import PhospholipidBanditBridge, bridge
from iaglobal.observability.search_bridge import PhospholipidSearchBridge

logging.basicConfig(level=logging.ERROR)


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────
# PhospholipidBanditBridge
# ─────────────────────────────────────────────


class TestBanditBridge:
    """PhospholipidBanditBridge: auto_report e select_instance."""

    def test_provider_from_model(self):
        assert bridge.provider_from_model("groq/llama3-70b") == "groq"
        assert bridge.provider_from_model("ollama/qwen2.5:0.5b") == "ollama"
        assert bridge.provider_from_model("nvidia/mistralai/mistral-large") == "nvidia"
        assert bridge.provider_from_model("no-slash") == "no-slash"

    def test_has_registered_services(self):
        b = PhospholipidBanditBridge(registry=PhospholipidRegistry())
        assert b.has_registered_services("groq") is False
        b.registry.register("groq-api", "http://groq:8080")
        assert b.has_registered_services("groq") is True
        assert b.has_registered_services("ollama") is False

    def test_select_instance_returns_none_when_no_services(self):
        b = PhospholipidBanditBridge(registry=PhospholipidRegistry())
        result = _run(b.select_instance("groq"))
        assert result is None

    def test_select_instance_returns_healthy(self):
        reg = PhospholipidRegistry()
        svc = reg.register("groq-api", "http://groq:8080")
        svc.last_heartbeat = time.time()
        lb = PhospholipidLoadBalancer(registry=reg)
        b = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        result = _run(b.select_instance("groq"))
        assert result is not None, (
            f"Esperava instância groq, mas select_instance retornou None. healthy={[s.name for s in reg.healthy_services()]}"
        )
        assert "groq" in result.name

    def test_register_provider_instance(self):
        reg = PhospholipidRegistry()
        b = PhospholipidBanditBridge(
            registry=reg, load_balancer=PhospholipidLoadBalancer(registry=reg)
        )
        svc = b.register_provider_instance(
            "groq-api", "http://groq:8080", weight=0.8, capacity=5
        )
        assert svc.name == "groq-api"
        assert svc.weight == 0.8
        assert svc.capacity == 5
        assert reg.service_count() == 1

    def test_auto_report_success(self):
        reg = PhospholipidRegistry()
        reg.register("groq-api", "http://groq:8080", weight=1.0)
        b = PhospholipidBanditBridge(registry=reg)
        b.auto_report("groq/llama3-70b", success=True, latency_ms=150)
        svc = reg.get("groq-api")
        assert svc is not None
        assert svc.latency_p95_ms == 150
        assert svc.consecutive_failures == 0

    def test_auto_report_failure(self):
        reg = PhospholipidRegistry()
        reg.register("groq-api", "http://groq:8080", weight=1.0)
        b = PhospholipidBanditBridge(registry=reg)
        b.auto_report("groq/llama3-70b", success=False, latency_ms=0)
        svc = reg.get("groq-api")
        assert svc is not None
        assert svc.consecutive_failures >= 1
        assert svc.weight < 1.0

    def test_auto_report_only_matching_provider(self):
        reg = PhospholipidRegistry()
        reg.register("groq-api", "http://groq:8080", weight=1.0)
        reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        b = PhospholipidBanditBridge(registry=reg)
        b.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        groq_svc = reg.get("groq-api")
        ollama_svc = reg.get("ollama-api")
        assert groq_svc.weight == 1.0  # untouched
        assert ollama_svc.weight < 1.0  # decayed

    def test_auto_report_no_registered_services(self):
        reg = PhospholipidRegistry()
        b = PhospholipidBanditBridge(registry=reg)
        b.auto_report("groq/llama3-70b", success=False, latency_ms=0)
        assert reg.service_count() == 0

    def test_auto_report_multiple_instances_same_provider(self):
        reg = PhospholipidRegistry()
        svc1 = reg.register("groq-api-1", "http://groq1:8080", weight=1.0)
        svc2 = reg.register("groq-api-2", "http://groq2:8080", weight=1.0)
        b = PhospholipidBanditBridge(registry=reg)
        b.auto_report("groq/llama3-70b", success=False, latency_ms=200)
        assert svc1.weight < 1.0
        assert svc2.weight < 1.0

    def test_report_success(self):
        reg = PhospholipidRegistry()
        svc = reg.register("groq-api", "http://groq:8080", weight=0.5)
        b = PhospholipidBanditBridge(registry=reg)
        b.report_success("groq-api", latency_ms=100)
        assert svc.weight > 0.5

    def test_report_failure(self):
        reg = PhospholipidRegistry()
        svc = reg.register("groq-api", "http://groq:8080", weight=1.0)
        b = PhospholipidBanditBridge(registry=reg)
        b.report_failure("groq-api", RuntimeError("timeout"))
        assert svc.weight < 1.0
        assert svc.consecutive_failures > 0

    def test_report_failure_unknown_instance(self):
        reg = PhospholipidRegistry()
        b = PhospholipidBanditBridge(registry=reg)
        b.report_failure("unknown-service", RuntimeError("fail"))


# ─────────────────────────────────────────────
# PhospholipidSearchBridge
# ─────────────────────────────────────────────


class TestSearchBridge:
    """PhospholipidSearchBridge: auto_report_search e select."""

    def test_register_search_service(self):
        reg = PhospholipidRegistry()
        sb = PhospholipidSearchBridge(
            registry=reg, load_balancer=PhospholipidLoadBalancer(registry=reg)
        )
        svc = sb.register_search_service("search-ddgs", "https://duckduckgo.com")
        assert "search" in svc.name
        assert reg.service_count() == 1

    def test_register_search_service_prefix_added(self):
        reg = PhospholipidRegistry()
        sb = PhospholipidSearchBridge(
            registry=reg, load_balancer=PhospholipidLoadBalancer(registry=reg)
        )
        svc = sb.register_search_service("ddgs", "https://duckduckgo.com")
        assert svc.name.startswith("search-")

    def test_has_search_services(self):
        sb = PhospholipidSearchBridge(registry=PhospholipidRegistry())
        assert sb.has_search_services() is False
        sb.registry.register("search-ddgs", "https://ddg:8080")
        assert sb.has_search_services() is True

    def test_has_search_services_only_search_prefix(self):
        reg = PhospholipidRegistry()
        reg.register("groq-api", "http://groq:8080")
        sb = PhospholipidSearchBridge(registry=reg)
        assert sb.has_search_services() is False

    def test_select_search_returns_none_when_no_services(self):
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        result = _run(sb.select_search())
        assert result is None

    def test_select_search_returns_healthy(self):
        reg = PhospholipidRegistry()
        svc = reg.register("search-ddgs", "https://ddg:8080")
        svc.last_heartbeat = time.time()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        result = _run(sb.select_search())
        assert result is not None
        assert "search" in result.name

    def test_auto_report_search_success(self):
        reg = PhospholipidRegistry()
        reg.register("search-ddgs", "https://ddg:8080", weight=1.0)
        sb = PhospholipidSearchBridge(registry=reg)
        sb.auto_report_search(True)
        svc = reg.get("search-ddgs")
        assert svc.consecutive_failures == 0

    def test_auto_report_search_failure(self):
        reg = PhospholipidRegistry()
        reg.register("search-ddgs", "https://ddg:8080", weight=1.0)
        sb = PhospholipidSearchBridge(registry=reg)
        sb.auto_report_search(False)
        svc = reg.get("search-ddgs")
        assert svc.consecutive_failures >= 1
        assert svc.weight < 1.0

    def test_auto_report_search_no_services(self):
        reg = PhospholipidRegistry()
        sb = PhospholipidSearchBridge(registry=reg)
        sb.auto_report_search(False)
        assert reg.service_count() == 0

    def test_search_with_lb_falls_back_to_ddgs(self):
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        results = _run(sb.search_with_lb("python asyncio", max_results=1))
        assert isinstance(results, list)

    def test_search_and_learn_with_lb_no_services(self):
        sb = PhospholipidSearchBridge(registry=PhospholipidRegistry())
        result = _run(sb.search_and_learn_with_lb("python asyncio", max_results=1))
        assert isinstance(result, bool)


# ─────────────────────────────────────────────
# Hook Integration
# ─────────────────────────────────────────────


class TestBanditPolicyHook:
    """BanditPolicy.generate() reporta ao PhospholipidRegistry automaticamente."""

    def test_bandit_generate_reports_to_registry(self):
        from iaglobal.graphs.bandit import _get_bandit

        bandit = _get_bandit()
        assert hasattr(bandit, "_report_phospholipid")

        from iaglobal.observability.phospholipid_bridge import bridge as _pb

        old_registry = _pb.registry

        reg = PhospholipidRegistry()
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        _pb.registry = reg
        _pb.load_balancer = PhospholipidLoadBalancer(registry=reg)

        _run(bandit._report_phospholipid(False, 1.0, "ollama/qwen2.5:0.5b"))

        assert svc.weight < 1.0, f"weight={svc.weight}"

        _pb.registry = old_registry


class TestSearchAgentHook:
    """SearchAgent.pesquisar_e_aprender() reporta ao registry."""

    def test_search_agent_has_report_hook(self):
        from iaglobal.agents.search_agent import SearchAgent

        agent = SearchAgent()
        import inspect

        source = inspect.getsource(agent.pesquisar_e_aprender)
        assert "auto_report_search" in source
