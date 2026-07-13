# Templates de Skills iaglobal

Esta pasta contém todos os templates de prompt usados pelas skills do sistema.

## Estrutura

Cada arquivo `.txt` corresponde a uma skill específica:
- `planner.txt` → SKILL_PLANNER
- `coder.txt` → SKILL_CODER
- `critic.txt` → SKILL_CRITIC
- etc.

## Sintaxe

Os templates usam placeholders no formato `{variavel}` que são preenchidos com o contexto da execução.

Exemplo:
```
Como desenvolvedor sênior, implemente código Python para: {task}
Siga o plano: {plan}
Requisitos: {requirements}
```

## Variáveis disponíveis

- `{task}` → Tarefa original do usuário
- `{refined_task}` → Tarefa refinada pelo interpreter
- `{plan}` → Plano de execução
- `{requirements}` → Requisitos (RFs + RNFs)
- `{business_rules}` → Regras de negócio
- `{architect}` → Arquitetura do sistema
- `{code}` → Código gerado
- `{execution_plan}` → Plano detalhado de execução

## Adicionando novo template

1. Crie `<nome_da_skill>.txt` nesta pasta
2. Use placeholders apropriados
3. O sistema carregará automaticamente via `template_loader.py`

## Modificando template existente

1. Edite o arquivo `.txt` correspondente
2. Teste com `iaglobal run "sua tarefa"`
3. O novo template será usado na próxima execução