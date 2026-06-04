# tests/test_agents.py

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock # MagicMock agora está aqui

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, raiz_projeto)

from iaglobal.agents.planner_agent import PlannerAgent
from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.debugger_agent import DebuggerAgent
from iaglobal.agents.reflexion_agent import ReflexionAgent
from iaglobal.validation.scoring import CodeScorer

from iaglobal.agents.multi_agent import (
    buscar_solucao_anterior, 
    gerar_solucoes, 
    criticar, 
    debuggar, 
    processar_testar_solucoes as testar_solucoes # Alias: mantém o nome antigo para o teste
)

class TestPlannerAgent(unittest.TestCase):
    def setUp(self):
        self.planner = PlannerAgent()

    def test_injetar_plano_no_prompt_formata_corretamente(self):
        plano = {
            "complexidade": "BAIXA",
            "arquitetura_proposta": "Algoritmo simples",
            "subtarefas": [
                {"id": 1, "titulo": "Criar função", "descricao": "Fazer algo", "alertas_seguranca": "Cuidado com loops"},
                {"id": 2, "titulo": "Testar", "descricao": "Validar resultado", "alertas_seguranca": "Nenhum"}
            ]
        }
        resultado = self.planner.injetar_plano_no_prompt(plano, subtarefa_atual_id=1)
        self.assertIn("Criar função", resultado)
        self.assertIn("EXECUTANDO AGORA", resultado)
        self.assertIn("Testar", resultado)
        self.assertIn("Algoritmo simples", resultado)

    def test_injetar_plano_marca_concluida_quando_id_passado(self):
        plano = {
            "complexidade": "BAIXA",
            "arquitetura_proposta": "Teste",
            "subtarefas": [
                {"id": 1, "titulo": "Passo 1", "descricao": "ok", "alertas_seguranca": ""},
                {"id": 2, "titulo": "Passo 2", "descricao": "ok", "alertas_seguranca": ""}
            ]
        }
        resultado = self.planner.injetar_plano_no_prompt(plano, subtarefa_atual_id=2)
        self.assertIn("Concluída", resultado)
        self.assertIn("EXECUTANDO AGORA", resultado)

    @patch('iaglobal.agents.planner_agent.executar')
    def test_criar_plano_execucao_com_resposta_valida(self, mock_executar):
        mock_executar.return_value = json.dumps({
            "complexidade": "BAIXA",
            "arquitetura_proposta": "Função simples",
            "subtarefas": [{"id": 1, "titulo": "Implementar", "descricao": "Criar a função", "alertas_seguranca": "Nada"}]
        })
        resultado = self.planner.criar_plano_execucao("teste")
        self.assertEqual(resultado["complexidade"], "BAIXA")
        self.assertEqual(len(resultado["subtarefas"]), 1)

    @patch('iaglobal.agents.planner_agent.executar')
    def test_criar_plano_execucao_fallback_quando_llm_falha(self, mock_executar):
        mock_executar.side_effect = Exception("LLM offline")
        resultado = self.planner.criar_plano_execucao("tarefa qualquer")
        self.assertEqual(resultado["complexidade"], "DESCONHECIDA")
        self.assertEqual(len(resultado["subtarefas"]), 1)
        self.assertEqual(resultado["subtarefas"][0]["titulo"], "Execução Direta")

    @patch('iaglobal.agents.planner_agent.executar')
    def test_criar_plano_execucao_extrai_json_de_markdown(self, mock_executar):
        mock_executar.return_value = "```json\n{\"complexidade\": \"ALTA\", \"arquitetura_proposta\": \"Teste\", \"subtarefas\": []}\n```"
        resultado = self.planner.criar_plano_execucao("tarefa")
        self.assertEqual(resultado["complexidade"], "ALTA")

