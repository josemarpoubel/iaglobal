# iaglobal/agents/performance_design_agent.py

from iaglobal.utils.logger import logger


class PerformanceDesignAgent:
    """Analisa requisitos de performance na fase de design."""

    def analyze(self, architecture: dict, requirements: dict,
                knowledge_context: str = "", error_context: str = "") -> dict:
        logger.info("⚡ [PERF-DESIGN] Analisando requisitos de performance...")

        issues = []
        recs = []

        arch_text = str(architecture)
        req_text = str(requirements)

        if knowledge_context:
            logger.info("⚡ [PERF-DESIGN] knowledge context available (%d chars)", len(knowledge_context))
        if error_context:
            logger.info("⚡ [PERF-DESIGN] error context available (%d chars)", len(error_context))
            if "n+1" in error_context.lower() or "query" in error_context.lower():
                issues.append("[REINCIDENCIA] N+1 queries recorrentes — necessário select_related")
                recs.append("Proibir queries N+1: usar select_related/prefetch_related obrigatório")
            if "cache" in error_context.lower():
                issues.append("[REINCIDENCIA] Falta de cache recorrente — necessário Redis/Memcached")
                recs.append("Implementar cache obrigatório — problema conhecido")

        if "cache" not in arch_text.lower():
            issues.append("Sem estratégia de caching definida")
            recs.append("Implementar cache com Redis ou Memcached para consultas frequentes")

        if "pagina" in req_text.lower() and "paginat" not in arch_text.lower():
            issues.append("Potencial listagem sem paginação")
            recs.append("Implementar paginação (limit/offset ou cursor-based)")

        if "async" not in arch_text.lower() and ("api" in arch_text.lower() or "request" in arch_text.lower()):
            issues.append("Operações I/O-bound sem async")
            recs.append("Usar async/await ou threading para operações I/O-bound")

        if "index" not in arch_text.lower() and "db" in arch_text.lower():
            issues.append("Sem índices de banco de dados definidos")
            recs.append("Criar índices para colunas usadas em WHERE, JOIN e ORDER BY")

        if "batch" not in arch_text.lower() and "muitos" in req_text.lower():
            issues.append("Processamento batch não definido para grandes volumes")
            recs.append("Implementar processamento batch com backpressure")

        report = {
            "total_issues": len(issues),
            "issues": issues,
            "recommendations": recs,
        }

        return {
            "performance_design_report": report,
            "performance_requirements": recs,
        }
