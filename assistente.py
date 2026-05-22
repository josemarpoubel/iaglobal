# assistente.py

import sys
from brain import escolher_modelo
from executor import executar
from memory import salvar, carregar
from memory_vector import store, search


def main():
    if len(sys.argv) < 2:
        print("uso: ia 'mensagem'")
        return

    prompt = sys.argv[1]

    print("\n🧠 Buscando memória semântica...\n")
    memoria_semantica = search(prompt)

    contexto_extra = ""
    if memoria_semantica:
        contexto_extra = "\n🧠 MEMÓRIA RELEVANTE:\n"
        for score, item in memoria_semantica:
            contexto_extra += f"- {item['text']} (score={score:.2f})\n"

    modelo = escolher_modelo(prompt)
    print(f"\n🧠 modelo escolhido: {modelo}\n")

    memoria = carregar()

    prompt_final = f"""
{memoria}

{contexto_extra}

USER: {prompt}
"""

    resposta = executar(modelo, prompt_final)

    print("\n" + "=" * 60)
    print(resposta)
    print("=" * 60)

    salvar(f"USER: {prompt}\nAI: {resposta}")

    # 🔥 agora sim: depois da resposta
    store(f"USER: {prompt}\nAI: {resposta}")

from brain import escolher_modelo
from executor import executar
from memory_vector import search, store
from reflexion_engine import reflexion_loop


def main(prompt):

    modelo = escolher_modelo(prompt)

    # 🧠 memória semântica
    mem = search(prompt)

    contexto = "\n".join([m[1] for m in mem])

    enriched_prompt = f"""
MEMÓRIA RELEVANTE:
{contexto}

PERGUNTA:
{prompt}
"""

    # 🧠 reflexão
    resposta = reflexion_loop(modelo, enriched_prompt)

    # 🧠 salvar aprendizado
    store(f"Q: {prompt}\nA: {resposta}", "episode")

    print(resposta)

if __name__ == "__main__":
    main()
