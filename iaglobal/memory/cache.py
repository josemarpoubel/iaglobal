# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Cache module for L1 and L2 memory layers.

Adiciona barreira imunológica (validação de conteúdo) e apoptose (TTL +
evicção de entradas tóxicas), eliminando o 'cache poisoning' silencioso que
servia respostas vazias/obsoletas como sucesso metabólico.

Regras (compatíveis com a arquitetura biológica do iaglobal):
  - IMUNE:    só respostas não-vazias e com comprimento mínimo são válidas.
  - APOPTOSE: entradas vencidas (TTL) ou tóxicas são evictadas ao serem
              acessadas e registram um evento na MetabolicImmuneBarrier,
              em vez de serem servidas silenciosamente como `success=True`.
  - HONESTIDADE: o token_count real é preservado para a telemetria (antes
              hardcoded 0 nos hits de cache).
  - DLQ:      entradas tóxicas/rejeitadas são persistidas em uma Dead Letter
              Queue (00_Quarentena/) como relatório JSON auditável, alimentando
              o FewShotProvider com exemplos negativos.
"""
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from iaglobal._paths import PACKAGE_DIR
from iaglobal.memory.memory_storage import storage, get_success_by_task
from iaglobal.immunity.metabolic_immune_barrier import barrier
from iaglobal.reflection.claim_detection import is_refusal_or_hallucination


QUARANTINE_DIR = PACKAGE_DIR / "obsidian" / "00_Quarentena"

_DLQ_BUFFER: List[Dict[str, Any]] = []
_DLQ_FLUSH_INTERVAL = 60
_DLQ_MAX_BATCH = 20
_DLQ_LOOP_STARTED = False


def _ensure_dlq_loop():
    global _DLQ_LOOP_STARTED
    if _DLQ_LOOP_STARTED:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_dlq_flush_loop())
        _DLQ_LOOP_STARTED = True
    except RuntimeError:
        pass


async def _dlq_flush_loop():
    """Background flush loop: escreve buffer da DLQ em lote a cada 60s."""
    global _DLQ_BUFFER, _DLQ_LOOP_STARTED
    while True:
        await asyncio.sleep(_DLQ_FLUSH_INTERVAL)
        batch = []
        if _DLQ_BUFFER:
            batch = _DLQ_BUFFER[:]
            _DLQ_BUFFER = []
        if batch:
            await asyncio.to_thread(_flush_quarantine_batch, batch)


def _flush_quarantine_batch(entries: List[Dict[str, Any]]):
    """Síncrono: escreve lote de relatórios em disco."""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        ts = entry.get("timestamp", datetime.now(timezone.utc).isoformat())
        key_hash = hashlib.md5(entry.get("prompt", "").encode()).hexdigest()[:12]
        fname = f"cache_poison_{entry['reason']}_{ts[:10]}_{key_hash}.json"
        fname = fname.replace(" ", "_").replace(":", "-")
        path = QUARANTINE_DIR / fname
        try:
            path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
            barrier.record("quarantine_written", detail=f"dlq {fname}")
        except Exception as e:
            barrier.record("quarantine_failed", detail=str(e))


def _report_quarantine(prompt: str, value: str, reason: str, model_hint: str = "") -> None:
    """Bufferiza entrada na DLQ. Flush em lote acontece em background."""
    _ensure_dlq_loop()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "prompt_snippet": prompt[:200],
        "response_snippet": value[:200] if value else "",
        "response_length": len(value) if value else 0,
        "model_hint": model_hint,
        "source": "cache_immune_barrier",
    }
    _DLQ_BUFFER.append(entry)
    if len(_DLQ_BUFFER) >= _DLQ_MAX_BATCH:
        batch = _DLQ_BUFFER[:]
        _DLQ_BUFFER.clear()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(asyncio.to_thread(_flush_quarantine_batch, batch))
        except RuntimeError:
            _flush_quarantine_batch(batch)


# TTL padrão de 24h; 0 desliga expiração (compatibilidade legada).
CACHE_TTL_SECONDS = int(os.environ.get("IAGLOBAL_CACHE_TTL_SECONDS", "86400"))
# Comprimento mínimo de uma resposta válida (barreira imunológica).
MIN_VALID_LEN = int(os.environ.get("IAGLOBAL_CACHE_MIN_LEN", "16"))


_cache: Dict[str, Dict[str, Any]] = {}


def hash_prompt(prompt: str) -> str:
    """Hash prompt using MD5 for speed in L1 memory."""
    return hashlib.md5(prompt.encode()).hexdigest()


def _is_valid_response(value: str) -> bool:
    """Barreira imunológica: resposta metabolicamente válida precisa ser
    não-vazia, ter comprimento mínimo, e não ser recusa/alucinação
    (rejeita stubs/tóxicos e recusas curtas-mas-plausíveis)."""
    if not value or len(value.strip()) < MIN_VALID_LEN:
        return False
    return not is_refusal_or_hallucination(value)


def _entry_age_seconds(entry: Dict[str, Any]) -> float:
    return time.monotonic() - entry.get("stored_at", 0.0)


def _is_expired(entry: Dict[str, Any]) -> bool:
    if CACHE_TTL_SECONDS <= 0:
        return False
    return _entry_age_seconds(entry) > CACHE_TTL_SECONDS


def _parse_iso(ts: str) -> Optional[float]:
    """Converte timestamp ISO-8601 (UTC 'Z') em epoch segundos."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _is_stale_iso(ts: Optional[str]) -> bool:
    """Entrada L2 (wall-clock) mais antiga que o TTL é considerada obsoleta.

    Evita servir como sucesso fresco uma resposta gerada semanas atrás —
    isso produziria a métrica falsa 'provider vivo / success=True' quando o
    provedor real pode estar fora do ar hoje.
    """
    if CACHE_TTL_SECONDS <= 0 or not ts:
        return False
    parsed = _parse_iso(ts)
    if parsed is None:
        return False
    return (time.time() - parsed) > CACHE_TTL_SECONDS


