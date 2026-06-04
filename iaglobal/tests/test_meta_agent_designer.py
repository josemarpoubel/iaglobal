import unittest
from unittest.mock import patch, MagicMock

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node


class TestGapAnalyzer(unittest.TestCase):
    def setUp(self):
        self.graph = ExecutionGraph()

    def _add_core_node(self, name: str, node_type: str = "multi_coder"):
        node = Node(name=name, run=lambda: None, depends_on=[], node_type=node_type)
        self.graph.add_node(node)
        return node

    def test_detecta_gap_security_para_login(self):
        from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
        gaps = GapAnalyzer.detect_gaps("criar login com autenticacao jwt", self.graph)
        nomes = [g["nome"] for g in gaps]
        self.assertIn("security_specialist", nomes)

    def test_detecta_gap_ux_para_acessibilidade(self):
        from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
        gaps = GapAnalyzer.detect_gaps("formulario com acessibilidade mobile", self.graph)
        nomes = [g["nome"] for g in gaps]
        self.assertIn("ux_reviewer", nomes)

    def test_detecta_gap_architecture_para_escalabilidade(self):
        from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
        gaps = GapAnalyzer.detect_gaps("api escalavel com clean architecture", self.graph)
        nomes = [g["nome"] for g in gaps]
        self.assertIn("architecture_reviewer", nomes)

    def test_nao_detecta_gap_se_ja_existe(self):
        from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
        node = Node(name="security_specialist_v1", run=lambda: None, depends_on=[], node_type="critic")
        self.graph.add_node(node)
        gaps = GapAnalyzer.detect_gaps("criar login com jwt", self.graph)
        nomes = [g["nome"] for g in gaps]
        self.assertNotIn("security_specialist", nomes)

    def test_sem_gaps_para_task_generica(self):
        from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
        gaps = GapAnalyzer.detect_gaps("ola mundo", self.graph)
        self.assertEqual(len(gaps), 0)


class TestMetaAgentDesigner(unittest.TestCase):
    def setUp(self):
        self.graph = ExecutionGraph()

    def test_design_team_gera_especializacao_para_django(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        result = designer.design_team("criar pagina de contato em django com tema escuro")
        self.assertIn("task_type", result)
        self.assertIn("specialization_instructions", result)
        self.assertIn("coder", result.get("specialization_instructions", {}))

    def test_design_team_detecta_lacunas_para_login(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        result = designer.design_team("sistema de login com autenticacao jwt")
        self.assertIn("lacunas_detectadas", result)

    def test_design_team_nao_cria_nos(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        antes = len(self.graph.nodes)
        designer.design_team("criar pagina web com login")
        depois = len(self.graph.nodes)
        self.assertEqual(antes, depois, "NÃO deve criar nós no DAG")

    def test_design_team_nao_quebra_para_task_vazia(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        result = designer.design_team("")
        self.assertIn("task_type", result)
        self.assertIn("specialization_instructions", result)

    def test_get_specialization_for_retorna_instrucoes(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        designer.design_team("criar formulario de contato com seguranca")
        instr = designer.get_specialization_for("coder")
        self.assertIn("ESPECIALIDADE", instr)
        instr_critic = designer.get_specialization_for("critic")
        self.assertIn("ESPECIALIDADE", instr_critic)

    def test_get_specialization_for_vazia_sem_design(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        self.assertEqual(designer.get_specialization_for("coder"), "")

    def test_get_composition_report_funciona(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        designer.design_team("criar api rest em flask com autenticacao")
        report = designer.get_composition_report()
        self.assertIn("RELATÓRIO DE ESPECIALIZAÇÃO", report)

    def test_especializacao_tema_escuro(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        result = designer.design_team("criar pagina com tema escuro")
        instr = result["specialization_instructions"].get("coder", "")
        self.assertIn("#121212", instr)

    def test_especializacao_seguranca_para_login(self):
        from iaglobal.evolution.meta_agent_designer import MetaAgentDesigner
        designer = MetaAgentDesigner(self.graph)
        result = designer.design_team("sistema de login com jwt")
        instr = result["specialization_instructions"].get("coder", "")
        self.assertIn("SEGURANÇA", instr.upper())


class TestTaskAnalyzerNewKeywords(unittest.TestCase):
    def test_detecta_security_keywords(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("proteger contra sql injection e xss")
        self.assertIn("security", result["strategies"])

    def test_detecta_ux_keywords(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("melhorar acessibilidade e ux do formulario")
        self.assertIn("ux", result["strategies"])

    def test_detecta_architecture_keywords(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("aplicar solid e clean architecture")
        self.assertIn("architecture", result["strategies"])

    def test_detecta_performance_keywords(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("otimizar performance com cache")
        self.assertIn("performance", result["strategies"])

    def test_recomenda_security_reviewer(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("sistema de login com seguranca")
        agentes = [a["nome"] for a in result["agentes_recomendados"]]
        self.assertIn("security_reviewer", agentes)

    def test_recomenda_ux_reviewer(self):
        from iaglobal.evolution.task_analyzer import TaskAnalyzer
        result = TaskAnalyzer.analyze("formulario com ux e acessibilidade")
        agentes = [a["nome"] for a in result["agentes_recomendados"]]
        self.assertIn("ux_reviewer", agentes)


if __name__ == "__main__":
    unittest.main()
