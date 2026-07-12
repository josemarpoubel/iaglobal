# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SnippetSynthesizer — Synthesizes multiple snippets into coherent summary.

Functionalities:
1. synthesize(snippets) → Summary + contradictions + sources
2. Consistency detection between sources
3. Summary in English (3-4 sentences)
4. Cache of syntheses to avoid repeated calls

Integrates with:
- SearchMiddleware (replaces brute concatenation with synthesis)
- BanditPolicy (optimized LLM call)
"""

import asyncio
import hashlib
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.snippet_synthesizer")


@dataclass
class SnippetSynthesis:
    """Result of snippet synthesis."""
    summary: str  # Coherent summary in English
    contradictions: List[str]  # Detected contradictions (may be empty)
    sources_used: List[str]  # URLs of sources used
    confidence: float  # 0.0 - 1.0 (confidence in synthesis)
    
    def to_dict(self) -> dict:
        return asdict(self)


class SnippetSynthesizer:
    """Synthesizes multiple snippets into coherent summary via LLM."""

    # Prompt for synthesis
    SYNTHESIS_PROMPT = """
You are a web information synthesizer. Your task is to analyze multiple search snippets and generate a coherent summary.

INPUT DATA:
{snippets_formatted}

INSTRUCTIONS:
1. Identify CONSISTENT information across sources (what all/most agree on)
2. Detect clear CONTRADICTIONS (conflicting information between sources)
3. Generate an ENGLISH SUMMARY of 3-4 sentences with the main information
4. List which sources were used for the summary

IMPORTANT:
- Be direct and objective
- If there are contradictions, mention them neutrally
- Do not invent information not present in the snippets
- Keep the summary clear and technical in English

OUTPUT FORMAT (strict JSON):
{{
  "summary": "summary in 3-4 sentences",
  "contradictions": ["contradiction 1", null, ...],
  "sources_used": ["url1", "url2", ...],
  "confidence": 0.85
}}

