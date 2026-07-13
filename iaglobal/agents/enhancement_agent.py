# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/enhancement_agent.py

from iaglobal.utils.logger import logger
from iaglobal.agents.agent_base import AgentBase


# Mapa de dominio → bibliotecas recomendadas (PyPI)
_LIB_SUGGESTIONS = {
    "php": ["requests", "guzzlehttp/guzzle", "phpmailer/phpmailer"],
    "web": ["flask", "django", "fastapi", "requests", "beautifulsoup4"],
    "api": ["fastapi", "flask", "requests", "httpx", "pydantic"],
    "dados": ["pandas", "numpy", "matplotlib", "seaborn", "scipy"],
    "financeiro": ["yfinance", "pandas", "numpy", "matplotlib", "plotly"],
    "mercado": ["yfinance", "pandas", "numpy", "matplotlib", "alpha_vantage"],
    "grafico": ["matplotlib", "plotly", "seaborn", "bokeh"],
    "banco": ["sqlalchemy", "psycopg2", "sqlite3", "redis", "pymongo"],
    "machine learning": ["sklearn", "numpy", "pandas", "scipy", "statsmodels"],
    "ia": ["transformers", "torch", "tensorflow", "sklearn", "sentence-transformers"],
    "blockchain": ["web3", "eth-hash", "sha3", "cbor2"],
    "email": ["smtplib", "yagmail", "flask-mail", "django-mailer"],
    "seguranca": ["bcrypt", "cryptography", "jwt", "passlib"],
    "autenticacao": ["flask-login", "django-allauth", "jwt", "python-jose"],
    "test": ["pytest", "unittest", "coverage", "hypothesis"],
    "html": ["jinja2", "mako", "beautifulsoup4", "lxml"],
    "css": ["beautifulsoup4", "tinycss2", "cssutils"],
    "javascript": ["selenium", "playwright", "requests"],
}


def _suggest_libs(task: str) -> list:
    """Retorna bibliotecas recomendadas baseadas no dominio da tarefa."""
    task_lower = task.lower()
    suggested = set()
    for keyword, libs in _LIB_SUGGESTIONS.items():
        if keyword in task_lower:
            for lib in libs:
                suggested.add(lib)
    # Libs universais para qualquer projeto web
    if any(
        w in task_lower for w in ["php", "html", "web", "site", "pagina", "formulario"]
    ):
        suggested.add("requests")
        suggested.add("beautifulsoup4")
    return sorted(suggested)[:8]


class EnhancementAgent(AgentBase):
    """Enriquece e refina o prompt de entrada após o intake."""

    def enhance(
        self,
        task: str,
        intake: dict,
        knowledge_context: str = "",
        error_context: str = "",
    ) -> dict:
        enhanced_task = task
        approach = []
        prerequisites = []

        domain = intake.get("domain", "unknown")
        objective = intake.get("objective", task)
        gaps = intake.get("gaps", [])

        logger.info("✨ [ENHANCEMENT] domain=%s, gaps=%d", domain, len(gaps))

        if knowledge_context:
            logger.info(
                "✨ [ENHANCEMENT] knowledge context available (%d chars)",
                len(knowledge_context),
            )
        if error_context:
            logger.info(
                "✨ [ENHANCEMENT] error context available (%d chars)",
                len(error_context),
            )
            err_lower = error_context.lower()
            if "sql" in err_lower or "injection" in err_lower:
                prerequisites.append(
                    "Usar ORM/parameterized queries para evitar SQL injection"
                )
                approach.append("segurança ofensiva/defensiva")
            if "n+1" in err_lower or "query" in err_lower:
                prerequisites.append(
                    "Otimizar queries N+1 com select_related/prefetch_related"
                )
                approach.append("performance")
            if "syntax" in err_lower or "json" in err_lower:
                prerequisites.append("Validar parsing de JSON e sintaxe")
            if "timeout" in err_lower or "timeout" in err_lower:
                prerequisites.append("Adicionar tratamento de timeout e retry")
            if "import" in err_lower or "module" in err_lower:
                prerequisites.append("Verificar dependências e imports")

        # Sugestão de bibliotecas baseada no dominio
        suggested_libs = _suggest_libs(task)
        if suggested_libs:
            libs_str = ", ".join(suggested_libs)
            prerequisites.append(f"Bibliotecas recomendadas: {libs_str}")
            # Injeta no enhanced_task para o coder ver as libs sugeridas
            if "php" not in task.lower():
                lib_hint = f"\n\n[BIBLIOTECAS DISPONÍVEIS]\nUse estas bibliotecas Python se necessário: {libs_str}"
                enhanced_task = task + lib_hint

        if gaps:
            if enhanced_task == task:
                enhanced_task = task + "\n\nInformações complementares:"
            for g in gaps:
                enhanced_task += f"\n- {g}: a ser definido"
            prerequisites.append(
                "Preencher lacunas identificadas: " + ", ".join(gaps[:3])
            )

        if knowledge_context and "blockchain" in knowledge_context.lower():
            approach.append("blockchain")
        if knowledge_context and "api" in knowledge_context.lower():
            approach.append("desenvolvimento web/api")

        if "web" in task.lower() or "api" in task.lower() or "site" in task.lower():
            approach.append("desenvolvimento web/api")
        if "dados" in task.lower() or "data" in task.lower():
            approach.append("análise/manipulação de dados")
        if "financeiro" in task.lower() or "mercado" in task.lower():
            approach.append("analise financeira")
            if "yfinance" not in prerequisites:
                prerequisites.append("Dados financeiros: yfinance, pandas, matplotlib")
        if "test" in task.lower():
            approach.append("desenvolvimento orientado a testes")
        if not approach:
            approach.append("desenvolvimento genérico")

        result = {
            "enhanced_task": enhanced_task,
            "approach": approach,
            "prerequisites": prerequisites,
            "suggested_libs": suggested_libs or [],
        }

        return result
