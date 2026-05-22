# reflexion_engine.py

def generate(model, prompt):
    return executar(model, prompt)


def reflect(model, prompt, draft):
    critic_prompt = f"""
Você é um engenheiro sênior crítico.

Pergunta:
{prompt}

Resposta inicial:
{draft}

1. O que está errado?
2. O que pode melhorar?
3. Reescreva a resposta melhorada.
"""
    return executar(model, critic_prompt)


def reflexion_loop(model, prompt):
    draft = generate(model, prompt)

    improved = reflect(model, prompt, draft)

    return improved