def get_entry(prompt: str) -> Optional[Dict[str, Any]]:
    """Retorna a entrada válida do cache ou None (miss / vencida / tóxica).

    Aplica apoptose: entradas vencidas ou tóxicas são evictadas e um evento
    imunológico é registrado, em vez de serem servidas silenciosamente.
    Retorna dict {"value", "tokens", "stored_at"} quando íntegro.
    """
    key = hash_prompt(prompt)

    # 1. L1 (RAM)
    entry = _cache.get(key)
    if entry is not None:
        toxic = not _is_valid_response(entry.get("value", ""))
        expired = _is_expired(entry)
        if expired:
            _cache.pop(key, None)
            barrier.record("stale_cache", detail=f"l1 key={key[:12]}")
            return None
        if toxic:
            value = entry.get("value", "")
            _cache.pop(key, None)
            barrier.record("cache_poison", detail=f"l1 toxic key={key[:12]}")
            _report_quarantine(prompt, value, "refusal_or_hallucination")
            return None
        return entry

    # 2. L2 (SQLite persistente entre runs)
    try:
        l2 = get_success_by_task(prompt)
    except Exception:
        l2 = None
    if l2:
        value = l2.get("codigo") or ""
        tokens = (l2.get("metadata") or {}).get("tokens", 0)
        if not _is_valid_response(value):
            # Apoptose de entrada tóxica no L2 (não serve, registra evento).
            try:
                storage.delete(prompt)
            except Exception:
                pass
            barrier.record("cache_poison", detail=f"l2 toxic key={key[:12]}")
            _report_quarantine(prompt, value, "refusal_or_hallucination")
            return None
        # Apoptose por idade: entrada L2 sem timestamp recente não é servida
        # como sucesso fresco (evita métrica falsa de provider vivo).
        if CACHE_TTL_SECONDS > 0 and _is_stale_iso(l2.get("timestamp")):
            try:
                storage.delete(prompt)
            except Exception:
                pass
            barrier.record("stale_cache", detail=f"l2 aged key={key[:12]}")
            return None
        fresh = {"value": value, "tokens": tokens, "stored_at": time.monotonic()}
        _cache[key] = fresh
        return fresh

    return None


def get(prompt: str) -> Optional[str]:
    """API legada: retorna o valor em cache ou None (miss / vencido / tóxico)."""
    entry = get_entry(prompt)
    return entry["value"] if entry else None


def set(prompt: str, response: str, tokens: int = 0) -> None:
    """Armazena resposta (L1 RAM + L2 SQLite) preservando o token_count real."""
    _cache[hash_prompt(prompt)] = {
        "value": response,
        "tokens": tokens,
        "stored_at": time.monotonic(),
    }
    try:
        storage.store(prompt, response, metadata={"source": "cache", "tokens": tokens})
    except Exception:
        pass


def evict(prompt: str) -> None:
    """Apoptose explícita de uma entrada (L1 + L2)."""
    _cache.pop(hash_prompt(prompt), None)
    try:
        storage.delete(prompt)
    except Exception:
        pass


class Cache:
    """Cache class for centralized caching operations."""

    def __init__(self):
        self.data = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self.data:
            self.hits += 1
            return self.data[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def delete(self, key: str) -> None:
        if key in self.data:
            del self.data[key]

    def clear(self) -> None:
        self.data.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": total,
            "hit_rate": f"{hit_rate:.2f}%",
        }
