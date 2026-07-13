# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SnippetSynthesizer — Sintese heuristica de snippets (SEM LLM).

Papel no organismo:
  - Consome snippets de busca web + RAG local
  - Aplica regras deterministicas para gerar resumo compacto
  - NÃO chama LLM diretamente (Lei da Obediencia / PSC)
  - Salva snapshot JSON em disco para o SynthesisPersistenceSweeper avaliar

Integra com:
  - SearchMiddleware (FASE 4: sintese opcional, habilitada via enable_synthesis)
  - SynthesisPersistenceSweeper (persistencia em disco + FakeNoiseDetector)
  - FusionEngine (dedup + Knowledge Graph no sweeper)

Nota: A sintese via LLM foi REMOVIDA. Apenas o CriticAgent pode escalar
para modelos externos. Este modulo e puramente heuristico.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.snippet_synthesizer")

# Diretorio de snapshots (produzido para o sweeper)
from iaglobal._paths import SYNTHESIS_JSON_DIR

SYNTHESIS_JSON_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# Dataclass de resultado
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SnippetSynthesis:
    """Resultado de sintese de snippets (heuristica, sem LLM)."""

    summary: str
    contradictions: List[str]
    sources_used: List[str]
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# SnippetSynthesizer (deterministico, sem LLM)
# ═══════════════════════════════════════════════════════════════════


