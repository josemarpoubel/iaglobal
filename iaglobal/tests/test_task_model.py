import os
import sys
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(raiz_projeto, "src")
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)
if src_path not in sys.path:
    sys.path.insert(0, src_path)


class TestTaskModel(unittest.TestCase):

    def setUp(self):
        from iaglobal.models.task import Task
        self.Task = Task

    def test_cria_com_valores_padrao(self):
        t = self.Task()
        self.assertTrue(t.id)
        self.assertEqual(t.objective, "")
        self.assertEqual(t.constraints, [])
        self.assertEqual(t.tests, [])
        self.assertEqual(t.metadata, {})
        self.assertEqual(t.context, {})
        self.assertTrue(t.created_at)

    def test_cria_com_objective(self):
        t = self.Task(objective="Criar uma função de soma")
        self.assertEqual(t.objective, "Criar uma função de soma")

    def test_str_retorna_objective(self):
        t = self.Task(objective="Escrever testes")
        self.assertEqual(str(t), "Escrever testes")

    def test_bool_verdadeiro_quando_tem_objective(self):
        t = self.Task(objective="Algo")
        self.assertTrue(t)

    def test_bool_falso_quando_sem_objective(self):
        t = self.Task()
        self.assertFalse(t)

    def test_id_auto_gerado(self):
        t1 = self.Task(objective="A")
        t2 = self.Task(objective="B")
        self.assertNotEqual(t1.id, t2.id)

    def test_id_customizado(self):
        t = self.Task(id="abc123", objective="Teste")
        self.assertEqual(t.id, "abc123")

    def test_to_dict_contem_todos_campos(self):
        t = self.Task(
            id="x1", objective="obj", constraints=["segurança"],
            tests=["test_1"], metadata={"versao": 1}, context={"memoria": "dado"}
        )
        d = t.to_dict()
        self.assertEqual(d["id"], "x1")
        self.assertEqual(d["objective"], "obj")
        self.assertEqual(d["constraints"], ["segurança"])
        self.assertEqual(d["tests"], ["test_1"])
        self.assertEqual(d["metadata"]["versao"], 1)
        self.assertEqual(d["context"]["memoria"], "dado")

    def test_from_dict_restaura_corretamente(self):
        original = self.Task(
            id="r1", objective="Refatorar", constraints=["init"],
            tests=["test_a"], metadata={"prioridade": "alta"}, context={"extra": "info"}
        )
        d = original.to_dict()
        copia = self.Task.from_dict(d)
        self.assertEqual(copia.id, "r1")
        self.assertEqual(copia.objective, "Refatorar")
        self.assertEqual(copia.constraints, ["init"])
        self.assertEqual(copia.tests, ["test_a"])
        self.assertEqual(copia.metadata["prioridade"], "alta")
        self.assertEqual(copia.context["extra"], "info")

    def test_from_dict_sem_id_gera_novo(self):
        t = self.Task.from_dict({"objective": "sem id"})
        self.assertTrue(t.id)
        self.assertEqual(t.objective, "sem id")

    def test_to_json_retorna_string_valida(self):
        t = self.Task(objective="JSON teste")
        j = t.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["objective"], "JSON teste")

    def test_from_json_restaura(self):
        payload = '{"id": "j1", "objective": "JSON", "constraints": [], "tests": [], "metadata": {}, "context": {}}'
        t = self.Task.from_json(payload)
        self.assertEqual(t.id, "j1")
        self.assertEqual(t.objective, "JSON")

    def test_from_string_factory(self):
        t = self.Task.from_string("Objetivo direto")
        self.assertEqual(t.objective, "Objetivo direto")
        self.assertTrue(t.id)
        self.assertTrue(t.created_at)

    def test_format_prompt_sem_constraints_ou_context(self):
        t = self.Task(objective="Fazer algo")
        self.assertEqual(t.format_prompt(), "Fazer algo")

    def test_format_prompt_com_constraints(self):
        t = self.Task(objective="Fazer algo", constraints=["sem os", "sem subprocess"])
        result = t.format_prompt()
        self.assertIn("Fazer algo", result)
        self.assertIn("sem os", result)
        self.assertIn("sem subprocess", result)

    def test_format_prompt_com_context_memory(self):
        t = self.Task(objective="Fazer algo", context={"memory": "dado antigo"})
        result = t.format_prompt()
        self.assertIn("dado antigo", result)

    def test_format_prompt_com_context_extra(self):
        t = self.Task(objective="Fazer algo", context={"extra": "info extra"})
        result = t.format_prompt()
        self.assertIn("info extra", result)

    def test_created_at_iso_format(self):
        t = self.Task()
        datetime.fromisoformat(t.created_at)

    def test_task_pode_ser_usado_como_string_em_fstring(self):
        t = self.Task(objective="minha tarefa")
        resultado = f"{t}"
        self.assertEqual(resultado, "minha tarefa")


if __name__ == "__main__":
    unittest.main()
