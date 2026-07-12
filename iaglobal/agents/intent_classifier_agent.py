# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# intent_classifier_agent.py

import re
import unicodedata
from typing import Dict, List, TypedDict
from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase

# --- 1. Contrato de Dados Rígido (Essencial para Pipelines) ---
class ClassificationResult(TypedDict):
    intents: List[str]
    entities: Dict[str, List[str]]
    domain: str
    confidence: float

# --- 2. Dicionários de Padrões ---
_INTENT_PATTERNS = {
    "web": ["site", "web", "html", "css", "frontend", "pagina", "website", "http", "browser"],
    "api": ["api", "rest", "endpoint", "graphql", "webservice", "microservice"],
    "dados": ["dado", "data", "analise", "analytics", "pipeline", "etl", "dataset", "csv", "json"],
    "banco": ["banco", "database", "sql", "nosql", "schema", "tabela", "query", "mongodb", "postgres"],
    "ia": ["ia", "ai", "machine learning", "deep learning", "gpt", "llm", "neural", "classificacao"],
    "automacao": ["automacao", "automation", "script", "bot", "crawler", "scraper"],
    "teste": ["test", "teste", "unitario", "integration", "coverage", "pytest"],
    "seguranca": ["security", "seguranca", "auth", "login", "cryptography", "hash", "token"],
    "mobile": ["mobile", "app", "android", "ios", "react native", "flutter"],
    "devops": ["deploy", "docker", "kubernetes", "ci/cd", "pipeline", "devops", "cloud"],
    "cli": ["cli", "command line", "terminal", "console", "script"],
    "financeiro": ["financeiro", "financial", "mercado", "stock", "bolsa", "investimento"],
    "falha": ["falha", "failure", "erro", "error", "crash", "exception", "bug", "log de erro", "analise de falha", "anomalia"],
}

_ENTITY_PATTERNS = {
    "linguagem": [
        "python", "javascript", "typescript", "java", "c#", "c++", "php", "ruby",
        "golang", "rust", "swift", "kotlin", "scala",
    ],
    "framework": [
        "django", "flask", "fastapi", "react", "angular", "vue", "spring", "laravel",
        "rails", "express", "next.js", "nuxt", "tensorflow", "pytorch",
    ],
    "formato": ["pdf", "csv", "json", "xml", "yaml", "toml", "xlsx", "html", "markdown"],
    "protocolo": ["http", "https", "grpc", "websocket", "mqtt", "tcp", "udp"],
}

# --- 3. Compilação de Regex (Performance e Precisão) ---
def _build_pattern(keywords: List[str]) -> re.Pattern:
    """
    Cria uma regex robusta:
    1. Ordena por tamanho (decrescente) para que 'react native' seja testado antes de 'react'.
    2. Usa lookarounds customizados para funcionar como word boundary, 
       mesmo com símbolos como 'c#' ou 'ci/cd'.
    3. Permite plurais opcionais '(?:s|es)?' no final.
    """
    escaped = sorted([re.escape(k) for k in keywords], key=len, reverse=True)
    pattern_str = r'(?<![a-zA-Z0-9_])(' + '|'.join(escaped) + r')(?:s|es)?(?![a-zA-Z0-9_])'
    return re.compile(pattern_str, re.IGNORECASE)

# Pré-compila todos os padrões uma única vez no carregamento do módulo
_INTENT_COMPILED = {k: _build_pattern(v) for k, v in _INTENT_PATTERNS.items()}
_ENTITY_COMPILED = {k: _build_pattern(v) for k, v in _ENTITY_PATTERNS.items()}

# Regex para detectar código (substitui o check frágil de substrings)
_CODE_MARKERS = re.compile(r'\b(?:def|class|function|import|include)\b|=>')


class IntentClassifierAgent(AgentBase):
    def __init__(self):
        super().__init__(agent_name="intent_classifier")

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos e normaliza para lower case (segurança == seguranca)."""
        nfkd = unicodedata.normalize('NFD', text)
        return nfkd.encode('ascii', 'ignore').decode('utf-8').lower()

    def classify(self, raw_text: str) -> ClassificationResult:
        if not raw_text or not isinstance(raw_text, str):
            return {
                "intents": ["unknown"],
                "entities": {},
                "domain": "geral",
                "confidence": 0.0
            }

        text_norm = self._normalize(raw_text)
        
        # --- 4. Extração de Intents com Regex ---
        intents = set()
        scores = {}
        for intent, pattern in _INTENT_COMPILED.items():
            matches = pattern.findall(text_norm)
            if matches:
                intents.add(intent)
                scores[intent] = len(matches)

        if not intents:
            intents.add("unknown")
            scores["unknown"] = 0

        # --- 5. Extração Universal de Entidades ---
        entities = {}
        for ent_type, pattern in _ENTITY_COMPILED.items():
            matches = pattern.findall(text_norm)
            if matches:
                # Usa set para remover duplicatas (ex: "python" citado 2 vezes)
                entities[ent_type] = list(set(matches))

        # --- 6. Cálculo de Confiança e Domínio ---
        sorted_intents = sorted(intents, key=lambda i: scores.get(i, 0), reverse=True)
        top_intent = sorted_intents[0]
        max_score = scores.get(top_intent, 0)
        
        # Heurística de confiança: 1 match = 0.4, 2 = 0.7, 3+ = 1.0
        confidence = min(0.4 + (max_score - 1) * 0.3, 1.0) if max_score > 0 else 0.0
        domain = top_intent if top_intent != "unknown" else "geral"

        logger.info(
            "[INTENT CLASSIFIER] intents=%s domain=%s confidence=%.2f entities=%d",
            sorted_intents, domain, confidence, sum(len(v) for v in entities.values())
        )

        return {
            "intents": sorted_intents,
            "entities": entities,
            "domain": domain,
            "confidence": confidence,
        }
