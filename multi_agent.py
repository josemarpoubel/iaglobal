from brain import escolher_modelo
from executor import executar
from sandbox import executar_codigo
import itertools

AGENTES = {
    "dev_fast": {
        "temperature": 0.2,
        "style": "direto, minimalista"
    },
    "dev_safe": {
        "temperature": 0.5,
        "style": "robusto, com validações"
    },
    "dev_exploratory": {
        "temperature": 0.9,
        "style": "criativo, diferente"
    }
}

def gerar_solucoes(task):
    solucoes = {}

    for nome, cfg in AGENTES.items():

        prompt = f"""
Você é um engenheiro Python {cfg['style']}.

Resolva o problema abaixo.

PROBLEMA:
{task}

Retorne APENAS código executável.
"""

        modelo = escolher_modelo(task)

        resposta = executar(modelo, prompt)

        solucoes[nome] = resposta

    return solucoes

def testar_solucoes(solucoes):

    resultados = []

    for nome, codigo in solucoes.items():

        status, out, err = executar_codigo(codigo)

        score = 0

        if status == 0:
            score += 100

        score -= len(err) * 0.1

        resultados.append((score, nome, codigo, err))

    resultados.sort(reverse=True, key=lambda x: x[0])

    return resultados

def debuggar(codigo, erro, task):

    prompt = f"""
Você é um engenheiro sênior especialista em debugging Python.

Tarefa:
{task}

Código com erro:
{codigo}

Erro:
{erro}

Corrija o código e devolva APENAS a versão corrigida.
"""

    modelo = escolher_modelo(task)

    return executar(modelo, prompt)

def resolver(task, max_iters=3):

    solucoes = gerar_solucoes(task)

    for i in range(max_iters):

        ranking = testar_solucoes(solucoes)

        melhor_score, nome, codigo, erro = ranking[0]

        if melhor_score >= 100:
            return codigo

        # 🧠 debug da melhor tentativa
        codigo_corrigido = debuggar(codigo, erro, task)

        solucoes[nome] = codigo_corrigido

    return ranking[0][2]
