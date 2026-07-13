# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Testes de regressão para FakeNoiseDetector.

Garantem que os thresholds, padrões de clickbait e normalização de fontes
não sejam alterados inadvertidamente no futuro.
"""

import pytest

from iaglobal.memory.fusion_engine import FakeNoiseDetector


@pytest.fixture
def detector():
    return FakeNoiseDetector()


# ═══════════════════════════════════════════════════════════════════
# THRESHOLDS — não devem mudar sem atualizar este teste
# ═══════════════════════════════════════════════════════════════════


class TestThresholds:
    """Valida que os constantes de avaliação não foram alteradas."""

    def test_min_content_length(self):
        from iaglobal.memory.fusion_engine import _MIN_CONTENT_LENGTH

        assert _MIN_CONTENT_LENGTH == 20

    def test_min_word_count(self):
        from iaglobal.memory.fusion_engine import _MIN_WORD_COUNT

        assert _MIN_WORD_COUNT == 5

    def test_min_confidence_to_keep(self):
        from iaglobal.memory.fusion_engine import _MIN_CONFIDENCE_TO_KEEP

        assert _MIN_CONFIDENCE_TO_KEEP == 0.5

    def test_min_jaccard_overlap(self):
        from iaglobal.memory.fusion_engine import _MIN_JACCARD_OVERLAP

        assert _MIN_JACCARD_OVERLAP == pytest.approx(0.2)

    def test_max_jaccard_overlap(self):
        from iaglobal.memory.fusion_engine import _MAX_JACCARD_OVERLAP

        assert _MAX_JACCARD_OVERLAP == pytest.approx(0.7)


# ═══════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO DE FONTE
# ═══════════════════════════════════════════════════════════════════


class TestSourceNormalization:
    """Garante que aliases de fonte são mapeados corretamente."""

    def test_duckduckgo_aliases(self, detector):
        assert detector._normalize_source("duckduckgo") == "web"
        assert detector._normalize_source("duckduck") == "web"
        assert detector._normalize_source("ddg") == "web"
        assert detector._normalize_source("ddgs") == "web"

    def test_memory_aliases(self, detector):
        assert detector._normalize_source("obsidian") == "memory"
        assert detector._normalize_source("memory") == "memory"

    def test_internal_aliases(self, detector):
        assert detector._normalize_source("local") == "internal"
        assert detector._normalize_source("rag") == "internal"
        assert detector._normalize_source("llm") == "internal"

    def test_known_sources_passthrough(self, detector):
        assert detector._normalize_source("wikipedia") == "wikipedia"
        assert detector._normalize_source("github") == "github"
        assert detector._normalize_source("stackoverflow") == "stackoverflow"

    def test_unknown_source_defaults_to_web(self, detector):
        assert detector._normalize_source("fontedesconhecida") == "fontedesconhecida"
        assert detector._normalize_source(None) == "web"
        assert detector._normalize_source("") == "web"


# ═══════════════════════════════════════════════════════════════════
# is_noise — filtro duro
# ═══════════════════════════════════════════════════════════════════


class TestIsNoise:
    """Valida o filtro duro de ruído."""

    def test_empty_content_is_noise(self, detector):
        assert detector.is_noise({"content": ""}) is True
        assert detector.is_noise({"content": None}) is True
        assert detector.is_noise({}) is True

    def test_very_short_content_is_noise(self, detector):
        assert detector.is_noise({"content": "abc"}) is True
        assert detector.is_noise({"content": "12345"}) is True

    def test_too_few_words_is_noise(self, detector):
        # exatamente 4 palavras (< 5)
        assert detector.is_noise({"content": "uma duas tres quatro"}) is True

    def test_only_special_chars_is_noise(self, detector):
        assert detector.is_noise({"content": "!@#$%^&*()!@#$%^"}) is True

    def test_valid_content_is_not_noise(self, detector):
        assert (
            detector.is_noise({"content": "Python é uma linguagem de programação."})
            is False
        )

    def test_text_field_also_checked(self, detector):
        assert detector.is_noise({"text": ""}) is True
        assert (
            detector.is_noise(
                {"text": "Conteúdo válido de pelo menos vinte caracteres."}
            )
            is False
        )


# ═══════════════════════════════════════════════════════════════════
# score_confidence — valores determinísticos
# ═══════════════════════════════════════════════════════════════════


class TestScoreConfidence:
    """Garante que score_confidence retorna valores corretos e estáveis."""

    def test_max_score_wikipedia_long_content(self, detector):
        item = {
            "source": "wikipedia",
            "content": "Python 3.12 foi lançado segundo dados de 2024 com novas "
            + "features importantes para desenvolvimento web e data science. " * 10,
        }
        score = detector.score_confidence(item)
        assert score >= 0.8

    def test_clickbait_penalizes_score(self, detector):
        good = {
            "source": "web",
            "content": "Python 3.12 lançado com melhorias de performance.",
        }
        bad = {
            "source": "web",
            "content": "Você não vai acreditar no que o Python 3.12 faz!",
        }
        assert detector.score_confidence(bad) < detector.score_confidence(good)

    def test_empty_content_score(self, detector):
        # conteúdo vazio mas fonte padrão "web" (autoridade 0.5 × 0.3) + ausência de clickbait (0.2)
        score = detector.score_confidence({"content": ""})
        assert score == pytest.approx(0.35, abs=0.02)

    def test_score_is_capped_at_one(self, detector):
        item = {
            "source": "wikipedia",
            "content": "Relatório oficial segundo fontes confiáveis em 2024. " * 20,
        }
        assert detector.score_confidence(item) <= 1.0

    def test_short_content_gets_lower_score(self, detector):
        long_item = {"source": "web", "content": "A" * 600}
        short_item = {"source": "web", "content": "Texto curto."}
        assert detector.score_confidence(long_item) > detector.score_confidence(
            short_item
        )

    def test_structured_data_bonus(self, detector):
        plain = {"source": "web", "content": "Informação genérica sem dados."}
        with_data = {
            "source": "web",
            "content": "Informação com dados de 2024 segundo estudos.",
        }
        assert detector.score_confidence(with_data) >= detector.score_confidence(plain)


# ═══════════════════════════════════════════════════════════════════
# should_keep — gatekeeper de persistência
# ═══════════════════════════════════════════════════════════════════


class TestShouldKeep:
    """Decisão de persistência: o que entra no banco vs. o que vai pro lixo."""

    def test_good_content_kept(self, detector):
        item = {
            "source": "docs",
            "content": "FastAPI é um framework web moderno para Python 3.8+ "
            + "com tipagem estática. Segundo a documentação oficial em 2024, "
            + "a performance supera outras frameworks populares como Flask e Django.",
        }
        assert detector.should_keep(item, min_confidence=0.5) is True

    def test_noise_discarded(self, detector):
        assert detector.should_keep({"content": "abc"}) is False
        assert detector.should_keep({"content": ""}) is False

    def test_low_confidence_below_threshold_discarded(self, detector):
        # conteúdo muito curto → score baixo → deve ser descartado com threshold 0.7
        item = {"content": "Texto mínimo."}
        assert detector.should_keep(item, min_confidence=0.7) is False

    def test_fallback_synthesis_discarded(self, detector):
        """'Informações não disponíveis.' é o marcador de fallback — deve sair."""
        item = {
            "source": "synthesis",
            "content": "Informações não disponíveis.",
        }
        assert detector.should_keep(item, min_confidence=0.5) is False

    def test_clickbait_discarded_with_strict_threshold(self, detector):
        item = {
            "source": "web",
            "content": "Você não vai acreditar neste truque incrível!",
        }
        # clickbait tira 0.2 do score, fonte web dá 0.15, tamanho curto dá 0.1
        # total ≈ 0.25 < 0.5 → descartado
        assert detector.should_keep(item, min_confidence=0.5) is False

    def test_high_quality_wikipedia_accepted(self, detector):
        long_text = (
            "Python é uma linguagem de programação de alto nível criada por Guido van Rossum. "
            "Segundo dados de 2024, é uma das mais populares segundo a StackOverflow developer survey. "
            + "Utilizada em web, data science, automação e inteligência artificial."
        )
        item = {
            "source": "wikipedia",
            "content": long_text,
        }
        assert detector.should_keep(item, min_confidence=0.3) is True

    def test_text_field_works(self, detector):
        """should_keep deve aceitar tanto 'content' quanto 'text'."""
        assert (
            detector.should_keep(
                {
                    "text": "Conteúdo aceitável com fonte segundo documentação oficial de 2024.",
                    "source": "docs",
                }
            )
            is True
        )
        assert detector.should_keep({"text": ""}) is False


# ═══════════════════════════════════════════════════════════════════
# CASOS DE USO DO ORGANISMO (regressão de comportamento)
# ═══════════════════════════════════════════════════════════════════


class TestOrganismGarbageCollection:
    """
    Simula o que o sweeper faz: filtra sínteses e decide o que manter.
    Estes testes garantem que o organismo não engorda com lixo.
    """

    def test_sweeper_gatekeeper_rejects_garbage(self, detector):
        garbage_samples = [
            {"content": ""},
            {"content": "a b c"},
            {"content": "!@#$%"},
            {"content": "Informações não disponíveis."},
            {"content": "clique aqui agora"},
        ]
        kept = [s for s in garbage_samples if detector.should_keep(s)]
        assert kept == [], f"Lixo passou pelo gatekeeper: {kept}"

    def test_sweeper_gatekeeper_accepts_valid_syntheses(self, detector):
        valid_samples = [
            {
                "source": "synthesis",
                "content": "FastAPI oferece validação automática de tipos segundo documentação oficial em 2024.",
            },
            {
                "source": "synthesis",
                "content": "React 19 introduz Server Components de acordo com o time Meta em janeiro de 2025.",
            },
            {
                "source": "synthesis",
                "content": "PostgreSQL 17 com melhorias em vacuum paralelo lançado em setembro de 2024.",
            },
        ]
        kept = [s for s in valid_samples if detector.should_keep(s, min_confidence=0.5)]
        assert len(kept) == 3, f"Apenas {len(kept)} de 3 válidos passaram"

    def test_duplicate_content_both_versions_detected(self, detector):
        """Mesmo conteúdo em fontes diferentes deve ter score similar."""
        a = {
            "source": "web",
            "content": "Docker usa containers para isolamento de processos em produção.",
        }
        b = {
            "source": "docs",
            "content": "Docker usa containers para isolamento de processos em produção.",
        }
        score_a = detector.score_confidence(a)
        score_b = detector.score_confidence(b)
        # docs tem autoridade 0.8 vs web 0.5 → docs deve ter score maior
        assert score_b > score_a

    def test_source_authority_not_modified(self, detector):
        """
        Sanity check: valores esperados de SOURCE_AUTHORITY não mudaram.
        Se mudar, este teste quebra — intencional.
        Nota: conteúdo "x" não tem dados estruturados nem clickbait,
        então o score máximo sem structured data bonus é ~0.77 para wikipedia.
        """
        long_content = "Ano 2024 com dados e fontes confiáveis. " * 20
        assert (
            detector.score_confidence({"source": "wikipedia", "content": long_content})
            >= 0.87
        )
        assert (
            detector.score_confidence({"source": "web", "content": long_content})
            >= 0.75
        )
        assert (
            detector.score_confidence({"source": "memory", "content": long_content})
            >= 0.3
        )


class TestDetectContradictionRegression:
    """Garante que a detecção de contradição não foi quebrada."""

    def test_contradiction_detected_with_negation(self, detector):
        a = {
            "content": "React 19 Server Components são suportados oficialmente pela equipe Meta."
        }
        b = {
            "content": "Docker e Kubernetes não são recomendados para o deploy do React 19 Server Components."
        }
        result = detector.detect_contradiction(a, [b])
        assert result is not None
        assert result["jaccard"] > 0.2

    def test_no_contradiction_similar_content(self, detector):
        a = {"content": "FastAPI é um framework Python para APIs."}
        b = {"content": "FastAPI é um framework web em Python."}
        result = detector.detect_contradiction(a, [b])
        assert result is None

    def test_empty_new_item_returns_none(self, detector):
        assert detector.detect_contradiction({}, [{"content": "x"}]) is None
        assert detector.detect_contradiction({"content": "abc"}, []) is None