class TestTesterAgent(unittest.TestCase):
    def setUp(self):
        self.tester = TesterAgent()

    def test_amalgamar_codigo_e_teste_funde_conteudo(self):
        codigo = "def foo(): pass"
        teste = "class TestFoo(unittest.TestCase): pass"
        resultado = self.tester.amalgamar_codigo_e_teste(codigo, teste)
        self.assertIn("def foo(): pass", resultado)
        self.assertIn("class TestFoo(unittest.TestCase): pass", resultado)
        self.assertIn("CÓDIGO DO DESENVOLVEDOR", resultado)
        self.assertIn("SUITE DE TESTES", resultado)

    @patch('iaglobal.agents.tester_agent.route_generate')
    def test_gerar_bateria_testes_com_resposta_valida(self, mock_route):
        mock_route.return_value = "```python\nimport unittest\nclass TestCalc(unittest.TestCase):\n    def test_soma(self): pass\nif __name__ == '__main__':\n    unittest.main()\n```"
        resultado = self.tester.gerar_bateria_testes("soma", "def somar(a,b): return a+b")
        self.assertIn("import unittest", resultado)
        self.assertIn("class TestCalc", resultado)

    @patch('iaglobal.agents.tester_agent.logger')
    @patch('iaglobal.agents.tester_agent.route_generate')
    def test_gerar_bateria_testes_fallback_quando_llm_falha(self, mock_route, mock_logger):
        mock_route.side_effect = Exception("API error")
        resultado = self.tester.gerar_bateria_testes("tarefa", "codigo")
        self.assertEqual(resultado, "")


class TestCriticAgent(unittest.TestCase):
    def setUp(self):
        self.critic = CriticAgent()

    @patch('iaglobal.agents.critic_agent.route_generate')
    def test_avaliar_solucao_retorna_ok(self, mock_route):
        import json
        mock_route.return_value = json.dumps({
            "correctness": 80, "completeness": 75, "security": 90, "spec_match": 85,
            "summary": "Código correto"
        })
        resultado = self.critic.avaliar_solucao("tarefa", "def foo(): return 42")
        dados = json.loads(resultado)
        self.assertEqual(dados["approved"], True)
        self.assertGreaterEqual(dados["score"], 60)

    @patch('iaglobal.agents.critic_agent.route_generate')
    def test_avaliar_solucao_retorna_reject(self, mock_route):
        import json
        mock_route.return_value = json.dumps({
            "correctness": 20, "completeness": 15, "security": 30, "spec_match": 10,
            "summary": "Código incorreto"
        })
        resultado = self.critic.avaliar_solucao("tarefa", "codigo_perigoso")
        dados = json.loads(resultado)
        self.assertEqual(dados["approved"], False)

    @patch('iaglobal.agents.critic_agent.route_generate')
    def test_avaliar_solucao_fallback_em_excecao(self, mock_route):
        import json
        mock_route.side_effect = Exception("Timeout")
        resultado = self.critic.avaliar_solucao("tarefa", "codigo")
        dados = json.loads(resultado)
        self.assertEqual(dados["approved"], False)


class TestCoderAgent(unittest.TestCase):
    def setUp(self):
        self.coder = CoderAgent()

    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_codigo_com_resposta_valida(self, mock_exec):
        mock_exec.return_value = "```python\ndef foo():\n    return 42\n```"
        resultado = self.coder.gerar_codigo("tarefa")
        self.assertIn("def foo():", resultado)
        self.assertEqual(resultado, "def foo():\n    return 42")

    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_codigo_retorna_vazio_em_falha(self, mock_exec):
        mock_exec.side_effect = Exception("LLM error")
        resultado = self.coder.gerar_codigo("tarefa")
        self.assertEqual(resultado, "")

    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_codigo_injeta_contexto(self, mock_exec):
        mock_exec.return_value = "```python\nprint('ok')\n```"
        resultado = self.coder.gerar_codigo("tarefa", contexto="[CONTEXTO]: algo", erros_contexto="[ERROS]: nenhum")
        self.assertEqual(resultado, "print('ok')")

    def test_extrair_codigo_puro_remove_markdown(self):
        texto = "```python\nx = 1\n```"
        resultado = self.coder._extrair_codigo_puro(texto)
        self.assertEqual(resultado, "x = 1")

    def test_sintaxe_valida(self):
        self.assertTrue(self.coder._sintaxe_valida("def foo():\n    return 1"))
        self.assertFalse(self.coder._sintaxe_valida("def foo(:"))


