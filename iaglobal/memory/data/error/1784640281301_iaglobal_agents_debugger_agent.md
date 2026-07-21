# Erro de Runtime

- **Componente**: iaglobal.agents.debugger_agent
- **Time**: 2026-07-21T13:24:41.301401Z

## Mensagem
```
AST validation failed
```

## Traceback
```
Traceback (most recent call last):
  File "/home/kitohamachi/iaglobal-main/iaglobal/agents/debugger_agent.py", line 105, in run
    self._validate(code)
    ~~~~~~~~~~~~~~^^^^^^
  File "/home/kitohamachi/iaglobal-main/iaglobal/agents/debugger_agent.py", line 335, in _validate
    raise ValueError("; ".join(result.errors))
ValueError: unexpected indent (<unknown>, line 1)

```
