# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes do SourceValidator — Fase 3 do RAG Autônomo.

Cobertura:
  - validate() retorna scores corretos
  - _score_domain para domínios conhecidos
  - _score_recency para datas variadas
  - _score_consistency detecta concordância/contradição
  - filter_by_score remove fontes abaixo do threshold
"""

import pytest
from datetime import datetime, timezone, timedelta

from iaglobal.search.source_validator import (
    SourceValidator,
    SourceScore,
    validate_source,
    filter_sources,
)


class TestSourceScore:
    """Testes da dataclass SourceScore."""

    def test_source_score_creation(self):
        """SourceScore deve criar com campos obrigatórios."""
        score = SourceScore(
            url="https://arxiv.org/abs/1234",
            domain="arxiv.org",
            credibility=0.95,
            recency=0.9,
            consistency=0.8,
            overall=0.89,
        )
        assert score.domain == "arxiv.org"
        assert score.credibility == 0.95
        assert score.overall == 0.89

    def test_source_score_to_dict(self):
        """to_dict deve serializar corretamente."""
        score = SourceScore(
            url="https://test.com",
            domain="test.com",
            credibility=0.7,
            recency=0.6,
            consistency=0.5,
            overall=0.62,
        )
        data = score.to_dict()
        assert data["url"] == "https://test.com"
        assert data["overall"] == 0.62


class TestSourceValidator:
    """Testes do SourceValidator."""

    @pytest.fixture
    def validator(self):
        """Cria validator com threshold padrão."""
        return SourceValidator(min_score=0.6)

    # ── Testes de _extract_domain ─────────────────────────────

    def test_extract_domain_simple(self, validator):
        """_extract_domain deve extrair domínio simples."""
        domain = validator._extract_domain("https://arxiv.org/abs/1234")
        assert domain == "arxiv.org"

    def test_extract_domain_with_www(self, validator):
        """_extract_domain deve remover www."""
        domain = validator._extract_domain("https://www.github.com/user/repo")
        assert domain == "github.com"

    def test_extract_domain_with_subdomain(self, validator):
        """_extract_domain deve remover subdomínios."""
        domain = validator._extract_domain("https://docs.python.org/3/library")
        assert domain == "python.org"

    def test_extract_domain_com_br(self, validator):
        """_extract_domain deve preservar .com.br."""
        domain = validator._extract_domain("https://www.site.com.br/page")
        assert domain == "site.com.br"

    # ── Testes de _score_domain ──────────────────────────────

    def test_score_domain_trusted_arxiv(self, validator):
        """_score_domain deve retornar score alto para arxiv."""
        score = validator._score_domain("arxiv.org")
        assert score == 0.95

    def test_score_domain_trusted_github(self, validator):
        """_score_domain deve retornar score alto para github."""
        score = validator._score_domain("github.com")
        assert score == 0.85

    def test_score_domain_trusted_subdomain(self, validator):
        """_score_domain deve retornar score alto para subdomínio confiável."""
        score = validator._score_domain("docs.python.org")
        assert score >= 0.90  # python.org * 0.95

    def test_score_domain_unknown(self, validator):
        """_score_domain deve retornar score neutro para desconhecido."""
        score = validator._score_domain("unknown-site.com")
        assert score == 0.50

    def test_score_domain_blacklisted(self, validator):
        """_score_domain deve retornar 0 para blacklist."""
        score = validator._score_domain("content-farm.com")
        assert score == 0.0

    def test_score_domain_empty(self, validator):
        """_score_domain deve retornar baixo para domínio vazio."""
        score = validator._score_domain("")
        assert score == 0.3

    # ── Testes de _score_recency ─────────────────────────────

    def test_score_recency_very_recent(self, validator):
        """_score_recency deve retornar 1.0 para < 30 dias."""
        date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        score = validator._score_recency(date)
        assert score == 1.0

    def test_score_recency_6_months(self, validator):
        """_score_recency deve retornar ~0.8 para 6 meses."""
        date = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        score = validator._score_recency(date)
        assert 0.7 <= score <= 0.9

    def test_score_recency_old(self, validator):
        """_score_recency deve retornar baixo para > 3 anos."""
        date = (datetime.now(timezone.utc) - timedelta(days=1200)).isoformat()
        score = validator._score_recency(date)
        assert score <= 0.5

    def test_score_recency_invalid_date(self, validator):
        """_score_recency deve retornar 0.5 para data inválida."""
        score = validator._score_recency("data-invalida")
        assert score == 0.5

    # ── Testes de _score_consistency ─────────────────────────

    def test_score_consistency_agreement(self, validator):
        """_score_consistency deve retornar alto para concordância."""
        snippet = {
            "title": "Python API",
            "snippet": "Flask is great for building APIs",
            "url": "url1",
        }
        all_snippets = [
            snippet,
            {
                "title": "Flask Tutorial",
                "snippet": "Flask is awesome for web development",
                "url": "url2",
            },
        ]
        score = validator._score_consistency(snippet, all_snippets)
        assert score >= 0.5  # Concordância (sobreposição de keywords)

    def test_score_consistency_contradiction(self, validator):
        """_score_consistency deve retornar baixo para contradição."""
        snippet = {
            "title": "API",
            "snippet": "Flask is recommended for production",
            "url": "url1",
        }
        all_snippets = [
            snippet,
            {
                "title": "API",
                "snippet": "Avoid Flask, don't use it in production",
                "url": "url2",
            },
        ]
        score = validator._score_consistency(snippet, all_snippets)
        assert score <= 0.5  # Contradição reduz score

    def test_score_consistency_no_others(self, validator):
        """_score_consistency deve retornar 0.5 se sem outros snippets."""
        snippet = {"title": "Test", "snippet": "Content", "url": "url1"}
        score = validator._score_consistency(snippet, [snippet])
        assert score == 0.5

    # ── Testes de validate (completo) ────────────────────────

    def test_validate_high_quality_source(self, validator):
        """validate deve retornar score alto para fonte confiável."""
        snippet = {
            "url": "https://arxiv.org/abs/2401.12345",
            "title": "Paper Title",
            "snippet": "Abstract content",
            "date": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        }
        score = validator.validate(snippet)
        assert score.overall >= 0.8
        assert score.credibility == 0.95  # arxiv.org

    def test_validate_low_quality_source(self, validator):
        """validate deve retornar score baixo para fonte não confiável."""
        snippet = {
            "url": "https://random-blog.com/post",
            "title": "Blog Post",
            "snippet": "Opinion content",
            "date": (datetime.now(timezone.utc) - timedelta(days=500)).isoformat(),
        }
        score = validator.validate(snippet)
        assert score.overall <= 0.6

    # ── Testes de filter_by_score ────────────────────────────

    def test_filter_by_score_removes_low(self, validator):
        """filter_by_score deve remover snippets abaixo do threshold."""
        snippets = [
            {"url": "https://arxiv.org/abs/123", "title": "Paper", "snippet": "Good"},
            {"url": "https://fake-news.org/post", "title": "Fake", "snippet": "Bad"},
        ]
        filtered = validator.filter_by_score(snippets, min_score=0.6)

        assert len(filtered) == 1
        assert "arxiv.org" in filtered[0]["url"]

    def test_filter_by_score_sorts_by_overall(self, validator):
        """filter_by_score deve ordenar por score (maior primeiro)."""
        snippets = [
            {"url": "https://medium.com/post", "title": "Blog", "snippet": "OK"},
            {"url": "https://arxiv.org/abs/123", "title": "Paper", "snippet": "Good"},
        ]
        filtered = validator.filter_by_score(snippets, min_score=0.5)

        assert len(filtered) == 2
        assert "arxiv.org" in filtered[0]["url"]  # Primeiro (maior score)


class TestSourceValidatorIntegration:
    """Testes de integração com SearchMiddleware."""

    def test_validate_source_wrapper(self):
        """validate_source wrapper deve funcionar."""
        snippet = {
            "url": "https://github.com/user/repo",
            "title": "Repo",
            "snippet": "Code",
        }
        score = validate_source(snippet)
        assert score.domain == "github.com"
        assert score.credibility >= 0.8

    def test_filter_sources_wrapper(self):
        """filter_sources wrapper deve funcionar."""
        snippets = [
            {"url": "https://arxiv.org/abs/123", "title": "Paper", "snippet": "Good"},
            {"url": "https://spam.com/post", "title": "Spam", "snippet": "Bad"},
        ]
        filtered = filter_sources(snippets, min_score=0.6)

        assert len(filtered) == 1
        assert "arxiv.org" in filtered[0]["url"]


class TestSourceValidatorE2E:
    """Testes end-to-end do SourceValidator."""

    def test_full_validation_pipeline(self):
        """Pipeline completo: validate → filter → sort."""
        validator = SourceValidator(min_score=0.6)

        snippets = [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "Deep Learning Paper",
                "snippet": "Novel approach to neural networks",
                "date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            },
            {
                "url": "https://github.com/user/ml-repo",
                "title": "ML Repository",
                "snippet": "Implementation of paper",
                "date": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            },
            {
                "url": "https://random-blog.com/opinion",
                "title": "Opinion Post",
                "snippet": "My thoughts on AI",
                "date": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
            },
        ]

        # Validar todos
        scores = [validator.validate(s, snippets) for s in snippets]

        # Verificar scores
        assert scores[0].overall > 0.8  # arxiv (alto)
        assert scores[1].overall > 0.7  # github (médio-alto)
        assert scores[2].overall < 0.6  # blog antigo (baixo)

        # Filtrar
        filtered = validator.filter_by_score(snippets, min_score=0.6)

        assert len(filtered) == 2  # arxiv + github
        assert "arxiv.org" in filtered[0]["url"]  # Primeiro (maior score)
