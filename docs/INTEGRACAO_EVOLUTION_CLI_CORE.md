# ROADMAP — Integração Incremental: Evolution + CLI + Core

> Objetivo: religar a pasta `evolution` ao pipeline principal sem perder estabilidade.
> Regra: 1 etapa por vez. Cada etapa tem teste de contrato. Nenhuma etapa avança sem teste verde.

---

## Etapa 1 — Diagnóstico de isolamento da pasta `evolution`
- [x] Confirmar que `iaglobal run` entra em `bootstrap.initialize()`
- [x] Confirmar qual `PipelineEngine` é chamado e se o resultado é `success=True` real
- [x] Mapear onde o texto `Resultado processado pela estratégia creative` é gerado
- [x] Identificar imports quebrados entre `core/orchestrator.py` e `pipeline/engine.py`
- [x] Identificar dependências quebradas da pasta `evolution` em relação ao CLI/core
- **Critério de aceite:** relatório limpo de causa-raiz, sem alterações funcionais ainda

## Etapa 2 — Correção mínima do orquestrador central
- [x] Remover import inexistente `execute_pipeline` em `core/orchestrator.py`
- [x] Fazer `Orchestrator.execute()` delegar para `self.pipeline.execute(...)` de forma segura
- [x] Garantir que `Bootstrap.initialize()` continua retornando o orquestrador com `pipeline` válido
- [x] Adicionar teste de contrato: `test_orchestrator_delegates_to_pipeline`
- **Critério de aceite:** `orch.execute({"task": "ping"})` retorna o resultado real do pipeline, sem sucesso falso

## Etapa 3 — Criação do teste de integração `evolution ↔ cli ↔ core`
- [x] Criar `tests/integration/test_evolution_cli_core.py`
- [x] Testar fluxo mínimo: `cli.main.run_cli()` → `bootstrap.initialize()` → `PipelineEngine.execute()`
- [x] Testar que `success` reflete o resultado real do grafo, não texto mock
- [x] Testar que `evolution_lab.py` não interfere no `iaglobal run`
- **Critério de aceite:** teste novo passa e serve como base para próximas etapas

## Etapa 4 — Remoção de fallback fake em skills LLM
- [x] Substituir retorno mock `Resultado processado pela estratégia ...` por chamada real ao provider
- [x] Se provider indisponível, retornar `success=False` ao invés de texto falso
- [x] Garantir que `SkillExecutor` preserva `success`/`error` no contrato
- [x] Atualizar teste: `test_skill_llm_failure_returns_false`
- **Critério de aceite:** não há mais outputs falsos marcados como sucesso

## Etapa 5 — Reconexão da pasta `evolution` ao pipeline principal
- [x] Mapear pontos de entrada da evolution usados pelo pipeline original
- [x] Restaurar chamadas de `evolution_runtime`/`evolver` no bootstrap/orchestrator quando `EVOLUTION_AUTO=1`
- [x] Garantir que `iaglobal run` registra métricas evolution sem travar o fluxo principal
- [x] Adicionar teste: `test_evolution_auto_start_on_bootstrap`
- **Critério de aceite:** `evolution` volta a participar do ciclo sem quebrar o `run`

## Etapa 6 — Purge de ruído e logs de debug
- [x] Remover prints de debug inseridos durante investigação
- [x] Remover `print("[OUTPUT-RENDERER] ...")` e afins
- [x] Garantir logging apenas via `logging.getLogger("iaglobal")`
- [x] Remover `test_analyze_orphans.py` e `auditoria_arquitetural.py` (não críticos para integração)
- [x] Confirmar que testes de integração continuam verdes
- **Critério de aceite:** saída do `iaglobal run` limpa, sem DEBUGs

## Etapa 7 — Testes de evolução automática (nova)
- [x] Criar `tests/integration/test_evolution_auto_mutation.py`
- [x] Testar fallback quando skill está faltando
- [x] Testar geração automática de skill via `MetaSkillGenerator`
- [x] Testar replicação de `EvoAgent` (mitose)
- [x] Testar apoptose preservando conhecimento
- [x] Testar ciclo completo de evolução quando falta habilidade
- **Critério de aceite:** 4 testes passando, cobrindo evolução automática

## Etapa 8 — Genesis Handshake Protocol (futuro)
- [x] Projetar protocolo de handshake SHA3-512 entre nós remotos
- [x] Implementar `GenesisHandshake` em `communication/genesis_handshake.py`
- [x] Criar testes simulativos (`test_genesis_handshake.py`)
- [x] Documentar em `ARCHITECTURE.md`
- **Critério de aceite:** 8 testes passando, protocolo documentado para uso futuro

## Etapa 9 — Correção de imports quebrados na integração
- [x] Criar `security/entropy_sentinel.py` wrapper para `immunity/entropy_sentinel.py`
- [x] Corrigir `membrane_key.py` para usar `GENESIS_HASH_OFFICIAL` ao invés de atributo inexistente
- [x] Corrigir `epigenetic_masking.py` para usar `GENESIS_HASH_OFFICIAL` ao invés de atributo inexistente
- [x] Adicionar `reset()` no `Bootstrap` para permitir testes independentes
- [x] Todos os 24 testes de integração passando
- **Critério de aceite:** integração evolution ↔ cli ↔ core estável e testada

## Ordem de execução
1. Etapa 1 — Diagnóstico
2. Etapa 2 — Correção mínima do orquestrador
3. Etapa 3 — Teste de integração
4. Etapa 4 — Remoção de fallback fake
5. Etapa 5 — Reconexão da pasta `evolution`
6. Etapa 6 — Purge de ruído

## Critérios gerais
- [ ] Nenhuma etapa avança sem teste verde da etapa anterior
- [ ] Nenhuma alteração pode reintroduzir `print()` em fluxos principais
- [ ] Manter assinatura async em todos os pontos de I/O
- [ ] `BanditPolicy` continua sendo único ponto de entrada para modelos de iA
