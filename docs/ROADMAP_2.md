# 🧬 ROADMAP_2.md — Integração #1: REMSleep como Orquestrador de Imunidade

## Visão Geral

**Objetivo:** Transformar o `REMSleepEngine` de um simples "administrador de arquivos" (Short → Long Term) para o **orquestrador da imunidade metabólica** do sistema.

**Problema Atual:** O `REMSleepEngine` consolida memórias, mas ignora a **DLQ (Dead Letter Queue)** — o repositório de erros tóxicos do sistema. Isso cria um gargalo: o sistema detecta falhas, mas não as transforma em aprendizado.

**Solução:** Integrar `_process_quarantine_dlq()` no início do ciclo `iniciar_fase_rem()`, permitindo que o REMSleep:
1. Varra a DLQ e agregue padrões recorrentes
2. Injete vacinas no `FewShotProvider` (aprendizado)
3. Opcionalmente, registre padrões no `EpigeneticRegistry` (introspecção)
4. Limpe arquivos antigos (decaimento físico)

**Status da Integração #1:** ✅ **COMPLETA** (Fases 1-7 implementadas, 807 testes passando)

---

## Integração #2: Mutação 1C (Expiry + Monitoramento) — Defesa em Profundidade

**Objetivo:** Implementar **limpeza ativa de vacinas antigas** + **métricas de saúde no `/health`** para prevenir "dívida técnica cognitiva" (prompt bloat por acumulação de exemplos negativos).

**Problema Previsto:** Se a DLQ crescer >50 arquivos/dia, em 30 dias teríamos **1500 exemplos negativos** → **450k tokens** de bloat, estourando a context window do Ollama (4096 tokens).

**Solução Híbrida (Opção C):**
1. **Expiry Ativo:** `_expire_old_vaccines()` remove vacinas com idade >30 dias
2. **Cap de Segurança:** Limite máximo de 100 vacinas (remove mais antiga se ultrapassar)
3. **Monitoramento:** Métricas no `/health` (`negative_examples_count`, `estimated_token_overhead`, etc.)
4. **Alertas:** REMSleep emite warnings se overhead >5000 tokens

**Status:** ✅ **COMPLETA** (Fases 1-6 implementadas, 812 testes passando)

---

## Integração #3: MitochondrialProbe — Sonda de Potencial do Event Loop (Opção A)

**Objetivo:** Implementar **sonda passiva de monitoramento do gradiente do event loop** para detectar hipóxia sistêmica antes do colapso (necrose).

**Problema Previsto:** Sem monitoramento do lag do event loop, o sistema pode entrar em **hipóxia sistêmica** (bloqueio por I/O síncrono acidental) sem alerta prévio, levando a:
- Acúmulo de tasks em fila (latência exponencial)
- Timeout em cascata
- Crash/necrose do processo sem diagnóstico

**Solução (Opção A — Sonda Passiva):**
1. **MitochondrialProbe:** Singleton que mede lag do event loop a cada 1s
2. **Baseline de 7 Dias:** Coleta dados de lag normal vs. pico de carga
3. **Métricas no `/health`:** `mitochondrial.current_lag_ms`, `hypoxia_detected`
4. **Alertas Críticos:** Logger `CRITICAL` se lag >50ms (início de hipóxia)
5. **Sem Inibição Alostérica (ainda):** Apenas observação, sem ação corretiva automática

**Status:** 📋 **EM IMPLEMENTAÇÃO** (Fases 1-5 abaixo)

**Protocolo de Implementação:**
- **Isolamento:** Singleton `mitochondrial_probe` para estado compartilhado
- **Proteção:** `asyncio.shield()` contra cancelamento acidental
- **Baseline:** 7 dias de coleta antes de implementar inibição alostérica
- **Correlação:** Lag do loop vs. número de tasks ativas (revele limite de saturação)

---

## Integração #4: Rastreabilidade MHC — Diagnóstico de "Parasitas Digitais"

**Objetivo:** Restaurar a "visibilidade imunológica" do sistema capturando stack traces quando o MHC detecta comportamento anômalo.

