"""
Testes do sistema de scoring: BanditPolicy + ProviderLoadBalancer.

Verifica:
- BanditPolicy: seleção ε-greedy, rank, aprendizado com histórico
- ProviderLoadBalancer: seleção com biases, feedback loop, cooldown
- Integração: ambos os sistemas convergem para o melhor provider
"""

import time
import secrets
from unittest.mock import MagicMock, patch

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.providers.provider_load_balancer import ProviderLoadBalancer
from iaglobal.providers.provider_state import ProviderState


# =========================================================================
# BANDIT POLICY
# =========================================================================

class TestBanditPolicy:

    def test_select_model_returns_candidate(self):
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        candidates = ["ollama/a", "ollama/b"]
        chosen = bandit.select_model("node", "strategy", candidates)
        assert chosen in candidates

    def test_rank_models_orders_by_score(self):
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        pairs = [("p1", "ollama/a"), ("p2", "ollama/b")]

        # p1 tem 100% sucesso, p2 tem 0%
        for _ in range(10):
            credit.record(ExecutionEvent("n", True, 0.5, "ollama/a", "s"))
            credit.record(ExecutionEvent("n", False, 1.0, "ollama/b", "s"))

        ranked = bandit.rank_models("n", "s", pairs)
        assert ranked[0][0] == "p1"
        assert ranked[1][0] == "p2"

    def test_rank_models_empty_candidates(self):
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        assert bandit.rank_models("n", "s", []) == []

    def test_score_starts_neutral(self):
        credit = CreditAssignmentEngine()
        assert credit.score("n", "ollama/x", "s") == 0.5

    def test_score_improves_with_success(self):
        credit = CreditAssignmentEngine()
        for _ in range(5):
            credit.record(ExecutionEvent("n", True, 0.5, "ollama/x", "s"))
        assert credit.score("n", "ollama/x", "s") == 1.0

    def test_score_drops_with_failures(self):
        credit = CreditAssignmentEngine()
        for _ in range(5):
            credit.record(ExecutionEvent("n", False, 1.0, "ollama/x", "s"))
        assert credit.score("n", "ollama/x", "s") == 0.0

    def test_best_model_wins_after_training(self):
        """Após treinamento, o bandit favorece o modelo com maior score."""
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        candidates = ["ollama/bom", "ollama/ruim"]

        for _ in range(20):
            credit.record(ExecutionEvent("n", True, 0.5, "ollama/bom", "s"))
            credit.record(ExecutionEvent("n", False, 2.0, "ollama/ruim", "s"))

        # ε-greedy: 80% greedy, 20% explore → múltiplas tentativas
        choices = {"ollama/bom": 0, "ollama/ruim": 0}
        for _ in range(100):
            c = bandit.select_model("n", "s", candidates)
            choices[c] = choices.get(c, 0) + 1
        assert choices["ollama/bom"] > choices["ollama/ruim"], f"choices={choices}"

    def test_egreedy_explores_sometimes(self):
        """ε-greedy explora 20% das vezes mesmo com modelo dominante."""
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        candidates = ["ollama/bom", "ollama/ruim"]

        for _ in range(20):
            credit.record(ExecutionEvent("n", True, 0.5, "ollama/bom", "s"))
            credit.record(ExecutionEvent("n", False, 2.0, "ollama/ruim", "s"))

        choices = {"ollama/bom": 0, "ollama/ruim": 0}
        for _ in range(500):
            c = bandit.select_model("n", "s", candidates)
            choices[c] = choices.get(c, 0) + 1

        # Deve explorar (escolher "ruim") em ~20% dos casos
        explore_rate = choices["ollama/ruim"] / 500
        # Tolerância: 5% a 35%
        assert 0.05 <= explore_rate <= 0.35, f"explore_rate={explore_rate:.3f}"

    def test_adapts_to_model_degradation(self):
        """Quando um modelo degrada, o score cai e o bandit troca."""
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        candidates = ["ollama/estavel", "ollama/degradou"]

        # Fase 1: estavel é perfeito
        for _ in range(10):
            credit.record(ExecutionEvent("n", True, 0.5, "ollama/estavel", "s"))
            credit.record(ExecutionEvent("n", False, 2.0, "ollama/degradou", "s"))

        score_before = credit.score("n", "ollama/estavel", "s")
        assert score_before > credit.score("n", "ollama/degradou", "s")

        # Fase 2: estavel falha, degradou melhora
        for _ in range(30):
            credit.record(ExecutionEvent("n", False, 3.0, "ollama/estavel", "s"))
            credit.record(ExecutionEvent("n", True, 0.3, "ollama/degradou", "s"))

        score_after = credit.score("n", "ollama/degradou", "s")
        assert score_after > credit.score("n", "ollama/estavel", "s")

    def test_different_strategies_independent(self):
        """Scores de estratégias diferentes não se misturam."""
        credit = CreditAssignmentEngine()
        credit.record(ExecutionEvent("n", True, 0.5, "ollama/x", "coding"))
        credit.record(ExecutionEvent("n", False, 1.0, "ollama/x", "research"))

        coding_score = credit.score("n", "ollama/x", "coding")
        research_score = credit.score("n", "ollama/x", "research")
        assert coding_score != research_score
        assert coding_score == 1.0
        assert research_score == 0.0


