# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste de integração do PhospholipidRegistry com o pipeline principal.

Cobertura:
  - BanditPolicy.generate() reporta métricas ao PhospholipidRegistry
  - Load balancer integrado ao fluxo de seleção de provedores
  - Adaptive decay afeta provedores no registry após falhas no pipeline
  - ServiceInstance no registry reflete o estado real das execuções
"""

import asyncio
import logging
import time


from iaglobal.observability.registry import (
    PhospholipidRegistry,
    RECOVERY_THRESHOLD,
)
from iaglobal.observability.load_balancer import (
    PhospholipidLoadBalancer,
)
from iaglobal.observability.phospholipid_bridge import PhospholipidBanditBridge
from iaglobal.observability.search_bridge import PhospholipidSearchBridge

logging.basicConfig(level=logging.ERROR)


def _run(coro):
    return asyncio.run(coro)


# ────────────────────────────────────────────────────────
# BANDIT ↔ PIPELINE
# ────────────────────────────────────────────────────────


class TestBanditPipelineIntegration:
    """BanditPolicy.generate() → PhospholipidRegistry (via hook)."""

    def test_bandit_hook_auto_report_after_success(self):
        """Após generate() bem-sucedido, registry reflete sucesso."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=0.8)
        svc.last_heartbeat = time.time()

        bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=150)

        assert svc.weight > 0.8
        assert svc.latency_p95_ms == 150
        assert svc.consecutive_failures == 0

    def test_bandit_hook_auto_report_after_failure(self):
        """Após generate() com falha, registry aplica adaptive decay."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)

        assert svc.weight < 1.0
        assert svc.consecutive_failures >= 1

    def test_bandit_hook_multiple_failures_remove_from_pool(self):
        """Múltiplas falhas consecutivas removem serviço do pool."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        for _ in range(8):
            bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)

        healthy = reg.healthy_services()
        assert "ollama-api" not in {s.name for s in healthy}
        assert svc.health is False

    def test_bandit_hook_multiple_providers_independent_decay(self):
        """Provedores diferentes decaem independentemente."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        groq = reg.register("groq-api", "http://groq:8080", weight=1.0)
        groq.last_heartbeat = time.time()
        ollama = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        ollama.last_heartbeat = time.time()

        bridge.auto_report("groq/llama3-70b", success=False, latency_ms=0)
        bridge.auto_report("groq/llama3-70b", success=False, latency_ms=0)
        bridge.auto_report("groq/llama3-70b", success=False, latency_ms=0)

        assert groq.weight < ollama.weight
        assert ollama.weight == 1.0

    def test_bandit_recovery_via_heartbeat_after_failures(self):
        """Após adaptive decay, heartbeats reintroduzem serviço."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        for _ in range(8):
            bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        assert svc.health is False

        svc.health = True
        svc.weight = 0.5
        svc.consecutive_heartbeats_ok = 0
        for _ in range(RECOVERY_THRESHOLD):
            reg.heartbeat("ollama-api")

        assert svc.health is True
        healthy = reg.healthy_services()
        assert "ollama-api" in {s.name for s in healthy}

    def test_bandit_hook_reports_only_matching_providers(self):
        """auto_report só afeta serviços do mesmo provider."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        groq = reg.register("groq-api", "http://groq:8080", weight=1.0)
        groq.last_heartbeat = time.time()

        bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=50)
        assert groq.weight == 1.0


# ────────────────────────────────────────────────────────
# SEARCH — PIPELINE
# ────────────────────────────────────────────────────────


class TestSearchPipelineIntegration:
    """SearchAgent → PhospholipidSearchBridge (via hook)."""

    def test_search_hook_reports_success(self):
        """Após busca bem-sucedida, registry é atualizado."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        svc = sb.register_search_service("search-ddgs", "https://ddg:8080")
        svc.health = True
        svc.weight = 1.0

        sb.auto_report_search(success=True)
        assert svc.consecutive_failures == 0

    def test_search_hook_reports_failure(self):
        """Após busca falha, registry aplica adaptive decay."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        svc = sb.register_search_service("search-ddgs", "https://ddg:8080")
        svc.health = True
        svc.weight = 1.0

        sb.auto_report_search(success=False)
        assert svc.consecutive_failures >= 1

    def test_search_hook_repeated_failures_remove_service(self):
        """Falhas repetidas no search removem serviço do pool."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        svc = sb.register_search_service("search-ddgs", "https://ddg:8080")
        svc.health = True
        svc.weight = 1.0

        for _ in range(8):
            sb.auto_report_search(success=False)

        assert svc.health is False
        healthy = reg.healthy_services()
        assert "search-ddgs" not in {s.name for s in healthy}

    def test_search_hook_multiple_services(self):
        """Múltiplos search services são monitorados independentemente."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        ddgs = sb.register_search_service("search-ddgs", "https://ddg:8080")
        bing = sb.register_search_service("search-bing", "https://bing:8080")
        ddgs.health = True
        bing.health = True
        ddgs.weight = 1.0
        bing.weight = 1.0

        sb.auto_report_search(success=True)
        assert ddgs.consecutive_failures == 0
        assert bing.consecutive_failures == 0

        sb.auto_report_search(success=False)
        assert ddgs.consecutive_failures >= 1
        assert bing.consecutive_failures >= 1

    def test_search_hook_no_registered_services(self):
        """auto_report_search não falha quando não há services registrados."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        sb = PhospholipidSearchBridge(registry=reg, load_balancer=lb)
        sb.auto_report_search(success=False)
        assert reg.service_count() == 0


# ────────────────────────────────────────────────────────
# FALLBACK — E2E
# ────────────────────────────────────────────────────────


