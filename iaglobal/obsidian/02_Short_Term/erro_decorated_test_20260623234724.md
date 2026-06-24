---
id: "erro_decorated_test_20260623234724"
tipo: "MemoriaBruta"
timestamp: "2026-06-23T23:47:24.450927+00:00Z"
tags: ["#test", "#erro", "#agente-decorated_test"]
---

# erro_decorated_test_20260623234724

## Erro no Agente: decorated_test

**Tarefa:** funcao_que_falha

**Erro:**
```
Traceback (most recent call last):
  File "/home/kitohamachi/projeto-iaglobal/tests/../iaglobal/obsidian/error_capture.py", line 72, in wrapper
    return func(*args, **kwargs)
  File "/home/kitohamachi/projeto-iaglobal/tests/test_system_integration.py", line 664, in funcao_que_falha
    raise ValueError("decorator error")
ValueError: decorator error

```