**Problema Identificado:** Traceback vazio transforma problemas de segurança (tentativa de rede não autorizada) em "cegueira imunológica" — impossibilita identificar a origem da chamada.

**Solução Implementada:**
1. **Injeção de Rastreabilidade:** `traceback.format_stack()` no handler `PARASITE DETECTED`
2. **Log de Origem:** Últimos 5 frames do stack trace registrados no log de erro
3. **Diagnóstico Diferenciado:** Permite classificar falhas como:
   - **Configural:** Rota faltando no `allowed_paths`
   - **Arquitetural:** Agente tentando bypass do gateway de rede
   - **Temporal:** Race condition (agente dispara antes do `netcheck` inicializar)

**Status:** ✅ **IMPLEMENTADA** (mhc_detector.py atualizado)

**Próximos Passos:**
- [ ] Executar processo e monitorar logs com stack trace
- [ ] Auditar módulos `lineage_proof` e `system_analysis` em busca de imports de rede diretos
- [ ] Validar configuração `allowed_paths` do MHC

**Comandos de Auditoria:**
```bash
# Busca por bibliotecas de rede instanciadas fora do gateway seguro
grep -rE "import (requests|httpx|aiohttp|socket)" iaglobal/graphs/nodes/

# Exibe configuração atual de rede carregada pelo MHC
python3 -c "from iaglobal.immunity.mhc_detector import MHCDetector; d = MHCDetector(); print('MHC initialized')"
```

---

## Passo a Passo da Implementação (Integração #2)

### Fase 1: Expiry de Vacinas (_expire_old_vaccines)

**Arquivo:** `iaglobal/core/few_shot_provider.py`

**Tarefa:** Implementar método assíncrono que varre a DLQ e retorna estatísticas.

```python
async def _process_quarantine_dlq(self) -> Dict[str, Any]:
    """Varre a DLQ, consolida padrões e prepara vacinas para o sistema."""
    
    def _scan_quarantine() -> List[Dict[str, Any]]:
        """I/O síncrono isolado em thread pool."""
        if not self.quarantine_dir.exists():
            return []
        
        patterns: Dict[str, Dict] = {}
        for fpath in self.quarantine_dir.glob("cache_poison_*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                reason = data.get("reason", "unknown")
                domain = self._extract_domain(data.get("prompt_snippet", ""))
                
                key = f"{reason}:{domain}"
                if key not in patterns:
                    patterns[key] = {
                        "reason": reason,
                        "domain": domain,
                        "count": 0,
                        "snippets": [],
                        "first_seen": data.get("timestamp"),
                        "last_seen": data.get("timestamp"),
                    }
                patterns[key]["count"] += 1
                patterns[key]["snippets"].append(data.get("prompt_snippet", "")[:100])
                patterns[key]["last_seen"] = data.get("timestamp")
            except Exception:
                continue
        
        return list(patterns.values())
    
    # Executa I/O em thread pool (non-blocking)
    patterns = await asyncio.to_thread(_scan_quarantine)
    
    # Filtra por threshold (padrões recorrentes)
    significant = [p for p in patterns if p["count"] >= self.DLQ_THRESHOLD]
    
    # Injeta no FewShotProvider como vacinas
    ingested = await few_shot_provider.ingest_dlq_examples(self.quarantine_dir)
    
    return {
        "total_files_scanned": len(patterns),
        "significant_patterns": len(significant),
        "vaccines_injected": ingested,
    }
```

**Critérios de Aceite:**
- [ ] Usa `asyncio.to_thread()` para I/O de disco
- [ ] Agrega por `(reason, domain)`
- [ ] Aplica threshold (`DLQ_THRESHOLD = 3`)
- [ ] Chama `few_shot_provider.ingest_dlq_examples()`
- [ ] Retorna dict com estatísticas

---

### Fase 2: Heurística de Domínio (_extract_domain)

**Arquivo:** `iaglobal/obsidian/consolidation.py`

**Tarefa:** Implementar método estático para extração de domínio a partir de snippets.

