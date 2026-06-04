import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ..memory.memory_storage import init_storage, store_success, get_success_by_task

# 1. Inicializa o banco
init_storage()

# 2. Simula um sucesso de tarefa
tarefa = "Criar um servidor HTTP básico em Flask"
codigo = "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef hello():\n    return 'Hello World'"

# 3. Grava no banco
print("Gravando sucesso no banco...")
store_success(tarefa, codigo)

# 4. Tenta recuperar
print("Recuperando conhecimento...")
resultado = get_success_by_task(tarefa)

if resultado and resultado["codigo"] == codigo:
    print("✅ SUCESSO: O cérebro está operacional e recuperou o dado corretamente!")
else:
    print("❌ ERRO: Falha na comunicação com o banco.")