# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SnippetSynthesizer — Sintetiza múltiplos snippets em resumo coerente.

Funcionalidades:
1. synthesize(snippets) → Resumo + contradições + fontes
2. Detecção de consistência entre fontes
3. Resumo em português (3-4 frases)
4. Cache de sínteses para evitar chamadas repetidas

Integra com:
- SearchMiddleware (substitui concatenação bruta por síntese)
- BanditPolicy (chamada LLM otimizada)
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
    """Resultado da síntese de snippets."""
    summary: str  # Resumo coerente em português
    contradictions: List[str]  # Contradições detectadas (pode ser vazio)
    sources_used: List[str]  # URLs das fontes usadas
    confidence: float  # 0.0 - 1.0 (confiança na síntese)
    
    def to_dict(self) -> dict:
        return asdict(self)


class SnippetSynthesizer:
    """Sintetiza múltiplos snippets em resumo coerente via LLM."""

    # Prompt para síntese
    SYNTHESIS_PROMPT = """
Você é um sintetizador de informações web. Sua tarefa é analisar múltiplos snippets de busca e gerar um resumo coerente.

DADOS DE ENTRADA:
{snippets_formatted}

INSTRUÇÕES:
1. Identifique informações CONSISTENTES entre as fontes (o que todas/majoria concordam)
2. Detecte CONTRADIÇÕES claras (informações conflitantes entre fontes)
3. Gere um RESUMO em português de 3-4 frases com as informações principais
4. Liste quais fontes foram usadas para o resumo

IMPORTANTE:
- Seja direto e objetivo
- Se houver contradições, mencione de forma neutra
- Não invente informações não presentes nos snippets
- Mantenha o resumo em português claro e técnico

FORMATO DE SAÍDA (JSON estrito):
{{
  "summary": "resumo em 3-4 frases",
  "contradictions": ["contradição 1", null, ...],
  "sources_used": ["url1", "url2", ...],
  "confidence": 0.85
}}

RESPOSTA:"""

    # Cache de sínteses
    _cache: Dict[str, tuple] = {}
    _cache_ttl = 300.0  # 5 minutos

    # Estatísticas
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
            logger.debug("[SYNTHESIS] Cache hit para %d snippets", len(snippets))
            self._stats["cache_hits"] += 1
            return cached

        # Formatrar snippets para o prompt
        snippets_formatted = self._format_snippets(snippets)
        
        if not snippets_formatted.strip():
            return None

        # Chamar LLM
        synthesis = await self._call_llm(snippets_formatted)
        
        if not synthesis:
            return None

        # Validar e retornar
        result = SnippetSynthesis(
            summary=synthesis.get("summary", ""),
            contradictions=synthesis.get("contradictions", []),
            sources_used=synthesis.get("sources_used", []),
            confidence=synthesis.get("confidence", 0.5),
        )

        # Salvar no cache
        self._save_cache(cache_key, result)

        # Atualizar stats
        self._stats["calls"] += 1
        self._stats["llm_calls"] += 1
        self._stats["avg_confidence"] = (
            (self._stats["avg_confidence"] * (self._stats["llm_calls"] - 1) + result.confidence)
            / self._stats["llm_calls"]
        )

        logger.info(
            "[SYNTHESIS] %d snippets → %d chars (confiança=%.2f)",
            len(snippets), len(result.summary), result.confidence
        )

        return result

    def _cache_key(self, snippets: List[dict]) -> str:
        """Gera hash único para os snippets."""
        # Usar URLs + snippets para gerar key
        content = "|".join(
            f"{s.get('url', '')}:{s.get('snippet', '')[:100]}"
            for s in sorted(snippets, key=lambda x: x.get('url', ''))
        )
        return hashlib.sha3_512(content.encode()).hexdigest()[:32]

    def _check_cache(self, cache_key: str) -> Optional[SnippetSynthesis]:
        """Verifica se síntese está em cache."""
        if cache_key in self._cache:
            timestamp, synthesis = self._cache[cache_key]
            if (time.time() - timestamp) < self._cache_ttl:
                return synthesis
            else:
                del self._cache[cache_key]
        return None

    def _save_cache(self, cache_key: str, synthesis: SnippetSynthesis):
        """Salva síntese no cache."""
        self._cache[cache_key] = (time.time(), synthesis)
        
        # Limpar cache antigo (simples)
        if len(self._cache) > 100:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])
            del self._cache[oldest[0]]

    def _format_snippets(self, snippets: List[dict]) -> str:
        """Formata snippets para o prompt."""
        lines = []
        for i, snippet in enumerate(snippets, 1):
            url = snippet.get("url", "N/A")
            title = snippet.get("title", "Sem título")
            body = snippet.get("snippet", "Sem conteúdo")
            score = snippet.get("_source_score", snippet.get("score"))
            
            score_str = f" (score={score:.2f})" if score else ""
            lines.append(f"[{i}] {title}{score_str}")
            lines.append(f"    URL: {url}")
            lines.append(f"    Conteúdo: {body}")
            lines.append("")

        return "\n".join(lines)

    async def _call_llm(self, snippets_formatted: str) -> Optional[dict]:
        """Chama LLM para síntese via BanditPolicy."""
        try:
            from iaglobal.graphs.bandit import BanditPolicy
            
            prompt = self.SYNTHESIS_PROMPT.format(snippets_formatted=snippets_formatted)
            
            # Chamar LLM via BanditPolicy
            result = await BanditPolicy.generate(
                prompt=prompt,
                model=self.model,
                max_tokens=500,
                temperature=0.3,  # Baixa temperatura para consistência
            )

            if not result or not result.get("response"):
                logger.warning("[SYNTHESIS] LLM retornou vazio")
                return None

            # Parse JSON da resposta
            response_text = result["response"].strip()
            synthesis = self._parse_json_response(response_text)

            if not synthesis:
                logger.warning("[SYNTHESIS] Falha ao parsear JSON")
                # Fallback: síntese básica sem LLM
                return self._fallback_synthesis(snippets_formatted)

            return synthesis

        except Exception as e:
            logger.error("[SYNTHESIS] Erro na chamada LLM: %s", e)
            # Fallback para síntese básica
            return self._fallback_synthesis(snippets_formatted)

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON da resposta do LLM."""
        try:
            # Tentar JSON direto
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Tentar extrair JSON de markdown
        import re
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Tentar extrair JSON entre chaves
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _fallback_synthesis(self, snippets_formatted: str) -> dict:
        """Síntese fallback sem LLM (extrai informações principais)."""
        # Extrair URLs
        urls = []
        for line in snippets_formatted.split("\n"):
            if line.startswith("    URL:"):
                urls.append(line.replace("    URL:", "").strip())

        # Extrair primeiros snippets
        summaries = []
        for line in snippets_formatted.split("\n"):
            if line.startswith("["):
                parts = line.split("]", 1)
                if len(parts) > 1:
                    content = parts[1].strip()
                    if content and not content.startswith("URL:"):
                        summaries.append(content.split("(")[0].strip())

        # Criar resumo básico
        summary = " | ".join(summaries[:3]) if summaries else "Informações não disponíveis."
        
        return {
            "summary": summary[:300],  # Limitar tamanho
            "contradictions": [],
            "sources_used": urls[:3],
            "confidence": 0.5,  # Confiança baixa para fallback
        }

    def get_stats(self) -> dict:
        """Retorna estatísticas de uso."""
        return self._stats.copy()

    def clear_cache(self):
        """Limpa cache de sínteses."""
        self._cache.clear()
        logger.debug("[SYNTHESIS] Cache limpo")


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