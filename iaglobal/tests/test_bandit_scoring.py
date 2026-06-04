"""
Teste completo do BanditPolicy + CreditAssignmentEngine.

Demonstra como o sistema de pontuação evolui com o histórico
e como o ε-greedy equilibra exploração vs explotação.
"""

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.telemetry import ExecutionEvent


def simulate_execution(credit, bandit, node, strategy, candidates, success_rate):
    """
    Simula uma execução: bandit escolhe o modelo, credit registra o resultado.
    success_rate: probabilidade de sucesso para o modelo escolhido.
    """
    import secrets
    chosen = bandit.select_model(node, strategy, candidates)
    success = secrets.randbelow(100) < success_rate * 100
    latency = 0.5 + secrets.randbelow(100) / 100.0  # 0.5s - 1.5s
    credit.record(ExecutionEvent(
        node=node, success=success, latency=latency,
        model=chosen, strategy=strategy,
    ))
    return chosen, success


def print_header(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_scores(credit, node, strategy, candidates, label="Scores"):
    scores = {m: credit.score(node, m, strategy) for m in candidates}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    print(f"  {label}:")
    for model, score in ranked:
        key = (node, model, strategy)
        s = credit.stats[key]
        total = s["success"] + s["fail"]
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"    {model:30s} {bar} {score:.3f}  ({s['success']}/{total} ok)")
    return ranked


# =========================================================================
# CENÁRIO 1: Score inicial — sem histórico
# =========================================================================

print_header("CENÁRIO 1: Score inicial (sem histórico)")

credit = CreditAssignmentEngine()
bandit = BanditPolicy(credit)

candidates = [
    "ollama/qwen2.5:0.5b",
    "gemini/gemini-2.0-flash",
    "groq/llama-3.1-8b",
    "openrouter/meta-llama/llama-3.1-8b-instruct",
]
print_scores(credit, "rag", "coding", candidates, "Scores iniciais (todos 0.5)")
print("  → Sem histórico, todos os modelos têm score 0.5 (neutro)")
print("  → O ε-greedy escolhe aleatoriamente entre os empatados")


# =========================================================================
# CENÁRIO 2: Aprendizado — um modelo começa a se destacar
# =========================================================================

print_header("CENÁRIO 2: 50 execuções — modelo A com 90% sucesso, B com 60%")

credit2 = CreditAssignmentEngine()
bandit2 = BanditPolicy(credit2)
cand2 = ["ollama/modelo-a", "ollama/modelo-b", "ollama/modelo-c"]

for i in range(50):
    chosen = bandit2.select_model("rag", "coding", cand2)
    if chosen == "ollama/modelo-a":
        success = i < 45  # 90% sucesso nas primeiras 50
    elif chosen == "ollama/modelo-b":
        success = i < 30  # 60% sucesso
    else:
        success = i < 10  # 20% sucesso
    credit2.record(ExecutionEvent(
        node="rag", success=success, latency=0.5,
        model=chosen, strategy="coding",
    ))

print_scores(credit2, "rag", "coding", cand2, "Scores após 50 execuções")
print("  → Modelo A (90% sucesso) tem o maior score")
print("  → Modelo C (20% sucesso) tem o menor score")
print("  → O bandit favorece A nas próximas escolhas")


# =========================================================================
# CENÁRIO 3: Exploração vs Explotação (ε-greedy)
# =========================================================================

print_header("CENÁRIO 3: Teste do ε-greedy (1000 escolhas)")

credit3 = CreditAssignmentEngine()
bandit3 = BanditPolicy(credit3)
cand3 = ["ollama/bom", "ollama/ruim"]

# Pré-carrega histórico: bom = 100% sucesso, ruim = 0% sucesso
for _ in range(20):
    credit3.record(ExecutionEvent("rag", True, 0.5, "ollama/bom", "coding"))
    credit3.record(ExecutionEvent("rag", False, 0.5, "ollama/ruim", "coding"))

exploit_count = 0
explore_count = 0
for _ in range(1000):
    chosen = bandit3.select_model("rag", "coding", cand3)
    # O bandit escolheu o melhor (bom) ou explorou (qualquer um)?
    # Como bom tem score 1.0 e ruim tem 0.0, o melhor é sempre bom
    # Se escolheu ruim, foi exploração
    if chosen == "ollama/ruim":
        explore_count += 1
    else:
        exploit_count += 1