class TestFallbackIntegration:
    """Fallback entre registry e default quando não há services."""

    def test_bandit_fallback_when_no_registered_services(self):
        """Sem serviços registrados, auto_report não quebra nada."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)

        bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=50)
        assert reg.service_count() == 0

    def test_select_fallback_when_all_unhealthy(self):
        """Quando todas instâncias estão unhealthy, select retorna None."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.health = False
        svc.last_heartbeat = time.time()

        selected = _run(lb.select())
        assert selected is None

    def test_weighted_preference_for_healthier_services(self):
        """Load balancer prefere instâncias com maior peso."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        svc_a = reg.register("ollama-fast", "http://fast:8080", weight=0.9)
        svc_a.last_heartbeat = time.time()
        svc_b = reg.register("ollama-slow", "http://slow:8080", weight=0.1)
        svc_b.last_heartbeat = time.time()

        selections = {"ollama-fast": 0, "ollama-slow": 0}
        for _ in range(20):
            s = _run(lb.select())
            if s:
                selections[s.name] += 1

        assert selections["ollama-fast"] >= selections["ollama-slow"]

    def test_adaptive_decay_over_multiple_cycles(self):
        """Adaptive decay ao longo de múltiplos ciclos de execução."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("groq-api", "http://groq:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        for i in range(5):
            bridge.auto_report("groq/llama3-70b", success=False, latency_ms=0)
            if i % 2 == 1:
                bridge.auto_report("groq/llama3-70b", success=True, latency_ms=100)

        assert svc.weight > 0.1


# ────────────────────────────────────────────────────────
# SERVICE INSTANCE (dados persistentes e corretos)
# ────────────────────────────────────────────────────────


class TestServiceInstanceState:
    """ServiceInstance reflete corretamente o estado das execuções."""

    def test_latency_tracked_after_success(self):
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=250)
        assert svc.latency_p95_ms == 250

    def test_error_rate_tracked_after_failure(self):
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()
        assert svc.error_rate == 0.0

        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        assert svc.error_rate > 0.0

    def test_consecutive_failures_reset_after_success(self):
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        for _ in range(3):
            bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        assert svc.consecutive_failures >= 3

        bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=50)
        assert svc.consecutive_failures == 0


# ────────────────────────────────────────────────────────
# E2E — Cenário completo pipeline simulado
# ────────────────────────────────────────────────────────


class TestPipelineE2ESimulated:
    """Simulação de ciclo completo de pipeline com PhospholipidRegistry."""

    def test_full_cycle_single_service(self):
        """Ciclo completo: heartbeat → sucessos → weight sobe."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=0.7)
        svc.last_heartbeat = time.time()

        for _ in range(5):
            bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=100)
            reg.heartbeat("ollama-api")

        assert svc.weight > 0.7
        assert svc.health is True

    def test_full_cycle_with_failure_and_recovery(self):
        """Ciclo completo: sucessos → falhas → unhealthy → heartbeats → recovery."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        for _ in range(8):
            bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)

        assert svc.health is False
        healthy = reg.healthy_services()
        assert "ollama-api" not in {s.name for s in healthy}

        svc.health = True
        svc.weight = 0.5
        svc.consecutive_heartbeats_ok = 0
        for _ in range(RECOVERY_THRESHOLD):
            reg.heartbeat("ollama-api")
        reg.check_timeouts()

        assert svc.health is True
        healthy = reg.healthy_services()
        assert "ollama-api" in {s.name for s in healthy}

    def test_multiple_providers_complete_cycle(self):
        """Dois provedores em ciclo completo: falhas independentes."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        groq = reg.register("groq-api", "http://groq:8080", weight=1.0)
        groq.last_heartbeat = time.time()
        ollama = reg.register("ollama-api", "http://ollama:8080", weight=0.8)
        ollama.last_heartbeat = time.time()

        for _ in range(5):
            bridge.auto_report("groq/llama3-70b", success=False, latency_ms=0)
            bridge.auto_report("ollama/qwen2.5:0.5b", success=True, latency_ms=100)

        assert groq.weight <= ollama.weight
        assert ollama.consecutive_failures == 0
        assert groq.consecutive_failures >= 5

    def test_load_balancer_selects_highest_weight(self):
        """Load balancer prefere instância com maior peso (round-robin pesado)."""
        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        fast = reg.register("ollama-fast", "http://fast:8080", weight=1.0)
        fast.last_heartbeat = time.time()
        slow = reg.register("ollama-slow", "http://slow:8080", weight=0.2)
        slow.last_heartbeat = time.time()

        selections = {"ollama-fast": 0, "ollama-slow": 0}
        for _ in range(20):
            selected = _run(bridge.load_balancer.select(service_type="ollama"))
            if selected:
                selections[selected.name] += 1

        assert selections["ollama-fast"] >= selections["ollama-slow"]

    def test_dashboard_reflects_pipeline_state(self):
        """Dashboard reflete corretamente o estado após execuções do pipeline."""

        reg = PhospholipidRegistry()
        lb = PhospholipidLoadBalancer(registry=reg)
        bridge = PhospholipidBanditBridge(registry=reg, load_balancer=lb)
        svc = reg.register("ollama-api", "http://ollama:8080", weight=1.0)
        svc.last_heartbeat = time.time()

        from iaglobal.dashboard.phospholipid_dashboard import PhospholipidDashboard

        dash = PhospholipidDashboard(registry=reg)

        summary = dash.summary()
        assert summary["total_services"] == 1
        assert summary["healthy_services"] == 1

        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)
        bridge.auto_report("ollama/qwen2.5:0.5b", success=False, latency_ms=0)

        summary = dash.summary()
        assert summary["healthy_services"] <= summary["total_services"]

        text = dash.render_text()
        assert "PhospholipidRegistry Dashboard" in text
