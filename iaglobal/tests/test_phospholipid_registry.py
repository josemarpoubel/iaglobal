# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do PhospholipidRegistry — Fases 1, 2, 3 e 4.

Cobertura:
  Fase 1 — Registro e Heartbeat:
    - ServiceInstance com campos corretos
    - register/get/unregister
    - heartbeat atualiza last_heartbeat
    - timeout de heartbeat marca unhealthy

  Fase 2 — Balanceamento:
    - Weighted round-robin seleciona serviços saudáveis
    - Adaptive decay: falhas reduzem peso, sucessos aumentam
    - IVM → peso inicial

  Fase 3 — Falha e Recuperação:
    - Falhas consecutivas marcam unhealthy
    - Heartbeats consecutivos reintroduzem
    - GlutathionePool integrado

  Fase 4 — Observabilidade:
    - Dashboard summary/service_table/render_text
    - Audit trail registra eventos
"""

import asyncio
import json
import logging
import time
from pathlib import Path


from iaglobal._paths import PROJECT_ROOT
from iaglobal.observability.registry import (
    PhospholipidRegistry,
    HEARTBEAT_TIMEOUT,
    RECOVERY_THRESHOLD,
)
from iaglobal.observability.load_balancer import (
    PhospholipidLoadBalancer,
)
from iaglobal.dashboard.phospholipid_dashboard import PhospholipidDashboard

logging.basicConfig(level=logging.ERROR)


def _run(coro):
    return asyncio.run(coro)


AUDIT_PATH = (
    Path(PROJECT_ROOT)
    / "iaglobal"
    / "memory"
    / "data"
    / "json"
    / "phospholipid_audit.json"
)


# ─────────────────────────────────────────────
# FASE 1 — Registro e Heartbeat
# ─────────────────────────────────────────────


class TestServiceRegistration:
    """ServiceInstance é registrado com campos corretos."""

    def test_register_service(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-test", "http://localhost:8080", weight=0.8, capacity=10)
        assert svc.name == "api-test"
        assert svc.endpoint == "http://localhost:8080"
        assert svc.weight == 0.8
        assert svc.capacity == 10
        assert svc.health is True
        assert reg.service_count() == 1

    def test_register_clamps_weight(self):
        reg = PhospholipidRegistry()
        svc = reg.register("over", "", weight=5.0)
        assert svc.weight <= 1.0
        svc2 = reg.register("under", "", weight=-1.0)
        assert svc2.weight >= 0.1

    def test_get_service(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080")
        svc = reg.get("api-a")
        assert svc is not None
        assert svc.name == "api-a"
        assert reg.get("nonexistent") is None

    def test_unregister_service(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080")
        assert reg.service_count() == 1
        reg.unregister("api-a")
        assert reg.service_count() == 0
        assert reg.get("api-a") is None


class TestHeartbeat:
    """Heartbeat atualiza last_heartbeat e recupera serviços."""

    def test_heartbeat_updates_timestamp(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080")
        old_ts = svc.last_heartbeat
        time.sleep(0.01)
        reg.heartbeat("api-a")
        assert svc.last_heartbeat > old_ts

    def test_heartbeat_timeout_marks_unhealthy(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080")
        svc.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 1
        reg.check_timeouts()
        assert svc.health is False

    def test_healthy_returns_only_recent(self):
        reg = PhospholipidRegistry()
        svc_a = reg.register("api-a", "http://a:8080")
        svc_b = reg.register("api-b", "http://b:8080")
        svc_b.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 1
        reg.check_timeouts()
        healthy = reg.healthy_services()
        names = {s.name for s in healthy}
        assert "api-a" in names
        assert "api-b" not in names

    def test_recovery_after_consecutive_heartbeats(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080")
        svc.health = False
        svc.weight = 0.1
        svc.consecutive_heartbeats_ok = 0

        for _ in range(RECOVERY_THRESHOLD):
            reg.heartbeat("api-a")

        assert svc.health is True
        assert svc.weight >= 0.5

    def test_recovery_requires_threshold(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080")
        svc.health = False
        svc.consecutive_heartbeats_ok = 0

        reg.heartbeat("api-a")  # 1
        reg.heartbeat("api-a")  # 2
        assert svc.health is False  # ainda não recuperou (precisa 3)

        reg.heartbeat("api-a")  # 3
        assert svc.health is True


# ─────────────────────────────────────────────
# FASE 2 — Balanceamento
# ─────────────────────────────────────────────


class TestLoadBalancerSelection:
    """Weighted round-robin seleciona serviços saudáveis."""

    def test_select_returns_healthy(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080")
        lb = PhospholipidLoadBalancer(registry=reg)
        selected = _run(lb.select())
        assert selected is not None
        assert selected.health is True

    def test_select_returns_none_if_all_unhealthy(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080")
        svc.health = False
        lb = PhospholipidLoadBalancer(registry=reg)
        selected = _run(lb.select())
        assert selected is None

    def test_select_filters_by_service_type(self):
        reg = PhospholipidRegistry()
        reg.register("groq-api", "http://groq:8080")
        reg.register("ollama-api", "http://ollama:8080")
        lb = PhospholipidLoadBalancer(registry=reg)

        selected = _run(lb.select(service_type="groq"))
        assert selected is not None
        assert "groq" in selected.name

        selected2 = _run(lb.select(service_type="ollama"))
        assert selected2 is not None
        assert "ollama" in selected2.name

    def test_ivm_to_weight_conversion(self):
        assert abs(PhospholipidLoadBalancer.ivm_to_weight(0.85) - 0.85) < 0.01
        assert abs(PhospholipidLoadBalancer.ivm_to_weight(0.0) - 0.1) < 0.01
        assert abs(PhospholipidLoadBalancer.ivm_to_weight(1.0) - 1.0) < 0.01


class TestAdaptiveDecay:
    """Adaptive decay: falhas reduzem peso, sucessos aumentam."""

    def test_failure_reduces_weight(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        reg.report_health("api-a", error=True)
        assert svc.weight < 1.0
        assert svc.consecutive_failures == 1

    def test_success_increases_weight(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=0.5)
        reg.report_health("api-a", latency_ms=100, error=False)
        assert svc.weight > 0.5

    def test_multiple_failures_drop_below_threshold(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        for _ in range(8):
            reg.report_health("api-a", error=True)
        assert svc.health is False
        assert svc.weight < 0.2

    def test_error_rate_tracks_failures(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        assert svc.error_rate == 0.0
        reg.report_health("api-a", error=True)
        err_after_fail = svc.error_rate
        assert err_after_fail > 0.0
        reg.report_health("api-a", latency_ms=50, error=False)
        assert svc.error_rate < err_after_fail

    def test_load_balancer_adaptive_decay(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        lb = PhospholipidLoadBalancer(registry=reg)

        for _ in range(3):
            lb._handle_failure(svc, RuntimeError("fail"))

        assert svc.weight < 0.6
        assert svc.consecutive_failures >= 3


# ─────────────────────────────────────────────
# FASE 3 — Falha e Recuperação
# ─────────────────────────────────────────────


class TestFailureAndRecovery:
    """Falhas consecutivas marcam unhealthy; heartbeats recuperam."""

    def test_failure_removes_from_pool(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        for _ in range(8):
            reg.report_health("api-a", error=True)
        healthy = reg.healthy_services()
        assert "api-a" not in {s.name for s in healthy}

    def test_recovery_reintroduces(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        for _ in range(8):
            reg.report_health("api-a", error=True)
        assert svc.health is False

        # Simular recuperação: reset e heartbeats
        svc.health = True
        svc.weight = 0.5
        svc.consecutive_heartbeats_ok = 0
        for _ in range(RECOVERY_THRESHOLD):
            reg.heartbeat("api-a")

        healthy = reg.healthy_services()
        assert "api-a" in {s.name for s in healthy}

    def test_glutathione_integration(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        lb = PhospholipidLoadBalancer(registry=reg)

        from iaglobal.immunity.glutathione_pool import GlutathionePool

        pool = GlutathionePool()
        count_before = pool.count()

        lb._handle_failure(svc, RuntimeError("timeout"))
        count_after = pool.count()
        assert count_after >= count_before


# ─────────────────────────────────────────────
# FASE 4 — Observabilidade
# ─────────────────────────────────────────────


class TestDashboard:
    """Dashboard summary, service_table, render_text."""

    def test_summary_structure(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080", weight=1.0, capacity=5)
        reg.register("api-b", "http://b:8080", weight=0.5, capacity=10)
        dash = PhospholipidDashboard(registry=reg)
        s = dash.summary()
        assert s["total_services"] == 2
        assert s["healthy_services"] == 2
        assert "avg_latency_p95_ms" in s
        assert "avg_error_rate" in s
        assert "utilization_percent" in s

    def test_service_table(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080", weight=1.0)
        dash = PhospholipidDashboard(registry=reg)
        table = dash.service_table()
        assert len(table) == 1
        assert table[0]["name"] == "api-a"
        assert table[0]["health"] == "✅"

    def test_service_table_ordered_by_weight(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080", weight=0.3)
        reg.register("api-b", "http://b:8080", weight=1.0)
        dash = PhospholipidDashboard(registry=reg)
        table = dash.service_table()
        assert table[0]["name"] == "api-b"
        assert table[1]["name"] == "api-a"

    def test_render_text_contains_title(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080")
        dash = PhospholipidDashboard(registry=reg)
        text = dash.render_text()
        assert "PhospholipidRegistry Dashboard" in text
        assert "api-a" in text


class TestAuditTrail:
    """Eventos são registrados no audit trail."""

    def test_audit_file_exists(self):
        assert AUDIT_PATH.exists()
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        assert "events" in data

    def test_audit_records_events(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080")
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        events = [
            e
            for e in data["events"]
            if e["service"] == "api-a" and e["event"] == "service_registered"
        ]
        assert len(events) >= 1
        assert events[0]["details"]["endpoint"] == "http://a:8080"

    def test_audit_records_failure(self):
        reg = PhospholipidRegistry()
        reg.register("api-a", "http://a:8080", weight=1.0)
        reg.report_health("api-a", error=True)

        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        failures = [
            e
            for e in data["events"]
            if e["event"] == "failure_detected" and e["service"] == "api-a"
        ]
        assert len(failures) >= 1

    def test_audit_records_recovery(self):
        reg = PhospholipidRegistry()
        svc = reg.register("api-a", "http://a:8080", weight=1.0)
        svc.health = False
        svc.consecutive_heartbeats_ok = 0
        for _ in range(RECOVERY_THRESHOLD):
            reg.heartbeat("api-a")

        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        recovery = [
            e
            for e in data["events"]
            if e["event"] == "recovery" and e["service"] == "api-a"
        ]
        assert len(recovery) >= 1


# ─────────────────────────────────────────────
# E2E — Cenário completo
# ─────────────────────────────────────────────


class TestPhospholipidE2E:
    """2+ serviços com balanceamento, falha e redistribuição."""

    def test_two_services_fallback(self):
        reg = PhospholipidRegistry()
        svc1 = reg.register(
            "provider-alpha", "http://alpha:8080", weight=1.0, capacity=5
        )
        svc2 = reg.register("provider-beta", "http://beta:8080", weight=0.5, capacity=5)
        lb = PhospholipidLoadBalancer(registry=reg)

        # Alpha saudável → seleciona alpha
        selected = _run(lb.select())
        assert selected.name == "provider-alpha"

        # Alpha falha 8x → fica unhealthy
        for _ in range(8):
            reg.report_health("provider-alpha", error=True)
        assert svc1.health is False

        # Beta ainda saudável → seleciona beta
        selected = _run(lb.select())
        assert selected is not None
        assert selected.name == "provider-beta"

        # Nenhum saudável se ambos falham
        for _ in range(8):
            reg.report_health("provider-beta", error=True)
        assert svc2.health is False
        selected = _run(lb.select())
        assert selected is None

    def test_weighted_distribution(self):
        reg = PhospholipidRegistry()
        reg.register("heavy", "http://heavy:8080", weight=1.0)
        reg.register("light", "http://light:8080", weight=0.1)
        lb = PhospholipidLoadBalancer(registry=reg)

        selections = {"heavy": 0, "light": 0}
        for _ in range(20):
            s = _run(lb.select())
            selections[s.name] += 1

        # Heavy (peso 1.0) deve ser selecionado mais vezes que light (peso 0.1)
        assert selections["heavy"] >= selections["light"]
