"""
Teste: PolicyRegistry + BanditPolicy — evolução por domínio.

Demonstra como cada domínio aprende independentemente,
como o score se adapta a mudanças de desempenho,
e como compute_node_policy reage aos scores.
"""

from iaglobal.graphs.policy import PolicyRegistry
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.graphs.credit import CreditAssignmentEngine


def simulate(credit, node, model, strategy, success, latency=0.5):
    credit.record(ExecutionEvent(node, success, latency, model, strategy))


def bar(score):
    n = int(score * 20)
    return "█" * n + "░" * (20 - n)


def test_policy_evolution(capsys):
    registry = PolicyRegistry()

    dominios = {
        "chat": {"ollama/gemma2": 0.9, "groq/llama-3.1": 0.7, "openrouter/claude": 0.6},
        "coding": {"ollama/gemma2": 0.4, "groq/llama-3.1": 0.8, "openrouter/claude": 0.95},
        "rag": {"ollama/gemma2": 0.5, "groq/llama-3.1": 0.6, "openrouter/claude": 0.85},
    }

    for dominio, modelos in dominios.items():
        policy = registry.get(dominio)
        models = list(modelos.keys())
        for _ in range(100):
            chosen = policy.select_model(dominio, dominio, models)
            rate = modelos[chosen]
            success = hash(str(_) + chosen) % 100 < rate * 100
            simulate(policy.credit, dominio, chosen, dominio, success, 0.3 + (1 - rate) * 2)

    print()
    print(f"{'Domínio':12s} {'Modelo':30s} {'Score':8s} {'Uso':6s}")
    print("-" * 56)
    for dominio, modelos in dominios.items():
        policy = registry.get(dominio)
        cand = list(modelos.keys())
        for model in cand:
            s = policy.credit.score(dominio, model, dominio)
            key = (dominio, model, dominio)
            total = policy.credit.stats[key]["success"] + policy.credit.stats[key]["fail"]
            print(f"{dominio:12s} {model:30s} {bar(s)} {s:.3f}  ({total}x)")
        print()

    candidates_all = list({m for mm in dominios.values() for m in mm})
    print("  Ranking por domínio (fallback chain):")
    for dominio in dominios:
        policy = registry.get(dominio)
        pairs = [(m.split("/")[0], m) for m in candidates_all]
        ranked = policy.rank_models(dominio, dominio, pairs)
        print(f"  {dominio}:")
        for i, (prov, model) in enumerate(ranked[:5], 1):
            s = policy.credit.score(dominio, model, dominio)
            print(f"    {i}. {model:30s} {bar(s)} {s:.3f}")
        print()

    print("  compute_node_policy reage aos scores:")
    for dominio in dominios:
        policy = registry.get(dominio)
        for model in list(dominios[dominio].keys()):
            score = policy.credit.score(dominio, model, dominio)
            node = type("node", (), {
                "success_rate": lambda self, s=score: s,
                "avg_latency": lambda self: 1.0,
                "model_hint": model,
            })()
            decision = PolicyRegistry.compute_node_policy(node)
            if decision:
                print(f"  {dominio:10s} {model:25s} score={score:.2f} → {decision}")
    print()

    print("  Degeneração simulada — modelo líder começa a falhar:")
    deg_domain = "degradacao"
    deg_models = ["ollama/modelo-bom", "ollama/modelo-ruim"]
    deg_policy = registry.get(deg_domain)
    for _ in range(30):
        for m in deg_models:
            success = hash("good" + str(_)) % 100 < 90
            simulate(deg_policy.credit, deg_domain, m, deg_domain, success, 0.5)

    print(f"    Antes da degradação:")
    for m in deg_models:
        s = deg_policy.credit.score(deg_domain, m, deg_domain)
        print(f"      {m:30s} {bar(s)} {s:.3f}")

    for _ in range(50):
        simulate(deg_policy.credit, deg_domain, deg_models[0], deg_domain, False, 3.0)
        simulate(deg_policy.credit, deg_domain, deg_models[1], deg_domain, True, 0.2)

    print(f"    Após 50 execuções com falha no bom e melhora no ruim:")
    for m in deg_models:
        s = deg_policy.credit.score(deg_domain, m, deg_domain)
        print(f"      {m:30s} {bar(s)} {s:.3f}")
    print(f"    → O bandit troca automaticamente para o modelo que agora performa melhor")
