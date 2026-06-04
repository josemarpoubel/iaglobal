# test_integracao.py

import sys
import time

from iaglobal.agents.multi_agent import resolver
from iaglobal.core.assistant import processar_assistente
from iaglobal.models.task import Task


def executar_testes():
    print("=" * 60)
    print("🚀 INICIANDO TESTE DE INTEGRAÇÃO - IAGLOBAL (COGNITIVO V2)")
    print("=" * 60)

    # =========================================================
    # 1. TESTE RESOLVER (PIPELINE + CACHE + EXECUTIONGRAPH)
    # =========================================================
    print("\n[1/3] Testando: resolver() - Geração de código...")

    try:
        start = time.time()
        codigo_cpf = resolver("Crie uma função que valide CPF")
        elapsed = time.time() - start

        print("\n🔹 Código Gerado:")
        print(codigo_cpf)
        print(f"\n⏱️ Tempo: {elapsed:.3f}s")

    except Exception as e:
        print(f"❌ Erro no resolver(): {e}")

    # =========================================================
    # 2. TESTE ASSISTENTE (MEMÓRIA + NEURO ORCHESTRATOR)
    # =========================================================
    print("\n" + "=" * 60)
    print("[2/3] Testando: processar_assistente() - Conceitos SOLID...")

    try:
        resposta_solid = processar_assistente("Explique conceitos de SOLID")

        print("\n🔹 Resposta:")
        print(resposta_solid[:500] + "...\n[CORTADO]")

    except Exception as e:
        print(f"❌ Erro no assistente(): {e}")

    # =========================================================
    # 2.1 TESTE DE MEMÓRIA REAL (VALIDAÇÃO COGNITIVA)
    # =========================================================
    print("\n" + "=" * 60)
    print("[2.1] Testando: Memória Cognitiva (L1/L2 + Critic)...")

    try:
        print("📥 Gravando informação na memória...")

        processar_assistente(
            "Grave a seguinte informação: meu codinome é DevDebian01"
        )

        print("\n⏳ Aguardando consolidação de memória (L2 async)...")
        time.sleep(0.5)  # reduzido (não precisa 1s fixo mais)

        print("\n🧠 Consultando memória real...")

        resposta_memoria = processar_assistente(
            "Qual é meu codinome de desenvolvedor?"
        )

        print("\n🔹 Resposta de Memória:")
        print(resposta_memoria)

    except Exception as e:
        print(f"❌ Erro na memória cognitiva: {e}")

    # =========================================================
    # 3. TESTE TASK ESTRUTURADO (GRAPH + EVOLUTION READY)
    # =========================================================
    print("\n" + "=" * 60)
    print("[3/3] Testando: Task() estruturado...")

    try:
        tarefa = Task(
            objective="Criar função de soma",
            constraints=["sem bibliotecas externas"],
            tests=["assert soma(1,2) == 3"]
        )

        start = time.time()
        codigo_soma = resolver(tarefa)
        elapsed = time.time() - start

        print("\n🔹 Código da Task:")
        print(codigo_soma)
        print(f"\n⏱️ Tempo: {elapsed:.3f}s")

    except Exception as e:
        print(f"❌ Erro na Task(): {e}")

    # =========================================================
    # FINAL
    # =========================================================
    print("\n" + "=" * 60)
    print("🏁 FIM DOS TESTES DE INTEGRAÇÃO (COGNITIVO V2)")
    print("=" * 60)


if __name__ == "__main__":
    executar_testes()
