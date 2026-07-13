# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
SourceValidator — Valida credibilidade de fontes web.

Funcionalidades:
1. validate(snippet) → Score de credibilidade (0.0 - 1.0)
2. _score_domain(domain) → Score baseado em domínio conhecido
3. _score_recency(date) → Score baseado na data
4. _score_consistency(snippet, all_snippets) → Concordância com outras fontes

Integra com:
- SearchMiddleware (filtra fontes com score < 0.6)
- WebSearchTool (enriquece snippets com scores)
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.search.source_validator")


@dataclass
class SourceScore:
    """Score de credibilidade de uma fonte."""

    url: str
    domain: str
    credibility: float  # 0.0 - 1.0 (baseado em domínio)
    recency: float  # 0.0 - 1.0 (baseado na data)
    consistency: float  # 0.0 - 1.0 (concorda com outras fontes?)
    overall: float  # Média ponderada

    def to_dict(self) -> dict:
        return asdict(self)


class SourceValidator:
    """Valida credibilidade de fontes web."""

    # Domínios confiáveis (curadoria manual)
    TRUSTED_DOMAINS: Dict[str, float] = {
        # Acadêmicos
        "arxiv.org": 0.95,
        "pubmed.ncbi.nlm.nih.gov": 0.95,
        "scholar.google.com": 0.90,
        "sciencedirect.com": 0.90,
        "ieee.org": 0.90,
        "acm.org": 0.90,
        # Documentação oficial
        "docs.python.org": 0.95,
        "developer.mozilla.org": 0.95,
        "rust-lang.org": 0.95,
        "go.dev": 0.95,
        "oracle.com": 0.85,
        "microsoft.com": 0.85,
        "google.com": 0.85,
        # Código/Repositórios
        "github.com": 0.85,
        "gitlab.com": 0.80,
        "stackoverflow.com": 0.85,
        "superuser.com": 0.80,
        "serverfault.com": 0.80,
        # Comunidade técnica
        "reddit.com/r/programming": 0.70,
        "reddit.com/r/python": 0.70,
        "news.ycombinator.com": 0.75,
        "lobste.rs": 0.75,
        # Blogs/Artigos
        "medium.com": 0.60,
        "dev.to": 0.65,
        "hashnode.com": 0.60,
        "substack.com": 0.55,
        # Genéricos (baixa confiança)
        "wikipedia.org": 0.75,  # Bom para visão geral, não para detalhes técnicos
        "quora.com": 0.50,
        "pinterest.com": 0.30,
    }

    # Domínios não confiáveis (blacklist)
    BLACKLISTED_DOMAINS = {
        "content-farm.com",
        "clickbait.net",
        "fake-news.org",
    }

    def __init__(self, min_score: float = 0.6):
        self.min_score = min_score

    def validate(
        self, snippet: dict, all_snippets: Optional[List[dict]] = None
    ) -> SourceScore:
        """
        Valida credibilidade de um snippet.

        Args:
            snippet: Dict com "url", "title", "snippet", "date" (opcional)
            all_snippets: Lista de todos os snippets (para consistência)

        Returns:
            SourceScore com scores detalhados
        """
        url = snippet.get("url", "")
        domain = self._extract_domain(url)
        date_str = snippet.get("date")

        # 1. Score de domínio
        credibility = self._score_domain(domain)

        # 2. Score de recência
        recency = (
            self._score_recency(date_str) if date_str else 0.5
        )  # Neutro se sem data

        # 3. Score de consistência
        consistency = 0.5  # Neutro se não há outros snippets
        if all_snippets and len(all_snippets) > 1:
            consistency = self._score_consistency(snippet, all_snippets)

        # Overall: média ponderada (credibilidade tem mais peso)
        overall = (credibility * 0.5) + (recency * 0.3) + (consistency * 0.2)

        score = SourceScore(
            url=url,
            domain=domain,
            credibility=credibility,
            recency=recency,
            consistency=consistency,
            overall=round(overall, 3),
        )

        logger.debug(
            "[SOURCE] %s: credibility=%.2f, recency=%.2f, consistency=%.2f → overall=%.2f",
            domain,
            credibility,
            recency,
            consistency,
            overall,
        )

        return score

    def _extract_domain(self, url: str) -> str:
        """Extrai domínio principal da URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remover www.
            if domain.startswith("www."):
                domain = domain[4:]

            # Extrair domínio base (últimas 2-3 partes)
            parts = domain.split(".")

            # Domínios com TLD composto (.com.br, .co.uk, etc.)
            tld_2_countries = ["br", "uk", "au", "ca", "jp", "in", "mx", "ar"]

            if len(parts) >= 3 and parts[-1] in tld_2_countries:
                # Manter últimas 3 partes (ex: site.com.br)
                domain = ".".join(parts[-3:])
            elif len(parts) >= 2:
                # Manter últimas 2 partes (ex: python.org)
                domain = ".".join(parts[-2:])

            return domain
        except Exception:
            return ""

    def _score_domain(self, domain: str) -> float:
        """Retorna score de credibilidade baseado no domínio."""
        if not domain:
            return 0.3  # Desconhecido

        # Blacklist
        if domain in self.BLACKLISTED_DOMAINS:
            return 0.0

        # Domínio exato
        if domain in self.TRUSTED_DOMAINS:
            return self.TRUSTED_DOMAINS[domain]

        # Subdomínio de domínio confiável (ex: docs.python.org)
        for trusted_domain, score in self.TRUSTED_DOMAINS.items():
            if domain.endswith(trusted_domain):
                return score * 0.95  # Pequeno desconto para subdomínios

        # Domínio desconhecido: score neutro
        return 0.50

    def _score_recency(self, date_str: str) -> float:
        """Retorna score baseado na recência da data."""
        try:
            # Parse de data ISO ou similar
            if "T" in date_str:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                date = datetime.strptime(date_str, "%Y-%m-%d")

            # Calcular idade em dias
            now = datetime.now(timezone.utc)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            age_days = (now - date).days

            # Score baseado na idade
            if age_days < 30:
                return 1.0  # Muito recente
            elif age_days < 90:
                return 0.9  # Recentemente
            elif age_days < 180:
                return 0.8  # 6 meses
            elif age_days < 365:
                return 0.7  # 1 ano
            elif age_days < 730:
                return 0.6  # 2 anos
            elif age_days < 1095:
                return 0.5  # 3 anos
            else:
                return 0.4  # Muito antigo

        except (ValueError, TypeError) as e:
            logger.debug("[SOURCE] Erro ao parsear data '%s': %s", date_str, e)
            return 0.5  # Neutro se não conseguiu parsear

    def _score_consistency(self, snippet: dict, all_snippets: List[dict]) -> float:
        """
        Calcula score de consistência com outras fontes.

        Compara o snippet com outros snippets para detectar:
        - Concordância (mesma informação)
        - Contradição (informação conflitante)
        - Isolamento (única fonte com essa informação)
        """
        if len(all_snippets) < 2:
            return 0.5  # Neutro se não há comparação

        snippet_text = (
            snippet.get("title", "") + " " + snippet.get("snippet", "")
        ).lower()

        if not snippet_text.strip():
            return 0.3  # Baixo se sem conteúdo

        # Extrair palavras-chave do snippet
        snippet_keywords = self._extract_keywords(snippet_text)

        if not snippet_keywords:
            return 0.3  # Baixo se sem keywords

        # Comparar com outros snippets
        consistent_count = 0
        contradictory_count = 0

        for other in all_snippets:
            if other.get("url") == snippet.get("url"):
                continue  # Pular ele mesmo

            other_text = (
                other.get("title", "") + " " + other.get("snippet", "")
            ).lower()
            other_keywords = self._extract_keywords(other_text)

            # Primeiro verificar contradição (prioridade)
            if self._has_contradiction(snippet_text, other_text):
                contradictory_count += 1
                continue  # Não conta como consistente se tem contradição

            # Calcular sobreposição de keywords
            overlap = len(snippet_keywords & other_keywords)
            total_keywords = len(snippet_keywords | other_keywords)

            if total_keywords > 0 and overlap / total_keywords >= 0.3:
                consistent_count += 1  # Concorda (30%+ de sobreposição)

        total_compared = consistent_count + contradictory_count
        if total_compared == 0:
            return 0.5  # Neutro se não há comparação válida

        # Score: mais concordância = maior score
        consistency_score = consistent_count / max(1, total_compared)

        # Penalizar se há contradições
        if contradictory_count > 0:
            consistency_score *= 0.5  # 50% de penalidade por contradição

        return round(consistency_score, 3)

    def _extract_keywords(self, text: str) -> set:
        """Extrai palavras-chave de um texto."""
        # Remover stopwords
        stopwords = {
            "a",
            "o",
            "as",
            "os",
            "um",
            "uma",
            "de",
            "do",
            "da",
            "em",
            "para",
            "com",
            "por",
            "the",
            "a",
            "an",
            "and",
            "or",
            "in",
            "on",
            "for",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
        }

        # Extrair palavras (somente letras)
        words = re.findall(r"\b[a-zA-ZÀ-ÿ]{3,}\b", text)

        # Filtrar stopwords e retornar set
        return set(w.lower() for w in words if w.lower() not in stopwords)

    def _has_contradiction(self, text1: str, text2: str) -> bool:
        """Detecta se dois textos têm contradições óbvias."""
        # Palavras de contradição
        contradiction_patterns = [
            r"não (é|são|funciona|recomenda)",
            r"never|don't|doesn't|not recommended",
            r"evite|avoid|não use|don't use",
        ]

        # Verificar se um texto tem padrão de contradição e o outro não
        has_contradiction_1 = any(re.search(p, text1) for p in contradiction_patterns)
        has_contradiction_2 = any(re.search(p, text2) for p in contradiction_patterns)

        return (
            has_contradiction_1 != has_contradiction_2
        )  # XOR: apenas um tem contradição

    def filter_by_score(
        self, snippets: List[dict], min_score: Optional[float] = None
    ) -> List[dict]:
        """
        Filtra snippets por score mínimo.

        Args:
            snippets: Lista de snippets
            min_score: Score mínimo (usa default se None)

        Returns:
            Lista de snippets com overall >= min_score
        """
        threshold = min_score if min_score is not None else self.min_score

        validated = []
        for snippet in snippets:
            score = self.validate(snippet, snippets)
            if score.overall >= threshold:
                snippet["_source_score"] = score.overall
                validated.append(snippet)

        # Ordenar por score (maior primeiro)
        validated.sort(key=lambda s: s.get("_source_score", 0), reverse=True)

        logger.info(
            "[SOURCE] %d/%d snippets passaram do threshold %.2f",
            len(validated),
            len(snippets),
            threshold,
        )

        return validated


# Singleton global
_validator: Optional[SourceValidator] = None


def get_source_validator(min_score: float = 0.6) -> SourceValidator:
    """Retorna singleton do SourceValidator."""
    global _validator
    if _validator is None:
        _validator = SourceValidator(min_score=min_score)
    return _validator


# Funções utilitárias
def validate_source(
    snippet: dict, all_snippets: Optional[List[dict]] = None
) -> SourceScore:
    """Wrapper para SourceValidator.validate()."""
    return get_source_validator().validate(snippet, all_snippets)


def filter_sources(snippets: List[dict], min_score: float = 0.6) -> List[dict]:
    """Wrapper para SourceValidator.filter_by_score()."""
    return get_source_validator().filter_by_score(snippets, min_score)
