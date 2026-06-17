from iaglobal.utils.logger import logger

_FUNC_REQ_PATTERNS = [
    "cadastrar", "listar", "buscar", "atualizar", "deletar", "calcular",
    "gerar", "exportar", "importar", "processar", "validar", "autenticar",
    "notificar", "enviar", "receber", "armazenar", "consultar", "filtrar",
    "ordenar", "agrupar", "concatenar", "converter", "parsear", "serializar",
    "logar", "registrar", "monitorar", "simular",
]

_NON_FUNC_REQ_PATTERNS = [
    "performance", "seguranca", "escalabilidade", "disponibilidade",
    "latencia", "concorrencia", "cache", "backup", "logging",
    "auditoria", "privacidade", "conformidade", "responsivo",
    "acessibilidade", "usabilidade", "manutenibilidade",
]


class PMAgent:
    def extract_requirements(self, prompt: str, enhancement: dict = None) -> dict:
        if not prompt:
            return {"functional": [], "non_functional": [], "priority": "low", "drivers": []}

        prompt_lower = prompt.lower()
        functional = set()
        non_functional = set()

        for pattern in _FUNC_REQ_PATTERNS:
            if pattern in prompt_lower:
                functional.add(f"Implementar funcionalidade de {pattern}")

        if not functional:
            if any(w in prompt_lower for w in ["criar", "fazer", "desenvolver", "construir"]):
                functional.add("Implementar funcionalidade principal conforme requisitos")

        for pattern in _NON_FUNC_REQ_PATTERNS:
            if pattern in prompt_lower:
                non_functional.add(f"Garantir {pattern}")

        drivers = enhancement.get("intents_detected", []) if isinstance(enhancement, dict) else []

        func_count = len(functional)
        non_func_count = len(non_functional)
        if func_count >= 5 or non_func_count >= 3:
            priority = "high"
        elif func_count >= 2 or non_func_count >= 1:
            priority = "medium"
        else:
            priority = "low"

        logger.info(
            "[PM AGENT] functional=%d non_functional=%d priority=%s",
            func_count, non_func_count, priority,
        )

        return {
            "functional": sorted(functional),
            "non_functional": sorted(non_functional),
            "priority": priority,
            "drivers": drivers,
        }
