import json
from iaglobal.cognition.task_fingerprint import TaskFingerprint
from iaglobal.utils.logger import logger


class TaskClassifierAgent:
    """
    Converte linguagem natural → TaskFingerprint estruturado
    Usa heurísticas locais (sem LLM) para classificação imediata.
    """

    DOMAIN_KEYWORDS = {
        "web": ["html", "css", "javascript", "php", "formulario", "pagina", "site", "frontend", "bootstrap"],
        "data": ["analise", "dados", "dataset", "csv", "sql", "query", "banco", "tabela", "pandas"],
        "ai": ["ia", "machine learning", "neural", "gpt", "treinamento", "modelo", "predicao"],
        "infra": ["deploy", "docker", "kubernetes", "servidor", "nginx", "cloud", "aws", "devops"],
    }

    LANGUAGE_KEYWORDS = {
        "python": ["python", "pandas", "flask", "django", "def ", "import "],
        "php": ["php", "<?php", "echo ", "$_"],
        "javascript": ["javascript", "js", "react", "vue", "node", "function("],
        "typescript": ["typescript", "ts", "interface ", "type "],
    }

    INTENT_KEYWORDS = {
        "generate": ["crie", "criar", "gere", "gerar", "cria", "faça", "desenvolva", "implemente"],
        "debug": ["corrige", "corrigir", "bug", "erro", "problema", "conserta", "debug"],
        "explain": ["explique", "explique", "o que é", "como funciona", "descreva"],
        "refactor": ["refatore", "refatorar", "melhore", "otimize", "simplifique"],
        "analyze": ["analise", "analisar", "diagnostique", "avalie"],
    }

    def classify(self, query: str) -> TaskFingerprint:
        q = query.lower().strip()
        return TaskFingerprint(
            domain=self._detect_domain(q),
            subdomain="general",
            language=self._detect_language(q),
            intent=self._detect_intent(q),
            complexity=self._detect_complexity(q),
            risk=self._detect_risk(q),
        )

    def _detect_domain(self, q: str) -> str:
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return domain
        return "unknown"

    def _detect_language(self, q: str) -> str:
        for lang, keywords in self.LANGUAGE_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return lang
        return "none"

    def _detect_intent(self, q: str) -> str:
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return intent
        return "explain"

    def _detect_complexity(self, q: str) -> str:
        words = len(q.split())
        if words > 30:
            return "high"
        if words > 12:
            return "medium"
        return "low"

    def _detect_risk(self, q: str) -> str:
        high_risk = ["banco", "pagamento", "cartao", "senha", "cripto", "blockchain", "pix", "dado sensivel"]
        medium_risk = ["login", "auth", "api", "integracao", "webhook"]
        ql = q.lower()
        if any(kw in ql for kw in high_risk):
            return "high"
        if any(kw in ql for kw in medium_risk):
            return "medium"
        return "low"
