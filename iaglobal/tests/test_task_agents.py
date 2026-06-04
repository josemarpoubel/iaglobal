"""Testes para o novo sistema de criação de agentes especialistas por task."""

import os
import sys
from unittest.mock import MagicMock

raiz_pacote = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, raiz_pacote)

from iaglobal.evolution.task_analyzer import TaskAnalyzer
from iaglobal.evolution.task_agent_factory import TaskAgentFactory, create_task_agents
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.node import Node
from iaglobal.graphs.builder import PIPELINE_SKILLS


class TestTaskAnalyzer:
    """Testa a análise de prompts para extração de estratégias."""

    def test_analisa_task_web_django(self):
        task = "crie uma pagina web usando django com tema escuro para o cliente enviar contato para a empresax"
        result = TaskAnalyzer.analyze(task)
        assert "web_development" in result["strategies"], (
            f"Deveria detectar web_development, obteve: {result['strategies']}"
        )
        assert "form_handling" in result["strategies"], (
            f"Deveria detectar form_handling, obteve: {result['strategies']}"
        )
        assert "theming" in result["strategies"], (
            f"Deveria detectar theming, obteve: {result['strategies']}"
        )
        assert "Django" in result["technologies"], (
            f"Deveria detectar Django, obteve: {result['technologies']}"
        )
        assert result["task_type"] == "web"
        assert len(result["agentes_recomendados"]) >= 3

    def test_analisa_task_blockchain(self):
        task = "crie um bloco genesis em sha3_512 para Bit512 com autor Kito Hamachi"
        result = TaskAnalyzer.analyze(task)
        assert "blockchain" in result["strategies"]
        assert result["task_type"] == "blockchain"

    def test_analisa_task_api(self):
        task = "crie uma API REST com FastAPI e PostgreSQL"
        result = TaskAnalyzer.analyze(task)
        assert "api_design" in result["strategies"]
        assert "database" in result["strategies"]
        assert "FastAPI" in result["technologies"]

    def test_analisa_task_cli(self):
        task = "crie um script CLI em Python para organizar arquivos"
        result = TaskAnalyzer.analyze(task)
        assert "cli_tool" in result["strategies"]

    def test_analisa_task_generica(self):
        task = "faca uma funcao que calcule fibonacci"
        result = TaskAnalyzer.analyze(task)
        assert result["task_type"] == "general"

    def test_analisa_task_com_form_e_email(self):
        task = "pagina de contato com formulario de email"
        result = TaskAnalyzer.analyze(task)
        assert "form_handling" in result["strategies"]
        assert "web_development" in result["strategies"]

    def test_analisa_task_autenticacao(self):
        task = "sistema de login com JWT e autenticacao de usuario"
        result = TaskAnalyzer.analyze(task)
        assert "authentication" in result["strategies"]


class TestTaskAgentFactory:
    """Testa a criação de agentes especialistas no grafo."""

    def setup_method(self):
        self.graph = ExecutionGraph()
        core_names = set()
        for name, opts in PIPELINE_SKILLS:
            node_name = opts.get("name", name)
            node = Node(
                name=node_name,
                run=lambda ctx: {"output": "ok"},
                depends_on=opts.get("depends_on", []),
                strategy=opts.get("strategy", "general"),
                critical=opts.get("critical", False),
                node_type=name,
            )
            self.graph.add_node(node)
            core_names.add(node_name)
        self.core_names = core_names

    def test_cria_agentes_web_django(self):
        task = "crie uma pagina web usando django com tema escuro para o cliente enviar contato"
        novos = create_task_agents(task, self.graph)

        assert len(novos) > 0, (
            f"Nenhum agente foi criado para task web django"
        )

        nomes = [n.name for n in novos]
        estrategias = [n.strategy for n in novos]
        node_types = [n.node_type for n in novos]

        print(f"\n  Agentes criados para task web django:")
        for n in novos:
            print(f"    • {n.name}: strategy={n.strategy}, type={n.node_type}")

        assert any("web_specialist" in name for name in nomes), (
            f"Deveria criar web_specialist, obteve: {nomes}"
        )
        assert any("form_handler" in name for name in nomes), (
            f"Deveria criar form_handler, obteve: {nomes}"
        )
        assert any("theming_specialist" in name for name in nomes), (
            f"Deveria criar theming_specialist, obteve: {nomes}"
        )

        # Verifica dependências válidas
        for n in novos:
            for dep in n.depends_on:
                assert dep in self.graph.nodes or dep in self.core_names, (
                    f"{n.name} depende de '{dep}' que não existe"
                )

    def test_cria_agentes_blockchain(self):
        task = "crie um bloco genesis em sha3_512 para Bit512"
        novos = create_task_agents(task, self.graph)

        assert len(novos) > 0
        nomes = [n.name for n in novos]
        assert any("blockchain_developer" in name for name in nomes)

    def test_agentes_tem_depends_on_correto(self):
        task = "crie uma pagina web django"
        novos = create_task_agents(task, self.graph)

        for n in novos:
            if n.node_type == "multi_coder":
                assert "planner" in n.depends_on, (
                    f"{n.name} (coder) deveria depender de planner"
                )

    def test_nao_cria_duplicatas(self):
        task = "crie uma pagina web django"
        count1 = len(create_task_agents(task, self.graph))
        count2 = len(create_task_agents(task, self.graph))
        # Segunda chamada não deve duplicar
        assert count2 == 0, (
            f"Segunda chamada criou {count2} agentes duplicados!"
        )

    def test_task_type_definido(self):
        task = "crie uma pagina web django"
        from iaglobal.evolution.task_agent_factory import TaskAgentFactory
        analysis = TaskAnalyzer.analyze(task)
        assert analysis["task_type"] == "web"
        for ag in analysis["agentes_recomendados"]:
            assert "nome" in ag
            assert "skill_base" in ag
            assert "estrategias" in ag
            assert len(ag["estrategias"]) > 0


class TestIntegracaoEvolutionTaskAware:
    """Testa se o EvolutionEngine cria agentes quando recebe uma task."""

    def test_evolution_engine_cria_task_agents(self):
        from iaglobal.evolution.evolutionengine import EvolutionEngine

        graph = ExecutionGraph()
        for name, opts in PIPELINE_SKILLS:
            node_name = opts.get("name", name)
            node = Node(
                name=node_name,
                run=lambda ctx: {"output": "ok"},
                depends_on=opts.get("depends_on", []),
                strategy=opts.get("strategy", "general"),
                critical=opts.get("critical", False),
                node_type=name,
            )
            graph.add_node(node)

        engine = EvolutionEngine(graph)
        engine.set_task(
            "crie uma pagina web usando django com tema escuro para o cliente enviar contato"
        )

        # Abordagem híbrida: MetaAgentDesigner gera instruções em vez de criar nós
        task_nodes = [n for n in graph.nodes if n.startswith("task_")]
        assert len(task_nodes) == 0, (
            "Abordagem híbrida: NÃO deve criar nós task_* no DAG. "
            f"Nós encontrados: {task_nodes}"
        )

        # Verifica que especializações foram geradas
        instructions = engine.designer.specialization_instructions
        assert len(instructions) > 0, (
            "MetaAgentDesigner deveria ter gerado specialization_instructions"
        )
        assert "coder" in instructions, (
            "Deveria ter instruções para coder. "
            f"Chaves: {list(instructions.keys())}"
        )
        assert any(w in instructions["coder"].lower() for w in ["escuro", "tema", "web"]), (
            "Instruções do coder deveriam mencionar tema escuro ou web. "
            f"Conteúdo: {instructions['coder'][:100]}"
        )