```python
@staticmethod
def _extract_domain(prompt_snippet: str) -> str:
    """Extrai domínio aproximado do prompt para agrupamento.
    
    Tolerante a null/empty strings — retorna 'general' como fallback.
    """
    if not prompt_snippet or not isinstance(prompt_snippet, str):
        return "general"
    
    snippet = prompt_snippet.lower()
    
    # Palavras-chave por domínio
    domains = {
        "api": ["api", "endpoint", "http", "rest", "graphql", "request"],
        "database": ["sql", "query", "database", "table", "insert", "select"],
        "frontend": ["react", "component", "jsx", "html", "css", "dom"],
        "security": ["auth", "token", "permission", "xss", "injection", "csrf"],
        "testing": ["test", "assert", "mock", "fixture", "pytest"],
        "async": ["async", "await", "event loop", "coroutine"],
    }
    
    for domain, keywords in domains.items():
        if any(kw in snippet for kw in keywords):
            return domain
    
    return "general"
```

**Critérios de Aceite:**
- [ ] Retorna `"general"` para input `None`, `""`, ou não-string
- [ ] Case-insensitive
- [ ] Fallback seguro se nenhuma keyword for encontrada
- [ ] Testado com edge cases (strings vazias, None, keywords parciais)

---

### Fase 3: Integração no Ciclo REM (iniciar_fase_rem)

**Arquivo:** `iaglobal/obsidian/consolidation.py`

**Tarefa:** Chamar `_process_quarantine_dlq()` no início de `iniciar_fase_rem()`.

```python
async def iniciar_fase_rem(self) -> Dict[str, Any]:
    """Executa o ciclo completo de consolidação de forma assíncrona."""
    resultado: Dict[str, Any] = {
        "iniciado_em": datetime.now(UTC).isoformat(),
        "memorias_processadas": 0,
        "memorias_consolidadas": 0,
        "contaminacoes_bloqueadas": 0,
        "dlq_processed": None,  # NOVO
        "erros": [],
    }

    # === NOVO: Processamento da DLQ (antes da consolidação) ===
    try:
        dlq_result = await self._process_quarantine_dlq()
        resultado["dlq_processed"] = dlq_result
        if dlq_result["vaccines_injected"]:
            logger.info(
                "[REMSleep] DLQ vaccinated: %d padrões significativos, %d vacinas injetadas",
                dlq_result["significant_patterns"],
                dlq_result["vaccines_injected"],
            )
    except Exception as e:
        logger.exception("[REMSleep] Falha ao processar DLQ: %s", e)
        resultado["erros"].append(f"dlq_processing: {e}")
    # =========================================================

    experiencias = await self._listar_memorias_curto_prazo()
    if not experiencias:
        resultado["status"] = "sem_memorias"
        logger.info("[REMSleep] Nenhuma memória de curto prazo para consolidar.")
        return resultado
    
    # ... restante do ciclo de consolidação ...
```

**Critérios de Aceite:**
- [ ] Chamada ocorre **antes** de `_listar_memorias_curto_prazo()`
- [ ] Envolto em `try/except` para não quebrar o ciclo principal
- [ ] Log de sucesso com contagem de vacinas
- [ ] Resultado incluído no dict de retorno

---

### Fase 4: Configuração e Thresholds

**Arquivo:** `iaglobal/obsidian/consolidation.py`

**Tarefa:** Adicionar constantes de configuração no `__init__`.

```python
def __init__(self, vault_path: Optional[Path] = None, ai_client=None):
    self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
    self.short_term_dir = self.vault_path / "02_Short_Term"
    self.long_term_dir = self.vault_path / "03_Long_Term"
    self.synapses_dir = self.vault_path / "04_Synapses"
    self.quarantine_dir = self.vault_path / "00_Quarentena"  # NOVO
    self.ai_client = ai_client
    
    # Thresholds de DLQ
    self.DLQ_THRESHOLD = 3  # Mínimo de ocorrências para padrão significativo
    
    # Futuro: threshold adaptativo
    # self.DLQ_THRESHOLD_MIN = 2
    # self.DLQ_THRESHOLD_MAX = 5

    for d in [self.short_term_dir, self.long_term_dir, self.synapses_dir, self.quarantine_dir]:
        d.mkdir(parents=True, exist_ok=True)
```

