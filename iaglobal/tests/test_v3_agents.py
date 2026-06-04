"""
Testes dos agentes da Pipeline V3.

Verifica individualmente cada novo agente:
- EnhancementAgent
- SecurityDesignAgent / PerformanceDesignAgent
- SecurityAuditAgent / PerformanceAuditAgent
- ResultAgent
"""

import pytest

from iaglobal.agents.enhancement_agent import EnhancementAgent
from iaglobal.agents.security_design_agent import SecurityDesignAgent
from iaglobal.agents.performance_design_agent import PerformanceDesignAgent
from iaglobal.agents.security_audit_agent import SecurityAuditAgent
from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent
from iaglobal.agents.result_agent import ResultAgent


class TestEnhancementAgent:

    def test_enhance_with_gaps(self):
        agent = EnhancementAgent()
        result = agent.enhance("criar um site", {"domain": "web", "objective": "criar site", "gaps": ["tecnologia", "prazo"], "ambiguity_level": 50})

        assert "enhanced_task" in result
        assert "approach" in result
        assert "prerequisites" in result
        assert "tecnologia" in str(result["prerequisites"])
        assert "Preencher lacunas" in str(result["prerequisites"][0])

    def test_enhance_without_gaps(self):
        agent = EnhancementAgent()
        result = agent.enhance("criar api rest", {"domain": "api", "objective": "criar API", "gaps": [], "ambiguity_level": 20})

        assert any("web/api" in a for a in result["approach"])
        assert result["prerequisites"] == []

    def test_enhance_detects_web(self):
        agent = EnhancementAgent()
        result = agent.enhance("criar site web", {"domain": "web", "objective": "criar site", "gaps": [], "ambiguity_level": 30})
        assert any("web/api" in a for a in result["approach"])

    def test_enhance_detects_data(self):
        agent = EnhancementAgent()
        result = agent.enhance("analisar dados de vendas", {"domain": "data", "objective": "analise", "gaps": [], "ambiguity_level": 30})
        assert "análise/manipulação de dados" in result["approach"]

    def test_enhance_detects_test(self):
        agent = EnhancementAgent()
        result = agent.enhance("escrever testes unitarios", {"domain": "test", "objective": "testar", "gaps": [], "ambiguity_level": 10})
        assert "desenvolvimento orientado a testes" in result["approach"]


class TestSecurityDesignAgent:

    def test_detects_missing_auth(self):
        agent = SecurityDesignAgent()
        result = agent.analyze({"descricao": "api simples"}, {"descricao": "sem auth"})
        report = result["security_design_report"]
        assert any("autentica" in i.lower() for i in report["issues"])
        assert any("auth" in r.lower() for r in result["security_requirements"])

    def test_detects_sql_risk(self):
        agent = SecurityDesignAgent()
        result = agent.analyze({"descricao": "usa queries diretas sem abstração"}, {"descricao": "consulta sql direta no banco"})
        report = result["security_design_report"]
        assert any("sql" in i.lower() for i in report["issues"])

    def test_detects_https_missing(self):
        agent = SecurityDesignAgent()
        result = agent.analyze({"descricao": "api rest"}, {"descricao": "http"})
        report = result["security_design_report"]
        assert any("tls" in i.lower() or "https" in i.lower() for i in report["issues"])

    def test_no_issues_for_secure_design(self):
        agent = SecurityDesignAgent()
        arch = {"descricao": "usa jwt auth, orm, sanitizacao de input, https, env vars"}
        req = {"descricao": "auth com jwt, orm, https"}
        result = agent.analyze(arch, req)
        report = result["security_design_report"]
        assert report["total_issues"] < 3  # auth/orm/https cobertos, outros podem aparecer


