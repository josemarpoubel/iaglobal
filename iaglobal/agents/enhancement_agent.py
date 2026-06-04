# iaglobal/agents/enhancement_agent.py

from iaglobal.utils.logger import logger


class EnhancementAgent:
    """Enriquece e refina o prompt de entrada após o intake."""

    def enhance(self, task: str, intake: dict, knowledge_context: str = "",
                error_context: str = "") -> dict:
        enhanced_task = task
        approach = []
        prerequisites = []

        domain = intake.get("domain", "unknown")
        objective = intake.get("objective", task)
        gaps = intake.get("gaps", [])

        logger.info("✨ [ENHANCEMENT] domain=%s, gaps=%d", domain, len(gaps))

        if knowledge_context:
            logger.info("✨ [ENHANCEMENT] knowledge context available (%d chars)", len(knowledge_context))
        if error_context:
            logger.info("✨ [ENHANCEMENT] error context available (%d chars)", len(error_context))
            err_lower = error_context.lower()
            if "sql" in err_lower or "injection" in err_lower:
                prerequisites.append("Usar ORM/parameterized queries para evitar SQL injection")
                approach.append("segurança ofensiva/defensiva")
            if "n+1" in err_lower or "query" in err_lower:
                prerequisites.append("Otimizar queries N+1 com select_related/prefetch_related")
                approach.append("performance")
            if "syntax" in err_lower or "json" in err_lower:
                prerequisites.append("Validar parsing de JSON e sintaxe")
            if "timeout" in err_lower or "timeout" in err_lower:
                prerequisites.append("Adicionar tratamento de timeout e retry")
            if "import" in err_lower or "module" in err_lower:
                prerequisites.append("Verificar dependências e imports")

        if gaps:
            enhanced_task = task + "\n\nInformações complementares:"
            for g in gaps:
                enhanced_task += f"\n- {g}: a ser definido"
            prerequisites.append("Preencher lacunas identificadas: " + ", ".join(gaps[:3]))

        if knowledge_context and "blockchain" in knowledge_context.lower():
            approach.append("blockchain")
        if knowledge_context and "api" in knowledge_context.lower():
            approach.append("desenvolvimento web/api")

        if "web" in task.lower() or "api" in task.lower() or "site" in task.lower():
            approach.append("desenvolvimento web/api")
        if "dados" in task.lower() or "data" in task.lower():
            approach.append("análise/manipulação de dados")
        if "test" in task.lower():
            approach.append("desenvolvimento orientado a testes")
        if not approach:
            approach.append("desenvolvimento genérico")

        result = {
            "enhanced_task": enhanced_task,
            "approach": approach,
            "prerequisites": prerequisites,
        }

        return result
