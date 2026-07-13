# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SynthesisPersistenceSweeper — Autofagia de sínteses: filtra, persiste e limpa.

Papel no organismo:
  1. Varre snapshots JSON em disco (json/synthesis/)
  2. Aplica FakeNoiseDetector.should_keep() → filtra lixo
  3. Aplica FusionEngine (dedup + KG) → evita redundância
  4. Persiste em core.db (synthesis_cache) e índice CBOR2 compacto
  5. Remove JSONs processados (autofagia — não deixa lixo acumular)

Integra com:
  - SnippetSynthesizer (produtor de snapshots)
  - FakeNoiseDetector (filtro de qualidade)
  - FusionEngine (dedup + conhecimento)
  - DatabaseManager (persistência SQLite)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from iaglobal._paths import CBOR2_DIR, JSON_DIR, SYNTHESIS_JSON_DIR
from iaglobal.memory.db_manager import db
from iaglobal.memory.fusion_engine import FakeNoiseDetector, FusionEngine
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.synthesis_sweeper")

# Garante que diretório existe (boot-safe)
SYNTHESIS_JSON_DIR.mkdir(parents=True, exist_ok=True)

# Índice CBOR2 para leitura massiva por agentes/LLM
SYNTHESIS_CBOR2 = CBOR2_DIR / "synthesis_index.cbor2"

# Configurações do sweeper
_SWEEPER_MIN_CONFIDENCE: float = 0.5
_SWEEPER_BATCH_SIZE: int = 50
_SWEEPER_MAX_AGE_SECONDS: int = 48 * 3600  # 48 horas


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _summary_hash(summary: str) -> str:
    return hashlib.sha256(summary.encode()).hexdigest()[:32]