class TestDebuggerAgent(unittest.TestCase):
    def setUp(self):
        self.debugger = DebuggerAgent()

    @patch('iaglobal.agents.debugger_agent.route_generate')
    def test_corrigir_codigo_com_resposta_valida(self, mock_route):
        mock_route.return_value = "```python\ndef foo():\n    return 1\n```"
        resultado = self.debugger.corrigir_codigo("def foo():\n    return x", "NameError", "tarefa")
        self.assertIn("def foo():", resultado)
        self.assertNotIn("```", resultado)

    @patch('iaglobal.agents.debugger_agent.route_generate')
    def test_corrigir_codigo_retorna_original_em_falha(self, mock_route):
        mock_route.side_effect = Exception("LLM error")
        codigo_original = "def foo():\n    return 1"
        resultado = self.debugger.corrigir_codigo(codigo_original, "erro", "tarefa")
        self.assertEqual(resultado, codigo_original)

    def test_extrair_codigo_puro(self):
        resultado = self.debugger._extrair_codigo_puro("```python\nprint(1)\n```")
        self.assertEqual(resultado, "print(1)")


class TestReflexionAgent(unittest.TestCase):
    def setUp(self):
        self.reflexion = ReflexionAgent()

    @patch('iaglobal.agents.reflexion_agent.route_generate')
    def test_analisar_resultado_chama_llm(self, mock_exec):
        mock_exec.return_value = "Análise: código correto, mas pode ser otimizado."
        resultado = self.reflexion.analisar_resultado(
            "def foo(): return 1",
            {"sucesso": True, "output": "OK"},
            "tarefa"
        )
        self.assertIn("Análise", resultado)

    @patch('iaglobal.agents.reflexion_agent.route_generate')
    def test_analisar_resultado_fallback_em_falha(self, mock_exec):
        mock_exec.side_effect = Exception("LLM error")
        resultado = self.reflexion.analisar_resultado("codigo", {"sucesso": False}, "tarefa")
        self.assertEqual(resultado, "Análise não disponível devido a erro de comunicação.")

    @patch('iaglobal.agents.reflexion_agent.route_generate')
    def test_sugerir_melhoria_chama_llm(self, mock_exec):
        mock_exec.return_value = "```python\ndef foo():\n    return 1\n```"
        resultado = self.reflexion.sugerir_melhoria("codigo", "analise", "tarefa")
        self.assertIn("def foo():", resultado)

    @patch('iaglobal.agents.reflexion_agent.route_generate')
    def test_sugerir_melhoria_fallback_em_falha(self, mock_exec):
        mock_exec.side_effect = Exception("LLM error")
        codigo = "def foo(): return 1"
        resultado = self.reflexion.sugerir_melhoria(codigo, "analise", "tarefa")
        self.assertEqual(resultado, codigo)

