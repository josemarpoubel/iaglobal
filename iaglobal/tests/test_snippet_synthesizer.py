# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do SnippetSynthesizer — Fase 4 do RAG Autônomo.

Cobertura:
  - synthesize() retorna SnippetSynthesis
  - _parse_json_response para vários formatos
  - _fallback_synthesis quando LLM falha
  - Cache funciona corretamente
  - Stats são atualizados
"""

import asyncio
import pytest
import json
from unittest.mock import patch, AsyncMock  # O import deve estar aqui no topo

# ... restante dos seus imports ...

from iaglobal.search.snippet_synthesizer import (
    SnippetSynthesizer,
    SnippetSynthesis,
    get_snippet_synthesizer,
    synthesize_snippets,
    get_synthesis_stats,
)

class TestSnippetSynthesis:
    """Testes da dataclass SnippetSynthesis."""

    def test_snippet_synthesis_creation(self):
        """SnippetSynthesis should create with required fields."""
        synthesis = SnippetSynthesis(
            summary="Coherent summary in English.",
            contradictions=[],
            sources_used=["https://arxiv.org/abs/123"],
            confidence=0.85,
        )
        assert synthesis.summary == "Coherent summary in English."
        assert synthesis.confidence == 0.85

    def test_snippet_synthesis_to_dict(self):
        """to_dict should serialize correctly."""
        synthesis = SnippetSynthesis(
            summary="Test",
            contradictions=["contradiction"],
            sources_used=["url1"],
            confidence=0.7,
        )
        data = synthesis.to_dict()
        assert data["summary"] == "Test"
        assert data["contradictions"] == ["contradiction"]
        assert data["confidence"] == 0.7


class TestSnippetSynthesizer:
    """Testes do SnippetSynthesizer."""

    @pytest.fixture
    def synthesizer(self):
        """Cria synthesizer."""
        return SnippetSynthesizer(model="qwen2.5:0.5b")

    @pytest.fixture
    def sample_snippets(self):
        """Snippets de exemplo."""
        return [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "Deep Learning Paper",
                "snippet": "Novel approach to neural networks with 95% accuracy",
                "_source_score": 0.92,
            },
            {
                "url": "https://github.com/user/dl-repo",
                "title": "DL Implementation",
                "snippet": "Implementation of the paper with PyTorch",
                "_source_score": 0.85,
            },
        ]

    # ── Testes de _format_snippets ───────────────────────────

    def test_format_snippets_basic(self, synthesizer, sample_snippets):
        """_format_snippets deve formatar snippets corretamente."""
        formatted = synthesizer._format_snippets(sample_snippets)
        
        assert "Deep Learning Paper" in formatted
        assert "arxiv.org" in formatted
        assert "PyTorch" in formatted
        assert "score=0.92" in formatted

    def test_format_snippets_no_score(self, synthesizer):
        """_format_snippets deve lidar sem score."""
        snippets = [{"url": "url1", "title": "Test", "snippet": "Content"}]
        formatted = synthesizer._format_snippets(snippets)
        
        assert "Test" in formatted
        assert "score=" not in formatted  # Sem score

    # ── Testes de _parse_json_response ───────────────────────

    def test_parse_json_direct(self, synthesizer):
        """_parse_json_response deve parsear JSON direto."""
        response = '{"summary": "Test", "confidence": 0.8}'
        result = synthesizer._parse_json_response(response)
        
        assert result is not None
        assert result["summary"] == "Test"
        assert result["confidence"] == 0.8

    def test_parse_json_markdown(self, synthesizer):
        """_parse_json_response deve extrair JSON de markdown."""
        response = '```json\n{"summary": "Test", "confidence": 0.8}\n```'
        result = synthesizer._parse_json_response(response)
        
        assert result is not None
        assert result["summary"] == "Test"

    def test_parse_json_in_text(self, synthesizer):
        """_parse_json_response deve extrair JSON no meio do texto."""
        response = 'Aqui está o resultado: {"summary": "Test", "confidence": 0.8}'
        result = synthesizer._parse_json_response(response)
        
        assert result is not None
        assert result["summary"] == "Test"

    def test_parse_json_invalid(self, synthesizer):
        """_parse_json_response deve retornar None para JSON inválido."""
        response = 'Texto sem JSON válido'
        result = synthesizer._parse_json_response(response)
        
        assert result is None

    # ── Testes de _fallback_synthesis ────────────────────────

    def test_fallback_synthesis_basic(self, synthesizer, sample_snippets):
        """_fallback_synthesis deve criar resumo básico."""
        formatted = synthesizer._format_snippets(sample_snippets)
        result = synthesizer._fallback_synthesis(formatted)
        
        assert "summary" in result
        assert "sources_used" in result
        assert result["confidence"] == 0.5  # Confiança baixa
        assert len(result["sources_used"]) <= 3

    def test_fallback_synthesis_no_snippets(self, synthesizer):
        """_fallback_synthesis deve lidar sem snippets."""
        result = synthesizer._fallback_synthesis("")
        
        assert result["summary"] == "Informações não disponíveis."
        assert result["sources_used"] == []

    # ── Testes de cache ──────────────────────────────────────

    def test_cache_key_generation(self, synthesizer, sample_snippets):
        """_cache_key deve gerar hash consistente."""
        key1 = synthesizer._cache_key(sample_snippets)
        key2 = synthesizer._cache_key(sample_snippets)
        
        assert key1 == key2
        assert len(key1) == 32  # SHA3-512[:32]

    def test_cache_save_and_check(self, synthesizer, sample_snippets):
        """_check_cache deve retornar None se não em cache."""
        key = synthesizer._cache_key(sample_snippets)
        result = synthesizer._check_cache(key)
        
        assert result is None

    def test_cache_hit(self, synthesizer, sample_snippets):
        """Cache deve retornar valor salvo."""
        synthesis = SnippetSynthesis(
            summary="Test",
            contradictions=[],
            sources_used=["url1"],
            confidence=0.8,
        )
        key = synthesizer._cache_key(sample_snippets)
        synthesizer._save_cache(key, synthesis)
        
        result = synthesizer._check_cache(key)
        assert result is not None
        assert result.summary == "Test"

    def test_cache_ttl(self, synthesizer, sample_snippets):
        """Cache deve expirar após TTL."""
        synthesis = SnippetSynthesis(
            summary="Test",
            contradictions=[],
            sources_used=["url1"],
            confidence=0.8,
        )
        key = synthesizer._cache_key(sample_snippets)
        synthesizer._save_cache(key, synthesis)
        
        # Simular expiração (modificar timestamp)
        import time
        synthesizer._cache[key] = (time.time() - 400, synthesis)  # 400s atrás (> 300s TTL)
        
        result = synthesizer._check_cache(key)
        assert result is None  # Expirado

    def test_cache_cleanup(self, synthesizer):
        """Cache deve limpar entradas antigas quando > 100."""
        # Adicionar 101 entradas
        for i in range(101):
            key = f"key_{i}"
            synthesis = SnippetSynthesis(
                summary=f"Test {i}",
                contradictions=[],
                sources_used=[f"url{i}"],
                confidence=0.8,
            )
            synthesizer._cache[key] = (0, synthesis)  # Timestamp antigo
        
        # Salvar nova entrada deve trigger cleanup
        new_key = "new_key"
        new_synthesis = SnippetSynthesis(
            summary="New",
            contradictions=[],
            sources_used=["new_url"],
            confidence=0.9,
        )
        synthesizer._save_cache(new_key, new_synthesis)
        
        assert len(synthesizer._cache) <= 101

    # ── Testes de stats ──────────────────────────────────────

    def test_get_stats_initial(self, synthesizer):
        """Stats iniciais devem ter valores padrão."""
        stats = synthesizer.get_stats()
        
        assert stats["calls"] == 0
        assert stats["cache_hits"] == 0
        assert stats["llm_calls"] == 0

    def test_clear_cache(self, synthesizer, sample_snippets):
        """clear_cache deve limpar todas as entradas."""
        # Adicionar entradas
        for i in range(5):
            key = f"key_{i}"
            synthesis = SnippetSynthesis(
                summary=f"Test {i}",
                contradictions=[],
                sources_used=[f"url{i}"],
                confidence=0.8,
            )
            synthesizer._cache[key] = (0, synthesis)
        
        synthesizer.clear_cache()
        assert len(synthesizer._cache) == 0


class TestSnippetSynthesizerAsync:
    """Testes assíncronos do SnippetSynthesizer."""

    @pytest.fixture
    def synthesizer(self):
        """Cria synthesizer."""
        return SnippetSynthesizer(model="qwen2.5:0.5b")

    @pytest.fixture
    def sample_snippets(self):
        """Snippets de exemplo."""
        return [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "Paper",
                "snippet": "Content 1",
            },
            {
                "url": "https://github.com/user/repo",
                "title": "Repo",
                "snippet": "Content 2",
            },
        ]

    @pytest.mark.asyncio
    async def test_synthesize_empty_snippets(self, synthesizer):
        """synthesize deve retornar None para snippets vazios."""
        result = await synthesizer.synthesize([])
        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_no_content(self, synthesizer):
        """synthesize deve retornar fallback se sem conteúdo."""
        snippets = [{"url": "url1", "title": "", "snippet": ""}]
        result = await synthesizer.synthesize(snippets)
        
        # Deve retornar fallback (não None)
        assert result is not None
        assert "não disponíveis" in result.summary or result.summary == ""

    @pytest.mark.asyncio
    async def test_synthesize_with_fallback(self, synthesizer, sample_snippets):
        """synthesize deve usar fallback se LLM falhar."""
        from unittest.mock import AsyncMock, patch
        
        # Patch no import correto
        with patch('iaglobal.graphs.bandit.BanditPolicy.generate', new_callable=AsyncMock, side_effect=Exception("LLM error")):
            result = await synthesizer.synthesize(sample_snippets)
        
        # Deve retornar fallback
        assert result is not None
        assert result.summary != ""
        assert result.confidence == 0.5  # Confiança de fallback


class TestSnippetSynthesizerIntegration:
    """Testes de integração."""

    @pytest.mark.asyncio
    async def test_synthesize_snippets_wrapper(self):
        """synthesize_snippets wrapper deve funcionar."""
        snippets = [
            {"url": "url1", "title": "Test", "snippet": "Content"},
        ]
        
        # Deve retornar None ou SnippetSynthesis (depende do LLM)
        result = await synthesize_snippets(snippets)
        
        # Se retornar, deve ser SnippetSynthesis
        if result is not None:
            assert isinstance(result, SnippetSynthesis)

    def test_get_synthesis_stats_wrapper(self):
        """get_synthesis_stats wrapper deve funcionar."""
        stats = get_synthesis_stats()
        
        assert "calls" in stats
        assert "cache_hits" in stats


class TestSnippetSynthesizerE2E:
    """Testes end-to-end."""

    @pytest.mark.asyncio
    async def test_full_synthesis_pipeline(self):
        """Pipeline completo: format → synthesize → cache."""
        synthesizer = SnippetSynthesizer(model="qwen2.5:0.5b")
        
        snippets = [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "Deep Learning Advances",
                "snippet": "Novel transformer architecture achieves SOTA",
                "_source_score": 0.92,
            },
            {
                "url": "https://github.com/user/transformer",
                "title": "Transformer Implementation",
                "snippet": "PyTorch implementation with 95% accuracy",
                "_source_score": 0.85,
            },
            {
                "url": "https://docs.pytorch.org/tutorials",
                "title": "PyTorch Tutorial",
                "snippet": "Best practices for transformer training",
                "_source_score": 0.90,
            },
        ]
        
        # Sintetizar (vai usar fallback pois LLM não está disponível no teste)
        result = await synthesizer.synthesize(snippets)
        
        # Verificar resultado
        assert result is not None
        assert result.summary != ""
        assert len(result.sources_used) <= 3
        assert result.confidence >= 0.5
        
        # Verificar stats
        stats = synthesizer.get_stats()
        assert stats["calls"] >= 1