**Critérios de Aceite:**
- [ ] `quarantine_dir` definido e criado se não existir
- [ ] `DLQ_THRESHOLD = 3` como constante de classe
- [ ] Comentário sobre futuro threshold adaptativo

---

### Fase 5: Testes (test_remsleep_dlq_scan.py)

**Arquivo:** `tests/test_remsleep_dlq_scan.py`

**Tarefa:** Criar suite de testes para o novo fluxo.

```python
# 🧬 LINEAGE_MARKER: ...
"""Testes do processamento de DLQ pelo REMSleepEngine."""
import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from iaglobal.obsidian.consolidation import REMSleepEngine
from iaglobal._paths import PACKAGE_DIR


@pytest.fixture
def rem_sleep_with_dlq(tmp_path):
    """Cria REMSleepEngine com quarantine_dir temporário."""
    engine = REMSleepEngine(vault_path=tmp_path)
    yield engine


@pytest.fixture
def dlq_seed_files(tmp_path):
    """Seed de arquivos DLQ para testes."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed 5 arquivos com reason="refusal", domain="api"
    for i in range(5):
        fpath = quarantine_dir / f"cache_poison_refusal_2026-01-0{i}_test{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"crie uma API endpoint {i}",
            "response_snippet": "Eu não posso ajudar com isso.",
            "reason": "refusal_or_hallucination",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    # Seed 2 arquivos com reason="hallucination", domain="database"
    for i in range(2):
        fpath = quarantine_dir / f"cache_poison_hallucination_2026-01-0{i}_test{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"query SQL para tabela {i}",
            "response_snippet": "SELECT * FROM fake_table",
            "reason": "irrelevant_response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    return quarantine_dir


async def test_dlq_scan_aggregates_patterns(rem_sleep_with_dlq, dlq_seed_files):
    """Varredura agrega múltiplos arquivos por (reason, domain)."""
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    
    assert result["total_files_scanned"] == 7  # 5 + 2
    assert result["significant_patterns"] == 1  # Apenas refusal atinge threshold=3
    assert result["vaccines_injected"] == 7     # Todos injetados


async def test_dlq_scan_respects_threshold(rem_sleep_with_dlq, tmp_path):
    """Padrões abaixo do threshold não são considerados significativos."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed apenas 2 arquivos (abaixo de threshold=3)
    for i in range(2):
        fpath = quarantine_dir / f"cache_poison_test_{i}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"test {i}",
            "response_snippet": "error",
            "reason": "test_reason",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    assert result["significant_patterns"] == 0


async def test_dlq_scan_async_io_non_blocking(rem_sleep_with_dlq, tmp_path):
    """I/O de disco não bloqueia event loop (thread pool)."""
    quarantine_dir = tmp_path / "00_Quarentena"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed 100 arquivos
    for i in range(100):
        fpath = quarantine_dir / f"cache_poison_batch_{i:03d}.json"
        fpath.write_text(json.dumps({
            "prompt_snippet": f"batch test {i}",
            "response_snippet": "error",
            "reason": "batch_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
    
    start = asyncio.get_event_loop().time()
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert result["total_files_scanned"] == 100
    assert elapsed < 2.0  # 100 arquivos em <2s (thread pool)


async def test_dlq_scan_missing_dir_returns_zero(rem_sleep_with_dlq):
    """Diretório inexistente retorna 0 sem erro."""
    result = await rem_sleep_with_dlq._process_quarantine_dlq()
    assert result["total_files_scanned"] == 0
    assert result["vaccines_injected"] == 0


async def test_dlq_scan_idempotent(rem_sleep_with_dlq, dlq_seed_files):
    """Segunda varredura não duplica vacinas (idempotência do FewShot)."""
    result1 = await rem_sleep_with_dlq._process_quarantine_dlq()
    result2 = await rem_sleep_with_dlq._process_quarantine_dlq()
    
    # Ambos retornam o mesmo count, mas FewShot não duplica
    assert result1["vaccines_injected"] == result2["vaccines_injected"]


def test_extract_domain_heuristics():
    """Heurística de domínio classifica corretamente."""
    from iaglobal.obsidian.consolidation import REMSleepEngine
    
    test_cases = [
        ("crie uma API endpoint", "api"),
        ("query SQL para tabela", "database"),
        ("component React JSX", "frontend"),
        ("token de autenticação", "security"),
        ("teste com pytest mock", "testing"),
        ("async await coroutine", "async"),
        ("texto genérico sem keywords", "general"),
        ("", "general"),  # empty string
        (None, "general"),  # None
    ]
    
    for snippet, expected in test_cases:
        result = REMSleepEngine._extract_domain(snippet)
        assert result == expected, f"Failed for {snippet!r}"
```

