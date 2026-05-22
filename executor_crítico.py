def criticar(resposta, prompt):
    return f"""
Você é um engenheiro de software sênior.
Avalie esta resposta.

PERGUNTA:
{prompt}

RESPOSTA:
{resposta}

1. O que está errado?
2. O que está incompleto?
3. Como deveria ser corrigido?
Responda de forma objetiva.
"""

def processar(prompt):
    modelo = escolher_modelo(prompt)

    resposta = executar(modelo, prompt)

    critica_prompt = criticar(resposta, prompt)
    critica = executar("gemini", critica_prompt)

    # armazenar erro como aprendizado
    store_error(prompt, resposta, critica, None)

    return resposta, critica
