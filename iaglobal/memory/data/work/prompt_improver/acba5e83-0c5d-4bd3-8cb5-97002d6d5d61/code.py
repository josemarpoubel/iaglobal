Aqui está um exemplo básica de como implementarse uma API REST simple em Python com a biblioteca `fastapi` e o módulo `dicionarios` do Django (pode ser usado qualquer outra API já desenvolvida ou algo new). Perguntas para adicionar mais funções, como ver a lista todas as tarefas, deletar um título específico da lista, etc. E para obter informações sobre memória em Dicionários, adicione:

```python
from fastapi import FastAPI

app = FastAPI()

todo_store: Dict[str, Set[Tarefa]] = {}

@app.get("/tarefas/")
async def get_tarefas():
    return todo_store.copy()

@app.post("/tarefas/")
async def criar_tarefa(tarefa: Tarefa):
    to_do_set = set()
    todo_store[tarefa.título] |= to_do_set
    return {"status": "success", "data": tarefa}

@app.delete("/tarefas/título/{titulo}")
def deletar_tarefa(titulo: str):
    if titulo in todos_dados:
        todo_store.pop(todo_store[titulo], None)
    else:
        return {"msg": f"Tarefa '{titulo}' não encontrada."}
```
Em cada exemplo, o `todos_dados` é um dicionário do tipo `List[Tarefa]`, que representa a lista de tarefas da API. No início, é criado o valor `Todos`. Depois adicionamos novas tarefas (criadas na interface web), a tarefa deletada usando `pop()`, ou a tarefa que pertence à `todos_dados` para limpar essa tarefa.

Você pode substituir isso pelo código que gostaria de adicionar mais funções relacionadas. Para adicionar memória em Dicionários, basta ajustar o tipo de lista para um `Set[Tarefa]`. Para adicionar as duas funcionalidades para listagem e deleto, faça o seguinte em uma nova função:

```python
def criar_tarefa(tarefa: Tarefa):
    to_do_set = set()
    todo_store[tarefa.título] |= to_do_set
    todos_dados.append(tarefa)

@app.post("/tarefas/")
async def criar_tarefa(tarefa: Tarefa):
  todos_dados.append(tarefa)
  return {"status": "success", "data": tarefa}

@app.delete("/tarefas/título/{titulo}")
def deletar_tarefa(titulo: str):
    todos_dados.remove(todos_dados[todo_store[titulo]]) # para remover o valor de Dicionário do Set
    todo_store.pop(todo_store[titulo], None)
```

Este é apenas um exemplo. O código pode ser ajustado, dependendo das necessidades específicas da sua aplicação. E ao adicionar algumas funções em que a API pode lidar diferentes tarefas e métodos para listagem e exclusão de registros, ficará mais fácil para futuros desenvolvedores que o seu código.