**Critérios de Aceite:**
- [ ] 6 testes cobrindo agregação, threshold, async I/O, missing dir, idempotência, heurística
- [ ] Todos os testes passam
- [ ] Teste de async I/O valida `<2s` para 100 arquivos

---

### Fase 6: Atualização da Documentação (ARCHITECTURE.md)

**Arquivo:** `docs/ARCHITECTURE.md`

**Tarefa:** Atualizar §18.6.4 para refletir autonomia do REMSleep.

**Mudanças:**
1. Adicionar diagrama de fluxo atualizado (REMSleep → DLQ scan → FewShot)
2. Documentar `_process_quarantine_dlq()` e `_extract_domain()`
3. Adicionar métricas de eficácia (tempo de scan, threshold)
4. Atualizar "Próximas Mutações" para marcar Integração #1 como ✅ IMPLEMENTADO

---

### Fase 7: Validação Final

**Comandos:**
```bash
# 1. Syntax check
python -c "import ast; ast.parse(open('iaglobal/obsidian/consolidation.py').read())"

# 2. Run new tests
python -m pytest tests/test_remsleep_dlq_scan.py -v

# 3. Full suite regression
python -m pytest tests/ -x -q

# 4. Manual integration test
python -c "
from iaglobal.obsidian.consolidation import REMSleepEngine
from iaglobal._paths import PACKAGE_DIR
import asyncio

async def test():
    engine = REMSleepEngine(vault_path=PACKAGE_DIR / 'obsidian')
    result = await engine._process_quarantine_dlq()
    print(f'DLQ processed: {result}')

asyncio.run(test())
"
```

**Critérios de Aceite:**
- [ ] Syntax OK
- [ ] 6/6 testes novos passam
- [ ] 801+ testes no total sem regressões
- [ ] Integration test retorna resultado válido

---

## Decisão de Design: Colisão de Vacinas (FewShotProvider)

**Problema:** `ingest_dlq_examples()` pode encontrar padrões já existentes no `_example_cache`.

**Solução Escolhida:** **Opção C (Aging/Score)** — precedência por `count` (ocorrências).

**Implementação no FewShotProvider:**
```python
# few_shot_provider.py: ingest_dlq_examples()

key = f"dlq:{reason}:{md5_hash[:12]}"

if key in self._example_cache:
    # Verifica se novo exemplo tem count maior
    existing_ex = self._example_cache[key][0][0]  # First example in cache
    existing_count = existing_ex.metadata.get("count", 1) if hasattr(existing_ex, "metadata") else 1
    
    if pattern["count"] > existing_count:
        # Substitui (novo é mais relevante)
        self._example_cache[key] = ([new_ex], time.monotonic())
        self._negative_examples = [
            ex for ex in self._negative_examples if ex != existing_ex
        ]
        self._negative_examples.append(new_ex)
    # else: mantém existente (mais relevante)
else:
    # Insert novo
    self._example_cache[key] = ([new_ex], time.monotonic())
    self._negative_examples.append(new_ex)
```

