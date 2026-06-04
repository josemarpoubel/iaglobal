# iaglobal MCP Tools

Este projeto tem um servidor MCP local chamado **iaglobal** que fornece
ferramentas de engenharia de software automatizada.

## Ferramentas disponíveis

### `iaglobal_run_task(prompt)`

Executa o pipeline completo de geracao de codigo (13 estagios):

1. planner → 2. web_classifier → 3. search → 4. multi_coder
5. critic → 6. semantic_validator → 7. ast_validator
8. tester → 9. debugger → 10. rank_final
11. final_gatekeeper → 12. artifact_writer → 13. reflexion

**Quando usar:** Sempre que o usuario pedir para criar codigo, gerar scripts,
implementar funcoes, criar blocos genesis, validar CPF, ou qualquer tarefa
de engenharia de software.

**Parametro:** `prompt` (string) — descricao da tarefa

**Retorno:** caminho do arquivo gerado + codigo produzido

### `iaglobal_get_status()`

Retorna o status atual do sistema iaglobal.

**Quando usar:** Quando o usuario perguntar sobre o estado do sistema,
quantidade de nos, ciclo de evolucao, metricas de memoria ou seguranca.

### `iaglobal_get_insights(agent, limit, min_score)`

Consulta aprendizados armazenados pelos agentes.

**Quando usar:** Quando o usuario perguntar o que o sistema aprendeu,
ou quiser ver erros passados e correcoes.

### `iaglobal_list_scripts()`

Lista todos os scripts Python gerados e persistidos.

**Quando usar:** Quando o usuario quiser ver os arquivos ja gerados.

## Regras de uso

1. Para tarefas de codigo, **sempre use** `iaglobal_run_task` em vez de
   tentar gerar o codigo manualmente. O pipeline testa, valida e persiste.

2. Para tarefas que o iaglobal nao consegue resolver (ex: editar arquivos
   existentes, refatorar codigo especifico), use as ferramentas padrao
   do opencode (read, write, edit, bash).

3. Se o usuario pedir status do ambiente de desenvolvimento, use
   `iaglobal_get_status()` para mostrar metricas do sistema.

## Exemplos

```
User: crie um bloco genesis em sha3_512 para Bit512
You:  [chama iaglobal_run_task com o prompt do usuario]
      "✅ Tarefa concluida! Script salvo em: ..."

User: o que o sistema aprendeu sobre hashlib?
You:  [chama iaglobal_get_insights(agent="reflexion", min_score=70)]
      "O sistema aprendeu que sha3_512 requer import hashlib"

User: quais scripts ja foram gerados?
You:  [chama iaglobal_list_scripts()]
      "10 scripts gerados: ..."

User: qual o status do iaglobal?
You:  [chama iaglobal_get_status()]
      "13 nos, 24 insights, evolução rodando"
```
