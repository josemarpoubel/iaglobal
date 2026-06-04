import ollama
import time
import sys

def executar_agente(modelo, prompt, sistema_prompt, max_tokens=250, temp=0.2):
    inicio = time.time()
    try:
        resposta = ollama.chat(
            model=modelo,
            messages=[
                {"role": "system", "content": sistema_prompt},
                {"role": "user", "content": prompt}
            ],
            options={
                "temperature": temp,
                "num_predict": max_tokens
            }
        )
        tempo_gasto = time.time() - inicio
        return resposta['message']['content'].strip(), tempo_gasto
    except Exception as e:
        print(f"\n❌ Erro no modelo {modelo}: {e}")
        sys.exit(1)

def main():
    print("================================================================")
    print("🔄 PIPELINE INVERTIDO v3.0 - PROJETO IAGLOBAL")
    print("================================================================\n")

    # ----------------------------------------------------------------
    # FASE 1: O CRIADOR (Qwen2.5) - Cria o alerta em Português
    # ----------------------------------------------------------------
    sys_criador = (
        "Você é um monitor de infraestrutura focado em clareza. "
        "Gere um alerta curto relatando uma falha técnica de exemplo."
    )
    prompt_criador = (
        "Escreva um alerta de erro simulando que o disco do servidor Debian "
        "atingiu 99% de uso. Inclua o caminho do diretório principal '/'."
    )
    
    print("✍️  [Fase 1] Invocando Criador (qwen2.5:0.5b)...")
    alerta_pt, tempo_criador = executar_agente(
        modelo="qwen2.5:0.5b", 
        prompt=prompt_criador, 
        sistema_prompt=sys_criador,
        max_tokens=150
    )
    
    print(f"⏱️  Criador finalizou em {tempo_criador:.2f}s.")
    print("-" * 50)
    print("📋 ALERTA GERADO EM PORTUGUÊS:")
    print(alerta_pt)
    print("-" * 50 + "\n")

    # ----------------------------------------------------------------
    # FASE 2: O ANALISADOR (TinyLlama) - Extrai a solução técnica (Inglês)
    # ----------------------------------------------------------------
    sys_analisador = (
        "You are a DevOps automation agent. Your job is to read an alert "
        "and provide the exact Linux commands to inspect and clean space."
    )
    
    prompt_analisador = f"""
    Read this system alert:
    "{alerta_pt}"
    
    Provide a bulleted list with:
    - 1 command to check disk space (df).
    - 1 command to find large files in '/'.
    Keep descriptions short and in English.
    """
    
    print("🧐 [Fase 2] Invocando Analisador (tinyllama:latest)...")
    analise_tecnica, tempo_analisador = executar_agente(
        modelo="tinyllama:latest", 
        prompt=prompt_analisador, 
        sistema_prompt=sys_analisador,
        max_tokens=200,
        temp=0.1  # Temperatura baixa para o TinyLlama não inventar texto
    )
    
    print(f"⏱️  Analisador finalizou em {tempo_analisador:.2f}s.")
    
    # ----------------------------------------------------------------
    # PRODUTO FINAL COMBINADO
    # ----------------------------------------------------------------
    print("\n======================= DIAGNÓSTICO COMBINADO =======================")
    print(f"🚨 NOTIFICAÇÃO ORIGINAL:\n{alerta_pt}\n")
    print(f"🛠️  TECHNICAL ACTIONS REQUIRED:\n{analise_tecnica}")
    print("======================================================================")
    print(f"⏱️  Tempo total: {tempo_criador + tempo_analisador:.2f}s")

if __name__ == "__main__":
    main()