**Justificativa:**
- **Eficiência:** Evita prompt bloat (não acumula exemplos redundantes)
- **Relevância:** Prioriza padrões recorrentes (lei de potência)
- **Biologicamente alinhado:** Sistema imune prioriza antígenos de alta exposição

---

## Vetores Futuros (Pós-Implementação)

1. **REMScan Idle:** Varredura periódica (cron) mesmo sem ciclo REM
2. **DLQ Prioritização:** `reason="security_violation"` ganha score 0.25+
3. **Expiry de Vacinas:** Exemplos >30 dias expiram se obsoletos
4. **EpigeneticRegistry Integration:** Padrões registrados para introspecção

---

## Status do Roadmap

| Fase | Status | Responsável |
|------|--------|-------------|
| 1. _process_quarantine_dlq | ⏳ Pendente | Implementação |
| 2. _extract_domain | ⏳ Pendente | Implementação |
| 3. Integração no iniciar_fase_rem | ⏳ Pendente | Implementação |
| 4. Configuração e Thresholds | ⏳ Pendente | Implementação |
| 5. Testes | ⏳ Pendente | Implementação |
| 6. Documentação | ⏳ Pendente | Implementação |
| 7. Validação Final | ⏳ Pendente | Implementação |

**Próximo Passo:** Iniciar Fase 1 (_process_quarantine_dlq) após aprovação deste roadmap.
---

## Integração #2: Mutação 1C (Expiry + Monitoramento) — Defesa em Profundidade

**Objetivo:** Implementar **limpeza ativa de vacinas antigas** + **métricas de saúde no `/health`** para prevenir "dívida técnica cognitiva" (prompt bloat por acumulação de exemplos negativos).

**Problema Previsto:** Se a DLQ crescer >50 arquivos/dia, em 30 dias teríamos **1500 exemplos negativos** → **450k tokens** de bloat, estourando a context window do Ollama (4096 tokens).

**Solução Híbrida (Opção C):**
1. **Expiry Ativo:** `_expire_old_vaccines()` remove vacinas com idade >30 dias
2. **Cap de Segurança:** Limite máximo de 100 vacinas (remove mais antiga se ultrapassar)
3. **Monitoramento:** Métricas no `/health` (`negative_examples_count`, `estimated_token_overhead`, etc.)
4. **Alertas:** REMSleep emite warnings se overhead >5000 tokens

**Status:** 📋 **EM IMPLEMENTAÇÃO** (Fases 1-6 abaixo)

---

### Fase 1: Expiry de Vacinas (_expire_old_vaccines)

**Arquivo:** `iaglobal/core/few_shot_provider.py`

**Tarefa:** Implementar método que remove vacinas antigas (>30 dias) e excedentes do cap (100 máx).

**Critérios de Aceite:**
- [ ] Remove vacinas com idade >30 dias
- [ ] Remove vacinas excedentes se count >100
- [ ] Sincroniza `_example_cache` e `_negative_examples`
- [ ] Log de limpeza com contagem
- [ ] Retorna estatísticas da operação

---

### Fase 2: Integração no ingest_dlq_examples

**Arquivo:** `iaglobal/core/few_shot_provider.py`

**Tarefa:** Chamar `_expire_old_vaccines()` no início de `ingest_dlq_examples()`.

**Critérios de Aceite:**
- [ ] `_expire_old_vaccines()` chamado antes de `_scan_and_load()`
- [ ] Estatísticas de expiry registradas no log
- [ ] Nova injeção ocorre após limpeza

---

### Fase 3: Métricas no Health Endpoint (/health)

**Arquivo:** `iaglobal/server/health_aggregator.py`

**Tarefa:** Adicionar métricas do FewShotProvider no endpoint `/health`.

**Critérios de Aceite:**
- [ ] `negative_examples_count` exposto
- [ ] `embedding_cache_size` e `embedding_cache_limit` expostos
- [ ] `oldest_vaccine_age_days` calculado corretamente
- [ ] `estimated_token_overhead` baseado em constante (300 tokens/exemplo)
- [ ] Métricas aparecem em `GET /health`

---

### Fase 4: Alertas no REMSleep

