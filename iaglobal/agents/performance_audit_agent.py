# iaglobal/agents/performance_audit_agent.py

import re
from iaglobal.utils.logger import logger


class PerformanceAuditAgent:
    """Audita o código gerado contra requisitos de performance."""

    def audit(self, code: str, performance_requirements: list,
              knowledge_context: str = "", error_context: str = "") -> dict:
        logger.info("📊 [PERF-AUDIT] Auditando performance do código...")

        bottlenecks = []
        severity_count = {"high": 0, "medium": 0, "low": 0}

        patterns = [
            (r"for\s+\w+\s+in\s+\w+\.objects\.all\(\)", "N+1 query: iterando sobre QuerySet sem select_related", "high"),
            (r"for\s+\w+\s+in\s+range\(len\(", "Anti-pattern: for i in range(len(...))", "medium"),
            (r"\.all\(\).*for", "Potencial carregamento de todos os registros", "high"),
            (r"time\.sleep", "Uso de sleep() bloqueante", "medium"),
            (r"while\s+True", "Loop infinito sem break — possível runaway", "high"),
            (r"print\s*\(", "print() em produção — overhead de I/O", "low"),
            (r"\.append\(.*for\s+\w+\s+in", "List comprehension pode substituir loop com append", "low"),
            (r"pandas\.read_csv|pd\.read_csv", "Carregamento de arquivo sem chunking", "medium"),
            (r"\.sort\(\)", "Ordenação in-place — considerar sorted() para grandes datasets", "low"),
            (r"json\.loads?\(", "Parsing JSON sem streaming para grandes arquivos", "medium"),
            (r"deepcopy", "deepcopy é caro — considerar alternativa", "medium"),
            (r"threading\.Lock\(\)", "Lock em hot path — possível contenção", "medium"),
        ]

        if knowledge_context:
            logger.info("📊 [PERF-AUDIT] knowledge context available (%d chars)", len(knowledge_context))
        if error_context:
            logger.info("📊 [PERF-AUDIT] error context available (%d chars)", len(error_context))
            if "n+1" in error_context.lower() or "query" in error_context.lower():
                patterns.insert(0, (r"for.*\.all\(\)|\.all\(\).*for", "[REINCIDENCIA] N+1 query ja ocorreu antes", "high"))
            if "loop" in error_context.lower():
                patterns.insert(0, (r"for\s+\w+\s+in\s+range\(len\(|while\s+True", "[REINCIDENCIA] Loop ineficiente ja ocorreu antes", "high"))

        for pattern, desc, severity in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                bottlenecks.append({"description": desc, "severity": severity, "pattern": pattern})
                severity_count[severity] = severity_count.get(severity, 0) + 1

        lines = code.split("\n")
        if len(lines) > 500:
            bottlenecks.append({"description": f"Arquivo muito longo: {len(lines)} linhas — considerar modularização", "severity": "medium", "pattern": "long_file"})
            severity_count["medium"] += 1

        complexity = sum(1 for line in lines if line.strip().startswith(("for ", "while ", "if ", "elif ", "except", "with ", "def ", "class ")))
        if complexity > 50:
            bottlenecks.append({"description": f"Alta complexidade ciclomática: {complexity} blocos de controle", "severity": "medium", "pattern": "high_complexity"})
            severity_count["medium"] += 1

        return {
            "performance_audit_report": {
                "total_bottlenecks": len(bottlenecks),
                "severity_count": severity_count,
                "bottlenecks": bottlenecks,
            },
            "bottlenecks": bottlenecks,
        }