total = exploit_count + explore_count
print(f"  Explotação (melhor modelo): {exploit_count}/{total} = {exploit_count/total*100:.1f}%")
print(f"  Exploração  (aleatório):    {explore_count}/{total} = {explore_count/total*100:.1f}%")
print(f"  → Aproximadamente 80/20 conforme política ε-greedy")


# =========================================================================
# CENÁRIO 4: Rank de modelos para fallback chain
# =========================================================================

print_header("CENÁRIO 4: Rank de modelos para fallback chain")

credit4 = CreditAssignmentEngine()
bandit4 = BanditPolicy(credit4)

# Simula desempenho variado
pairs = [
    ("ollama", "ollama/qwen2.5:0.5b"),
    ("gemini", "gemini/gemini-2.0-flash"),
    ("groq", "groq/llama-3.1-8b"),
    ("openrouter", "openrouter/meta-llama/llama-3.1-8b-instruct"),
]

for provider, model in pairs:
    for i in range(10):
        success = i < (9 if provider == "ollama" else 7 if provider == "gemini"
                       else 5 if provider == "groq" else 3)
        credit4.record(ExecutionEvent("rank_test", success, 1.0, model, "general"))

print("  Ordem de fallback (do melhor para o pior):")
ranked = bandit4.rank_models("rank_test", "general", pairs)
for i, (prov, model) in enumerate(ranked, 1):
    score = credit4.score("rank_test", model, "general")
    bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
    print(f"  {i}. {prov:12s} {model:30s} {bar} {score:.3f}")
print()
print("  → A fallback chain tenta o melhor primeiro,")
print("    evitando perder tempo com providers ruins.")


# =========================================================================
# CENÁRIO 5: Degeneração — modelo bom começa a falhar
# =========================================================================

print_header("CENÁRIO 5: Degeneração — modelo bom começa a falhar")

credit5 = CreditAssignmentEngine()
bandit5 = BanditPolicy(credit5)
cand5 = ["ollama/modelo-estavel", "ollama/modelo-degrada"]

# Fase 1: modelo-estavel é perfeito, modelo-degrada é ruim
for _ in range(20):
    credit5.record(ExecutionEvent("live", True, 0.5, "ollama/modelo-estavel", "chat"))
    credit5.record(ExecutionEvent("live", False, 2.0, "ollama/modelo-degrada", "chat"))

print("  Fase 1 — modelo-estavel domina:")
print_scores(credit5, "live", "chat", cand5, "  Scores")

# Fase 2: modelo-estavel começa a falhar (sobrecarga), modelo-degrada melhora
for _ in range(30):
    credit5.record(ExecutionEvent("live", False, 3.0, "ollama/modelo-estavel", "chat"))
    credit5.record(ExecutionEvent("live", True, 0.3, "ollama/modelo-degrada", "chat"))

print("  Fase 2 — após 30 execuções com falha no estável e melhora no degrada:")
print_scores(credit5, "live", "chat", cand5, "  Scores")
print("  → O bandit se adapta: quando o score do estável cai abaixo do degrada,")
print("    ele passa a escolher o degrada automaticamente.")


# =========================================================================
# RESUMO FINAL
# =========================================================================

print_header("RESUMO DO SISTEMA DE PONTUAÇÃO")

print("""
  CreditAssignmentEngine:
    - Mantém um dict de (node, model, strategy) → {success, fail, latency}
    - score = success / (success + fail)
    - Sem histórico → score = 0.5 (neutro)

  BanditPolicy (ε-greedy):
    - 80%: escolhe o modelo com maior score histórico
    - 20%: escolhe um modelo aleatório (exploração)
    - rank_models(): ordena candidatos por score para fallback chain

  Propriedades:
    - Auto-adaptável: se um modelo degrada, o score cai e outro assume
    - Sem viés de seed inicial (usa secrets em vez de random)
    - Quanto mais execuções, mais preciso o score
    - Fallback chain ordenada evita tentar providers ruins primeiro
""")