**Arquivo:** `iaglobal/obsidian/consolidation.py`

**Tarefa:** REMSleep emite warnings se overhead >5000 tokens.

**Critérios de Aceite:**
- [ ] Warning log se token_overhead >5000
- [ ] `token_overhead` incluído no dict de retorno
- [ ] Threshold configurável (constante no topo do arquivo)

---

### Fase 5: Testes de Expiry e Monitoramento

**Arquivo:** `tests/test_fewshot_vaccine_expiry.py`

**Tarefa:** Criar suite de testes para expiry e métricas.

**Critérios de Aceite:**
- [ ] 5 testes cobrindo expiry por idade, cap, sincronização, constante de tokens, integração
- [ ] Todos os testes passam
- [ ] Teste de idade usa `monkeypatch` para simular avanço temporal
- [ ] Teste de cap valida limite de 100 vacinas

---

### Fase 6: Validação Final

**Comandos:**
```bash
# 1. Syntax check
python -c "import ast; ast.parse(open('iaglobal/core/few_shot_provider.py').read())"
python -c "import ast; ast.parse(open('iaglobal/server/health_aggregator.py').read())"

# 2. Run new tests
python -m pytest tests/test_fewshot_vaccine_expiry.py -v

# 3. Full suite regression
python -m pytest tests/ -x -q

# 4. Manual integration test
curl http://localhost:8000/health | jq '.cognitive.few_shot'
```

**Critérios de Aceite:**
- [ ] Syntax OK
- [ ] 5/5 testes novos passam
- [ ] 807+ testes no total sem regressões
- [ ] `/health` retorna métricas de few_shot

---

## Status Atualizado do Roadmap

| Integração | Fase | Status |
|------------|------|--------|
| #1 (DLQ Scan) | 1-7 | ✅ **COMPLETA** |
| #2 (Expiry + Monitoramento) | 1 | ⏳ Pendente |
| #2 (Expiry + Monitoramento) | 2 | ⏳ Pendente |
| #2 (Expiry + Monitoramento) | 3 | ⏳ Pendente |
| #2 (Expiry + Monitoramento) | 4 | ⏳ Pendente |
| #2 (Expiry + Monitoramento) | 5 | ⏳ Pendente |
| #2 (Expiry + Monitoramento) | 6 | ⏳ Validação |

**Próximo Passo:** Implementar Fase 1 (_expire_old_vaccines) da Integração #2.

---

## Decisão de Design: Responsabilidade de Alertas

**Pergunta:** REMSleep emite alertas ou agente externo monitora `/health`?

**Decisão:** **Híbrida** — REMSleep emite warnings logs durante o ciclo, mas alertas críticos (ex: overhead >10000 tokens) disparam eventos no `AcetylcholineBus` para agentes de monitoramento.

**Justificativa:**
- **REMSleep:** Melhor posição para detectar tendências (ciclo após ciclo)
- **Agentes externos:** Podem tomar ações corretivas (ex: solicitar aumento de threshold)
- **Bus events:** Permite auditoria e histórico de alertas

---

## Passo a Passo da Implementação (Integração #3: MitochondrialProbe)

### Fase 1: Implementar MitochondrialProbe (Sonda Passiva)

**Arquivo:** `iaglobal/core/mitochondrial_probe.py`

**Tarefa:** Implementar singleton que monitora lag do event loop.

**Critérios de Aceite:**
- [ ] Singleton global `mitochondrial_probe`
- [ ] Loop de monitoramento a cada 1s com sleep de 10ms
- [ ] Detecção de hipóxia se lag >50ms
- [ ] Logger `CRITICAL` com valor do lag
- [ ] Método `get_health_status()` para `/health`
- [ ] Proteção contra cancelamento (`asyncio.shield`)
- [ ] Registro de callbacks para futura inibição alostérica

---

### Fase 2: Integrar no /health Endpoint

**Arquivo:** `iaglobal/server/health_aggregator.py`

**Tarefa:** Adicionar métricas do `mitochondrial_probe` no endpoint `/health`.

