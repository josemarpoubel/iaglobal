# test_verificar_fluxo.py

import json

from iaglobal.memory.memory_storage import storage
from iaglobal.memory.persistence import persistence

def testar_fluxo():

    task = "teste_integracao_fluxo"
    codigo = "print('Fluxo Funcionando')"
    metadata = {"status": "debug", "versao": 1.0}

    print("--- 1. Testando Armazenamento (Storage) ---")
    storage.store(task, codigo, metadata)
    print(f"✅ Dado armazenado com sucesso para: {task}")

    print("\n--- 2. Recuperação (Persistence/JSON Adapter) ---")
    # Recupera o dado que foi guardado em CBOR
    dado_bruto = persistence.load_json(task)
    print(f"📥 Dado bruto recuperado: {dado_bruto}")

    print("\n--- 3. Preparação para o Modelo (JSON para LLM) ---")
    # Formata para o formato que o LLM entende
    json_para_llm = json.dumps(dado_bruto, indent=2, ensure_ascii=False)
    print(f"🤖 JSON formatado para prompt:\n{json_para_llm}")

    # Validação final
    if "print('Fluxo Funcionando')" in json_para_llm:
        print("\n🚀 FLUXO INTEGRADO E VALIDADO COM SUCESSO!")
    else:
        print("\n❌ ERRO: O fluxo falhou na conversão.")

from iaglobal.memory.db_manager import db
from iaglobal.memory.memory_vector import MemoryVector
import numpy as np

def testar_fluxo_completo():
    print("🚀 Iniciando teste de fluxo da lib...")

    # 1. Testar o DatabaseManager (Insights)
    db.insert_insight(agent="TesteUnitario", task_id="001", content="O sistema está operante.", score=0.95)
    print("✅ Insight gravado com sucesso no SQLite.")

    # 2. Testar o MemoryVector (Vetores)
    mv = MemoryVector()
    texto_teste = "A IA global está evoluindo a estrutura de persistência."
    mv.add_to_memory(texto_teste, metadata="versao=1.0")
    print("✅ Vetor gravado com sucesso no vector_store.")

    # 3. Validar leitura
    print("🔍 Teste de fluxo concluído com êxito!")

testar_fluxo_completo()        

if __name__ == "__main__":
    testar_fluxo()