# =========================================================================
# PROVIDER LOAD BALANCER
# =========================================================================

class TestProviderLoadBalancer:

    def test_select_returns_provider(self):
        lb = ProviderLoadBalancer()
        chosen = lb.select("general")
        assert chosen in ["ollama", "nvidia", "groq", "openrouter", "opencode"]

    def test_select_respects_availability(self):
        lb = ProviderLoadBalancer()
        # Marca todos como indisponíveis exceto groq
        for p in ["ollama", "nvidia", "openrouter", "opencode"]:
            lb.state.providers[p].cooldown_until = time.time() + 9999
        chosen = lb.select("general")
        assert chosen == "groq"

    def test_select_fallback_to_ollama(self):
        lb = ProviderLoadBalancer()
        for p in lb.state.providers:
            lb.state.providers[p].cooldown_until = time.time() + 9999
        chosen = lb.select("general")
        assert chosen == "ollama"  # fallback padrão

    def test_coding_bias_openrouter(self):
        lb = ProviderLoadBalancer()
        # Zera latência de todos para dar score igual
        for p in lb.state.providers.values():
            p.success = 10
            p.fail = 0
            p.total_latency = 0.0
        lb.state.providers["openrouter"].success = 5  # menor que os outros
        chosen = lb.select("coding")
        # Com bias +0.2 e scores próximos, openrouter deve ganhar
        assert chosen == "openrouter"

    def test_fast_bias_groq(self):
        lb = ProviderLoadBalancer()
        for p in lb.state.providers.values():
            p.success = 10
            p.fail = 0
            p.total_latency = 0.0
        lb.state.providers["groq"].success = 5
        chosen = lb.select("fast")
        assert chosen == "groq"  # bias +0.3 para groq em fast

    def test_reduces_score_on_failure(self):
        lb = ProviderLoadBalancer()
        score_before = lb.state.score("groq")
        lb.report("groq", success=False, latency=5.0)
        score_after = lb.state.score("groq")
        assert score_after < score_before

    def test_cooldown_after_failure(self):
        lb = ProviderLoadBalancer()
        lb.state.providers["groq"].fail = 3
        lb.state.providers["groq"].success = 0
        lb.state.providers["groq"].cooldown_until = time.time() + 5
        assert not lb.state.is_available("groq")

    def test_improves_score_on_success(self):
        lb = ProviderLoadBalancer()
        lb.state.providers["nvidia"].success = 0
        lb.state.providers["nvidia"].fail = 0
        score_before = lb.state.score("nvidia")
        for _ in range(10):
            lb.report("nvidia", success=True, latency=0.3)
        score_after = lb.state.score("nvidia")
        assert score_after > score_before

    def test_high_latency_penalizes(self):
        lb = ProviderLoadBalancer()
        lb.report("nvidia", success=True, latency=10.0)
        slow_score = lb.state.score("nvidia")

        lb2 = ProviderLoadBalancer()
        lb2.report("groq", success=True, latency=0.1)
        fast_score = lb2.state.score("groq")
        assert fast_score > slow_score


# =========================================================================
# INTEGRAÇÃO: BANDIT + LOAD BALANCER
# =========================================================================

