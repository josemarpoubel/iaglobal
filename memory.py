# memory.py

import os

PASTA = os.path.expanduser("~/.ia-global")
ARQ = os.path.join(PASTA, "evolucao_cerebral.md")

def carregar():
    if not os.path.exists(ARQ):
        return "memória vazia"

    with open(ARQ, "r", encoding="utf-8") as f:
        return f.read()[-20000:]  # corte simples

def salvar(texto):
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQ, "a", encoding="utf-8") as f:
        f.write(texto + "\n\n---\n\n")