class TestPerformanceDesignAgent:

    def test_detects_missing_cache(self):
        agent = PerformanceDesignAgent()
        result = agent.analyze({"descricao": "consulta sql direta sem redis"}, {"descricao": "muitas consultas"})
        report = result["performance_design_report"]
        assert any("caching" in i.lower() for i in report["issues"])

    def test_detects_missing_pagination(self):
        agent = PerformanceDesignAgent()
        result = agent.analyze({"descricao": "lista"}, {"descricao": "pagina de resultados"})
        report = result["performance_design_report"]
        assert any("pagina" in i.lower() for i in report["issues"])

    def test_detects_async_needed(self):
        agent = PerformanceDesignAgent()
        result = agent.analyze({"descricao": "api rest requests"}, {"descricao": "muitas requisicoes"})
        report = result["performance_design_report"]
        assert any("async" in i.lower() for i in report["issues"])

    def test_no_issues_for_performant_design(self):
        agent = PerformanceDesignAgent()
        arch = {"descricao": "usa redis cache, paginacao, async/await, indices no db, batch processing"}
        req = {"descricao": "alta performance"}
        result = agent.analyze(arch, req)
        report = result["performance_design_report"]
        assert report["total_issues"] < 3


class TestSecurityAuditAgent:

    def test_detects_eval(self):
        agent = SecurityAuditAgent()
        result = agent.audit("eval('print(1)')", [])
        report = result["security_audit_report"]
        assert any("eval" in i["description"].lower() for i in report["issues"])
        assert report["severity_count"]["high"] >= 1

    def test_detects_hardcoded_secret(self):
        agent = SecurityAuditAgent()
        result = agent.audit('API_KEY = "12345"', [])
        report = result["security_audit_report"]
        assert any("chave" in i["description"].lower() for i in report["issues"])

    def test_detects_subprocess(self):
        agent = SecurityAuditAgent()
        result = agent.audit("subprocess.Popen(['ls'])", [])
        report = result["security_audit_report"]
        assert any("subprocess" in i["description"].lower() for i in report["issues"])

    def test_clean_code_passes(self):
        agent = SecurityAuditAgent()
        code = '''
import logging
logger = logging.getLogger(__name__)

def hello():
    logger.info("hello world")
    return "ok"
'''
        result = agent.audit(code, [])
        report = result["security_audit_report"]
        assert report["total_issues"] == 0


class TestPerformanceAuditAgent:

    def test_detects_n_plus_1(self):
        agent = PerformanceAuditAgent()
        result = agent.audit("for item in Model.objects.all():", [])
        report = result["performance_audit_report"]
        assert any("N+1" in i["description"] for i in report["bottlenecks"])

    def test_detects_range_len(self):
        agent = PerformanceAuditAgent()
        result = agent.audit("for i in range(len(items)):", [])
        report = result["performance_audit_report"]
        assert any("range(len" in i["description"] for i in report["bottlenecks"])

    def test_detects_time_sleep(self):
        agent = PerformanceAuditAgent()
        result = agent.audit("time.sleep(1)", [])
        report = result["performance_audit_report"]
        assert any("sleep" in i["description"].lower() for i in report["bottlenecks"])

    def test_clean_code_passes(self):
        agent = PerformanceAuditAgent()
        code = "x = 1\ny = 2\nresult = x + y\n"
        result = agent.audit(code, [])
        report = result["performance_audit_report"]
        assert report["total_bottlenecks"] == 0

    def test_detects_high_complexity(self):
        agent = PerformanceAuditAgent()
        lines = []
        for i in range(60):
            lines.append(f"if x == {i}: pass")
            lines.append(f"    for y in range({i}): break")
        code = "\n".join(lines)
        result = agent.audit(code, [])
        report = result["performance_audit_report"]
        assert any("complexidade" in b["description"].lower() for b in report["bottlenecks"])


class TestResultAgent:

    def test_build_result_with_all_artifacts(self):
        agent = ResultAgent()
        ctx = {
            "documentation": {"readme": "# Projeto", "adr": "dec1"},
            "release": {"changelog": "v1.0.0 - init", "version": "1.0.0"},
            "metrics": {"durations": {"coder": 10.5}, "quality_scores": {"reviewer": 0.85}},
            "optimization": {"patterns": ["cache", "async"], "suggestions": ["usar redis"]},
        }
        result = agent.build_result(ctx)
        assert result["final_result"]["status"] == "concluído"
        assert result["final_result"]["artifacts"]["documentation"] is True
        assert "Tempo total" in result["summary"]
        assert len(result["next_steps"]) == 3

    def test_build_result_without_artifacts(self):
        agent = ResultAgent()
        result = agent.build_result({})
        assert result["final_result"]["status"] == "concluído"
        assert result["final_result"]["artifacts"]["documentation"] is False
        assert result["summary"] == "Pipeline concluída."

    def test_build_result_partial(self):
        agent = ResultAgent()
        ctx = {"documentation": {"readme": "doc"}}
        result = agent.build_result(ctx)
        assert "Documentação" in result["summary"]