class TestMultiAgentSolucoes(unittest.TestCase):

    @patch('iaglobal.agents.critic_agent.route_generate')
    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_solucoes_chama_todos_agentes(self, mock_coder_exec, mock_critic_exec):
        mock_coder_exec.return_value = "```python\nprint('ok')\n```"
        mock_critic_exec.return_value = "OK"
        solucoes = gerar_solucoes("tarefa simples")
        self.assertEqual(len(solucoes), 3)
        for nome in ["dev_fast", "dev_safe", "dev_exploratory"]:
            self.assertIn(nome, solucoes)
            self.assertEqual(solucoes[nome], "print('ok')")

    @patch('iaglobal.agents.critic_agent.route_generate')
    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_solucoes_mantem_mesmo_com_critic_reprovando(self, mock_coder_exec, mock_critic_exec):
        mock_coder_exec.return_value = "```python\nprint('ok')\n```"
        mock_critic_exec.return_value = "Falha: código inseguro"
        solucoes = gerar_solucoes("tarefa")
        self.assertGreaterEqual(len(solucoes), 1)

    @patch('iaglobal.agents.critic_agent.route_generate')
    @patch('iaglobal.agents.coder_agent.executar')
    def test_gerar_solucoes_ignora_coder_que_falha(self, mock_coder_exec, mock_critic_exec):
        mock_coder_exec.side_effect = Exception("Falha")
        mock_critic_exec.return_value = "OK"
        solucoes = gerar_solucoes("tarefa")
        self.assertEqual(len(solucoes), 0)

    @patch('iaglobal.agents.critic_agent.route_generate')
    @patch('iaglobal.agents.debugger_agent.route_generate')
    def test_debuggar_codigo_com_erro(self, mock_route, mock_critic_exec):
        mock_route.return_value = "```python\ndef foo():\n    return 1\n```"
        resultado = debuggar("def foo():\n    return x", "NameError: x", "tarefa")
        self.assertIn("def foo():", resultado)
        self.assertNotIn("```", resultado)

    @patch('iaglobal.agents.critic_agent.route_generate')
    @patch('iaglobal.agents.debugger_agent.route_generate')
    def test_debuggar_retorna_codigo_original_em_falha(self, mock_route, mock_critic_exec):
        mock_route.side_effect = Exception("LLM error")
        codigo_original = "def foo():\n    return 1"
        resultado = debuggar(codigo_original, "erro", "tarefa")
        self.assertEqual(resultado, codigo_original)

    @patch('iaglobal.agents.critic_agent.route_generate')
    def test_criticar_chama_critic_agent(self, mock_route):
        import json
        mock_route.return_value = json.dumps({
            "correctness": 80, "completeness": 75, "security": 90, "spec_match": 85,
            "summary": "OK"
        })
        resultado = criticar("def foo(): pass", "tarefa")
        dados = json.loads(resultado)
        self.assertEqual(dados["approved"], True)

    @patch('iaglobal.agents.multi_agent.sqlite3.connect')
    def test_buscar_solucao_anterior_sem_resultado(self, mock_connect):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        resultado = buscar_solucao_anterior("tarefa")
        self.assertIsNone(resultado)

    @patch('iaglobal.agents.multi_agent.sqlite3.connect')
    def test_buscar_solucao_anterior_com_cache(self, mock_connect):
        import cbor2
        from datetime import datetime, timezone
        dados_cbor = cbor2.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "task": "tarefa",
            "codigo": "print('ok')",
            "metadata": {}
        })
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(dados_cbor,)]
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        resultado = buscar_solucao_anterior("tarefa")
        self.assertIsNotNone(resultado)
        self.assertIn("codigo", resultado)

    def test_buscar_solucao_anterior_banco_inexistente(self):
        resultado = buscar_solucao_anterior("tarefa_qualquer")
        self.assertIsNone(resultado)