class SynthesisPersistenceSweeper:
    """
    Varre, filtra e persiste sínteses em disco.

    Uso:
      sweeper = SynthesisPersistenceSweeper()
      result = await sweeper.run()

    Ou agendado periodicamente:
      asyncio.create_task(sweeper.run_periodic(interval_seconds=300))
    """

    def __init__(
        self,
        json_dir: Path = SYNTHESIS_JSON_DIR,
        cbor2_path: Path = SYNTHESIS_CBOR2,
        min_confidence: float = _SWEEPER_MIN_CONFIDENCE,
        batch_size: int = _SWEEPER_BATCH_SIZE,
        max_age_seconds: int = _SWEEPER_MAX_AGE_SECONDS,
    ) -> None:
        self.json_dir = Path(json_dir)
        self.cbor2_path = Path(cbor2_path)
        self.min_confidence = min_confidence
        self.batch_size = batch_size
        self.max_age_seconds = max_age_seconds

        self.noise_detector = FakeNoiseDetector()
        self.fusion_engine = FusionEngine()
        self._processed_hashes: set[str] = set()

    # ── descoberta de arquivos ──────────────────────────────────────

    def _list_pending_files(self) -> list[Path]:
        """Lista JSONs pendentes, ordenados por idade (mais antigos primeiro)."""
        if not self.json_dir.exists():
            return []
        files = list(self.json_dir.glob("*.json"))
        files.sort(key=lambda p: p.stat().st_mtime)
        return files

    def _is_expired(self, path: Path) -> bool:
        age = time.time() - path.stat().st_mtime
        return age > self.max_age_seconds

    # ── carga e parse ──────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("[SWEEPER] JSON inválido %s: %s", path.name, exc)
            return None

    def _save_failure(self, path: Path, reason: str) -> None:
        """Move JSON problemático para a pasta de erros para inspeção."""
        error_dir = JSON_DIR.parent / "error"
        error_dir.mkdir(parents=True, exist_ok=True)
        dest = error_dir / f"synthesis_{int(time.time() * 1000)}_{path.name}"
        try:
            path.rename(dest)
            logger.debug("[SWEEPER] Movido para error: %s (%s)", dest.name, reason)
        except OSError:
            path.unlink(missing_ok=True)

    # ── persistência SQLite ─────────────────────────────────────────

    def _persist_sqlite(self, record: dict) -> bool:
        """
        INSERT OR IGNORE no core.db → tabela synthesis_cache.
        Retorna True se foi inserido, False se já existia.
        """
        try:
            conn = db._get_conn()
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO synthesis_cache
                        (cache_key, summary, confidence, score, agent_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["cache_key"],
                        record["summary"],
                        record["confidence"],
                        record["score"],
                        record.get("agent_id", "unknown"),
                        record.get("created_at", _now_iso()),
                    ),
                )
                conn.commit()
                return conn.total_changes > 0
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[SWEEPER] Falha ao persistir SQLite: %s", exc)
            return False

    # ── índice CBOR2 ────────────────────────────────────────────────

    def _update_cbor2_index(self, records: list[dict]) -> None:
        """
        Atualiza índice CBOR2 compacto para leitura massiva por agentes/LLM.
        Estrutura: dict[cache_key, record] serializado como CBOR2.
        """
        existing: dict[str, dict] = {}
        if self.cbor2_path.exists():
            try:
                import cbor2

                with open(self.cbor2_path, "rb") as f:
                    existing = cbor2.load(f)
                if not isinstance(existing, dict):
                    existing = {}
            except Exception as exc:
                logger.debug("[SWEEPER] CBOR2 corrompido, recriando: %s", exc)
                existing = {}

        for rec in records:
            existing[rec["cache_key"]] = {
                "summary": rec["summary"],
                "confidence": rec["confidence"],
                "score": rec["score"],
                "agent_id": rec.get("agent_id", "unknown"),
                "created_at": rec.get("created_at", _now_iso()),
            }

        try:
            import cbor2

            self.cbor2_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cbor2_path, "wb") as f:
                cbor2.dump(existing, f)
        except Exception as exc:
            logger.error("[SWEEPER] Falha ao escrever CBOR2: %s", exc)

    # ── pipeline principal ──────────────────────────────────────────

    def _process_record(self, data: dict, path: Path) -> dict | None:
        """
        Aplica gatekeeper (FakeNoiseDetector) + dedup (FusionEngine)
        e retorna dict normalizado para persistência.
        """
        # Campos esperados
        summary = data.get("summary", "").strip()
        if not summary:
            self._save_failure(path, "summary vazio")
            return None

        # Normaliza fonte para avaliação
        source = data.get("source", "synthesis")
        item_for_scoring = {
            "source": FakeNoiseDetector._normalize_source(source),
            "content": summary,
            "text": summary,
        }

        # Gatekeeper: ruído + confiança mínima
        if not self.noise_detector.should_keep(
            item_for_scoring, min_confidence=self.min_confidence
        ):
            logger.debug("[SWEEPER] Descartado %s (ruído/confiança baixa)", path.name)
            self._save_failure(path, "noise_or_low_confidence")
            return None

        # Dedup via FusionEngine (hash exato + similaridade)
        cache_key = _summary_hash(summary)
        if cache_key in self._processed_hashes:
            logger.debug("[SWEEPER] Duplicado %s", cache_key)
            path.unlink(missing_ok=True)
            return None

        # Score de confiança oficial
        confidence = round(self.noise_detector.score_confidence(item_for_scoring), 4)

        # Integração com Knowledge Graph do FusionEngine
        self.fusion_engine.kg.extract_and_store(summary, source="synthesis")

        return {
            "cache_key": cache_key,
            "summary": summary,
            "confidence": confidence,
            "score": confidence,
            "agent_id": data.get("agent_id", "unknown"),
            "created_at": data.get("created_at", _now_iso()),
            "source": data.get("source", "synthesis"),
            "raw_path": str(path),
        }

    async def run(self, max_files: int | None = None) -> dict:
        """
        Executa uma passada de limpeza e persistência.

        Returns:
            dict com estatísticas: processed, persisted, discarded, errors
        """
        start = time.monotonic()
        pending = self._list_pending_files()
        if max_files is not None:
            pending = pending[:max_files]

        stats = {
            "scanned": len(pending),
            "processed": 0,
            "persisted": 0,
            "discarded": 0,
            "errors": 0,
            "duration_s": 0.0,
        }

        if not pending:
            logger.debug("[SWEEPER] Nenhum snapshot pendente")
            stats["duration_s"] = round(time.monotonic() - start, 3)
            return stats

        to_persist: list[dict] = []

        for path in pending:
            # Remove arquivos expirados imediatamente
            if self._is_expired(path):
                path.unlink(missing_ok=True)
                stats["discarded"] += 1
                continue

            data = await asyncio.to_thread(self._load_json, path)
            if data is None:
                stats["errors"] += 1
                path.unlink(missing_ok=True)
                continue

            record = self._process_record(data, path)
            if record is None:
                stats["discarded"] += 1
                continue

            stats["processed"] += 1
            self._processed_hashes.add(record["cache_key"])
            to_persist.append(record)

            # Remove JSON processado (autofagia)
            path.unlink(missing_ok=True)

        # Lote de persistência SQLite (em thread para não bloquear event loop)
        if to_persist:
            persisted = await asyncio.to_thread(self._batch_persist_sqlite, to_persist)
            stats["persisted"] = persisted
            # Atualiza índice CBOR2
            await asyncio.to_thread(self._update_cbor2_index, to_persist)

        stats["duration_s"] = round(time.monotonic() - start, 3)
        logger.info(
            "[SWEEPER] %(scanned)d escaneados | %(processed)d processados | "
            "%(persisted)d persistidos | %(discarded)d descartados | "
            "%(errors)d erros | %(duration_s).2fs",
            stats,
        )
        return stats

    def _batch_persist_sqlite(self, records: list[dict]) -> int:
        """Insere lote em SQLite, retorna quantidade inserida."""
        count = 0
        try:
            conn = db._get_conn()
            try:
                with conn:
                    for rec in records:
                        try:
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO synthesis_cache
                                    (cache_key, summary, confidence, score, agent_id, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    rec["cache_key"],
                                    rec["summary"],
                                    rec["confidence"],
                                    rec["score"],
                                    rec.get("agent_id", "unknown"),
                                    rec.get("created_at", _now_iso()),
                                ),
                            )
                            if conn.total_changes > 0:
                                count += 1
                        except Exception as exc:
                            logger.debug(
                                "[SWEEPER] Falha ao inserir %s: %s",
                                rec.get("cache_key", "?"),
                                exc,
                            )
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[SWEEPER] Falha no lote SQLite: %s", exc)
        return count

    async def run_periodic(self, interval_seconds: float = 300.0) -> None:
        """Loop periódico de limpeza (fire-and-forget)."""
        logger.info(
            "[SWEEPER] Loop periódico iniciado (intervalo=%.0fs)", interval_seconds
        )
        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("[SWEEPER] Erro no loop periódico: %s", exc)
            await asyncio.sleep(interval_seconds)

    def prune_cbor2(self, max_age_seconds: int | None = None) -> int:
        """
        Remove entradas do índice CBOR2 que não existem mais no SQLite.
        Retorna quantidade removida.
        """
        max_age = max_age_seconds or self.max_age_seconds
        cutoff = time.time() - max_age

        existing: dict[str, dict] = {}
        removed = 0

        if self.cbor2_path.exists():
            try:
                import cbor2

                with open(self.cbor2_path, "rb") as f:
                    existing = cbor2.load(f)
                if not isinstance(existing, dict):
                    return 0
            except Exception as exc:
                logger.debug("[SWEEPER] CBOR2 ilegível no prune: %s", exc)
                return 0

        keys_to_remove: list[str] = []
        try:
            conn = db._get_conn()
            try:
                for key in existing:
                    row = conn.execute(
                        "SELECT cache_key FROM synthesis_cache WHERE cache_key = ?",
                        (key,),
                    ).fetchone()
                    if row is None:
                        keys_to_remove.append(key)
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[SWEEPER] Falha no prune SQLite: %s", exc)
            return 0

        for key in keys_to_remove:
            del existing[key]
            removed += 1

        if removed:
            try:
                import cbor2

                with open(self.cbor2_path, "wb") as f:
                    cbor2.dump(existing, f)
            except Exception as exc:
                logger.error("[SWEEPER] Falha ao reescrever CBOR2 no prune: %s", exc)

        if removed:
            logger.info("[SWEEPER] prune_cbor2 removeu %d entradas órfãs", removed)
        return removed


# Instância global para uso direto
synthesis_sweeper = SynthesisPersistenceSweeper()


async def run_synthesis_sweeper(max_files: int | None = None) -> dict:
    """Wrapper async para execução pontual do sweeper."""
    return await synthesis_sweeper.run(max_files=max_files)