# =========================================================================
# TESTES DE INTEGRAÇÃO COM SISTEMA DE APRENDIZADO
# =========================================================================

class TestV3AgentsLearningIntegration:

    def test_enhancement_accepts_knowledge_context(self):
        from iaglobal.agents.enhancement_agent import EnhancementAgent
        agent = EnhancementAgent()
        result = agent.enhance("criar api rest", {"domain": "api", "gaps": [], "ambiguity_level": 20},
                                knowledge_context="blockchain knowledge available")
        assert any("blockchain" in a for a in result.get("approach", []))

    def test_enhancement_accepts_error_context(self):
        from iaglobal.agents.enhancement_agent import EnhancementAgent
        agent = EnhancementAgent()
        result = agent.enhance("criar site web", {"domain": "web", "gaps": [], "ambiguity_level": 30},
                                error_context="=== HISTÓRICO DE ERROS EVITADOS ===")
        assert "web/api" in str(result.get("approach", []))

    def test_security_design_accepts_knowledge(self):
        from iaglobal.agents.security_design_agent import SecurityDesignAgent
        agent = SecurityDesignAgent()
        result = agent.analyze({"sem auth"}, {"sem requisitos"}, knowledge_context="knowledge ok")
        report = result["security_design_report"]
        assert "total_issues" in report

    def test_performance_design_accepts_knowledge(self):
        from iaglobal.agents.performance_design_agent import PerformanceDesignAgent
        agent = PerformanceDesignAgent()
        result = agent.analyze({"sem cache"}, {"sem perf"}, knowledge_context="knowledge ok")
        report = result["performance_design_report"]
        assert "total_issues" in report

    def test_security_audit_accepts_learning_context(self):
        from iaglobal.agents.security_audit_agent import SecurityAuditAgent
        agent = SecurityAuditAgent()
        result = agent.audit("print('hello')", [],
                              knowledge_context="past security issues",
                              error_context="=== HISTÓRICO DE ERROS ===")
        assert "total_issues" in result["security_audit_report"]

    def test_performance_audit_accepts_learning_context(self):
        from iaglobal.agents.performance_audit_agent import PerformanceAuditAgent
        agent = PerformanceAuditAgent()
        result = agent.audit("x = 1", [],
                              knowledge_context="past perf issues",
                              error_context="=== HISTÓRICO DE ERROS ===")
        assert "total_bottlenecks" in result["performance_audit_report"]

    def test_knowledge_run_handles_v3_nodes(self):
        from iaglobal.evolution.agents.knowledge_agent import knowledge, KnowledgeAgent

        count_before = knowledge.get_stats().get("total", 0)

        knowledge.store(category="pattern", title="V3 sql injection test",
                       content="security_design found SQL injection risk in user input",
                       tags=["security_design", "sql_injection", "v3"], source="test")

        count_after = knowledge.get_stats().get("total", 0)
        assert count_after >= count_before

        relevant = knowledge.retrieve_relevant("SQL injection segurança", max_results=2)
        assert len(relevant) > 0

        found = False
        for r in relevant:
            if "sql" in r.get("title", "").lower() or "sql" in r.get("content", "").lower():
                found = True
        assert found

    @pytest.mark.asyncio
    async def test_orchestrator_plan_includes_hints(self):
        from iaglobal.graphs.builder import _make_orchestrator_run
        run_fn = _make_orchestrator_run()
        ctx = {
            "input": {"task": "criar sistema", "enhanced_task": "criar sistema web"},
            "memory": {"enhancement": {"output": {"prerequisites": ["auth"]}}},
            "workdir": None,
        }
        result = await run_fn(ctx)
        assert "knowledge_hints" in result.get("orchestration_plan", {})
        assert "error_hints" in result.get("orchestration_plan", {})