class TestBanditLoadBalancerIntegration:

    def test_both_converge_to_best_provider(self):
        """
        Simula execuções e verifica que ambos os sistemas
        convergem para o provider com maior taxa de sucesso.
        """
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        lb = ProviderLoadBalancer()

        # Simula 200 execuções: opencode 90% sucesso, nvidia 70%, groq 50%
        candidates = [
            "opencode/nemotron-3-super-free",
            "nvidia/meta/llama-3.3-70b-instruct",
            "groq/llama-3.1-8b-instant",
        ]

        for _ in range(200):
            chosen = bandit.select_model("pipeline", "coding", candidates)
            provider = chosen.split("/")[0]

            if provider == "opencode":
                success = secrets.randbelow(100) < 90
                latency = 0.3 + secrets.randbelow(50) / 100
            elif provider == "nvidia":
                success = secrets.randbelow(100) < 70
                latency = 0.5 + secrets.randbelow(50) / 100
            else:
                success = secrets.randbelow(100) < 50
                latency = 0.8 + secrets.randbelow(50) / 100

            credit.record(ExecutionEvent(
                node="pipeline", success=success, latency=latency,
                model=chosen, strategy="coding",
            ))
            lb.report(provider, success, latency)

        # Bandit deve rankear opencode primeiro
        pairs = [("opencode", candidates[0]), ("nvidia", candidates[1]), ("groq", candidates[2])]
        ranked = bandit.rank_models("pipeline", "coding", pairs)
        assert ranked[0][0] == "opencode", f"Esperado opencode primeiro, got {ranked[0]}"

        # LoadBalancer deve ter opencode como melhor score
        scores = {p: lb.state.score(p) for p in ["opencode", "nvidia", "groq"]}
        assert scores["opencode"] > scores["nvidia"], f"scores: {scores}"
        assert scores["opencode"] > scores["groq"], f"scores: {scores}"

    def test_feedback_loop_improves_efficiency(self):
        """
        Verifica que o feedback loop faz o bandit convergir
        para o modelo com melhor taxa de sucesso.
        """
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)

        candidates = [
            "opencode/nemotron-3-super-free",
            "nvidia/meta/llama-3.3-70b-instruct",
        ]
        pairs = [("opencode", candidates[0]), ("nvidia", candidates[1])]

        for _ in range(300):
            chosen = bandit.select_model("pipe", "coding", candidates)
            provider = chosen.split("/")[0]
            if provider == "opencode":
                success = secrets.randbelow(100) < 90
            else:
                success = secrets.randbelow(100) < 60
            latency = 0.3 if success else 1.5
            credit.record(ExecutionEvent(
                node="pipe", success=success, latency=latency,
                model=chosen, strategy="coding",
            ))

        ranked = bandit.rank_models("pipe", "coding", pairs)
        assert ranked[0][0] == "opencode", (
            "Esperado opencode 1\u00ba, got %s" % [(p, round(credit.score("pipe", m, "coding"), 3)) for p, m in ranked]
        )

    def test_recovery_after_provider_failure(self):
        """
        Simula um provider que falha, entra em cooldown,
        e verifica que o sistema escolhe outro automaticamente.
        """
        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        lb = ProviderLoadBalancer()

        # Marca opencode como falho
        for _ in range(5):
            lb.report("opencode", False, 5.0)
        lb.state.providers["opencode"].cooldown_until = time.time() + 30

        # Bandit também aprende que opencode falha
        for _ in range(10):
            credit.record(ExecutionEvent("p", False, 5.0, "opencode/nemo", "g"))

        # LoadBalancer não deve escolher opencode
        chosen = lb.select("coding")
        assert chosen != "opencode", "LoadBalancer escolheu provider em cooldown"

        # Bandit pode explorar mas não deve favorecer opencode
        candidates = ["opencode/nemo", "nvidia/meta"]
        choices = {"opencode/nemo": 0, "nvidia/meta": 0}
        for _ in range(200):
            c = bandit.select_model("p", "g", candidates)
            choices[c] = choices.get(c, 0) + 1
        # opencode não deve ser o mais escolhido (score baixo)
        assert choices["opencode/nemo"] < choices["nvidia/meta"], (
            f"Bandit favoreceu opencode falho: {choices}"
        )

    def test_strategies_pick_different_providers(self):
        """
        Estratégias diferentes (coding vs fast vs reasoning)
        devem selecionar providers diferentes graças aos biases.
        """
        lb = ProviderLoadBalancer()
        for p in lb.state.providers.values():
            p.success = 5
            p.fail = 0
            p.total_latency = 0.0

        # Com scores iguais, os biases definem a escolha
        coding_choice = lb.select("coding")
        fast_choice = lb.select("fast")
        reasoning_choice = lb.select("reasoning")

        # Cada bias favorece um provider diferente
        assert coding_choice == "openrouter", f"coding esperado openrouter, got {coding_choice}"
        assert fast_choice == "groq", f"fast esperado groq, got {fast_choice}"
        assert reasoning_choice == "nvidia", f"reasoning esperado nvidia, got {reasoning_choice}"

    def test_full_pipeline_integration(self):
        """
        Teste end-to-end simulando o fluxo real:
        provider_router → bandit → load_balancer → execution → feedback
        """
        from iaglobal.providers.provider_router import CREDIT_CANDIDATES

        credit = CreditAssignmentEngine()
        bandit = BanditPolicy(credit)
        lb = ProviderLoadBalancer()

        candidates = [
            "opencode/nemotron-3-super-free",
            "nvidia/meta/llama-3.3-70b-instruct",
        ]
        pairs = [("opencode", candidates[0]), ("nvidia", candidates[1])]

        for _ in range(200):
            chosen = bandit.select_model("pipe", "general", candidates)
            provider = chosen.split("/")[0]
            if provider == "opencode":
                success = secrets.randbelow(100) < 90
                latency = 0.3 + secrets.randbelow(50) / 100
            else:
                success = secrets.randbelow(100) < 60
                latency = 0.5 + secrets.randbelow(50) / 100

            credit.record(ExecutionEvent(
                node="pipe", success=success, latency=latency,
                model=chosen, strategy="general",
            ))
            lb.report(provider, success, latency)

        # opencode deve liderar o rank do bandit (melhor qualidade)
        ranked = bandit.rank_models("pipe", "general", pairs)
        assert ranked[0][0] == "opencode", (
            "Esperado opencode 1\u00ba, got %s" % [(p, round(credit.score("pipe", m, "general"), 3)) for p, m in ranked]
        )