class SnippetSynthesizer:
    """
    Sintese heuristica de snippets — SEM chamada a LLM.

    Usa regras deterministicas (tamanho, fonte, diversidade) para
    construir resumo compacto. O FakeNoiseDetector avaliara a qualidade
    no sweeper antes de persistir no banco.
    """

    # Cache em memoria com TTL
    _cache: Dict[str, tuple] = {}
    _cache_ttl: float = 300.0

    # Estatisticas
    _stats: Dict[str, Any] = {
        "calls": 0,
        "cache_hits": 0,
        "llm_calls": 0,  # sempre 0 — sem LLM
        "avg_confidence": 0.0,
    }

    def __init__(self, model: str = "qwen2.5:0.5b") -> None:
        self.model = model

    # ── entrada principal ──────────────────────────────────────────

    async def synthesize(self, snippets: List[dict]) -> Optional[SnippetSynthesis]:
        """
        Sintetiza snippets em resumo heuristico (sem LLM).

        Args:
            snippets: Lista de dicts com "url", "title", "snippet", "score"

        Returns:
            SnippetSynthesis com confidence=0.5 (heuristica pura)
        """
        if not snippets:
            return None

        cache_key = self._cache_key(snippets)

        # Cache hit
        cached = self._check_cache(cache_key)
        if cached:
            logger.debug("[SYNTHESIS] Cache hit (%d snippets)", len(snippets))
            self._stats["cache_hits"] += 1
            return cached

        snippets_formatted = self._format_snippets(snippets)
        if not snippets_formatted.strip():
            return None

        # Heuristica pura — sem LLM
        result = self._heuristic_synthesis(snippets_formatted, snippets)
        result_dict = result.to_dict()
        result_dict["cache_key"] = cache_key

        # Salva em cache RAM
        self._save_cache(cache_key, result)

        # Atualiza estatisticas
        self._stats["calls"] += 1
        n = self._stats["calls"]
        self._stats["avg_confidence"] = (
            self._stats["avg_confidence"] * (n - 1) + result.confidence
        ) / n

        logger.info(
            "[SYNTHESIS] %d snippets → %d chars (heuristic, conf=%.2f)",
            len(snippets),
            len(result.summary),
            result.confidence,
        )

        # Fire-and-forget: snapshot JSON para o sweeper avaliar
        if result.summary and result.summary != "Informações não disponíveis.":
            snapshot = {
                "cache_key": cache_key,
                "summary": result.summary,
                "confidence": result.confidence,
                "score": result.confidence,
                "source": "synthesis",
                "agent_id": "snippet_synthesizer",
                "created_at": _now_iso(),
                "snippets_input": [
                    {"url": s.get("url", ""), "snippet": s.get("snippet", "")[:120]}
                    for s in snippets
                ],
            }
            asyncio.ensure_future(
                _save_snapshot_async(cache_key=cache_key, data=snapshot)
            )

        return result

    # ── sintese heuristica (deterministica) ────────────────────────

    def _heuristic_synthesis(
        self,
        snippets_formatted: str,
        snippets: List[dict],
    ) -> SnippetSynthesis:
        """
        Sintese deterministica sem LLM.

        Estrategia:
          1. Extrai titulos e conteudos de cada snippet
          2. Remove duplicatas exatas por hash sha256
          3. Ordena por score (maior primeiro)
          4. Concatena top N com separadores
          5. Detecta contradicoes por keywords (Jaccard + negacao)
          6.confidence fixa = 0.5 (sem LLM = sem certeza semantica)
        """
        summaries: List[str] = []
        urls: List[str] = []
        seen_hashes: set = set()

        for s in snippets:
            url = s.get("url", "")
            title = (s.get("title") or "").strip()
            body = (s.get("snippet") or "").strip()

            if url:
                urls.append(url)

            # Hash do conteudo para dedup exato
            content_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
            if content_hash in seen_hashes or not body:
                continue
            seen_hashes.add(content_hash)

            if title and title != "No title":
                summaries.append(f"{title}: {body}")
            else:
                summaries.append(body)

        # Monta resumo final (top 3 snippets unicos)
        if not summaries:
            summary = "Informações não disponíveis."
        else:
            # Ordenar por score (maior primeiro)
            scored = list(zip(snippets, summaries))
            scored.sort(
                key=lambda x: x[0].get("_source_score", x[0].get("score", 0) or 0),
                reverse=True,
            )
            top = [s for _, s in scored[:3]]
            summary = " | ".join(top)

        # Limitacao de tamanho
        summary = summary[:300]

        # Contradicoes: comparar todos contra todos (Jaccard + negacao)
        contradictions = self._detect_contradictions(snippets)

        return SnippetSynthesis(
            summary=summary,
            contradictions=contradictions,
            sources_used=urls[:3],
            confidence=0.5,
        )

    def _detect_contradictions(self, snippets: List[dict]) -> List[str]:
        """Detecta contradicoes por Jaccard + negacao entre snippets."""
        contradictions: List[str] = []
        texts = []
        for s in snippets:
            body = (s.get("snippet") or "").strip()
            if body:
                texts.append(body.lower())

        import re as _re

        neg_pattern = _re.compile(r"\b(não|not|never|nunca)\b", _re.IGNORECASE)
        word_pattern = _re.compile(r"\b[a-z]{4,}\b", _re.IGNORECASE)

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, b = texts[i], texts[j]
                kw_a = set(word_pattern.findall(a))
                kw_b = set(word_pattern.findall(b))
                if not kw_a or not kw_b:
                    continue
                overlap = len(kw_a & kw_b)
                total = len(kw_a | kw_b)
                if total == 0:
                    continue
                jaccard = overlap / total
                if 0.2 < jaccard < 0.7:
                    neg_a = bool(neg_pattern.search(a))
                    neg_b = bool(neg_pattern.search(b))
                    if neg_a != neg_b:
                        contradictions.append(
                            f"Contradicao entre fonte {i + 1} e {j + 1} (Jaccard={jaccard:.2f})"
                        )
        return contradictions[:3]  # Max 3 contradicoes reportadas

    # ── cache ──────────────────────────────────────────────────────

    def _cache_key(self, snippets: List[dict]) -> str:
        content = "|".join(
            f"{s.get('url', '')}:{s.get('snippet', '')[:100]}"
            for s in sorted(snippets, key=lambda x: x.get("url", ""))
        )
        return hashlib.sha3_512(content.encode()).hexdigest()[:32]

    def _check_cache(self, cache_key: str) -> Optional[SnippetSynthesis]:
        ts, synth = self._cache.get(cache_key, (0, None))
        if synth and (time.time() - ts) < self._cache_ttl:
            return synth
        if cache_key in self._cache:
            del self._cache[cache_key]
        return None

    def _save_cache(self, cache_key: str, synthesis: SnippetSynthesis) -> None:
        self._cache[cache_key] = (time.time(), synthesis)
        if len(self._cache) > 100:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])
            del self._cache[oldest[0]]

    # ─- formatacao ─────────────────────────────────────────────────

    def _format_snippets(self, snippets: List[dict]) -> str:
        lines: List[str] = []
        for i, s in enumerate(snippets, 1):
            url = s.get("url", "N/A")
            title = s.get("title", "No title")
            body = s.get("snippet", "No content")
            score = s.get("_source_score", s.get("score"))
            score_str = f" (score={score:.2f})" if score else ""
            lines.append(f"[{i}] {title}{score_str}")
            lines.append(f" URL: {url}")
            lines.append(f" Content: {body}")
            lines.append("")
        return "\n".join(lines)

    # ── estatisticas ───────────────────────────────────────────────

    # ── compatibilidade (sem LLM — PSC safe) ──────────────────────

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """
        Parse JSON de texto (estatico — sem LLM envolvido).

        Usado pelos testes de regressao e pelo fallback quando
        resposta contem JSON embutido. Nao viola PSC pois nao
        faz chamada a modelo externo — apenas parse estatico.
        """
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        _re2 = __import__("re")
        match = _re2.search(r"```json\\s*(.*?)\\s*```", response, _re2.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = _re2.search(r"\{.*\}", response, _re2.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _fallback_synthesis(self, snippets_formatted: str) -> dict:
        """Stub: sintese heuristica como fallback (sem chamada a LLM)."""
        snippets = self._format_snippets_to_list(snippets_formatted)
        result = self._heuristic_synthesis(snippets_formatted, snippets)
        return result.to_dict()

    def _format_snippets_to_list(self, snippets_formatted: str) -> List[dict]:
        """Reconstrói lista de dicts a partir do texto formatado."""
        snippets: List[dict] = []
        current: dict = {}
        for raw_line in snippets_formatted.split("\n"):
            line = raw_line.strip()
            if line.startswith("["):
                if current:
                    snippets.append(current)
                current = {}
            elif line.startswith(" URL:"):
                current["url"] = line.replace(" URL:", "").strip()
            elif line.startswith(" Content:"):
                current["snippet"] = line.replace(" Content:", "").strip()
            elif line.startswith("["):
                current["title"] = line.strip("[] ").strip()
        if current:
            snippets.append(current)
        return snippets

    def get_stats(self) -> dict:
        return self._stats.copy()

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.debug("[SYNTHESIS] Cache cleared")


# ═══════════════════════════════════════════════════════════════════
# Persistencia de snapshot (fire-and-forget para o sweeper)
# ═══════════════════════════════════════════════════════════════════


async def _save_snapshot_async(cache_key: str, data: dict) -> None:
    """
    Salva snapshot JSON em disco (thread-safe via asyncio.to_thread).
    O SynthesisPersistenceSweeper consume estes arquivos periodicamente.
    """
    try:
        from iaglobal._paths import SYNTHESIS_JSON_DIR

        path = SYNTHESIS_JSON_DIR / f"{cache_key}.json"
        await asyncio.to_thread(_write_snapshot, path, data)
    except Exception as exc:
        logger.debug("[SYNTHESIS] Falha ao salvar snapshot: %s", exc)


def _write_snapshot(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None)
    tmp.replace(path)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ═══════════════════════════════════════════════════════════════════
# Singleton + wrappers
# ═══════════════════════════════════════════════════════════════════

_synthesizer: Optional[SnippetSynthesizer] = None


def get_snippet_synthesizer(model: str = "qwen2.5:0.5b") -> SnippetSynthesizer:
    """Retorna singleton do SnippetSynthesizer."""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = SnippetSynthesizer(model=model)
    return _synthesizer


async def synthesize_snippets(snippets: List[dict]) -> Optional[SnippetSynthesis]:
    """Wrapper async para SnippetSynthesizer.synthesize()."""
    return await get_snippet_synthesizer().synthesize(snippets)


def get_synthesis_stats() -> dict:
    """Wrapper para estatisticas."""
    return get_snippet_synthesizer().get_stats()