RESPONSE:"""

    # Synthesis cache
    _cache: Dict[str, tuple] = {}
    _cache_ttl = 300.0  # 5 minutes

    # Statistics
    _stats = {
        "calls": 0,
        "cache_hits": 0,
        "llm_calls": 0,
        "avg_confidence": 0.0,
    }

    def __init__(self, model: str = "qwen2.5:0.5b"):
        self.model = model

    async def synthesize(self, snippets: List[dict]) -> Optional[SnippetSynthesis]:
        """
        Sintetiza múltiplos snippets em resumo coerente.

        Args:
            snippets: Lista de dicts com "url", "title", "snippet", "score" (opcional)

        Returns:
            SnippetSynthesis ou None se falha
        """
        if not snippets or len(snippets) < 1:
            return None

        # Gerar cache key
        cache_key = self._cache_key(snippets)
        
        # Check cache
        cached = self._check_cache(cache_key)
        if cached:
            logger.debug("[SYNTHESIS] Cache hit for %d snippets", len(snippets))
            self._stats["cache_hits"] += 1
            return cached

        # Format snippets for prompt
        snippets_formatted = self._format_snippets(snippets)
        
        if not snippets_formatted.strip():
            return None

        # Call LLM
        synthesis = await self._call_llm(snippets_formatted)
        
        if not synthesis:
            return None

        # Validate and return
        result = SnippetSynthesis(
            summary=synthesis.get("summary", ""),
            contradictions=synthesis.get("contradictions", []),
            sources_used=synthesis.get("sources_used", []),
            confidence=synthesis.get("confidence", 0.5),
        )

        # Save to cache
        self._save_cache(cache_key, result)

        # Update stats
        self._stats["calls"] += 1
        self._stats["llm_calls"] += 1
        self._stats["avg_confidence"] = (
            (self._stats["avg_confidence"] * (self._stats["llm_calls"] - 1) + result.confidence)
            / self._stats["llm_calls"]
        )

        logger.info(
            "[SYNTHESIS] %d snippets → %d chars (confidence=%.2f)",
            len(snippets), len(result.summary), result.confidence
        )

        return result

    def _cache_key(self, snippets: List[dict]) -> str:
        """Generates unique hash for snippets."""
        # Use URLs + snippets to generate key
        content = "|".join(
            f"{s.get('url', '')}:{s.get('snippet', '')[:100]}"
            for s in sorted(snippets, key=lambda x: x.get('url', ''))
        )
        return hashlib.sha3_512(content.encode()).hexdigest()[:32]

    def _check_cache(self, cache_key: str) -> Optional[SnippetSynthesis]:
        """Checks if synthesis is in cache."""
        if cache_key in self._cache:
            timestamp, synthesis = self._cache[cache_key]
            if (time.time() - timestamp) < self._cache_ttl:
                return synthesis
            else:
                del self._cache[cache_key]
        return None

    def _save_cache(self, cache_key: str, synthesis: SnippetSynthesis):
        """Saves synthesis to cache."""
        self._cache[cache_key] = (time.time(), synthesis)
        
        # Clear old cache (simple)
        if len(self._cache) > 100:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])
            del self._cache[oldest[0]]

    def _format_snippets(self, snippets: List[dict]) -> str:
        """Formats snippets for prompt."""
        lines = []
        for i, snippet in enumerate(snippets, 1):
            url = snippet.get("url", "N/A")
            title = snippet.get("title", "No title")
            body = snippet.get("snippet", "No content")
            score = snippet.get("_source_score", snippet.get("score"))
            
            score_str = f" (score={score:.2f})" if score else ""
            lines.append(f"[{i}] {title}{score_str}")
            lines.append(f"    URL: {url}")
            lines.append(f"    Content: {body}")
            lines.append("")

        return "\n".join(lines)

    async def _call_llm(self, snippets_formatted: str) -> Optional[dict]:
        """Calls LLM for synthesis via BanditPolicy."""
        try:
            from iaglobal.graphs.bandit import BanditPolicy
            
            prompt = self.SYNTHESIS_PROMPT.format(snippets_formatted=snippets_formatted)
            
            # Call LLM via BanditPolicy
            result = await BanditPolicy.generate(
                prompt=prompt,
                model=self.model,
                max_tokens=500,
                temperature=0.3,  # Low temperature for consistency
            )

            if not result or not result.get("response"):
                logger.warning("[SYNTHESIS] LLM returned empty")
                return None

            # Parse JSON from response
            response_text = result["response"].strip()
            synthesis = self._parse_json_response(response_text)

            if not synthesis:
                logger.warning("[SYNTHESIS] Failed to parse JSON")
                # Fallback: basic synthesis without LLM
                return self._fallback_synthesis(snippets_formatted)

            return synthesis

        except Exception as e:
            logger.error("[SYNTHESIS] Error in LLM call: %s", e)
            # Fallback to basic synthesis
            return self._fallback_synthesis(snippets_formatted)

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response."""
        try:
            # Try direct JSON
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown
        import re
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to extract JSON between braces
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _fallback_synthesis(self, snippets_formatted: str) -> dict:
        """Fallback synthesis without LLM (extracts main information)."""
        # Extract URLs
        urls = []
        for line in snippets_formatted.split("\n"):
            if line.startswith("    URL:"):
                urls.append(line.replace("    URL:", "").strip())

        # Extract first snippets
        summaries = []
        for line in snippets_formatted.split("\n"):
            if line.startswith("["):
                parts = line.split("]", 1)
                if len(parts) > 1:
                    content = parts[1].strip()
                    if content and not content.startswith("URL:"):
                        summaries.append(content.split("(")[0].strip())

        # Create basic summary
        summary = " | ".join(summaries[:3]) if summaries else "Information not available."
        
        return {
            "summary": summary[:300],  # Limit size
            "contradictions": [],
            "sources_used": urls[:3],
            "confidence": 0.5,  # Low confidence for fallback
        }

    def get_stats(self) -> dict:
        """Returns usage statistics."""
        return self._stats.copy()

    def clear_cache(self):
        """Clears synthesis cache."""
        self._cache.clear()
        logger.debug("[SYNTHESIS] Cache cleared")


# Singleton global
_synthesizer: Optional[SnippetSynthesizer] = None


def get_snippet_synthesizer(model: str = "qwen2.5:0.5b") -> SnippetSynthesizer:
    """Retorna singleton do SnippetSynthesizer."""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = SnippetSynthesizer(model=model)
    return _synthesizer


# Funções utilitárias
async def synthesize_snippets(snippets: List[dict]) -> Optional[SnippetSynthesis]:
    """Wrapper para SnippetSynthesizer.synthesize()."""
    return await get_snippet_synthesizer().synthesize(snippets)


def get_synthesis_stats() -> dict:
    """Wrapper para estatísticas."""
    return get_snippet_synthesizer().get_stats()