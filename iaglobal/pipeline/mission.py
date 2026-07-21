# iaglobal/pipeline/mission.py
"""
Mission Cortex — análise da missão antes da execução do grafo.

Executado uma vez no início do pipeline. Popula state.context['mission']
com domínio, intenção, entidades e prioridades. Nenhum nó do grafo precisa
re-derivar estas informações — todas consultam state.context['mission'].
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

from iaglobal.pipeline.context.protocol import MissionContext as _MissionCtx


def _new_mission(**kwargs) -> _MissionCtx:
    """Cria MissionContext (frozen) com parâmetros compatíveis."""
    return _MissionCtx(
        objective=kwargs.get("objective", ""),
        domain=kwargs.get("domain", "unknown"),
        project_type=kwargs.get("project_type", "unknown"),
        language=kwargs.get("language", "python"),
        complexity=kwargs.get("complexity", "medium"),
        architecture=kwargs.get("architecture", "monolithic"),
        entities=tuple(kwargs.get("entities", [])),
        constraints=tuple(kwargs.get("constraints", [])),
        priorities=tuple(kwargs.get("priorities", [])),
        confidence=kwargs.get("confidence", 0.0),
        skip_nodes=tuple(kwargs.get("skip_nodes", [])),
        required_nodes=tuple(kwargs.get("required_nodes", [])),
    )


# Re-export para compatibilidade — agora é o frozen de protocol
MissionContext = _MissionCtx


class MissionAnalyzer:
    """
    Analisa o prompt e produz um MissionContext.

    Zero chamadas LLM — usa heurísticas, patterns e a ToolLibrary.
    Executa antes de qualquer nó do grafo.
    """

    _DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "restaurant": [
            "restaurante",
            "restaurant",
            "cardapio",
            "menu",
            "prato",
            "cozinha",
            "pedido",
            "garcom",
            "comanda",
            "mesa",
            "delivery",
            "ifood",
            "buffet",
            "lanchonete",
            "pizzaria",
        ],
        "ecommerce": [
            "ecommerce",
            "e-commerce",
            "loja",
            "produto",
            "catalogo",
            "carrinho",
            "checkout",
            "pagamento",
            "frete",
            "pedido",
            "estoque",
            "venda",
            "compra",
        ],
        "erp": [
            "erp",
            "gestao",
            "estoque",
            "financeiro",
            "fiscal",
            "contabil",
            "rh",
            "departamento",
            "relatorio",
            "dashboard",
            "indicador",
        ],
        "webapp": [
            "app",
            "aplicacao",
            "aplicativo",
            "site",
            "portal",
            "sistema",
            "plataforma",
            "frontend",
            "backend",
        ],
        "api": [
            "api",
            "rest",
            "endpoint",
            "servico",
            "microservico",
            "integracao",
            "webhook",
            "graphql",
        ],
        "document": [
            "documento",
            "relatorio",
            "pdf",
            "contrato",
            "certidao",
            "ata",
            "oficio",
            "carta",
        ],
        "game": [
            "jogo",
            "game",
            "rpg",
            "fps",
            "plataforma",
            "personagem",
            "nivel",
            "fase",
        ],
        "data": [
            "dado",
            "analise",
            "dashboard",
            "grafico",
            "relatorio",
            "etl",
            "pipeline",
            "data warehouse",
            "lake",
        ],
        "mobile": [
            "mobile",
            "app",
            "android",
            "ios",
            "smartphone",
            "tablet",
            "aplicativo movel",
        ],
    }

    _PROJECT_TYPE_KEYWORDS: dict[str, list[str]] = {
        "web_application": [
            "app",
            "aplicacao",
            "site",
            "portal",
            "sistema web",
            "frontend",
            "spa",
            "pagina",
            "interface",
        ],
        "api_service": [
            "api",
            "backend",
            "servico",
            "microservico",
            "endpoint",
            "rest",
            "graphql",
        ],
        "cli_tool": [
            "cli",
            "terminal",
            "linha de comando",
            "script",
            "comando",
            "ferramenta",
        ],
        "mobile_app": [
            "mobile",
            "android",
            "ios",
            "app movel",
            "smartphone",
        ],
        "library": [
            "biblioteca",
            "lib",
            "pacote",
            "modulo",
            "framework",
        ],
        "document": [
            "documento",
            "relatorio",
            "pdf",
            "arquivo",
        ],
        "data_pipeline": [
            "etl",
            "pipeline",
            "dado",
            "data",
            "batch",
        ],
        "game": [
            "jogo",
            "game",
            "rpg",
            "fps",
            "plataforma 2d",
            "personagem",
            "nivel",
            "fase",
            "plataformer",
        ],
    }

    _COMPLEXITY_HINTS = {
        "high": [
            "complexo",
            "grande",
            "microservico",
            "distribuido",
            "escalavel",
            "multi-usuario",
            "tempo real",
            "milhoes",
        ],
        "medium": ["crud", "api", "sistema", "app"],
        "low": ["script", "funcao", "funcaozinha", "simples"],
    }

    @staticmethod
    def _normalize(text: str) -> str:
        nfkd = unicodedata.normalize("NFD", text)
        return nfkd.encode("ascii", "ignore").decode("utf-8").lower()

    @staticmethod
    def _score_keywords(text: str, keywords: list[str]) -> int:
        count = 0
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                count += 1
        return count

    def analyze(self, prompt: str) -> MissionContext:
        clean = self._normalize(prompt)

        objective = prompt[:200] if prompt else ""
        entities = self._extract_entities(clean)
        constraints = self._extract_constraints(clean)
        domain = self._detect_domain(clean)
        project_type = self._detect_project_type(clean)
        complexity = self._detect_complexity(clean)
        priorities = self._extract_priorities(clean, entities)

        # Linguagem: padrão, detectada no futuro por análise de stack
        language = self._detect_language(clean)

        return _new_mission(
            objective=objective,
            domain=domain,
            project_type=project_type,
            language=language,
            complexity=complexity,
            entities=entities,
            constraints=constraints,
            priorities=priorities,
            confidence=0.85 if domain != "unknown" else 0.3,
        )

    def _detect_domain(self, text: str) -> str:
        best_domain = "unknown"
        best_score = 0
        for domain, keywords in self._DOMAIN_KEYWORDS.items():
            score = self._score_keywords(text, keywords)
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    def _detect_project_type(self, text: str) -> str:
        best = "unknown"
        best_score = 0
        for ptype, keywords in self._PROJECT_TYPE_KEYWORDS.items():
            score = self._score_keywords(text, keywords)
            if score > best_score:
                best_score = score
                best = ptype
        return best

    def _detect_complexity(self, text: str) -> str:
        scores = {"high": 0, "medium": 0, "low": 0}
        for level, hints in self._COMPLEXITY_HINTS.items():
            scores[level] = self._score_keywords(text, hints)
        if scores["high"] >= 2:
            return "high"
        if scores["medium"] >= 1:
            return "medium"
        return "low"

    def _detect_language(self, text: str) -> str:
        if re.search(r"\brust\b", text):
            return "rust"
        if re.search(r"\b(go|golang)\b", text):
            return "go"
        if re.search(r"\b(python|flask|django|fastapi)\b", text):
            return "python"
        if re.search(r"\b(javascript|typescript|react|node|vue|angular)\b", text):
            return "javascript"
        if re.search(r"\b(java|spring|kotlin)\b", text):
            return "java"
        return "python"

    def _extract_entities(self, text: str) -> list[str]:
        entities = []
        # Procura por substantivos após palavras de domínio
        domain_markers = [
            "de",
            "do",
            "da",
            "dos",
            "das",
            "para",
            "controle de",
            "gestao de",
            "cadastro de",
        ]
        tokens = text.split()
        for i, t in enumerate(tokens):
            if t in {"controle", "gestao", "cadastro", "gerenciamento"}:
                # espera "de" → noun
                for j in range(i + 1, min(i + 4, len(tokens))):
                    if tokens[j] in {"de", "do", "da", "dos", "das", "para", "com"}:
                        continue
                    if len(tokens[j]) > 2 and tokens[j] not in entities:
                        entities.append(tokens[j])
                    break
        # Substantivos após preposições "de" + contexto relevante
        for i, t in enumerate(tokens):
            if t == "de" and i + 1 < len(tokens):
                noun = tokens[i + 1]
                if len(noun) > 3 and noun not in entities:
                    # Filtra preposições e artigos
                    if noun not in {
                        "um",
                        "uma",
                        "o",
                        "a",
                        "os",
                        "as",
                        "para",
                        "com",
                        "por",
                        "em",
                        "no",
                        "na",
                    }:
                        entities.append(noun)
        return entities[:12]  # limita a 12 entidades

    def _extract_constraints(self, text: str) -> list[str]:
        constraints = []
        hint_map = {
            "escuro": "tema escuro",
            "elegante": "design elegante",
            "responsivo": "design responsivo",
            "acessivel": "acessibilidade",
            "seguro": "seguranca",
            "rapido": "alta performance",
            "escalavel": "escalabilidade",
        }
        for word in text.split():
            if word in hint_map and hint_map[word] not in constraints:
                constraints.append(hint_map[word])
        return constraints

    def _extract_priorities(self, text: str, entities: list[str]) -> list[str]:
        # Usa a ordem de aparição no prompt como proxy de prioridade
        text_lower = text.lower()
        priorities = []
        for entity in entities:
            if entity in text_lower:
                priorities.append(entity)
        return priorities