class TestMultiAgentTestarSolucoes(unittest.TestCase):

    @patch('iaglobal.agents.tester_agent.route_generate')
    @patch('iaglobal.agents.multi_agent.executar_codigo')
    def test_testar_solucoes_ranking(self, mock_sandbox, mock_exec):
        mock_exec.return_value = "import unittest\nclass T(unittest.TestCase):\n    def test(self): pass\nif __name__ == '__main__':\n    unittest.main()"
        mock_sandbox.return_value = {"sucesso": True, "output": "OK\n\nRan 1 test in 0.001s\n\nOK"}

        solucoes = {"dev_fast": "def foo(): return 1", "dev_safe": "def foo(): return 2"}
        resultados = testar_solucoes(solucoes, "tarefa")

        self.assertEqual(len(resultados), 2)
        for score, nome, codigo, erro in resultados:
            self.assertIsInstance(score, float)
            self.assertIn(nome, ["dev_fast", "dev_safe"])

    @patch('iaglobal.agents.tester_agent.route_generate')
    @patch('iaglobal.agents.multi_agent.executar_codigo')
    def test_testar_solucoes_score_100_em_sucesso(self, mock_sandbox, mock_exec):
        mock_exec.return_value = "import unittest\nclass T(unittest.TestCase):\n    def test(self): pass\nif __name__ == '__main__':\n    unittest.main()"
        mock_sandbox.return_value = {"sucesso": True, "output": "Ran 1 test in 0.001s\n\nOK"}

        solucoes = {"dev_fast": "def foo(): return 1"}
        resultados = testar_solucoes(solucoes, "tarefa")
        melhor_score = resultados[0][0]
        self.assertGreaterEqual(melhor_score, 90.0)

    @patch('iaglobal.agents.tester_agent.route_generate')
    @patch('iaglobal.agents.multi_agent.executar_codigo')
    def test_testar_solucoes_score_baixo_em_falha(self, mock_sandbox, mock_exec):
        mock_exec.return_value = "import unittest\nclass T(unittest.TestCase):\n    def test(self): pass\nif __name__ == '__main__':\n    unittest.main()"
        mock_sandbox.return_value = {"sucesso": False, "output": "Ran 1 test in 0.001s\nFAILED (failures=1)"}

        solucoes = {"dev_fast": "def foo(): return 1"}
        resultados = testar_solucoes(solucoes, "tarefa")
        melhor_score = resultados[0][0]
        self.assertLess(melhor_score, 90.0)

    @patch('iaglobal.agents.tester_agent.route_generate')
    @patch('iaglobal.agents.multi_agent.executar_codigo')
    def test_testar_solucoes_score_zero_em_erro_runtime(self, mock_sandbox, mock_exec):
        mock_exec.return_value = "import unittest\nclass T(unittest.TestCase):\n    def test(self): pass\nif __name__ == '__main__':\n    unittest.main()"
        mock_sandbox.return_value = {"sucesso": False, "output": "SyntaxError: invalid syntax"}

        solucoes = {"dev_fast": "def foo(:"}
        resultados = testar_solucoes(solucoes, "tarefa")
        melhor_score = resultados[0][0]
        self.assertEqual(melhor_score, 0.0)


class TestCodeScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = CodeScorer()

    def test_calcular_nota_codigo_vazio(self):
        self.assertEqual(self.scorer.calcular_nota_estatica(""), 0.0)
        self.assertEqual(self.scorer.calcular_nota_estatica("   "), 0.0)

    def test_calcular_nota_sintaxe_invalida(self):
        self.assertEqual(self.scorer.calcular_nota_estatica("def foo(:"), 0.0)

    def test_calcular_nota_codigo_simples(self):
        nota = self.scorer.calcular_nota_estatica("def foo():\n    return 1")
        self.assertGreater(nota, 0.0)
        self.assertLessEqual(nota, 100.0)

    def test_calcular_nota_codigo_completo(self):
        codigo = '''
def calcular_media(notas):
    """Calcula a média de uma lista de notas."""
    if not notas:
        return 0.0
    try:
        return sum(notas) / len(notas)
    except ZeroDivisionError:
        return 0.0
'''
        nota = self.scorer.calcular_nota_estatica(codigo)
        self.assertGreater(nota, 50.0)
        self.assertLessEqual(nota, 100.0)

    def test_calcular_nota_penaliza_linhas_excessivas(self):
        codigo_longo = "\n".join([f"x{i} = {i}" for i in range(100)])
        nota = self.scorer.calcular_nota_estatica(codigo_longo)
        self.assertGreaterEqual(nota, 0.0)
        self.assertLessEqual(nota, 100.0)

    def test_calcular_nota_documentacao_aumenta_score(self):
        codigo_com_doc = 'def foo():\n    """Docstring."""\n    return 1'
        codigo_sem_doc = "def foo():\n    return 1"
        nota_com = self.scorer.calcular_nota_estatica(codigo_com_doc)
        nota_sem = self.scorer.calcular_nota_estatica(codigo_sem_doc)
        self.assertGreater(nota_com, nota_sem)


if __name__ == "__main__":
    unittest.main()