**Critérios de Aceite:**
- [ ] `mitochondrial.current_lag_ms` exposto
- [ ] `mitochondrial.hypoxia_detected` exposto
- [ ] `mitochondrial.threshold_ms` exposto
- [ ] `mitochondrial.status` ("healthy" ou "hypoxic")

---

### Fase 3: Iniciar Sonda no Bootstrap do Sistema

**Arquivo:** `iaglobal/__main__.py` ou `iaglobal/cli/main.py`

**Tarefa:** Iniciar `mitochondrial_probe.start_monitoring()` como task de background no bootstrap.

**Critérios de Aceite:**
- [ ] Sonda inicia com o sistema
- [ ] Task roda em background (baixa prioridade)
- [ ] Log de inicialização da sonda
- [ ] Sonda não bloqueia startup

---

### Fase 4: Coleta de Baseline (7 Dias)

**Tarefa:** Configurar telemetria para coletar `current_lag` continuamente.

**Critérios de Aceite:**
- [ ] Log de lag a cada ciclo (ou amostragem estatística)
- [ ] Armazenamento em formato analisável (JSON, CSV, ou Obsidian)
- [ ] Após 7 dias: plot de "Lag vs. Carga" para identificar thresholds naturais

---

### Fase 5: Testes da Sonda

**Arquivo:** `tests/test_mitochondrial_probe.py`

**Tarefa:** Criar suite de testes para a sonda.

**Critérios de Aceite:**
- [ ] Teste de detecção de hipóxia (simula lag >50ms)
- [ ] Teste de recuperação (lag volta ao normal)
- [ ] Teste de `get_health_status()`
- [ ] Teste de registro de callbacks (preparação para inibição alostérica)
- [ ] Teste de proteção contra cancelamento

---

### Fase 6: Validação Final

**Comandos:**
```bash
# 1. Syntax check
python -c "import ast; ast.parse(open('iaglobal/core/mitochondrial_probe.py').read())"

# 2. Run new tests
python -m pytest tests/test_mitochondrial_probe.py -v

# 3. Full suite regression
python -m pytest tests/ -x -q

# 4. Manual integration test
curl http://localhost:8000/health | jq '.metabolic_state.mitochondrial'
```

**Critérios de Aceite:**
- [ ] Syntax OK
- [ ] 4/4 testes novos passam
- [ ] 812+ testes no total sem regressões
- [ ] `/health` retorna métricas de mitochondrial

---

## Status Atualizado do Roadmap

| Integração | Fase | Status |
|------------|------|--------|
| #1 (DLQ Scan) | 1-7 | ✅ **COMPLETA** |
| #2 (Expiry + Monitoramento) | 1-6 | ✅ **COMPLETA** |
| #3 (MitochondrialProbe) | 1 | ⏳ Pendente |
| #3 (MitochondrialProbe) | 2 | ⏳ Pendente |
| #3 (MitochondrialProbe) | 3 | ⏳ Pendente |
| #3 (MitochondrialProbe) | 4 | ⏳ Coleta (7 dias) |
| #3 (MitochondrialProbe) | 5 | ⏳ Pendente |
| #3 (MitochondrialProbe) | 6 | ⏳ Validação |

**Próximo Passo:** Implementar Fase 1 (MitochondrialProbe) da Integração #3.

---

## Decisão de Design: Observação Antes da Regulação

**Princípio:** Implementar **sonda passiva** primeiro, coletar baseline de 7 dias, **depois** implementar inibição alostérica.

**Justificativa:**
- **Sem baseline:** Risk de falsos positivos (inibir tasks desnecessariamente)
- **Com baseline:** Thresholds calibrados com dados reais de produção
- **Analogia biológica:** Organismos não nascem com regulação alostérica completa — ela evolui após exposição repetida a stress

**Fase Seguinte (Pós-7-dias):**
- Implementar inibição alostérica (`register_alosteric_inhibitor`)
- Definir hierarquia de sobrevivência (Essencial > Importante > Opcional > Luxo)
- Auto-recuperação quando lag < threshold
