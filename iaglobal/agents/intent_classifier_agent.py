from iaglobal.utils.logger import logger

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


class IntentClassifierAgent:
    def classify(self, raw_text: str) -> dict:
        if not raw_text or not isinstance(raw_text, str):
            return {"intents": ["unknown"], "entities": {}, "domain": "unknown", "confidence": 0.0}

        text_lower = raw_text.lower()
        intents = set()
        scores = {}

        for intent, keywords in _INTENT_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                intents.add(intent)
                scores[intent] = score

        if not intents:
            intents.add("unknown")

        entities = {}
        for ent_type, patterns in _ENTITY_PATTERNS.items():
            found = [p for p in patterns if p in text_lower]
            if found:
                entities[ent_type] = found

        sorted_intents = sorted(intents, key=lambda i: scores.get(i, 0), reverse=True)
        max_score = max(scores.values()) if scores else 1
        confidence = min(max_score / 3, 1.0)

        domain = sorted_intents[0] if sorted_intents[0] != "unknown" else "geral"

        has_code = any(c in raw_text for c in ["def ", "class ", "function", "=>", "import ", "#include"])
        if has_code and "linguagem" not in entities:
            for lang in _ENTITY_PATTERNS["linguagem"]:
                if lang in text_lower:
                    entities.setdefault("linguagem", []).append(lang)

        logger.info(
            "[INTENT CLASSIFIER] intents=%s domain=%s confidence=%.2f entities=%d",
            sorted_intents, domain, confidence, sum(len(v) for v in entities.values()),
        )

        return {
            "intents": sorted_intents,
            "entities": entities,
            "domain": domain,
            "confidence": confidence,
        }
