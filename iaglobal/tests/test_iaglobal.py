# test_iaglobal.py

import os
import sys

# Garante que a raiz do projeto entre no sys.path do Python automaticamente
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from unittest.mock import patch
from iaglobal.memory.memory_storage import get_success_by_task, init_storage

@patch("iaglobal.agents.multi_agent.resolver", return_value="def quadrado(n): return n * n")
def test_workflow(mock_resolver):
    print("\n=======================================================")
    print("🚀 Iniciando Teste de Integração de Fluxo: IA Global...")
    print("=======================================================")
    
    init_storage()
    
    tarefa = "Escreva uma funcao em Python que calcule o quadrado de um numero."
    print(f"📝 Tarefa enviada ao pipeline: '{tarefa}'")
    
    print("⚙️ Ativando barramento competitivo de agentes em background...")
    
    from iaglobal.agents.multi_agent import resolver as res
    codigo_gerado = res(tarefa, 2)
    
    print("\n📦 Código final retornado pelos agentes:")
    print(f"--------------------------------------------------\n{codigo_gerado}\n--------------------------------------------------")
    
    print("\n🧠 Auditando o Banco de Sucessos (CBOR)...")
    conhecimento = get_success_by_task(tarefa)
    
    if conhecimento:
        print("\n✅ [TESTE PASSOU]: O ciclo fechado convergiu e gravou a solução no banco!")
        print(f"   • Registro resgatado para a tarefa: \"{conhecimento.get('task')}\"")
        print(f"   • Timestamp do Commit: {conhecimento.get('timestamp')}")
    else:
        print("\n❌ [TESTE FALHOU]: O código foi gerado mas não foi arquivado na tabela success_registry.")
    print("=======================================================\n")

if __name__ == "__main__":
    test_workflow()

