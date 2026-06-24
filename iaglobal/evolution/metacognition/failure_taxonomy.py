"""Failure Taxonomy — classifica erros em categorias: prompt, config, modelo, infra, skill_ausente."""

import re
from typing import Dict, List, Any

# Palavras-chave por categoria
PROMPT_KEYWORDS = ["prompt", "instrucao", "instruction", "ambiguo", "ambíguo",
                    "mal formatado", "malformed", "incompleto", "contexto"]
CONFIG_KEYWORDS = ["config", "configuracao", "configuração", "environment",
                   ".env", "variavel", "variável", "setting", "api_key",
                   "timeout", "max_tokens", "temperature"]
MODELO_KEYWORDS = ["modelo", "model", "llm", "provedor", "provider",
                   "token limit", "context length", "rate limit",
                   "modelo nao suportado", "model not supported"]
INFRA_KEYWORDS = ["infra", "network", "conexao", "conexão", "timeout",
                  "servidor", "server", "503", "500", "erro interno",
                  "internal error", "connection", "dns", "ssl"]
SKILL_KEYWORDS = ["skill_ausente", "missing skill", "specialty missing",
                  "falta especialista", "expertise", "conhecimento",
                  "library not found", "modulo nao encontrado", "módulo não encontrado"]


def classify_error(error_text: str, error_type: str = "") -> Dict[str, Any]:
    """Classifica um erro em uma das 5 categorias."""
    text = f"{error_text} {error_type}".lower()

    score_prompt = _count_matches(text, PROMPT_KEYWORDS)
    score_config = _count_matches(text, CONFIG_KEYWORDS)
    score_modelo = _count_matches(text, MODELO_KEYWORDS)
    score_infra = _count_matches(text, INFRA_KEYWORDS)
    score_skill = _count_matches(text, SKILL_KEYWORDS)

    scores = {
        "prompt": score_prompt,
        "config": score_config,
        "modelo": score_modelo,
        "infra": score_infra,
        "skill_ausente": score_skill,
    }

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        best = "skill_ausente"

    return {
        "category": best,
        "scores": scores,
        "confidence": scores[best] / max(sum(scores.values()), 1),
    }


def classify_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Classifica uma lista de erros, adicionando categoria a cada um."""
    classified = []
    for err in errors:
        error_text = err.get("error", err.get("description", ""))
        error_type = err.get("error_type", "")
        tax = classify_error(error_text, error_type)
        classified.append({**err, "taxonomy": tax})
    return classified


def _count_matches(text: str, keywords: List[str]) -> int:
    return sum(1 for kw in keywords if kw.lower() in text)
